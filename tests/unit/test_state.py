import asyncio
from dataclasses import dataclass

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
    node = app.start()
    assert node.type == "Text"
    assert node.props["content"] == "n=0"
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
