"""Offline speech synthesis and synchronization."""

from .audio import AudioPlayer, StreamingAudioPlayer
from .indic import IndicParlerEngine
from .kokoro import KokoroEngine
from .speech import (
    SpeechCache,
    SpeechChunk,
    SpeechTrack,
    Synthesizer,
    synthesize_lesson,
    synthesize_step,
)

__all__ = [
    "AudioPlayer",
    "IndicParlerEngine",
    "KokoroEngine",
    "SpeechCache",
    "SpeechChunk",
    "SpeechTrack",
    "StreamingAudioPlayer",
    "Synthesizer",
    "synthesize_lesson",
    "synthesize_step",
]
