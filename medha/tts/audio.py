"""Wall-clock audio playback used as the master clock for board animation."""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AudioPlayer:
    def __init__(self, samples: np.ndarray, sample_rate: int, enabled: bool = True) -> None:
        self.samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        self.sample_rate = sample_rate
        self.enabled = enabled
        self._started_at: float | None = None
        self._offset_ms = 0
        self._duration_ms = round(self.samples.size / sample_rate * 1000)
        self._last_error: str | None = None

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def start(self, at_ms: int = 0) -> bool:
        self._last_error = None
        if self._started_at is not None:
            return self.enabled
        self._offset_ms = max(0, min(self._duration_ms, int(at_ms)))
        if self.enabled:
            try:
                import sounddevice as sd

                start = round(self.samples.size * self._offset_ms / max(1, self._duration_ms))
                if start < self.samples.size:
                    sd.play(self.samples[start:], self.sample_rate)
            except Exception as exc:
                logger.warning("Audio output unavailable (%s); continuing silently", exc)
                self._last_error = str(exc)
                self.enabled = False
        self._started_at = time.perf_counter()
        return self.enabled

    def clock_ms(self) -> int:
        if self._started_at is None:
            return self._offset_ms
        elapsed = int((time.perf_counter() - self._started_at) * 1000)
        return self._offset_ms + max(0, elapsed)

    def position_ms(self) -> int:
        return min(self._duration_ms, self.clock_ms())

    def stop(self) -> None:
        if self.enabled:
            try:
                import sounddevice as sd

                sd.stop()
            except Exception:
                pass
        self._started_at = None
        self._offset_ms = 0


class StreamingAudioPlayer:
    """Appendable audio output whose play position is the master clock."""

    def __init__(self, sample_rate: int, enabled: bool = True) -> None:
        self.sample_rate = sample_rate
        self.enabled = enabled
        self._chunks: list[np.ndarray] = []
        self._lock = threading.RLock()
        self._stream: Any = None
        self._index = 0
        self._offset = 0
        self._playing = False
        self._buffering = False
        self._last_error: str | None = None
        self._clock_started: float | None = None
        self._clock_offset_ms = 0

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def buffering(self) -> bool:
        with self._lock:
            return self._buffering

    @property
    def duration_ms(self) -> int:
        with self._lock:
            return self._duration_ms_locked()

    def append(self, samples: np.ndarray) -> None:
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return
        with self._lock:
            self._chunks.append(samples)
            self._buffering = False

    def start(self, at_ms: int = 0) -> bool:
        failed_stream: Any = None
        with self._lock:
            if self._playing:
                return self.enabled
            self._last_error = None
            self._seek_locked(at_ms)
            self._playing = True
            if self.enabled:
                try:
                    import sounddevice as sd

                    if self._stream is None:
                        self._stream = sd.OutputStream(
                            samplerate=self.sample_rate,
                            channels=1,
                            dtype="float32",
                            callback=self._callback,
                        )
                    self._stream.start()
                except Exception as exc:
                    logger.warning("Streaming audio unavailable (%s); continuing silently", exc)
                    self._last_error = str(exc)
                    self.enabled = False
                    failed_stream = self._detach_stream_locked()
            if not self.enabled:
                self._clock_offset_ms = max(0, min(self._duration_ms_locked(), int(at_ms)))
                self._clock_started = time.perf_counter()
            enabled = self.enabled
        self._close_stream(failed_stream)
        return enabled

    def position_ms(self) -> int:
        with self._lock:
            if not self.enabled:
                if self._clock_started is None:
                    position = self._clock_offset_ms
                else:
                    elapsed = int((time.perf_counter() - self._clock_started) * 1000)
                    position = self._clock_offset_ms + max(0, elapsed)
                return min(self._duration_ms_locked(), position)
            frames = sum(int(chunk.size) for chunk in self._chunks[: self._index])
            frames += self._offset
            return min(self._duration_ms_locked(), round(frames / self.sample_rate * 1000))

    def seek(self, at_ms: int) -> None:
        with self._lock:
            if not self.enabled:
                self._clock_offset_ms = max(0, min(self._duration_ms_locked(), int(at_ms)))
                self._clock_started = time.perf_counter() if self._playing else None
            self._seek_locked(at_ms)

    def pause(self) -> None:
        with self._lock:
            if not self._playing:
                return
            position = self.position_ms()
            self._playing = False
            stream = self._detach_stream_locked()
            if not self.enabled:
                self._clock_offset_ms = position
                self._clock_started = None
        self._close_stream(stream)

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            stream = self._detach_stream_locked()
            self._index = 0
            self._offset = 0
            self._buffering = False
            self._clock_offset_ms = 0
            self._clock_started = None
        self._close_stream(stream)

    def _duration_ms_locked(self) -> int:
        frames = sum(int(chunk.size) for chunk in self._chunks)
        return round(frames / self.sample_rate * 1000)

    def _seek_locked(self, at_ms: int) -> None:
        target = max(0, min(self._duration_ms_locked(), int(at_ms)))
        remaining = round(target * self.sample_rate / 1000)
        for index, chunk in enumerate(self._chunks):
            size = int(chunk.size)
            if remaining < size:
                self._index = index
                self._offset = remaining
                return
            remaining -= size
        self._index = len(self._chunks)
        self._offset = 0

    def _detach_stream_locked(self) -> Any:
        stream, self._stream = self._stream, None
        return stream

    @staticmethod
    def _close_stream(stream: Any) -> None:
        if stream is None:
            return
        with contextlib.suppress(Exception):
            stream.stop()
        with contextlib.suppress(Exception):
            stream.close()

    def _callback(
        self,
        outdata: Any,
        frames: int,
        _time: Any,
        _status: Any,
    ) -> None:
        outdata.fill(0)
        data = outdata if outdata.ndim == 2 else outdata.reshape(-1, 1)
        try:
            with self._lock:
                if not self._playing:
                    return
                written = 0
                while written < frames:
                    if self._index >= len(self._chunks):
                        self._buffering = True
                        break
                    chunk = self._chunks[self._index]
                    available = int(chunk.size) - self._offset
                    if available <= 0:
                        self._index += 1
                        self._offset = 0
                        continue
                    take = min(frames - written, available)
                    data[written : written + take, 0] = chunk[self._offset : self._offset + take]
                    written += take
                    self._offset += take
                    if self._offset >= int(chunk.size):
                        self._index += 1
                        self._offset = 0
                if written:
                    self._buffering = False
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Streaming audio callback failed")
