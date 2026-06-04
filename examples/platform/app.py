"""Platform / system capabilities demo (phase E8).

Exercises the platform-and-system native surface in a way that runs on the Qt
simulator today and on a real device unchanged:

* **Haptics** — tapping "Vibrate" calls :func:`tempestroid.vibrate`. On the
  device it buzzes; on the desktop simulator there is no haptics hardware, so the
  call raises :class:`~tempestroid.NativeError` (or a bare ``RuntimeError`` for
  the missing host) which the handler catches and reports in the UI.
* **Preferences** — "Save name" persists the typed name via
  :func:`tempestroid.set_pref` and the count via the same key-value store. On the
  simulator the store is a *real* JSON file under ``~/.tempestroid/prefs.json``,
  so the value survives a restart with no device.
* **Lifecycle** — :func:`tempestroid.on_app_state_change` registers a callback
  that records foreground/background transitions (driven by
  ``QApplication.applicationStateChanged`` in the simulator).
* **KeyboardAvoidingView** — wraps the name :class:`~tempestroid.Input` so the
  focused field stays visible above the on-screen keyboard on the device.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/platform/app.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    AlignItems,
    App,
    Button,
    Color,
    Column,
    Edge,
    FlexDirection,
    FontWeight,
    Input,
    KeyboardAvoidingView,
    LifecycleEvent,
    NativeError,
    Style,
    Text,
    TextChangeEvent,
    Widget,
    on_app_state_change,
    set_pref,
    vibrate,
)


@dataclass
class PlatformState:
    """The demo's mutable state.

    Attributes:
        name: The current value of the name input field.
        status: The last status line to show (haptics / prefs result).
        last_app_state: The most recent lifecycle state observed.
    """

    name: str = ""
    status: str = "Type a name, then try the actions."
    last_app_state: str = "foreground"
    _registered: bool = field(default=False, repr=False)


def make_state() -> PlatformState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new platform-demo state.
    """
    return PlatformState()


def view(app: App[PlatformState]) -> Widget:
    """Build the platform-demo UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the demo screen.
    """
    if not app.state._registered:
        # Register the lifecycle callback once; the simulator's app runner drives
        # it from QApplication.applicationStateChanged.
        def _on_lifecycle(event: LifecycleEvent) -> None:
            app.set_state(lambda s: setattr(s, "last_app_state", event.state.value))

        on_app_state_change(_on_lifecycle)
        app.state._registered = True

    def on_name_change(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "name", event.value))

    def buzz() -> None:
        try:
            vibrate(80)
            message = "Vibrated (device only)."
        except NativeError as exc:  # device-only capability missing
            message = f"Haptics unavailable: {exc.code}"
        except RuntimeError:  # no native host on the desktop simulator
            message = "Haptics unavailable: device_only (Qt simulator)."
        app.set_state(lambda s: setattr(s, "status", message))

    def save_name() -> None:
        # prefs writes to a real JSON file on the desktop — no device needed.
        set_pref("name", app.state.name)
        app.set_state(
            lambda s: setattr(s, "status", f"Saved name={s.name!r} to prefs.")
        )

    def _button_style(background: str) -> Style:
        """Build a shared button style with the given background hex."""
        return Style(
            padding=Edge.symmetric(vertical=10.0, horizontal=18.0),
            radius=10.0,
            background=Color.from_hex(background),
            color=Color.from_hex("#ffffff"),
            font_size=16.0,
        )

    return KeyboardAvoidingView(
        style=Style(
            direction=FlexDirection.COLUMN,
            align=AlignItems.CENTER,
            gap=14.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="tempestroid — platform",
                style=Style(
                    color=Color.from_hex("#f9fafb"),
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            Input(
                value=app.state.name,
                placeholder="Your name",
                on_change=on_name_change,
                key="name",
            ),
            Column(
                style=Style(gap=8.0),
                children=[
                    Button(
                        label="Vibrate",
                        on_click=buzz,
                        key="vibrate",
                        style=_button_style("#22c55e"),
                    ),
                    Button(
                        label="Save name",
                        on_click=save_name,
                        key="save",
                        style=_button_style("#2563eb"),
                    ),
                ],
            ),
            Text(
                content=app.state.status,
                style=Style(color=Color.from_hex("#cbd5e1"), font_size=14.0),
                key="status",
            ),
            Text(
                content=f"App state: {app.state.last_app_state}",
                style=Style(color=Color.from_hex("#94a3b8"), font_size=12.0),
                key="lifecycle",
            ),
        ],
    )


def main() -> int:
    """Run the platform demo in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(
        make_state(), view, title="tempestroid — platform", size=(360, 420)
    )


if __name__ == "__main__":
    raise SystemExit(main())
