"""Studio jobs that are independent of Qt and safe to run in a worker thread."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

import config
from medha.core.schema import LanguageCode, LessonScript
from medha.eval import LessonReport, evaluate_lesson
from medha.lesson import (
    GenerationRequest,
    GenerationResult,
    LessonGenerator,
    load_lesson,
    save_lesson,
)
from medha.rag.errors import is_memory_error
from medha.render.playback import ChunkedPlayback, LessonPlayback, prepare_playback

Progress = Callable[[str], None]
PartialPlayback = Callable[[ChunkedPlayback], None]
Playback = LessonPlayback | ChunkedPlayback
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StudioOptions:
    topic: str
    subject: str = "general"
    difficulty: str = "beginner"
    audience: str = config.LESSON_DEFAULT_AUDIENCE
    steps: int = config.LESSON_DEFAULT_STEPS
    style_id: str = "default"
    rag_query: str | None = None
    use_rag: bool = True
    use_rerank: bool = True
    use_cache: bool = True
    materials: tuple[Path, ...] = field(default_factory=tuple)
    ocr: bool | None = None
    tts: bool = True
    voice: str = config.KOKORO_VOICE
    speed: float = config.KOKORO_SPEED
    language: LanguageCode = "en"

    def request(self) -> GenerationRequest:
        return GenerationRequest(
            topic=self.topic,
            subject=self.subject,  # type: ignore[arg-type]
            difficulty=self.difficulty,  # type: ignore[arg-type]
            audience=self.audience,
            steps=self.steps,
            style_id=self.style_id,
            rag_query=self.rag_query or None,
            use_rag=self.use_rag or bool(self.materials),
            use_rerank=self.use_rerank,
        )


@dataclass
class StudioResult:
    lesson: LessonScript
    playback: Playback
    report: LessonReport
    path: Path | None = None
    generation: GenerationResult | None = None
    warnings: list[str] = field(default_factory=list)
    tts_error: str | None = None


def _lesson_path(lesson: LessonScript) -> Path:
    return config.LESSON_CONTENT_DIR / f"{lesson.lesson_id}.json"


def _translate(
    lesson: LessonScript,
    language: LanguageCode,
    progress: Progress,
    warnings: list[str],
) -> LessonScript:
    if language == "en" or lesson.language == language:
        return lesson
    progress(f"Translating lesson to {config.LANGUAGE_NAMES[language]}...")
    try:
        from medha.language import translate_lesson

        return translate_lesson(lesson, language)
    except Exception as exc:
        warnings.append(
            f"{config.LANGUAGE_NAMES[language]} translation unavailable; "
            f"keeping {config.LANGUAGE_NAMES.get(lesson.language, lesson.language)}: {exc}"
        )
        return lesson


def _prepare(
    lesson: LessonScript,
    options: StudioOptions,
    progress: Progress,
    warnings: list[str],
) -> tuple[LessonPlayback, str | None]:
    progress("Preparing speech and timeline...")
    tts_error = None
    prepared = None
    if options.tts:
        for attempt in (1, 2):
            try:
                prepared = prepare_playback(
                    lesson,
                    use_tts=True,
                    voice=options.voice,
                    speed=options.speed,
                )
                break
            except Exception as exc:
                logger.exception(
                    "TTS preparation failed (attempt %s/2, voice=%s, speed=%.2f)",
                    attempt,
                    options.voice,
                    options.speed,
                )
                tts_error = str(exc)
                if attempt == 2:
                    warnings.append(f"TTS unavailable; using silent timing: {exc}")
    if prepared is None:
        prepared = prepare_playback(lesson, use_tts=False)
    return LessonPlayback(prepared), tts_error


def _prepare_progressive(
    lesson: LessonScript,
    options: StudioOptions,
    progress: Progress,
    warnings: list[str],
    partial: PartialPlayback,
) -> tuple[ChunkedPlayback, str | None]:
    from medha.tts.kokoro import KokoroEngine
    from medha.tts.speech import SpeechCache, synthesize_step

    progress("Preparing speech and timeline...")
    playback = ChunkedPlayback(
        lesson,
        play_audio=True,
        voice=options.voice,
        speed=options.speed,
    )
    tts_error = None
    engine = None
    cache = None
    try:
        engine = KokoroEngine(voice=options.voice, speed=options.speed)
        cache = SpeechCache()
    except Exception as exc:
        logger.exception(
            "TTS engine unavailable (voice=%s, speed=%.2f)",
            options.voice,
            options.speed,
        )
        tts_error = str(exc)
        warnings.append(f"TTS unavailable; using silent timing: {exc}")

    total = len(lesson.steps)
    for index, step in enumerate(lesson.steps):
        progress(f"Generating speech for step {index + 1}/{total}...")
        chunk = None
        if engine is not None:
            for attempt in (1, 2):
                try:
                    chunk = synthesize_step(
                        step,
                        step_index=index,
                        engine=engine,
                        cache=cache,
                        use_cache=options.use_cache,
                        voice=options.voice,
                        speed=options.speed,
                    )
                    break
                except Exception as exc:
                    logger.exception(
                        "TTS failed for step %s (attempt %s/2, voice=%s, speed=%.2f)",
                        step.id,
                        attempt,
                        options.voice,
                        options.speed,
                    )
                    tts_error = str(exc)
                    if attempt == 2:
                        warnings.append(
                            f"TTS unavailable for step {step.id}; "
                            f"using silent timing: {exc}"
                        )
        playback.append(step, chunk)
        partial(playback)
    playback.mark_complete()
    return playback, tts_error


def _generate_stepwise(
    options: StudioOptions,
    progress: Progress,
    partial: PartialPlayback,
    retriever: object | None,
    initial_warnings: list[str] | None = None,
) -> StudioResult:
    from medha.tts.kokoro import KokoroEngine
    from medha.tts.speech import SpeechCache, synthesize_step

    warnings: list[str] = list(initial_warnings or [])
    playback: ChunkedPlayback | None = None
    tts_error: str | None = None
    engine = None
    cache = None
    engine_failed = False
    emitted = False

    def on_step(event: object) -> None:
        nonlocal playback, tts_error, engine, cache, engine_failed, emitted
        from medha.lesson import StepEvent

        assert isinstance(event, StepEvent)
        if playback is None:
            playback = ChunkedPlayback(
                event.lesson,
                play_audio=options.tts,
                voice=options.voice,
                speed=options.speed,
            )
            progress("Preparing speech and timeline..." if options.tts else "Preparing timeline...")
        chunk = None
        if options.tts and engine is None and not engine_failed:
            try:
                engine = KokoroEngine(voice=options.voice, speed=options.speed)
                cache = SpeechCache()
            except Exception as exc:
                logger.exception(
                    "TTS engine unavailable (voice=%s, speed=%.2f)",
                    options.voice,
                    options.speed,
                )
                tts_error = str(exc)
                warnings.append(f"TTS unavailable; using silent timing: {exc}")
                engine_failed = True
        if options.tts and engine is not None:
            for attempt in (1, 2):
                try:
                    chunk = synthesize_step(
                        event.step,
                        step_index=event.index,
                        engine=engine,
                        cache=cache,
                        use_cache=options.use_cache,
                        voice=options.voice,
                        speed=options.speed,
                    )
                    break
                except Exception as exc:
                    logger.exception(
                        "TTS failed for step %s (attempt %s/2, voice=%s, speed=%.2f)",
                        event.step.id,
                        attempt,
                        options.voice,
                        options.speed,
                    )
                    tts_error = str(exc)
                    if attempt == 2:
                        warnings.append(
                            f"TTS unavailable for step {event.step.id}; "
                            f"using silent timing: {exc}"
                        )
        playback.append(event.step, chunk)
        progress(
            f"Speech ready for step {event.index + 1}."
            if options.tts
            else f"Step {event.index + 1} ready."
        )
        partial(playback)
        emitted = True

    generator = LessonGenerator(retriever=retriever)  # type: ignore[arg-type]
    try:
        result = generator.generate_stepwise(
            options.request(),
            on_step,
            use_cache=options.use_cache,
        )
    except Exception as exc:
        logger.exception("Stepwise generation failed")
        if emitted:
            warnings.append(
                "stepwise generation stopped early; using full lesson fallback: "
                f"{exc}"
            )
        else:
            warnings.append(
                f"stepwise generation failed; using full lesson fallback: {exc}"
            )
        if playback is not None:
            playback.stop()
        fallback_steps = min(options.steps, 2)
        if fallback_steps != options.steps:
            warnings.append(
                f"fallback lesson reduced from {options.steps} to {fallback_steps} steps"
            )
        fallback_options = replace(
            options,
            materials=(),
            use_rag=False,
            steps=fallback_steps,
        )
        fallback = generate_lesson(fallback_options, progress, None)
        fallback.warnings = warnings + fallback.warnings
        return fallback

    lesson = result.lesson
    warnings.extend(result.warnings)
    progress("Checking lesson quality...")
    path = save_lesson(lesson, _lesson_path(lesson))
    report = evaluate_lesson(lesson, path=path)
    if playback is None:
        fallback = generate_lesson(options, progress, None)
        fallback.warnings = warnings + fallback.warnings
        return fallback
    playback.mark_complete()
    if playback.prepared.track is not None:
        report = evaluate_lesson(
            lesson,
            path=path,
            speech_track=playback.prepared.track,
        )
    progress("Ready")
    return StudioResult(
        lesson=lesson,
        playback=playback,
        report=report,
        path=path,
        generation=result,
        warnings=warnings,
        tts_error=tts_error,
    )


def generate_lesson(
    options: StudioOptions,
    progress: Progress | None = None,
    partial: PartialPlayback | None = None,
) -> StudioResult:
    notify = progress or (lambda _message: None)
    config.ensure_dirs()
    retriever = None
    warnings: list[str] = []
    if options.materials:
        from medha.rag import RagService

        notify("Loading retrieval models...")
        retriever = RagService()
        for path in options.materials:
            notify(f"Indexing {path.name}...")
            try:
                index_report = retriever.index_file(path, ocr=options.ocr)
            except Exception as exc:
                if not is_memory_error(exc):
                    raise
                logger.exception("Material indexing ran out of memory")
                warnings.append(
                    "material indexing ran out of memory; using the topic only: "
                    f"{exc}"
                )
                close = getattr(retriever, "close", None)
                if callable(close):
                    close()
                retriever = None
                options = replace(options, materials=(), use_rag=False)
                break
            if index_report.indexed:
                notify(f"Indexed {path.name}: {index_report.indexed} chunk(s)")
            else:
                notify(f"{path.name} is already indexed")

    if partial is not None and options.language == "en":
        return _generate_stepwise(options, notify, partial, retriever, warnings)

    notify("Generating lesson...")
    generator = LessonGenerator(retriever=retriever)
    result = generator.generate(options.request(), use_cache=options.use_cache)

    warnings = [*warnings, *result.warnings]
    lesson = _translate(result.lesson, options.language, notify, warnings)
    path = save_lesson(lesson, _lesson_path(lesson))
    notify("Checking lesson quality...")
    report = evaluate_lesson(lesson, path=path)
    playback: Playback
    if options.tts and partial is not None:
        playback, tts_error = _prepare_progressive(
            lesson, options, notify, warnings, partial
        )
    else:
        playback, tts_error = _prepare(lesson, options, notify, warnings)
    if playback.prepared.track is not None:
        report = evaluate_lesson(
            lesson,
            path=path,
            speech_track=playback.prepared.track,
        )
    notify("Ready")
    return StudioResult(
        lesson=lesson,
        playback=playback,
        report=report,
        path=path,
        generation=result,
        warnings=warnings,
        tts_error=tts_error,
    )


def open_lesson(
    path: Path,
    options: StudioOptions,
    progress: Progress | None = None,
    partial: PartialPlayback | None = None,
) -> StudioResult:
    notify = progress or (lambda _message: None)
    notify("Loading lesson...")
    lesson = load_lesson(path)
    warnings: list[str] = []
    translated = _translate(lesson, options.language, notify, warnings)
    translation_changed = translated is not lesson
    if translation_changed:
        lesson = translated
    from medha.lesson.layout import normalize_layout

    lesson, layout_warnings = normalize_layout(lesson)
    warnings.extend(layout_warnings)
    if translation_changed:
        path = save_lesson(lesson, _lesson_path(lesson))
    notify("Checking lesson quality...")
    report = evaluate_lesson(lesson, path=path)
    playback: Playback
    if options.tts and partial is not None:
        playback, tts_error = _prepare_progressive(
            lesson, options, notify, warnings, partial
        )
    else:
        playback, tts_error = _prepare(lesson, options, notify, warnings)
    if playback.prepared.track is not None:
        report = evaluate_lesson(
            lesson,
            path=path,
            speech_track=playback.prepared.track,
        )
    notify("Ready")
    return StudioResult(
        lesson=lesson,
        playback=playback,
        report=report,
        path=path,
        warnings=warnings,
        tts_error=tts_error,
    )
