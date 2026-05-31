"""Form — gallery example for the value-bearing widgets.

Exercises all four input widgets and their typed change events end to end:
:class:`Input` (``TextChangeEvent``), :class:`Checkbox` (``ToggleEvent``),
:class:`DatePicker` (``DateChangeEvent``) and :class:`FilePicker`
(``FileSelectEvent``). Each handler reads the typed value off the event and folds
it into state; a live summary reflects the result.

Runs in the Qt simulator::

    uv run python examples/form/app.py

and on a device via code-push::

    uv run tempest serve examples/form/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    Checkbox,
    Color,
    Column,
    DatePicker,
    Edge,
    FilePicker,
    FontWeight,
    Input,
    Style,
    Text,
    Widget,
)


@dataclass
class FormState:
    """The form's mutable state.

    Attributes:
        name: The typed name.
        subscribe: Whether the newsletter checkbox is checked.
        birthdate: The selected date (ISO ``yyyy-mm-dd``), or ``""``.
        attachment: The selected file's display name, or ``""``.
    """

    name: str = ""
    subscribe: bool = False
    birthdate: str = ""
    attachment: str = ""


def make_state() -> FormState:
    """Build a fresh, empty form state.

    Returns:
        A new form state.
    """
    return FormState()


def view(app: App[FormState]) -> Widget:
    """Build the form UI for the current state.

    Args:
        app: The running app.

    Returns:
        The root widget of the form screen.
    """
    state = app.state
    field_style = Style(
        padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
        radius=8.0,
        background=Color.from_hex("#1f2937"),
        color=Color.from_hex("#f9fafb"),
    )
    summary = (
        f"{state.name or '—'} · "
        f"{'subscribed' if state.subscribe else 'not subscribed'} · "
        f"{state.birthdate or 'no date'} · "
        f"{state.attachment or 'no file'}"
    )
    return Column(
        style=Style(
            gap=14.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="Sign up",
                style=Style(
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#f9fafb"),
                ),
                key="title",
            ),
            Input(
                value=state.name,
                placeholder="Your name",
                on_change=lambda e: app.set_state(
                    lambda s: setattr(s, "name", e.value)
                ),
                key="name",
                style=field_style,
            ),
            Checkbox(
                label="Subscribe to the newsletter",
                checked=state.subscribe,
                on_change=lambda e: app.set_state(
                    lambda s: setattr(s, "subscribe", e.checked)
                ),
                key="subscribe",
            ),
            DatePicker(
                value=state.birthdate,
                label="Pick your birthdate",
                on_change=lambda e: app.set_state(
                    lambda s: setattr(s, "birthdate", e.value)
                ),
                key="birthdate",
                style=field_style,
            ),
            FilePicker(
                label="Attach a file",
                value=state.attachment,
                on_select=lambda e: app.set_state(
                    lambda s: setattr(s, "attachment", e.name or e.uri)
                ),
                key="attachment",
                style=field_style,
            ),
            Text(
                content=summary,
                style=Style(font_size=14.0, color=Color.from_hex("#9ca3af")),
                key="summary",
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — form", size=(380, 520))
    )
