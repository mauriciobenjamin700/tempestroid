"""Overlays + feedback demo (phase E2).

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/overlays/app.py

Exercises the four overlay flavours through the app's imperative overlay API:

* a modal **Dialog** with a barrier (taps behind it are blocked);
* a **BottomSheet** that slides up from the bottom edge;
* a **Toast** that auto-dismisses after a couple of seconds (no interaction);
* an anchored **Menu** whose selection routes a ``MenuSelectEvent`` back.

Each overlay is pushed with ``app.show_dialog`` / ``app.show_sheet`` /
``app.toast`` / ``app.show_menu`` and removed with ``app.dismiss`` (or, for a
toast, automatically). The renderers realize each as the platform-native surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    BottomSheet,
    Button,
    Color,
    Column,
    Dialog,
    Edge,
    FlexDirection,
    FontWeight,
    Menu,
    MenuItem,
    MenuSelectEvent,
    Style,
    Text,
    Toast,
    Widget,
)


@dataclass
class OverlayState:
    """The demo's mutable state.

    Attributes:
        last_action: A human-readable description of the last overlay action.
    """

    last_action: str = "no action yet"


def make_state() -> OverlayState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new overlay-demo state.
    """
    return OverlayState()


def _button_style(background: str) -> Style:
    """Build a shared button style with the given background hex.

    Args:
        background: The button background, as a hex string.

    Returns:
        The button style.
    """
    return Style(
        padding=Edge.symmetric(vertical=10.0, horizontal=18.0),
        radius=10.0,
        background=Color.from_hex(background),
        color=Color.from_hex("#ffffff"),
        font_size=16.0,
    )


def view(app: App[OverlayState]) -> Widget:
    """Build the overlay-demo UI for the current state.

    Args:
        app: The running app (read ``app.state``, push overlays via the overlay
            API, wire handlers to ``app.set_state``).

    Returns:
        The root widget of the demo screen.
    """

    def _note(text: str) -> None:
        app.set_state(lambda s: setattr(s, "last_action", text))

    def open_dialog() -> None:
        dialog_id = ""

        def close() -> None:
            app.dismiss(dialog_id)
            _note("dialog dismissed")

        dialog_id = app.show_dialog(
            Dialog(
                title="Confirm",
                children=[
                    Text(content="This dialog blocks taps behind it (barrier)."),
                    Button(label="Close", on_click=close, key="dlg-close"),
                ],
                key="confirm-dialog",
            ),
            barrier=True,
        )
        _note("dialog opened")

    def open_sheet() -> None:
        sheet_id = ""

        def close() -> None:
            app.dismiss(sheet_id)
            _note("sheet dismissed")

        sheet_id = app.show_sheet(
            BottomSheet(
                children=[
                    Text(content="A bottom sheet slid up from the edge."),
                    Button(label="Done", on_click=close, key="sheet-done"),
                ],
                key="info-sheet",
            ),
            barrier=True,
        )
        _note("sheet opened")

    def show_toast() -> None:
        app.toast(
            Toast(message="Saved!", duration_s=2.0, key="saved-toast"),
            duration_s=2.0,
        )
        _note("toast shown (auto-dismisses)")

    def open_menu() -> None:
        def on_select(event: MenuSelectEvent) -> None:
            _note(f"menu selected: {event.label} ({event.value})")

        app.show_menu(
            Menu(
                items=[
                    MenuItem(label="Rename", value="rename"),
                    MenuItem(label="Duplicate", value="duplicate"),
                    MenuItem(label="Delete", value="delete"),
                ],
                on_select=on_select,
                key="actions-menu",
            ),
            anchor="menu-btn",
        )
        _note("menu opened")

    return Column(
        style=Style(
            direction=FlexDirection.COLUMN,
            align=AlignItems.CENTER,
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="Overlays demo",
                style=Style(
                    color=Color.from_hex("#f9fafb"),
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            Text(
                content=app.state.last_action,
                style=Style(color=Color.from_hex("#9ca3af"), font_size=14.0),
                key="status",
            ),
            Button(
                label="Open dialog (barrier)",
                on_click=open_dialog,
                key="dialog-btn",
                style=_button_style("#2563eb"),
            ),
            Button(
                label="Open bottom sheet",
                on_click=open_sheet,
                key="sheet-btn",
                style=_button_style("#16a34a"),
            ),
            Button(
                label="Show toast",
                on_click=show_toast,
                key="toast-btn",
                style=_button_style("#d97706"),
            ),
            Button(
                label="Open menu",
                on_click=open_menu,
                key="menu-btn",
                style=_button_style("#7c3aed"),
            ),
        ],
    )


def main() -> int:
    """Run the overlays demo in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(
        make_state(), view, title="tempestroid — overlays", size=(360, 420)
    )


if __name__ == "__main__":
    raise SystemExit(main())
