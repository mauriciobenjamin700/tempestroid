"""G6 spike — prove ``import scipy`` + ``import sklearn`` work on device.

The science-stack step of Trilho G: the app's ``view`` imports ``scipy`` and
``scikit-learn`` (the cross-compiled ``android_26_x86_64`` wheels staged into the
device site-packages — OpenBLAS static-linked into scipy, NDK ``libomp``
vendored into sklearn), then fits a tiny :class:`LogisticRegression` and predicts.
If the stack imports and predicts on device, the screen shows a green "sklearn OK"
line with the versions + the prediction; any failure is caught and shown as red
text instead of a blank screen — so the screenshot is self-describing.

This closes the historically-feared scipy/sklearn "calcanhar" (Fortran/LAPACK +
OpenMP) on Android: both cross-compile clang-only, zero Fortran.

Renderer-agnostic (no top-level Qt import): runs in the Qt simulator AND on the
emulator/device via the Compose renderer.

Runs in the Qt simulator::

    uv run python examples/sklearnspike/app.py
"""

# scipy / scikit-learn ship no (or incomplete) type stubs, so pyright strict can
# only infer partial types for their runtime calls. They are device-only science
# deps exercised at runtime, not a typed surface — suppress the stub-driven noise
# here (the rest of the file stays fully typed).
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def _science_report() -> tuple[bool, list[str]]:
    """Import scipy + sklearn and run a tiny fit/predict, capturing any failure.

    Trains a :class:`LogisticRegression` on a trivially separable 1-D dataset and
    predicts two held-out points, exercising the real BLAS/LAPACK + OpenMP paths
    that make scipy/sklearn the hard case on Android.

    Returns:
        An ``(ok, lines)`` pair: ``ok`` is whether the stack imported and
        predicted; ``lines`` are human-readable report lines (versions + result,
        or the error).
    """
    try:
        import numpy as np
        import scipy
        import sklearn
        from scipy import linalg
        from sklearn.linear_model import LogisticRegression

        # A tiny separable problem: y = 1 iff x >= 5.
        x = np.arange(0, 10, dtype=np.float64).reshape(-1, 1)
        y = (x.ravel() >= 5).astype(np.int64)
        model = LogisticRegression()
        model.fit(x, y)
        preds: Any = model.predict(np.array([[2.0], [8.0]]))
        # Exercise a scipy LAPACK path too (solve a small linear system).
        sol = linalg.solve(np.array([[3.0, 1.0], [1.0, 2.0]]), np.array([9.0, 8.0]))
        return (
            True,
            [
                f"scipy {scipy.__version__}  sklearn {sklearn.__version__}",
                f"LogisticRegression.predict([2, 8]) = {preds.tolist()}",
                f"scipy.linalg.solve = [{sol[0]:.1f}, {sol[1]:.1f}]",
            ],
        )
    except Exception as exc:  # noqa: BLE001 — surface ANY failure on screen
        return (False, [f"{type(exc).__name__}: {exc}"])


def view(app: App[SpikeState]) -> Widget:
    """Build the spike screen reporting the scipy/sklearn import + predict result.

    Args:
        app: The running app (state is unused; the report is computed here).

    Returns:
        The root widget showing the science-stack status.
    """
    ok, lines = _science_report()
    children: list[Widget] = [
        Text(
            content="Trilho G — scipy + sklearn on device",
            style=Style(color=_TEXT, font_size=22, font_weight=FontWeight.BOLD),
            key="title",
        ),
        Text(
            content=("sklearn OK" if ok else "sklearn FAILED"),
            style=Style(
                color=(_OK if ok else _ERR),
                font_size=18,
                font_weight=FontWeight.BOLD,
            ),
            key="status",
        ),
    ]
    children.extend(
        Text(
            content=line,
            style=Style(color=_SUBTLE, font_size=14),
            key=f"line{index}",
        )
        for index, line in enumerate(lines)
    )
    return Column(
        style=Style(background=_BG, padding=Edge.all(24), gap=12, grow=1),
        children=children,
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — sklearn spike", size=(480, 280))
    )
