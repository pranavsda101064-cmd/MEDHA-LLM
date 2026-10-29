from medha.core.schema import (
    BoardAction,
    LessonScript,
    LessonStep,
    Rect,
    WriteTextAction,
)
from medha.lesson.layout import normalize_layout, text_collisions


def _action(index: int) -> WriteTextAction:
    return WriteTextAction(
        id=f"a{index}",
        op="write_text",
        text=f"Item {index}",
        rect=Rect(x=0.06, y=0.2, w=0.4, h=0.1),
    )


def _lesson() -> LessonScript:
    steps = []
    action = 1
    for step_index in range(1, 5):
        board: list[BoardAction] = []
        for _ in range(3):
            board.append(_action(action))
            action += 1
        steps.append(
            LessonStep(
                id=f"s{step_index}",
                concept="item",
                narration="First sentence. Second sentence.",
                board=board,
            )
        )
    final_board: list[BoardAction] = []
    for _ in range(4):
        final_board.append(_action(action))
        action += 1
    steps.append(
        LessonStep(
            id="s5",
            concept="final",
            narration="First sentence. Second sentence.",
            board=final_board,
        )
    )
    return LessonScript(
        lesson_id="layout-test",
        title="Layout Test",
        steps=steps,
    )


def test_normalize_layout_clears_a_full_board() -> None:
    repaired, warnings = normalize_layout(_lesson())

    assert any(action.op == "clear" for action in repaired.steps[-1].board)
    assert any("board was full" in warning for warning in warnings)
    assert text_collisions(repaired) == []
