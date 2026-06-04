"""Tests for the overlay layer: Scene, build_scene/diff_scene, App overlay API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tempestroid import (
    App,
    BottomSheet,
    Dialog,
    Insert,
    Menu,
    MenuItem,
    Patch,
    Popover,
    Reorder,
    Scene,
    Text,
    Toast,
    Tooltip,
    Update,
    build_scene,
    diff_scene,
)


@dataclass
class _State:
    label: str = "root"


def _view(app: App[_State]) -> Text:
    return Text(content=app.state.label)


# --- build_scene -----------------------------------------------------------


def test_build_scene_with_no_overlays_reduces_to_root() -> None:
    """A scene with no overlays carries the root tree and an empty layer."""
    scene = build_scene(Text(content="hi"), [])
    assert isinstance(scene, Scene)
    assert scene.root.type == "Text"
    assert scene.overlays == []


def test_build_scene_keys_overlays_by_id_and_records_barrier() -> None:
    """Each overlay node carries its id as key and a barrier prop."""
    scene = build_scene(
        Text(content="root"),
        [
            ("dlg-1", Dialog(title="Hi", children=[Text(content="body")]), True),
            ("toast-1", Toast(message="saved"), False),
        ],
    )
    assert [o.key for o in scene.overlays] == ["dlg-1", "toast-1"]
    assert scene.overlays[0].type == "Dialog"
    assert scene.overlays[0].props["barrier"] is True
    assert scene.overlays[1].props["barrier"] is False
    # The dialog's children survive into the overlay node.
    assert scene.overlays[0].children[0].props["content"] == "body"


# --- diff_scene ------------------------------------------------------------


def test_diff_scene_diffs_root_with_unchanged_paths() -> None:
    """The root tree diffs exactly like the bare diff: paths stay int-only."""
    old = build_scene(Text(content="a"), [])
    new = build_scene(Text(content="b"), [])
    patches = diff_scene(old, new)
    assert len(patches) == 1
    update = patches[0]
    assert isinstance(update, Update)
    assert update.path == ()
    assert update.set_props == {"content": "b"}


def test_diff_scene_overlay_add_emits_namespaced_insert() -> None:
    """Adding an overlay emits an Insert under the ('overlay',) prefix."""
    old = build_scene(Text(content="root"), [])
    new = build_scene(
        Text(content="root"), [("dlg", Dialog(title="t"), True)]
    )
    patches = diff_scene(old, new)
    inserts = [p for p in patches if isinstance(p, Insert)]
    assert len(inserts) == 1
    assert inserts[0].path == ("overlay",)
    assert inserts[0].index == 0
    assert inserts[0].node.type == "Dialog"
    assert inserts[0].node.key == "dlg"


def test_diff_scene_overlay_remove_emits_namespaced_remove() -> None:
    """Removing an overlay emits a Remove under the ('overlay',) prefix."""
    old = build_scene(
        Text(content="root"), [("dlg", Dialog(title="t"), True)]
    )
    new = build_scene(Text(content="root"), [])
    patches = diff_scene(old, new)
    removes = [p for p in patches if p.__class__.__name__ == "Remove"]
    assert len(removes) == 1
    assert removes[0].path == ("overlay",)


def test_diff_scene_overlay_reorder_keyed() -> None:
    """Reordering keyed overlays emits a single Reorder under the prefix."""
    a = ("a", Dialog(title="A"), True)
    b = ("b", Dialog(title="B"), True)
    old = build_scene(Text(content="root"), [a, b])
    new = build_scene(Text(content="root"), [b, a])
    patches = diff_scene(old, new)
    reorders = [p for p in patches if isinstance(p, Reorder)]
    assert len(reorders) == 1
    assert reorders[0].path == ("overlay",)
    assert reorders[0].order == [1, 0]


def test_diff_scene_matched_overlay_recurses_with_namespaced_update() -> None:
    """A matched overlay key recurses, emitting an Update at ('overlay', i)."""
    old = build_scene(
        Text(content="root"), [("dlg", Dialog(title="old"), True)]
    )
    new = build_scene(
        Text(content="root"), [("dlg", Dialog(title="new"), True)]
    )
    patches = diff_scene(old, new)
    updates = [p for p in patches if isinstance(p, Update) and p.path]
    assert len(updates) == 1
    assert updates[0].path == ("overlay", 0)
    assert updates[0].set_props["title"] == "new"


def test_diff_scene_identical_scenes_emit_no_patches() -> None:
    """No change anywhere → no patches."""
    scene = build_scene(Text(content="x"), [("d", Dialog(title="t"), True)])
    other = build_scene(Text(content="x"), [("d", Dialog(title="t"), True)])
    assert diff_scene(scene, other) == []


# --- App overlay API -------------------------------------------------------


async def _flush() -> None:
    """Let the coalesced rebuild run on the loop."""
    await asyncio.sleep(0)


async def test_show_dialog_pushes_overlay_and_returns_id() -> None:
    """show_dialog pushes a barrier overlay and returns its stable id."""
    captured: list[list[Patch]] = []
    app: App[_State] = App(_State(), _view, lambda p: captured.append(list(p)))
    app.start()
    overlay_id = app.show_dialog(Dialog(title="Hi"))
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert [o.key for o in scene.overlays] == [overlay_id]
    assert scene.overlays[0].props["barrier"] is True
    # The patch batch carried the namespaced overlay insert.
    inserts = [p for batch in captured for p in batch if isinstance(p, Insert)]
    assert any(p.path == ("overlay",) for p in inserts)


async def test_show_sheet_barrier_flag() -> None:
    """show_sheet defaults to a barrier and lowers to the overlay node prop."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    app.show_sheet(BottomSheet(), barrier=False)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays[0].props["barrier"] is False


async def test_show_menu_applies_anchor() -> None:
    """show_menu folds the anchor key into a menu that exposes one."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    items = [MenuItem(label="One", value="1")]
    app.show_menu(Menu(items=items), anchor="btn")
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays[0].props["anchor"] == "btn"


async def test_dismiss_removes_overlay_by_id() -> None:
    """dismiss removes only the named overlay and rebuilds."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    a = app.show_dialog(Dialog(title="A"))
    b = app.show_dialog(Dialog(title="B"))
    await _flush()
    app.dismiss(a)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert [o.key for o in scene.overlays] == [b]


async def test_dismiss_unknown_id_is_noop() -> None:
    """Dismissing an unknown id makes no change and schedules no rebuild."""
    captured: list[list[Patch]] = []
    app: App[_State] = App(_State(), _view, lambda p: captured.append(list(p)))
    app.start()
    captured.clear()
    app.dismiss("nope")
    await _flush()
    assert captured == []


async def test_toast_auto_expires_via_loop_call_later() -> None:
    """A toast auto-dismisses after its duration via loop.call_later."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    app.toast(Toast(message="saved", duration_s=0.01), duration_s=0.01)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert len(scene.overlays) == 1
    # Wait past the duration so the scheduled call_later fires.
    await asyncio.sleep(0.05)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays == []


async def test_overlays_stack_in_push_order() -> None:
    """Overlays keep their push order (ascending z-order)."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    first = app.show_dialog(Dialog(title="first"))
    second = app.show_sheet(BottomSheet())
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert [o.key for o in scene.overlays] == [first, second]


# --- Tooltip and Popover overlays (E2 completeness) --------------------------


async def test_show_menu_tooltip_uses_show_dialog_path() -> None:
    """Tooltip pushed via show_dialog has no barrier and records the message prop."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    app.show_dialog(Tooltip(message="help text"), barrier=False)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays[0].type == "Tooltip"
    assert scene.overlays[0].props["message"] == "help text"
    assert scene.overlays[0].props["barrier"] is False


async def test_show_dialog_with_popover_widget() -> None:
    """A Popover pushed via show_dialog records its props and is dismissible."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    ov_id = app.show_dialog(Popover(anchor="btn-1"), barrier=False)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays[0].type == "Popover"
    assert scene.overlays[0].props["anchor"] == "btn-1"
    # Dismiss removes it cleanly.
    app.dismiss(ov_id)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays == []


async def test_overlays_empty_list_before_any_push() -> None:
    """Before any overlay is pushed, current_tree has an empty overlays list."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays == []


async def test_multiple_dismiss_calls_clear_all_overlays() -> None:
    """Dismissing every overlay by id leaves the layer empty."""
    app: App[_State] = App(_State(), _view, lambda _p: None)
    app.start()
    ids = [app.show_dialog(Dialog(title=f"d{i}")) for i in range(3)]
    await _flush()
    for ov_id in ids:
        app.dismiss(ov_id)
    await _flush()
    scene = app.current_tree
    assert scene is not None
    assert scene.overlays == []


async def test_build_scene_empty_overlay_list_is_not_none() -> None:
    """Scene.overlays is [] (not None) for a root-only scene."""
    scene = build_scene(Text(content="x"), [])
    assert scene.overlays == []
    assert scene.overlays is not None


def test_diff_scene_both_identical_empty_scenes_no_patch() -> None:
    """Two empty scenes (no overlays, same root) produce zero patches."""
    a = build_scene(Text(content="same"), [])
    b = build_scene(Text(content="same"), [])
    assert diff_scene(a, b) == []
