"""Form — gallery example exercising the value-bearing input widgets.

Showcases the leaf inputs that carry a value and a typed change event:
``Input`` (text), ``Checkbox`` (boolean), ``DatePicker`` (ISO date) and
``FilePicker`` (file selection). Each handler receives the validated typed event
and folds the new value back into state, which re-renders a live summary.

Runs in the Qt simulator::

    uv run python examples/form/app.py
    uv run tempest dev examples/form/app.py     # + hot restart on save

On a device the input widgets render once the Compose host renderer grows the
matching cases (Trilho B follow-up); the contract (``view`` / ``make_state``) is
identical either way.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    Checkbox,
    Color,
    Column,
    DateChangeEvent,
    DatePicker,
    Edge,
    FilePicker,
    FileSelectEvent,
    FontWeight,
    Input,
    Style,
    Text,
    TextChangeEvent,
    ToggleEvent,
    Widget,
)


@dataclass
class FormState:
    """The form's mutable state.

    Attributes:
        name: The text typed into the name field.
        subscribe: Whether the newsletter checkbox is checked.
        birthday: The selected birthday as an ISO ``yyyy-mm-dd`` string.
        attachment: The display name of the chosen file (``""`` until one is set).
    """

    name: str = ""
    subscribe: bool = False
    birthday: str = ""
    attachment: str = ""


def make_state() -> FormState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new, empty form state.
    """
    return FormState()


def view(app: App[FormState]) -> Widget:
    """Build the form UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the form screen.
    """
    state = app.state

    def on_name(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "name", event.value))

    def on_subscribe(event: ToggleEvent) -> None:
        app.set_state(lambda s: setattr(s, "subscribe", event.checked))

    def on_birthday(event: DateChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "birthday", event.value))

    def on_attachment(event: FileSelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "attachment", event.name or event.uri))

    summary = ", ".join(
        part
        for part in (
            f"name={state.name}" if state.name else "",
            f"subscribed={state.subscribe}",
            f"birthday={state.birthday}" if state.birthday else "",
            f"file={state.attachment}" if state.attachment else "",
        )
        if part
    )

    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="Sign up",
                style=Style(
                    color=Color.from_hex("#ffffff"),
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            Input(
                value=state.name,
                placeholder="Your name",
                on_change=on_name,
                key="name",
            ),
            Checkbox(
                label="Subscribe to the newsletter",
                checked=state.subscribe,
                on_change=on_subscribe,
                key="subscribe",
            ),
            DatePicker(
                value=state.birthday,
                label="Birthday",
                on_change=on_birthday,
                key="birthday",
            ),
            FilePicker(
                label="Attach a file",
                value=state.attachment,
                on_select=on_attachment,
                key="attachment",
            ),
            Text(
                content=summary or "Fill the form above…",
                style=Style(color=Color.from_hex("#9ca3af"), font_size=14.0),
                key="summary",
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — form", size=(380, 480))
    )
