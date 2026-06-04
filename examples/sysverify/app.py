"""On-device verification harness for the E8/E9 platform capabilities.

Exercises the capabilities that need real hardware/OS behaviour, so they can be
proven on a physical device (``tempest build`` → install → tap):

* **Sensors** — registers the accelerometer; the live ``[x, y, z]`` sample (the
  device reports gravity even at rest) is shown, proving the sensor stream.
* **Biometrics** — taps trigger ``authenticate``; the typed result/error is
  shown (success with an enrolled fingerprint, else a typed error — either way
  the BiometricPrompt path is exercised).
* **Background** — schedules a WorkManager task (proves the enqueue path).
* **Push** — posts a local notification immediately, and requests an FCM token
  (``not_configured`` without ``google-services.json`` — proves the path).
* **Semantics** — the status line carries ``Semantics(label=...)`` so the label
  reaches the accessibility tree (verified via an a11y node dump).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    NativeError,
    Row,
    Semantics,
    SensorEvent,
    SensorType,
    Style,
    Text,
    Widget,
    authenticate,
    register_push,
    schedule_notification,
    schedule_task,
    start_sensor,
)


def _no_floats() -> list[float]:
    """Typed empty-list factory for the accelerometer sample field."""
    return []


@dataclass
class VerifyState:
    """State for the verification harness."""

    accel: list[float] = field(default_factory=_no_floats)
    status: str = "tap an action"
    sensor_started: bool = False


def make_state() -> VerifyState:
    """Build the initial state.

    Returns:
        A fresh :class:`VerifyState`.
    """
    return VerifyState()


def view(app: App[VerifyState]) -> Widget:
    """Render the harness and register the accelerometer once.

    Args:
        app: The running app.

    Returns:
        The widget tree.
    """
    if not app.state.sensor_started:
        app.state.sensor_started = True

        def on_sample(event: SensorEvent) -> None:
            def apply(state: VerifyState) -> None:
                state.accel = list(event.values)

            app.set_state(apply)

        start_sensor(SensorType.ACCELEROMETER, on_sample, rate_ms=200)

    def set_status(text: str) -> None:
        def apply(state: VerifyState) -> None:
            state.status = text

        app.set_state(apply)

    async def do_biometrics() -> None:
        try:
            result = await authenticate(reason="Verify identity")
            set_status(f"biometrics: authenticated={result.authenticated} "
                       f"error={result.error!r}")
        except NativeError as exc:
            set_status(f"biometrics error: {exc}")

    def do_background() -> None:
        schedule_task("sysverify-task", interval_s=900)
        set_status("background: scheduled WorkManager task 'sysverify-task'")

    def do_notify() -> None:
        schedule_notification("Tempest E8", "local notification fired", 0.0)
        set_status("push: posted a local notification")

    async def do_push_token() -> None:
        try:
            token = await register_push()
            set_status(f"push token: {token.token[:24]}…")
        except NativeError as exc:
            set_status(f"push token error: {exc}")

    accel = app.state.accel
    if accel:
        accel_text = f"accel = [{', '.join(f'{v:.2f}' for v in accel)}]"
    else:
        accel_text = "accel = (waiting…)"

    def button(label: str, handler: object, color: str) -> Button:
        return Button(
            label=label,
            on_click=handler,  # type: ignore[arg-type]
            style=Style(
                padding=Edge.symmetric(vertical=12.0, horizontal=14.0),
                background=Color.from_hex(color),
                color=Color.from_hex("#ffffff"),
                radius=10.0,
            ),
        )

    return Column(
        style=Style(
            padding=Edge.all(20.0),
            gap=14.0,
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="tempestroid — E8/E9 verify",
                style=Style(color=Color.from_hex("#f9fafb"), font_size=22.0),
            ),
            Text(
                content=accel_text,
                style=Style(color=Color.from_hex("#22c55e"), font_size=18.0),
            ),
            Text(
                content=app.state.status,
                style=Style(color=Color.from_hex("#e5e7eb"), font_size=16.0),
                semantics=Semantics(label=f"status: {app.state.status}"),
            ),
            Row(
                style=Style(gap=10.0),
                children=[
                    button("Biometrics", do_biometrics, "#2563eb"),
                    button("Background", do_background, "#7c3aed"),
                ],
            ),
            Row(
                style=Style(gap=10.0),
                children=[
                    button("Notify", do_notify, "#16a34a"),
                    button("Push token", do_push_token, "#ea580c"),
                ],
            ),
        ],
    )
