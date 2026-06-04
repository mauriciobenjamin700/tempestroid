import asyncio
from dataclasses import dataclass

import pytest

from tempestroid import App, Text, Update, Widget


@dataclass
class Counter:
    value: int = 0


def _view(app: "App[Counter]") -> Widget:
    return Text(content=f"n={app.state.value}")


async def test_start_returns_initial_node():
    captured: list[list[object]] = []
    app: App[Counter] = App(
        Counter(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    scene = app.start()
    assert scene.root.type == "Text"
    assert scene.root.props["content"] == "n=0"
    assert scene.overlays == []
    assert captured == []


async def test_set_state_triggers_rebuild_and_patch():
    captured: list[list[object]] = []
    app: App[Counter] = App(
        Counter(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    app.set_state(lambda s: setattr(s, "value", 1))
    await asyncio.sleep(0)
    assert len(captured) == 1
    patch = captured[0][0]
    assert isinstance(patch, Update)
    assert patch.set_props == {"content": "n=1"}


async def test_multiple_set_state_in_one_tick_coalesce():
    captured: list[list[object]] = []
    app: App[Counter] = App(
        Counter(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    app.set_state(lambda s: setattr(s, "value", 1))
    app.set_state(lambda s: setattr(s, "value", 2))
    app.set_state(lambda s: setattr(s, "value", 3))
    await asyncio.sleep(0)
    # one rebuild, one apply, reflecting only the final state
    assert len(captured) == 1
    patch = captured[0][0]
    assert isinstance(patch, Update)
    assert patch.set_props == {"content": "n=3"}


async def test_no_visible_change_emits_no_patches():
    captured: list[list[object]] = []
    app: App[Counter] = App(
        Counter(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    app.set_state()  # request a rebuild without mutating anything
    await asyncio.sleep(0)
    assert captured == []


def _view_b(app: "App[Counter]") -> Widget:
    return Text(content=f"b={app.state.value}")


def _view_bad(app: "App[Counter]") -> Widget:
    return Text(content=f"x={app.state.missing}")  # type: ignore[attr-defined]


def test_swap_view_preserves_state_and_diffs():
    captured: list[list[object]] = []
    app: App[Counter] = App(
        Counter(value=7), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    patches = app.swap_view(_view_b)
    # State object is untouched; the new view diffs against the live tree.
    assert app.state.value == 7
    assert len(patches) == 1
    assert isinstance(patches[0], Update)
    assert patches[0].set_props == {"content": "b=7"}


def test_swap_view_rolls_back_on_incompatible_view():
    captured: list[list[object]] = []
    app: App[Counter] = App(
        Counter(value=3), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    captured.clear()
    with pytest.raises(AttributeError):
        app.swap_view(_view_bad)
    # The failed swap is rolled back: the old view still renders correctly.
    assert app.current_tree is not None
    assert app.current_tree.root.props["content"] == "n=3"
    assert captured == []  # nothing applied on failure


def test_swap_view_before_start_raises():
    app: App[Counter] = App(Counter(), _view, apply_patches=lambda _p: None)
    with pytest.raises(RuntimeError):
        app.swap_view(_view_b)
