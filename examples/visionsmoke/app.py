"""Vision-stack smoke app — proves the on-device imports the bug was about.

Runs on the device's embedded CPython. It imports ``numpy`` and
``ort_vision_sdk`` (the two modules a vision app needs and which a lean,
non-``vision`` build was missing), does a tiny numpy compute, and renders the
result — so a green screen is proof the ``vision`` feature staged them.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Color,
    Column,
    Edge,
    JustifyContent,
    Style,
    Text,
    Widget,
)


def _probe() -> tuple[bool, str]:
    """Import the vision stack on-device and run a tiny numpy compute.

    Returns:
        A ``(ok, message)`` pair — ``ok`` is ``True`` when both imports and the
        compute succeed; ``message`` is a human summary (or the error).
    """
    try:
        import numpy as np
        import ort_vision_sdk

        dot = float(np.arange(4, dtype="float64") @ np.arange(4, dtype="float64"))
        version = getattr(ort_vision_sdk, "__version__", "?")
        return True, f"numpy {np.__version__} dot={dot:.0f} | ort_vision_sdk {version}"
    except Exception as exc:  # noqa: BLE001 — surface any import/compute failure on screen
        return False, f"{type(exc).__name__}: {exc}"


@dataclass
class SmokeState:
    """Holds the probe result computed once at startup.

    Attributes:
        ok: Whether the vision stack imported + computed successfully.
        message: The summary or error string to render.
    """

    ok: bool
    message: str


def make_state() -> SmokeState:
    """Build the initial state by running the vision-stack probe.

    Returns:
        A state carrying the probe outcome.
    """
    ok, message = _probe()
    return SmokeState(ok=ok, message=message)


def view(app: App[SmokeState]) -> Widget:
    """Render the probe result full-screen.

    Args:
        app: The running app (reads ``app.state``).

    Returns:
        The root widget.
    """
    state = app.state
    bg = Color(r=22, g=163, b=74) if state.ok else Color(r=220, g=38, b=38)
    title = "VISION OK" if state.ok else "VISION FAIL"
    return Column(
        style=Style(
            background=bg,
            padding=Edge.all(24),
            justify=JustifyContent.CENTER,
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content=title,
                style=Style(color=Color(r=255, g=255, b=255), font_size=28.0),
            ),
            Text(
                content=state.message,
                style=Style(color=Color(r=255, g=255, b=255), margin=Edge.all(16)),
            ),
        ],
    )


def main() -> int:
    """Run the smoke app in the Qt simulator (desktop only).

    Returns:
        The Qt application exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(
        make_state(), view, title="tempestroid — vision smoke", size=(360, 480)
    )


if __name__ == "__main__":
    raise SystemExit(main())
