"""G1 spike — prove ``import numpy`` works inside the embedded interpreter.

The first device-facing step of Trilho G: the app's ``view`` imports ``numpy``
(the cross-compiled ``android_24_x86_64`` wheel staged into the device
site-packages) and renders its version plus the result of a small array
computation. If numpy imports and computes on the device, the screen shows a
green "numpy OK" line; if it fails to import, the failure is caught and shown as
red text instead of a blank screen — so the screenshot is self-describing either
way.

This is intentionally renderer-agnostic (no top-level Qt import): it runs in the
Qt simulator AND on the emulator/device via the Compose renderer.

Runs in the Qt simulator::

    uv run python examples/onnxspike/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    Color,
    Column,
    Edge,
    FontWeight,
    Style,
    Text,
    Widget,
)

_BG = Color.from_hex("#0b0f14")
_OK = Color.from_hex("#22c55e")
_ERR = Color.from_hex("#ef4444")
_TEXT = Color.from_hex("#f9fafb")
_SUBTLE = Color.from_hex("#9ca3af")


@dataclass
class SpikeState:
    """Empty state — the spike is computed on every build.

    Attributes:
        _unused: Placeholder so the dataclass is non-empty.
    """

    _unused: int = 0


def make_state() -> SpikeState:
    """Build a fresh state.

    Returns:
        A new spike state.
    """
    return SpikeState()


def _numpy_report() -> tuple[bool, str]:
    """Import numpy and run a tiny computation, capturing any failure.

    Returns:
        A ``(ok, message)`` pair: ``ok`` is whether numpy imported and computed;
        ``message`` is a human-readable line (version + result, or the error).
    """
    try:
        import numpy as np

        arr = np.arange(1, 11, dtype=np.float64)
        total = float(arr.sum())
        mean = float(arr.mean())
        dot = float(np.dot(arr, arr))
        return (
            True,
            f"numpy {np.__version__}  sum={total:.0f}  mean={mean:.1f}  dot={dot:.0f}",
        )
    except Exception as exc:  # noqa: BLE001 — surface ANY failure on screen
        return (False, f"{type(exc).__name__}: {exc}")


def view(app: App[SpikeState]) -> Widget:
    """Build the spike screen reporting the numpy import result.

    Args:
        app: The running app (state is unused; the report is computed here).

    Returns:
        The root widget showing the numpy status.
    """
    ok, message = _numpy_report()
    return Column(
        style=Style(
            background=_BG,
            padding=Edge.all(24),
            gap=16,
            grow=1,
        ),
        children=[
            Text(
                content="Trilho G — numpy on device",
                style=Style(color=_TEXT, font_size=22, font_weight=FontWeight.BOLD),
                key="title",
            ),
            Text(
                content=("numpy OK" if ok else "numpy FAILED"),
                style=Style(
                    color=(_OK if ok else _ERR),
                    font_size=18,
                    font_weight=FontWeight.BOLD,
                ),
                key="status",
            ),
            Text(
                content=message,
                style=Style(color=_SUBTLE, font_size=14),
                key="detail",
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — numpy spike", size=(420, 240))
    )
