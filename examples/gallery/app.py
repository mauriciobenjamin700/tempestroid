"""Component gallery (utility widgets + input styling + implicit transitions).

Showcases the widgets added on top of the A1 primitives — ``Slider``, ``Switch``,
``ProgressBar``, ``Spinner``, ``Image``, ``Icon``, ``ScrollView``, the secure /
regex / multiline text fields — plus a ``Style.transition`` that animates a
panel's background on the device renderer.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/gallery/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Color,
    Column,
    Curve,
    Edge,
    Icon,
    Input,
    KeyboardType,
    ProgressBar,
    Row,
    ScrollView,
    SlideEvent,
    Slider,
    Spinner,
    Style,
    Switch,
    Text,
    TextArea,
    TextChangeEvent,
    ToggleEvent,
    Transition,
    Widget,
)

_EMAIL_PATTERN = r"[^@\s]+@[^@\s]+\.[^@\s]+"


@dataclass
class GalleryState:
    """The gallery's mutable state.

    Attributes:
        email: The current value of the email field.
        email_valid: Whether the email field currently matches its pattern.
        password: The current value of the password field.
        notes: The current value of the multi-line notes field.
        volume: The slider value, 0-100.
        dark: Whether the dark-panel switch is on.
    """

    email: str = ""
    email_valid: bool | None = None
    password: str = ""
    notes: str = ""
    volume: float = 30.0
    dark: bool = False


def make_state() -> GalleryState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new gallery state.
    """
    return GalleryState()


def view(app: App[GalleryState]) -> Widget:
    """Build the gallery UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the gallery screen.
    """
    state = app.state

    def on_email(event: TextChangeEvent) -> None:
        def mutate(s: GalleryState) -> None:
            s.email = event.value
            s.email_valid = event.valid

        app.set_state(mutate)

    def on_password(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "password", event.value))

    def on_notes(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "notes", event.value))

    def on_volume(event: SlideEvent) -> None:
        app.set_state(lambda s: setattr(s, "volume", event.value))

    def on_dark(event: ToggleEvent) -> None:
        app.set_state(lambda s: setattr(s, "dark", event.checked))

    panel_bg = Color.from_hex("#101418") if state.dark else Color.from_hex("#f4f6f8")
    panel_fg = Color.from_hex("#ffffff") if state.dark else Color.from_hex("#101418")

    return ScrollView(
        style=Style(gap=16.0, padding=Edge.all(20.0)),
        children=[
            Row(
                style=Style(gap=8.0, align=AlignItems.CENTER),
                children=[
                    Icon(name="widgets", size=20.0),
                    Text(content="Component gallery", style=Style(font_size=22.0)),
                ],
            ),
            Input(
                placeholder="email",
                value=state.email,
                pattern=_EMAIL_PATTERN,
                keyboard=KeyboardType.EMAIL,
                error="" if state.email_valid in (None, True) else "invalid email",
                on_change=on_email,
            ),
            Input(
                placeholder="password",
                value=state.password,
                secure=True,
                max_length=32,
                on_change=on_password,
            ),
            TextArea(
                placeholder="notes",
                value=state.notes,
                rows=4,
                on_change=on_notes,
            ),
            Row(
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(content=f"Volume: {int(state.volume)}"),
                    Slider(
                        value=state.volume,
                        min_value=0.0,
                        max_value=100.0,
                        on_change=on_volume,
                        style=Style(grow=1.0),
                    ),
                ],
            ),
            ProgressBar(value=state.volume / 100.0),
            Row(
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Switch(label="Dark panel", checked=state.dark, on_change=on_dark),
                    Spinner(size=24.0),
                ],
            ),
            Column(
                style=Style(
                    padding=Edge.all(16.0),
                    radius=12.0,
                    background=panel_bg,
                    color=panel_fg,
                    transition=Transition(duration_ms=300, curve=Curve.EASE_IN_OUT),
                ),
                children=[
                    Text(
                        content="This panel animates its background on the device.",
                        style=Style(color=panel_fg),
                    ),
                ],
            ),
        ],
    )


def main() -> int:
    """Run the gallery in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(
        make_state(), view, title="tempestroid — gallery", size=(380, 640)
    )


if __name__ == "__main__":
    raise SystemExit(main())
