# pyright: reportPrivateUsage=false
"""Deterministic unit tests for the core animation framework.

The animation clock is driven through an injectable ``time_source`` so these
tests never depend on real wall-clock timing: a controller is advanced by an
explicit ``dt``, and the :class:`~tempestroid.App` clock is stepped by mutating
a fake clock between manual :meth:`App._tick` calls.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tempestroid import (
    AnimationController,
    App,
    Color,
    Curve,
    Edge,
    Spring,
    Text,
    Tween,
    Widget,
)


@dataclass
class _State:
    """Trivial app state for the clock-integration tests."""

    value: int = 0


def _view(app: App[_State]) -> Widget:
    """Render the state as a single ``Text`` node."""
    return Text(content=f"n={app.state.value}")


def test_controller_forward_reaches_one() -> None:
    """``forward`` drives ``value`` to exactly 1.0 once the duration elapses."""
    ctrl = AnimationController(duration_s=1.0, curve=Curve.LINEAR)
    ctrl.forward()
    assert ctrl._advance(0.5) is False
    assert ctrl.value == 0.5
    # Advancing past the duration clamps to the target and reports completion.
    assert ctrl._advance(0.5) is True
    assert ctrl.value == 1.0


def test_controller_reverse() -> None:
    """``reverse`` from a settled 1.0 walks ``value`` back to 0.0."""
    ctrl = AnimationController(duration_s=1.0, curve=Curve.LINEAR)
    ctrl.value = 1.0
    ctrl.reverse()
    assert ctrl._advance(0.5) is False
    assert ctrl.value == 0.5
    assert ctrl._advance(0.5) is True
    assert ctrl.value == 0.0


def test_controller_zero_duration_snaps() -> None:
    """A zero-duration ramp snaps straight to the target in one frame."""
    ctrl = AnimationController(duration_s=0.0, curve=Curve.LINEAR)
    ctrl.forward()
    assert ctrl._advance(0.016) is True
    assert ctrl.value == 1.0


def test_controller_spring_settles() -> None:
    """A spring-driven controller eventually settles at its target."""
    ctrl = AnimationController(
        duration_s=0.0, spring=Spring(stiffness=200.0, damping=20.0, mass=1.0)
    )
    ctrl.forward()
    done = False
    for _ in range(600):
        if ctrl._advance(1.0 / 60.0):
            done = True
            break
    assert done is True
    assert ctrl.value == 1.0


def test_tween_float() -> None:
    """A float tween interpolates linearly at the midpoint."""
    tween: Tween[float] = Tween(begin=0.0, end=100.0)
    assert tween.at(0.0) == 0.0
    assert tween.at(0.5) == 50.0
    assert tween.at(1.0) == 100.0


def test_tween_color() -> None:
    """A color tween interpolates every channel at the midpoint."""
    tween: Tween[Color] = Tween(
        begin=Color(r=0, g=0, b=0, a=0.0),
        end=Color(r=100, g=200, b=50, a=1.0),
    )
    mid = tween.at(0.5)
    assert mid.r == 50
    assert mid.g == 100
    assert mid.b == 25
    assert mid.a == 0.5


def test_tween_edge() -> None:
    """An edge tween interpolates each side at the midpoint."""
    tween: Tween[Edge] = Tween(
        begin=Edge.all(0.0), end=Edge(top=10.0, right=20.0, bottom=30.0, left=40.0)
    )
    mid = tween.at(0.5)
    assert (mid.top, mid.right, mid.bottom, mid.left) == (5.0, 10.0, 15.0, 20.0)


def test_tween_tuple() -> None:
    """A numeric tuple tween interpolates element-wise."""
    tween: Tween[tuple[float, ...]] = Tween(begin=(0.0, 10.0), end=(10.0, 30.0))
    assert tween.at(0.5) == (5.0, 20.0)


async def test_app_clock_integrates() -> None:
    """Registering a controller and ticking the clock requests a rebuild."""
    clock = {"now": 0.0}
    captured: list[list[object]] = []
    app: App[_State] = App(
        _State(),
        _view,
        apply_patches=lambda p: captured.append(list(p)),
        time_source=lambda: clock["now"],
    )
    app.start()
    rebuilds = {"count": 0}
    original = app.request_rebuild

    def _spy() -> None:
        rebuilds["count"] += 1
        original()

    app.request_rebuild = _spy  # type: ignore[method-assign]
    ctrl = AnimationController(duration_s=1.0, curve=Curve.LINEAR)
    app.register_animation(ctrl)
    ctrl.forward()
    assert ctrl in app._animations
    # Advance the fake clock and tick: the controller advances toward 1.0 and a
    # coalesced rebuild is requested.
    clock["now"] = 0.5
    app._tick()
    await asyncio.sleep(0)
    assert ctrl.value == 0.5
    assert rebuilds["count"] == 1
    # ``captured`` may be empty: the view does not read the controller, so the
    # diff is a no-op — what matters is that the clock requested the rebuild.
    assert captured == []


async def test_app_clock_stops_when_empty() -> None:
    """Once a controller finishes/stops, the clock drains and no tick re-arms."""
    clock = {"now": 0.0}
    app: App[_State] = App(
        _State(),
        _view,
        apply_patches=lambda _p: None,
        time_source=lambda: clock["now"],
    )
    app.start()
    ctrl = AnimationController(duration_s=1.0, curve=Curve.LINEAR)
    app.register_animation(ctrl)
    ctrl.forward()
    ctrl.stop()
    assert ctrl not in app._animations
    # With nothing registered, ticking is inert and never re-arms.
    app._tick_scheduled = False
    clock["now"] = 1.0
    app._tick()
    assert app._tick_scheduled is False


async def test_tick_from_device_advances_once() -> None:
    """The device frame token advances the clock once without re-arming."""
    clock = {"now": 0.0}
    captured: list[list[object]] = []
    app: App[_State] = App(
        _State(),
        _view,
        apply_patches=lambda p: captured.append(list(p)),
        time_source=lambda: clock["now"],
    )
    app.start()
    ctrl = AnimationController(duration_s=1.0, curve=Curve.LINEAR)
    app.register_animation(ctrl)
    ctrl.forward()
    app._last_tick = 0.0
    clock["now"] = 0.25
    app._tick_scheduled = False
    app._tick_from_device()
    await asyncio.sleep(0)
    assert ctrl.value == 0.25
    # The device owns the cadence: no loop timer is armed by the core.
    assert app._tick_scheduled is False


# ---------------------------------------------------------------------------
# New Curve members (E3a): EASE / BOUNCE / ELASTIC
# ---------------------------------------------------------------------------


def test_controller_ease_curve_reaches_one() -> None:
    """A controller with ``Curve.EASE`` drives ``value`` to 1.0 by completion."""
    ctrl = AnimationController(duration_s=1.0, curve=Curve.EASE)
    ctrl.forward()
    assert ctrl._advance(0.5) is False
    # At the midpoint the value should be non-zero (ease does a smooth ramp).
    assert ctrl.value > 0.0
    done = ctrl._advance(0.5)
    assert done is True
    assert ctrl.value == 1.0


def test_controller_bounce_curve_reaches_one() -> None:
    """A controller with ``Curve.BOUNCE`` completes at exactly 1.0."""
    ctrl = AnimationController(duration_s=1.0, curve=Curve.BOUNCE)
    ctrl.forward()
    # Step in small increments to exercise the bounce segments.
    done = False
    for _ in range(100):
        if ctrl._advance(0.01):
            done = True
            break
    assert done is True
    assert ctrl.value == 1.0


def test_controller_elastic_curve_reaches_one() -> None:
    """A controller with ``Curve.ELASTIC`` completes at exactly 1.0."""
    ctrl = AnimationController(duration_s=1.0, curve=Curve.ELASTIC)
    ctrl.forward()
    # Elastic overshoots; value may go slightly negative mid-animation, but must
    # clamp to the target on completion.
    done = ctrl._advance(1.0)
    assert done is True
    assert ctrl.value == 1.0


def test_controller_ease_curve_is_distinct_from_linear() -> None:
    """``Curve.EASE`` produces a different value than ``Curve.LINEAR`` at t=0.25.

    The smooth cubic maps 0.25→0.0625 while LINEAR maps 0.25→0.25.
    At t=0.5 both curves happen to pass through exactly 0.5 (a symmetric
    coincidence of the cubic formula); t=0.25 is a reliable discriminant.
    """
    linear = AnimationController(duration_s=1.0, curve=Curve.LINEAR)
    linear.forward()
    linear._advance(0.25)

    ease = AnimationController(duration_s=1.0, curve=Curve.EASE)
    ease.forward()
    ease._advance(0.25)

    # At t=0.25 the smooth cubic gives 4*(0.25)^3 ≈ 0.0625, not 0.25.
    assert ease.value != linear.value
    assert abs(ease.value - 0.0625) < 1e-6


# ---------------------------------------------------------------------------
# Spring: pydantic frozen + field constraints
# ---------------------------------------------------------------------------


def test_spring_defaults() -> None:
    """A ``Spring`` created with no arguments uses the documented defaults."""
    s = Spring()
    assert s.stiffness == 300.0
    assert s.damping == 30.0
    assert s.mass == 1.0


def test_spring_is_frozen() -> None:
    """``Spring`` is a frozen Pydantic model — mutation raises."""
    from pydantic import ValidationError

    s = Spring(stiffness=200.0, damping=20.0, mass=1.0)
    try:
        s.stiffness = 999.0  # type: ignore[misc]
        raise AssertionError("expected frozen model to raise on assignment")
    except (ValidationError, TypeError):
        pass  # Either Pydantic ValidationError or a TypeError — both are correct.


def test_spring_custom_values() -> None:
    """A ``Spring`` accepts valid custom parameters."""
    s = Spring(stiffness=500.0, damping=0.0, mass=2.0)
    assert s.stiffness == 500.0
    assert s.damping == 0.0  # damping >= 0 (critically damped or overdamped)
    assert s.mass == 2.0


def test_spring_rejects_non_positive_stiffness() -> None:
    """A ``Spring`` must reject non-positive stiffness (the spring constant)."""
    from pydantic import ValidationError

    try:
        Spring(stiffness=0.0)
        raise AssertionError("expected ValidationError for stiffness=0.0")
    except ValidationError:
        pass


def test_spring_rejects_non_positive_mass() -> None:
    """A ``Spring`` must reject non-positive mass."""
    from pydantic import ValidationError

    try:
        Spring(mass=0.0)
        raise AssertionError("expected ValidationError for mass=0.0")
    except ValidationError:
        pass


# ---------------------------------------------------------------------------
# Tween: error paths
# ---------------------------------------------------------------------------


def test_tween_rejects_unsupported_type() -> None:
    """``Tween.at`` raises ``TypeError`` for unsupported endpoint types."""
    tween: Tween[str] = Tween(begin="a", end="z")
    try:
        tween.at(0.5)
        raise AssertionError("expected TypeError for string endpoints")
    except TypeError as err:
        assert "str" in str(err)


def test_tween_rejects_bool_endpoints() -> None:
    """``Tween.at`` raises ``TypeError`` for bool endpoints (not numeric)."""
    tween: Tween[bool] = Tween(begin=False, end=True)
    try:
        tween.at(0.5)
        raise AssertionError("expected TypeError for bool endpoints")
    except TypeError:
        pass


def test_tween_rejects_mismatched_tuple_lengths() -> None:
    """``Tween.at`` raises ``ValueError`` when tuple endpoints differ in length."""
    tween: Tween[tuple[float, ...]] = Tween(begin=(0.0, 1.0), end=(0.0, 1.0, 2.0))
    try:
        tween.at(0.5)
        raise AssertionError("expected ValueError for length mismatch")
    except ValueError as err:
        assert "length" in str(err)


def test_tween_float_boundary_values() -> None:
    """``Tween[float].at`` returns ``begin`` at ``t=0`` and ``end`` at ``t=1``."""
    tween: Tween[float] = Tween(begin=10.0, end=20.0)
    assert tween.at(0.0) == 10.0
    assert tween.at(1.0) == 20.0


def test_tween_color_boundary_values() -> None:
    """``Tween[Color].at(0)`` returns ``begin``; ``at(1)`` returns ``end``."""
    begin = Color(r=0, g=0, b=0, a=0.0)
    end = Color(r=255, g=128, b=64, a=1.0)
    tween: Tween[Color] = Tween(begin=begin, end=end)
    result_begin = tween.at(0.0)
    result_end = tween.at(1.0)
    assert result_begin.r == 0 and result_begin.g == 0 and result_begin.b == 0
    assert result_end.r == 255 and result_end.g == 128 and result_end.b == 64


def test_tween_edge_boundary_values() -> None:
    """``Tween[Edge].at(0)`` returns ``begin``; ``at(1)`` returns ``end``."""
    begin = Edge.all(0.0)
    end = Edge(top=10.0, right=20.0, bottom=30.0, left=40.0)
    tween: Tween[Edge] = Tween(begin=begin, end=end)
    assert tween.at(0.0) == begin
    assert tween.at(1.0) == end


# ---------------------------------------------------------------------------
# Register/unregister round-trip
# ---------------------------------------------------------------------------


async def test_register_then_unregister_leaves_clock_idle() -> None:
    """Registering and immediately unregistering leaves the clock inactive."""
    clock = {"now": 0.0}
    app: App[_State] = App(
        _State(),
        _view,
        apply_patches=lambda _p: None,
        time_source=lambda: clock["now"],
    )
    app.start()
    ctrl = AnimationController(duration_s=1.0, curve=Curve.LINEAR)
    app.register_animation(ctrl)
    assert ctrl in app._animations
    app.unregister_animation(ctrl)
    assert ctrl not in app._animations


async def test_tick_from_device_noop_when_no_animations() -> None:
    """``_tick_from_device`` is a no-op when no animation is registered."""
    clock = {"now": 0.0}
    app: App[_State] = App(
        _State(),
        _view,
        apply_patches=lambda _p: None,
        time_source=lambda: clock["now"],
    )
    app.start()
    # No animation registered — should not raise.
    app._tick_from_device()
    assert app._tick_scheduled is False
