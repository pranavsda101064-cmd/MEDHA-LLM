"""Visual timeline for silent previews and real TTS audio.

`sentence_ms` carries Kokoro durations in B4; action timings and the renderer
stay the same. Anchors are resolved against sentence-relative positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from medha.core.schema import LessonScript, split_sentences


@dataclass(frozen=True)
class ActionTiming:
    start_ms: int
    duration_ms: int

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms


@dataclass(frozen=True)
class CheckpointTiming:
    step_id: str
    at_ms: int
    question: str
    expected: str
    hints: tuple[str, ...] = ()


@dataclass
class Timeline:
    actions: dict[str, ActionTiming] = field(default_factory=dict)
    step_start_ms: list[int] = field(default_factory=list)
    checkpoints: list[CheckpointTiming] = field(default_factory=list)
    total_ms: int = 0

    def timing(self, action_id: str) -> ActionTiming | None:
        return self.actions.get(action_id)


def estimate_sentence_ms(sentence: str, chars_per_second: float = 15.0) -> int:
    return max(600, int(len(sentence) / max(1.0, chars_per_second) * 1000) + 120)


def _distributed_starts(count: int, starts: list[int], total_ms: int) -> list[int]:
    """Spread unanchored actions across a step instead of stacking them at zero."""
    if count <= 0:
        return []
    if not starts:
        return [0] * count
    if count <= len(starts):
        return [starts[index] for index in range(count)]
    out: list[int] = []
    previous = -1
    for index in range(count):
        target = round(index * total_ms / count)
        target = max(previous + 1, target)
        out.append(target)
        previous = target
    return out


def build_timeline(
    lesson: LessonScript,
    sentence_ms: list[list[int]] | None = None,
    step_gap_ms: int = 250,
    sentence_gap_ms: int = 0,
    lead_ms: int = 0,
    chars_per_second: float = 15.0,
) -> Timeline:
    timeline = Timeline()
    cursor = max(0, lead_ms) if lesson.steps else 0
    last_action_end = 0
    for step_index, step in enumerate(lesson.steps):
        sentences = split_sentences(step.narration)
        if sentence_ms is not None and step_index < len(sentence_ms):
            durations = list(sentence_ms[step_index])
        else:
            durations = [estimate_sentence_ms(s, chars_per_second) for s in sentences]
        if len(durations) < len(sentences):
            durations.extend(
                estimate_sentence_ms(s, chars_per_second)
                for s in sentences[len(durations) :]
            )

        starts: list[int] = []
        sentence_cursor = 0
        for index, duration in enumerate(durations):
            starts.append(sentence_cursor)
            sentence_cursor += duration
            if index < len(durations) - 1:
                sentence_cursor += max(0, sentence_gap_ms)

        timeline.step_start_ms.append(cursor)
        meaningful_anchor = any(
            action.start is not None and action.op != "clear" for action in step.board
        )
        distributed = (
            []
            if meaningful_anchor
            else _distributed_starts(
                sum(1 for action in step.board if action.start is None),
                starts,
                sentence_cursor,
            )
        )
        distributed_index = 0
        previous_end = 0
        for action in step.board:
            local_start = previous_end
            if action.start is not None and action.start.sentence < len(sentences):
                sentence = sentences[action.start.sentence]
                sentence_duration = durations[action.start.sentence]
                fraction = 0.0 if not sentence else action.start.char / len(sentence)
                local_start = starts[action.start.sentence] + int(
                    sentence_duration * fraction
                )
            elif distributed:
                local_start = distributed[distributed_index]
                distributed_index += 1
            timing = ActionTiming(cursor + local_start, action.duration_ms)
            timeline.actions[action.id] = timing
            previous_end = max(previous_end, local_start + action.duration_ms)
            last_action_end = max(last_action_end, timing.end_ms)

        if step.checkpoint is not None:
            timeline.checkpoints.append(
                CheckpointTiming(
                    step_id=step.id,
                    at_ms=cursor + max(0, sentence_cursor),
                    question=step.checkpoint.question,
                    expected=step.checkpoint.expected,
                    hints=tuple(step.checkpoint.hints),
                )
            )

        cursor += max(0, sentence_cursor) + step_gap_ms

    timeline.total_ms = max(cursor, last_action_end)
    return timeline
