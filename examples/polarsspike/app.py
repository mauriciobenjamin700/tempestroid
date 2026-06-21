"""G spike — prove ``import polars`` + reading/writing work on device.

The Polars step of Trilho G: the app's ``view`` imports ``polars`` (the
cross-compiled ``polars-runtime-32`` abi3 Android wheel + the pure-Python
wrapper), builds a small :class:`DataFrame`, runs a group_by/aggregate, and
exercises the **reading/writing** surface from the Polars getting-started — a
round-trip through CSV (``write_csv`` -> ``read_csv``), entirely in memory (no
filesystem needed: ``write_csv()`` with no path returns the CSV string). If Polars
imports and round-trips on device, the screen shows a green "polars OK" line with
the version + results; any failure is caught and shown as red text instead of a
blank screen.

Polars is the lightest DataFrame for the device — a Rust core (abi3,
dependency-free, CSV/JSON/Parquet native), no numpy/pandas needed.

Renderer-agnostic (no top-level Qt import): runs in the Qt simulator AND on the
emulator/device via the Compose renderer.

Runs in the Qt simulator::

    uv run python examples/polarsspike/app.py
"""

# polars ships type stubs but pyright strict still infers partial types for many
# chained calls; it is a device-only dep exercised at runtime, not a typed
# surface — suppress the stub-driven noise (the rest stays fully typed).
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import io
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


def _polars_report() -> tuple[bool, list[str]]:
    """Import polars, run a group_by, and round-trip through CSV in memory.

    Exercises the Rust core's compute (group_by/agg) and the reading/writing path
    (``write_csv`` -> ``read_csv``) from the getting-started, with no filesystem.

    Returns:
        An ``(ok, lines)`` pair: ``ok`` is whether polars imported and round-
        tripped; ``lines`` are human-readable report lines (version + result, or
        the error).
    """
    try:
        import polars as pl

        frame = pl.DataFrame(
            {
                "team": ["a", "b", "a", "b", "a", "b"],
                "points": [10, 7, 3, 12, 5, 1],
            }
        )
        totals: pl.DataFrame = (
            frame.group_by("team")
            .agg(pl.col("points").sum().alias("total"))
            .sort("team")
        )
        # Reading/writing: write_csv() with no path returns the CSV text; read it
        # back from an in-memory buffer — a full round-trip with no filesystem.
        csv_text: str = frame.write_csv()
        restored: pl.DataFrame = pl.read_csv(io.StringIO(csv_text))
        a_total = totals.filter(pl.col("team") == "a")["total"][0]
        return (
            True,
            [
                f"polars {pl.__version__}",
                f"group_by('team').sum() team=a total={a_total}",
                f"write_csv -> read_csv round-trip: {restored.height} rows",
            ],
        )
    except Exception as exc:  # noqa: BLE001 — surface ANY failure on screen
        import traceback

        tb = traceback.format_exc().strip().splitlines()
        return (False, [f"{type(exc).__name__}: {exc}", *tb[-6:]])


def view(app: App[SpikeState]) -> Widget:
    """Build the spike screen reporting the polars import + round-trip result.

    Args:
        app: The running app (state is unused; the report is computed here).

    Returns:
        The root widget showing the polars status.
    """
    ok, lines = _polars_report()
    children: list[Widget] = [
        Text(
            content="Trilho G — polars on device",
            style=Style(color=_TEXT, font_size=22, font_weight=FontWeight.BOLD),
            key="title",
        ),
        Text(
            content=("polars OK" if ok else "polars FAILED"),
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
        run_qt(make_state(), view, title="tempestroid — polars spike", size=(480, 260))
    )
