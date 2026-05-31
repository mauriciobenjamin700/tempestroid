"""Button-grid calculator — gallery example.

The button grid *is* the input (no text-entry widget needed), which makes it a
dense layout showcase: nested ``Row``/``Column`` with a shared key scheme so the
reconciler patches only the display ``Text`` between taps.

Runs in the Qt simulator::

    uv run python examples/calculator/app.py

and on a device via code-push::

    uv run tempest serve examples/calculator/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    FontWeight,
    JustifyContent,
    Row,
    Style,
    Text,
    Widget,
)

_ROWS: tuple[tuple[str, ...], ...] = (
    ("7", "8", "9", "÷"),
    ("4", "5", "6", "×"),
    ("1", "2", "3", "-"),
    ("C", "0", "=", "+"),
)
_OPS: dict[str, str] = {"÷": "/", "×": "*", "-": "-", "+": "+"}


@dataclass
class CalcState:
    """The calculator's mutable state.

    Attributes:
        entry: The digits typed for the current operand.
        acc: The accumulated value, or ``None`` before the first operator.
        op: The pending operator symbol, or ``None``.
        just_evaluated: Whether the last key was ``=`` (so a digit starts fresh).
    """

    entry: str = "0"
    acc: float | None = None
    op: str | None = None
    just_evaluated: bool = False


def make_state() -> CalcState:
    """Build a fresh initial state.

    Returns:
        A new calculator state showing ``0``.
    """
    return CalcState()


def _fold(state: CalcState) -> float:
    """Apply the pending operator to ``acc`` and the current entry.

    Returns:
        The folded result (or the entry alone when no op is pending).
    """
    value = float(state.entry)
    if state.acc is None or state.op is None:
        return value
    left = state.acc
    if state.op == "+":
        return left + value
    if state.op == "-":
        return left - value
    if state.op == "*":
        return left * value
    if state.op == "/":
        return left / value if value != 0 else 0.0
    return value


def _press(state: CalcState, key: str) -> None:
    """Apply one key press to the calculator state.

    Args:
        state: The state to mutate.
        key: The label of the pressed button.
    """
    if key == "C":
        state.entry, state.acc, state.op, state.just_evaluated = "0", None, None, False
        return
    if key.isdigit():
        if state.entry == "0" or state.just_evaluated:
            state.entry = key
        else:
            state.entry += key
        state.just_evaluated = False
        return
    if key in _OPS:
        state.acc = _fold(state)
        state.op = _OPS[key]
        state.entry = "0"
        state.just_evaluated = False
        return
    if key == "=":
        state.acc = _fold(state)
        state.entry = _format(state.acc)
        state.op = None
        state.just_evaluated = True


def _format(value: float) -> str:
    """Render a float without a trailing ``.0`` for whole numbers."""
    return str(int(value)) if value == int(value) else f"{value:.4g}"


def _key(app: App[CalcState], label: str) -> Widget:
    """Build one calculator key button."""
    is_op = label in _OPS or label == "="
    background = Color.from_hex("#f59e0b") if is_op else Color.from_hex("#1f2937")
    return Button(
        label=label,
        on_click=lambda: app.set_state(lambda s: _press(s, label)),
        key=f"k-{label}",
        style=Style(
            padding=Edge.symmetric(vertical=18.0, horizontal=22.0),
            radius=10.0,
            background=background,
            color=Color.from_hex("#f9fafb"),
            font_size=20.0,
        ),
    )


def view(app: App[CalcState]) -> Widget:
    """Build the calculator UI for the current state.

    Args:
        app: The running app.

    Returns:
        The root widget of the calculator screen.
    """
    return Column(
        style=Style(
            gap=10.0,
            padding=Edge.all(20.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content=app.state.entry,
                style=Style(
                    font_size=40.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#f9fafb"),
                ),
                key="display",
            ),
            *[
                Row(
                    style=Style(gap=10.0, justify=JustifyContent.CENTER),
                    children=[_key(app, label) for label in row],
                    key=f"row-{i}",
                )
                for i, row in enumerate(_ROWS)
            ],
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — calculator", size=(360, 480))
    )
