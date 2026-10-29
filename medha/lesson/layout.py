"""Deterministic board layout repair for generated lessons.

Models usually obey the board rules, but when they do not, text actions can all
target the title band and overlap. This pass keeps the opening title of a board
section and moves every other text block to a free body slot. It also starts a
new board section with a clear when a later step introduces another title,
unless the step needs an action from an earlier step.
"""

from __future__ import annotations

from dataclasses import dataclass

import config
from medha.core.schema import (
    Anchor,
    BoardAction,
    BulletListAction,
    ClearAction,
    EraseAction,
    LessonScript,
    LessonStep,
    Rect,
    WriteMathAction,
    WriteTextAction,
)

TEXT_OPS = {"write_text", "write_math", "bullet_list"}
TITLE_OPS = {"write_text", "write_math", "bullet_list"}
_EPS = 0.002


@dataclass(frozen=True)
class _Placed:
    action_id: str
    rect: Rect


def _region_rect(region: str) -> Rect:
    mx = config.BOARD_MARGIN_X
    my = config.BOARD_MARGIN_Y
    if region == "title":
        return Rect(x=mx, y=0.045, w=1.0 - 2.0 * mx, h=config.TITLE_BAND_H)
    if region == "top":
        return Rect(x=mx, y=0.04, w=1.0 - 2.0 * mx, h=0.22)
    if region == "left":
        return Rect(x=mx, y=0.23, w=0.45, h=0.60)
    if region == "right":
        return Rect(x=0.52, y=0.23, w=0.43, h=0.60)
    if region == "center":
        return Rect(x=0.18, y=0.24, w=0.64, h=0.48)
    if region == "bottom":
        return Rect(x=mx, y=0.76, w=1.0 - 2.0 * mx, h=0.16)
    if region == "full":
        return Rect(x=mx, y=my, w=1.0 - 2.0 * mx, h=1.0 - 2.0 * my)
    return Rect(x=mx, y=0.23, w=0.45, h=0.60)


def _action_rect(action: BoardAction) -> Rect | None:
    if isinstance(action, (WriteTextAction, WriteMathAction, BulletListAction)):
        return action.rect or _region_rect(action.region)
    if isinstance(action, (ClearAction, EraseAction)):
        return None
    return getattr(action, "rect", None)


def _overlaps(left: Rect, right: Rect) -> bool:
    return not (
        left.x + left.w <= right.x + _EPS
        or right.x + right.w <= left.x + _EPS
        or left.y + left.h <= right.y + _EPS
        or right.y + right.h <= left.y + _EPS
    )


def _collides(rect: Rect, placed: list[_Placed]) -> bool:
    return any(_overlaps(rect, item.rect) for item in placed)


def _slots() -> list[Rect]:
    rows = (0.20, 0.32, 0.44, 0.56, 0.68, 0.80)
    slots: list[Rect] = []
    for y in rows:
        slots.append(Rect(x=0.06, y=y, w=0.40, h=0.10))
        slots.append(Rect(x=0.54, y=y, w=0.40, h=0.10))
    return slots


def _free_slot(placed: list[_Placed]) -> Rect | None:
    for slot in _slots():
        if not _collides(slot, placed):
            return slot
    return None


def _move_to_slot(action: BoardAction, slot: Rect) -> BoardAction:
    if isinstance(action, (WriteTextAction, WriteMathAction, BulletListAction)):
        return action.model_copy(update={"rect": slot, "region": "auto"})
    return action


def _step_has_clear(step: LessonStep) -> bool:
    return any(action.op == "clear" for action in step.board)


def _title_action(step: LessonStep) -> bool:
    return any(
        action.op in TITLE_OPS
        and getattr(action, "region", None) == "title"
        and getattr(action, "rect", None) is None
        for action in step.board
    )


def _references_prior(step: LessonStep, prior_ids: set[str]) -> bool:
    for action in step.board:
        target = getattr(action, "target", None)
        if isinstance(target, str) and target in prior_ids:
            return True
    return False


def _clear_id(index: int, used: set[str]) -> str:
    base = f"auto_clear_s{index + 1}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _erase_placed(action: EraseAction, placed: list[_Placed]) -> list[_Placed]:
    if action.target is None:
        return placed
    return [item for item in placed if item.action_id != action.target]


def _place_step(
    step: LessonStep,
    *,
    placed: list[_Placed],
    title_free: bool,
    warnings: list[str],
) -> tuple[LessonStep, list[_Placed], bool]:
    board: list[BoardAction] = []
    for action in step.board:
        if isinstance(action, ClearAction):
            placed = []
            title_free = True
            board.append(action)
            continue
        if isinstance(action, EraseAction):
            placed = _erase_placed(action, placed)
            board.append(action)
            continue

        rect = _action_rect(action)
        if rect is None:
            board.append(action)
            continue

        is_text = action.op in TEXT_OPS
        is_title = (
            action.op in TITLE_OPS
            and getattr(action, "region", None) == "title"
            and getattr(action, "rect", None) is None
        )

        if is_title and title_free:
            title_free = False
            placed.append(_Placed(action.id, rect))
            board.append(action)
            continue

        if is_text and (not is_title and (not _collides(rect, placed))):
            placed.append(_Placed(action.id, rect))
            board.append(action)
            continue

        if is_text:
            slot = _free_slot(placed)
            if slot is not None:
                action = _move_to_slot(action, slot)
                rect = slot
                warnings.append(f"moved overlapping action {action.id} to a free board slot")
            else:
                warnings.append(f"no free board slot for action {action.id}; layout may overlap")
            placed.append(_Placed(action.id, rect))
        else:
            placed.append(_Placed(action.id, rect))

        board.append(action)

    return step.model_copy(update={"board": board}), placed, title_free


def text_collisions(lesson: LessonScript) -> list[tuple[str, str]]:
    """Return pairs of text-like action ids that overlap while both are visible."""
    collisions: list[tuple[str, str]] = []
    placed: list[_Placed] = []
    for step in lesson.steps:
        for action in step.board:
            if isinstance(action, ClearAction):
                placed = []
                continue
            if isinstance(action, EraseAction):
                placed = _erase_placed(action, placed)
                continue
            if action.op not in TEXT_OPS:
                continue
            rect = _action_rect(action)
            if rect is None:
                continue
            for existing in placed:
                if _overlaps(rect, existing.rect):
                    collisions.append((existing.action_id, action.id))
            placed.append(_Placed(action.id, rect))
    return collisions


def normalize_layout(lesson: LessonScript) -> tuple[LessonScript, list[str]]:
    """Return a layout-repaired copy and human-readable warnings.

    The pass is idempotent and only moves text-like actions. Drawings and other
    geometry are preserved.
    """
    warnings: list[str] = []
    used_ids = {action.id for step in lesson.steps for action in step.board}
    prior_ids: set[str] = set()
    placed: list[_Placed] = []
    title_free = True
    steps: list[LessonStep] = []

    for index, step in enumerate(lesson.steps):
        board = list(step.board)
        has_clear = _step_has_clear(step)
        body_text = [
            action
            for action in step.board
            if action.op in TEXT_OPS
            and not (
                title_free
                and action.op in TITLE_OPS
                and getattr(action, "region", None) == "title"
                and getattr(action, "rect", None) is None
            )
        ]
        free_slots = sum(
            1 for slot in _slots() if not _collides(slot, placed)
        )
        board_full = bool(placed) and len(body_text) > free_slots
        if (
            (board_full or (_title_action(step) and not title_free))
            and not has_clear
            and not _references_prior(step, prior_ids)
        ):
            clear_id = _clear_id(index, used_ids)
            used_ids.add(clear_id)
            board.insert(
                0,
                ClearAction(
                    op="clear",
                    id=clear_id,
                    duration_ms=120,
                    start=Anchor(sentence=0, char=0),
                ),
            )
            step = step.model_copy(update={"board": board})
            placed = []
            title_free = True
            reason = "the board was full" if board_full else "to keep the board readable"
            warnings.append(f"started step {step.id} with a clear because {reason}")

        step, placed, title_free = _place_step(
            step,
            placed=placed,
            title_free=title_free,
            warnings=warnings,
        )
        steps.append(step)
        prior_ids.update(action.id for action in step.board)

    if not warnings:
        return lesson, []
    return lesson.model_copy(update={"steps": steps}), warnings
