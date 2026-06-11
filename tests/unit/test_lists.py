"""Unit tests for the virtualized list widgets and the window diff (E1a).

Coverage map
------------
* Build: LazyColumn/LazyRow/LazyGrid/SectionList/RefreshControl are leaves in the
  direct IR (no static children). ``item_builder`` survives as a live callable in
  ``node.props``; it is NOT serialized over the boundary.
* Diff: sliding and growing windows exercise ``_reconcile_keyed``; prop-only
  changes produce ``Update`` patches.
* Events: ``parse_event`` validates ScrollEvent/RefreshEvent/EndReachedEvent and
  raises a structured ``EventValidationError`` on bad payloads.
* Serialization: ``serialize_node`` drops ``item_builder``/``header_builder``; handler
  props become ``{"$handler": token, "event": EventName}`` dicts.
* Protocol: ``EVENT_SCHEMAS`` and ``event_type_for`` cover all five widgets.
* Introspection: ``introspect()`` lists all five widgets and three events.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from tempestroid import (
    DEFAULT_WINDOW_SIZE,
    App,
    Column,
    EndReachedEvent,
    Insert,
    LazyColumn,
    LazyGrid,
    LazyRow,
    Node,
    RefreshControl,
    RefreshEvent,
    Remove,
    Reorder,
    ScrollEvent,
    SectionHeader,
    SectionList,
    Text,
    Update,
    Widget,
    build,
    diff,
    parse_event,
    serialize_node,
)
from tempestroid.bridge.protocol import EVENT_SCHEMAS, event_type_for
from tempestroid.core.introspection import introspect
from tempestroid.widgets.events import EventValidationError

_LIST_WIDGETS = ("LazyColumn", "LazyRow", "LazyGrid", "SectionList", "RefreshControl")
_LIST_EVENTS = ("ScrollEvent", "RefreshEvent", "EndReachedEvent")

# --- helpers ----------------------------------------------------------------


def _materialize_window(
    item_builder: Callable[[int], Text],
    start: int,
    end: int,
) -> Node:
    """Build a LazyColumn IR node with a materialized, keyed window.

    Mirrors what the renderer/App does: only items in ``[start, end)`` are built
    into ``children``, each keyed by its absolute index, so a sliding window is a
    keyed diff. ``item_count`` and ``window`` ride along as props.

    Args:
        item_builder: The factory building each item widget.
        start: The first visible index (inclusive).
        end: The one-past-last visible index (exclusive).

    Returns:
        The list node with the windowed children attached.
    """
    children = [
        build(item_builder(index).model_copy(update={"key": str(index)}))
        for index in range(start, end)
    ]
    return Node(
        type="LazyColumn",
        key=None,
        props={"item_count": 100, "window": [start, end]},
        children=children,
    )


def _item(index: int) -> Text:
    """Build the item widget for ``index``.

    Args:
        index: The item index.

    Returns:
        A text widget showing the index.
    """
    return Text(content=str(index))


# --- build: virtual widgets carry no static children ------------------------


def test_lazy_column_materializes_initial_window_on_build():
    """build() materializes the default initial window (not all item_count)."""
    node = build(LazyColumn(item_count=100, item_builder=_item))
    assert node.type == "LazyColumn"
    # The default window is [0, DEFAULT_WINDOW_SIZE) — content on first mount,
    # but never all 100 items (virtualization preserved).
    assert len(node.children) == DEFAULT_WINDOW_SIZE
    expected_keys = [str(i) for i in range(DEFAULT_WINDOW_SIZE)]
    assert [c.key for c in node.children] == expected_keys
    assert node.props["item_count"] == 100
    assert node.props["window_size"] == DEFAULT_WINDOW_SIZE
    assert node.props["end_reached_threshold"] == 0.8
    # item_builder is a live prop on the node (renderer calls it directly).
    assert callable(node.props["item_builder"])


def test_lazy_column_window_clamps_to_item_count():
    """A short list materializes only item_count items, not window_size."""
    node = build(LazyColumn(item_count=3, item_builder=_item))
    assert len(node.children) == 3
    assert [c.key for c in node.children] == ["0", "1", "2"]


def test_lazy_column_explicit_window_materializes_that_slice():
    """An explicit window field materializes exactly that slice, keyed absolutely."""
    node = build(LazyColumn(item_count=100, item_builder=_item, window=(5, 12)))
    assert [c.key for c in node.children] == [str(i) for i in range(5, 12)]
    assert node.props["window"] == (5, 12)


def test_lazy_column_defaults():
    widget = LazyColumn(item_count=10, item_builder=_item)
    assert widget.refreshing is False
    assert widget.end_reached_threshold == 0.8
    assert widget.on_scroll is None


def test_materialized_window_has_exactly_window_children_keyed():
    node = _materialize_window(_item, 0, 10)
    assert len(node.children) == 10
    assert [c.key for c in node.children] == [str(i) for i in range(10)]
    assert [c.props["content"] for c in node.children] == [str(i) for i in range(10)]


# --- diff: sliding the visible window ---------------------------------------


def test_window_slide_emits_remove_reorder_insert():
    old = _materialize_window(_item, 0, 10)
    new = _materialize_window(_item, 5, 15)
    patches = diff(old, new)

    removes = [p for p in patches if isinstance(p, Remove)]
    reorders = [p for p in patches if isinstance(p, Reorder)]
    inserts = [p for p in patches if isinstance(p, Insert)]

    # Keys "0".."4" left the window -> 5 removes, descending index.
    assert [p.index for p in removes] == [4, 3, 2, 1, 0]
    # Survivors "5".."9" keep their relative order -> at most one Reorder (no-op
    # here because they stay contiguous after the removals).
    assert len(reorders) <= 1
    # Keys "10".."14" entered -> 5 inserts at ascending final indices.
    assert [p.index for p in inserts] == [5, 6, 7, 8, 9]
    assert [p.node.key for p in inserts] == ["10", "11", "12", "13", "14"]


def test_window_grow_appends_only_new_items():
    old = _materialize_window(_item, 0, 10)
    new = _materialize_window(_item, 0, 15)
    patches = diff(old, new)
    inserts = [p for p in patches if isinstance(p, Insert)]
    # The five new items are appended; surviving items emit no child patches.
    assert [p.index for p in inserts] == [10, 11, 12, 13, 14]
    assert all(isinstance(p, (Insert, Update)) for p in patches)
    # The window prop changed [0,10] -> [0,15], so exactly one root Update fires.
    updates = [p for p in patches if isinstance(p, Update)]
    assert len(updates) == 1
    assert updates[0].set_props["window"] == [0, 15]


def test_item_count_change_emits_update():
    old = _materialize_window(_item, 0, 10)
    new = Node(
        type="LazyColumn",
        key=None,
        props={"item_count": 200, "window": [0, 10]},
        children=old.children,
    )
    patches = diff(old, new)
    updates = [p for p in patches if isinstance(p, Update)]
    assert len(updates) == 1
    assert updates[0].set_props["item_count"] == 200


# --- event contract ---------------------------------------------------------


def test_parse_scroll_event():
    event = parse_event(ScrollEvent, {"offset": 120.5, "direction": "vertical"})
    assert event.offset == 120.5
    assert event.direction == "vertical"


def test_parse_refresh_event():
    assert parse_event(RefreshEvent, {}) == RefreshEvent()


def test_parse_end_reached_event():
    assert parse_event(EndReachedEvent, {}) == EndReachedEvent()


def test_events_are_frozen():
    event = ScrollEvent(offset=1.0, direction="vertical")
    with pytest.raises(ValidationError):
        event.offset = 2.0  # type: ignore[misc]


def test_event_schemas_per_widget():
    assert LazyColumn.event_schemas == {
        "on_scroll": ScrollEvent,
        "on_refresh": RefreshEvent,
        "on_end_reached": EndReachedEvent,
    }
    assert LazyRow.event_schemas == LazyColumn.event_schemas
    assert LazyGrid.event_schemas == {
        "on_scroll": ScrollEvent,
        "on_end_reached": EndReachedEvent,
    }
    assert SectionList.event_schemas == LazyGrid.event_schemas
    assert RefreshControl.event_schemas == {"on_refresh": RefreshEvent}


def test_event_schemas_registered_in_protocol():
    for widget in _LIST_WIDGETS:
        assert widget in EVENT_SCHEMAS
    assert event_type_for("LazyColumn", "on_scroll") is ScrollEvent
    assert event_type_for("RefreshControl", "on_refresh") is RefreshEvent
    assert event_type_for("LazyGrid", "on_end_reached") is EndReachedEvent


# --- serialization: builders never cross the boundary -----------------------


def test_item_builder_dropped_from_serialized_node():
    node = build(LazyColumn(item_count=5, item_builder=_item))
    props = serialize_node(node)["props"]
    assert "item_builder" not in props
    assert props["item_count"] == 5


def test_section_builders_dropped_from_serialized_node():
    import json

    node = Node(
        type="SectionList",
        key=None,
        props={
            "sections": [
                SectionHeader(
                    title="A",
                    item_count=3,
                    item_builder=_item,
                    header_builder=lambda: Text(content="A"),
                )
            ],
            "end_reached_threshold": 0.8,
        },
        children=[],
    )
    serialized = serialize_node(node)
    props = serialized["props"]
    assert "item_builder" not in props
    assert "header_builder" not in props
    # sections cross as JSON-able metadata (title + item_count), not the raw
    # SectionHeader models that carry the Python builders.
    assert props["sections"] == [{"title": "A", "item_count": 3}]
    # The whole serialized node must actually survive json.dumps — the bridge
    # boundary JSON-encodes it. (Regression: SectionHeader models leaked here and
    # blew up json.dumps even though "item_builder" was absent at the top level.)
    json.dumps(serialized)


# --- introspection ----------------------------------------------------------


def test_new_widgets_and_events_in_introspect():
    contract = introspect()
    for widget in _LIST_WIDGETS:
        assert widget in contract["widgets"]
    for event in _LIST_EVENTS:
        assert event in contract["events"]


def test_introspect_widget_event_mapping_is_accurate():
    """Each widget's event map in introspect() matches its event_schemas classvar."""
    contract = introspect()
    lazy_col = contract["widgets"]["LazyColumn"]["events"]
    assert lazy_col == {
        "on_scroll": "ScrollEvent",
        "on_refresh": "RefreshEvent",
        "on_end_reached": "EndReachedEvent",
    }
    lazy_grid = contract["widgets"]["LazyGrid"]["events"]
    assert lazy_grid == {
        "on_scroll": "ScrollEvent",
        "on_end_reached": "EndReachedEvent",
    }
    assert contract["widgets"]["RefreshControl"]["events"] == {
        "on_refresh": "RefreshEvent",
    }


# --- additional widget builds and defaults ----------------------------------


def test_lazy_row_materializes_initial_window():
    node = build(LazyRow(item_count=50, item_builder=_item))
    assert node.type == "LazyRow"
    assert len(node.children) == DEFAULT_WINDOW_SIZE
    assert node.props["item_count"] == 50
    assert node.props["end_reached_threshold"] == 0.8
    assert node.props["refreshing"] is False
    assert callable(node.props["item_builder"])


def test_lazy_row_defaults():
    widget = LazyRow(item_count=20, item_builder=_item)
    assert widget.on_scroll is None
    assert widget.on_refresh is None
    assert widget.on_end_reached is None


def test_lazy_grid_materializes_initial_window():
    node = build(LazyGrid(item_count=100, item_builder=_item, columns=3))
    assert node.type == "LazyGrid"
    assert len(node.children) == DEFAULT_WINDOW_SIZE
    assert node.props["item_count"] == 100
    assert node.props["columns"] == 3
    assert node.props["end_reached_threshold"] == 0.8
    # LazyGrid has no on_refresh
    assert "on_refresh" not in node.props or node.props.get("on_refresh") is None


def test_lazy_grid_defaults():
    widget = LazyGrid(item_count=10, item_builder=_item)
    assert widget.columns == 2
    assert widget.on_scroll is None
    assert widget.on_end_reached is None


def test_section_list_build_is_a_leaf_with_empty_sections():
    """Empty SectionList builds cleanly as a leaf — empty list, not None."""
    node = build(SectionList())
    assert node.type == "SectionList"
    assert node.children == []
    # sections may be stored as a list of objects; serialization handles them
    assert node.props["end_reached_threshold"] == 0.8


def test_section_list_with_sections():
    sections = [
        SectionHeader(
            title="A",
            item_count=3,
            item_builder=_item,
            header_builder=lambda: Text(content="A"),
        ),
        SectionHeader(
            title="B",
            item_count=5,
            item_builder=_item,
            header_builder=lambda: Text(content="B"),
        ),
    ]
    widget = SectionList(sections=sections)
    node = build(widget)
    assert node.type == "SectionList"
    # Each section materializes its header + its (clamped) item window: A has 3
    # items, B has 5 — both under DEFAULT_WINDOW_SIZE, so all items show.
    # children = (header + 3 items) + (header + 5 items) = 10.
    assert len(node.children) == 10
    keys = [c.key for c in node.children]
    assert keys[0] == "sec:A:header"
    assert "sec:A:0" in keys
    assert "sec:B:header" in keys
    assert "sec:B:4" in keys
    # sections survive in props as Python objects (not serialized here)
    assert len(node.props["sections"]) == 2


def test_refresh_control_build_defaults():
    node = build(RefreshControl())
    assert node.type == "RefreshControl"
    assert node.children == []
    assert node.props["refreshing"] is False


def test_refresh_control_refreshing_flag():
    node = build(RefreshControl(refreshing=True))
    assert node.props["refreshing"] is True


# --- SectionHeader immutability ---------------------------------------------


def test_section_header_is_frozen():
    header = SectionHeader(
        title="X",
        item_count=1,
        item_builder=_item,
        header_builder=lambda: Text(content="X"),
    )
    with pytest.raises((TypeError, ValidationError)):
        header.title = "Y"  # type: ignore[misc]


# --- parse_event: error path ------------------------------------------------


def test_parse_scroll_event_missing_required_field_raises_structured_error():
    """Omitting a required field yields EventValidationError with field errors."""
    with pytest.raises(EventValidationError) as exc_info:
        parse_event(ScrollEvent, {"offset": 10.0})  # direction missing
    err = exc_info.value
    assert err.event_type is ScrollEvent
    # errors is a list of dicts with at least a 'loc' key
    assert isinstance(err.errors, list) and len(err.errors) > 0
    locs = [tuple(e["loc"]) for e in err.errors]
    assert ("direction",) in locs


def test_parse_scroll_event_wrong_type_raises_structured_error():
    """A payload with the wrong value type raises EventValidationError."""
    with pytest.raises(EventValidationError) as exc_info:
        parse_event(ScrollEvent, {"offset": "not-a-number", "direction": "vertical"})
    assert exc_info.value.event_type is ScrollEvent
    assert exc_info.value.errors


def test_parse_refresh_event_ignores_extra_fields():
    """Extra payload fields are silently ignored (Pydantic default)."""
    event = parse_event(RefreshEvent, {"extra": "junk"})
    assert event == RefreshEvent()


def test_parse_end_reached_event_ignores_extra_fields():
    event = parse_event(EndReachedEvent, {"extra": "junk"})
    assert event == EndReachedEvent()


def test_scroll_event_horizontal():
    event = parse_event(ScrollEvent, {"offset": 55.0, "direction": "horizontal"})
    assert event.direction == "horizontal"
    assert event.offset == 55.0


# --- serialization: handler props become tokens ----------------------------


def _on_scroll_handler(event: ScrollEvent) -> None:
    """Stable handler for serialization tests."""


def _on_refresh_handler() -> None:
    """Stable zero-arg handler for serialization tests."""


def _on_end_reached_handler() -> None:
    """Stable zero-arg handler for end-reached serialization tests."""


def test_handler_serialized_as_token_with_event_name():
    """on_scroll handler → {"$handler": token, "event": "ScrollEvent"}."""
    node = build(
        LazyColumn(item_count=5, item_builder=_item, on_scroll=_on_scroll_handler)
    )
    serialized = serialize_node(node)
    on_scroll_val = serialized["props"].get("on_scroll")
    assert on_scroll_val is not None, "on_scroll should be present in serialized props"
    assert isinstance(on_scroll_val, dict)
    assert "$handler" in on_scroll_val
    assert on_scroll_val["event"] == "ScrollEvent"


def test_on_refresh_handler_serialized_with_event_name():
    node = build(
        LazyColumn(item_count=5, item_builder=_item, on_refresh=_on_refresh_handler)
    )
    serialized = serialize_node(node)
    on_refresh_val = serialized["props"].get("on_refresh")
    assert on_refresh_val is not None
    assert on_refresh_val["event"] == "RefreshEvent"


def test_on_end_reached_handler_serialized_with_event_name():
    node = build(
        LazyGrid(
            item_count=10, item_builder=_item, on_end_reached=_on_end_reached_handler
        )
    )
    serialized = serialize_node(node)
    val = serialized["props"].get("on_end_reached")
    assert val is not None
    assert val["event"] == "EndReachedEvent"


def test_serialized_node_contains_end_reached_threshold():
    node = build(
        LazyColumn(item_count=5, item_builder=_item, end_reached_threshold=0.9)
    )
    props = serialize_node(node)["props"]
    assert props["end_reached_threshold"] == 0.9


def test_lazy_grid_item_builder_dropped_from_serialized_node():
    node = build(LazyGrid(item_count=20, item_builder=_item))
    props = serialize_node(node)["props"]
    assert "item_builder" not in props
    assert props["item_count"] == 20


def test_refresh_control_serialized_no_builder():
    node = build(RefreshControl(refreshing=True))
    props = serialize_node(node)["props"]
    assert "item_builder" not in props
    assert "header_builder" not in props
    assert props["refreshing"] is True


# --- event_schemas: full widget coverage ------------------------------------


def test_lazy_column_event_schemas_keys():
    assert set(LazyColumn.event_schemas.keys()) == {
        "on_scroll",
        "on_refresh",
        "on_end_reached",
    }


def test_lazy_row_event_schemas_keys():
    assert set(LazyRow.event_schemas.keys()) == {
        "on_scroll",
        "on_refresh",
        "on_end_reached",
    }


def test_lazy_grid_event_schemas_keys():
    assert set(LazyGrid.event_schemas.keys()) == {"on_scroll", "on_end_reached"}
    assert "on_refresh" not in LazyGrid.event_schemas


def test_section_list_event_schemas_keys():
    assert set(SectionList.event_schemas.keys()) == {"on_scroll", "on_end_reached"}
    assert "on_refresh" not in SectionList.event_schemas


def test_refresh_control_event_schemas_keys():
    assert set(RefreshControl.event_schemas.keys()) == {"on_refresh"}
    assert "on_scroll" not in RefreshControl.event_schemas
    assert "on_end_reached" not in RefreshControl.event_schemas


# --- protocol: full event_type_for coverage ---------------------------------


def test_event_type_for_lazy_row_on_scroll():
    assert event_type_for("LazyRow", "on_scroll") is ScrollEvent


def test_event_type_for_lazy_row_on_refresh():
    assert event_type_for("LazyRow", "on_refresh") is RefreshEvent


def test_event_type_for_lazy_row_on_end_reached():
    assert event_type_for("LazyRow", "on_end_reached") is EndReachedEvent


def test_event_type_for_section_list_on_scroll():
    assert event_type_for("SectionList", "on_scroll") is ScrollEvent


def test_event_type_for_section_list_on_end_reached():
    assert event_type_for("SectionList", "on_end_reached") is EndReachedEvent


def test_event_type_for_lazy_grid_no_refresh():
    """LazyGrid does not emit RefreshEvent — event_type_for returns None."""
    assert event_type_for("LazyGrid", "on_refresh") is None


def test_event_type_for_unknown_widget_returns_none():
    assert event_type_for("NonExistent", "on_scroll") is None


def test_event_schemas_dict_has_all_five_widgets():
    for widget_name in _LIST_WIDGETS:
        assert widget_name in EVENT_SCHEMAS, (
            f"{widget_name!r} missing from EVENT_SCHEMAS"
        )


# --- window diff: edge cases ------------------------------------------------


def test_window_shrink_removes_tail_items():
    """Shrinking the window [0,10] -> [0,5] removes tail items (descending index)."""
    old = _materialize_window(_item, 0, 10)
    new = _materialize_window(_item, 0, 5)
    patches = diff(old, new)

    removes = [p for p in patches if isinstance(p, Remove)]
    inserts = [p for p in patches if isinstance(p, Insert)]

    # Items 5..9 leave the window — removed descending.
    assert [p.index for p in removes] == [9, 8, 7, 6, 5]
    assert inserts == []

    # The window prop changes [0,10] -> [0,5] → one Update.
    updates = [p for p in patches if isinstance(p, Update)]
    assert len(updates) == 1
    assert updates[0].set_props["window"] == [0, 5]


def test_empty_window_diff_adds_all_items():
    """Diff from an empty window to a 5-item window inserts all items."""
    empty = Node(
        type="LazyColumn",
        key=None,
        props={"item_count": 100, "window": [0, 0]},
        children=[],
    )
    full = _materialize_window(_item, 0, 5)
    patches = diff(empty, full)

    inserts = [p for p in patches if isinstance(p, Insert)]
    removes = [p for p in patches if isinstance(p, Remove)]

    assert removes == []
    assert [p.index for p in inserts] == [0, 1, 2, 3, 4]
    assert [p.node.key for p in inserts] == ["0", "1", "2", "3", "4"]


# --- App: initial window materialization + scroll-driven slide --------------


def _lists_view(app: App[None]) -> Widget:
    """A view with a keyed LazyColumn (10k items) and a keyed SectionList.

    Args:
        app: The running app (unused — the demo is stateless here).

    Returns:
        A column holding the two virtualized lists.
    """
    sections = [
        SectionHeader(
            title="A",
            item_count=100,
            item_builder=_item,
            header_builder=lambda: Text(content="A"),
        ),
    ]
    return Column(
        children=[
            LazyColumn(key="feed", item_count=10_000, item_builder=_item),
            SectionList(key="grouped", sections=sections),
        ]
    )


def test_app_mount_materializes_initial_window_without_materializing_all():
    """App.start materializes a bounded initial window for both list kinds."""
    app: App[None] = App(None, _lists_view, lambda _patches: None)
    root = app.start().root
    lazy, section = root.children[0], root.children[1]

    # LazyColumn: content on first mount, but bounded — never all 10k items.
    assert lazy.type == "LazyColumn"
    assert len(lazy.children) == DEFAULT_WINDOW_SIZE
    assert len(lazy.children) < 10_000
    assert [c.key for c in lazy.children[:3]] == ["0", "1", "2"]

    # SectionList: header + a bounded item window for the section.
    assert section.type == "SectionList"
    assert len(section.children) == DEFAULT_WINDOW_SIZE + 1  # header + window
    assert section.children[0].key == "sec:A:header"
    assert section.children[1].key == "sec:A:0"


async def test_slide_window_slides_the_lazy_column_via_keyed_diff():
    """App.slide_window slides the window; the diff is a minimal keyed patch set."""
    import asyncio

    captured: list[list[object]] = []
    app: App[None] = App(None, _lists_view, lambda p: captured.append(list(p)))
    app.start()

    # Slide the feed window [0,20] -> [10,30] and flush the coalesced rebuild.
    app.slide_window("feed", 10, 30)
    await asyncio.sleep(0)

    assert len(captured) == 1
    patches = captured[0]
    inserts = [p for p in patches if isinstance(p, Insert)]
    removes = [p for p in patches if isinstance(p, Remove)]
    # 10 keys (0..9) leave, 10 keys (20..29) enter — minimal, not a full rebuild.
    assert len(removes) == 10
    assert {p.node.key for p in inserts} == {str(i) for i in range(20, 30)}
    # The list node still carries a bounded window after the slide.
    feed = app.current_tree.root.children[0]  # type: ignore[union-attr]
    assert [c.key for c in feed.children] == [str(i) for i in range(10, 30)]


async def test_slide_section_window_slides_one_section():
    """App.slide_section_window slides a single SectionList section's window."""
    import asyncio

    app: App[None] = App(None, _lists_view, lambda _patches: None)
    app.start()

    app.slide_section_window("grouped", "A", 50, 60)
    await asyncio.sleep(0)

    section = app.current_tree.root.children[1]  # type: ignore[union-attr]
    keys = [c.key for c in section.children]
    assert keys[0] == "sec:A:header"
    assert keys[1:] == [f"sec:A:{i}" for i in range(50, 60)]


def test_serialized_materialized_list_node_survives_json_dumps():
    """A materialized list node round-trips through serialize_node + json.dumps."""
    import json

    app: App[None] = App(None, _lists_view, lambda _patches: None)
    root = app.start().root
    serialized = serialize_node(root)
    # The materialized window children cross as real serialized nodes...
    feed = serialized["children"][0]
    assert feed["type"] == "LazyColumn"
    assert len(feed["children"]) == DEFAULT_WINDOW_SIZE
    assert "item_builder" not in feed["props"]
    assert feed["props"]["item_count"] == 10_000
    assert feed["props"]["window_size"] == DEFAULT_WINDOW_SIZE
    # ...and the whole tree is JSON-encodable (the bridge boundary requires it).
    json.dumps(serialized)


async def test_window_tuple_serializes_as_json_array():
    """A slid window (start, end) tuple crosses the boundary as a 2-element list."""
    import asyncio

    app: App[None] = App(None, _lists_view, lambda _patches: None)
    app.start()
    app.slide_window("feed", 5, 25)
    await asyncio.sleep(0)

    feed = app.current_tree.root.children[0]  # type: ignore[union-attr]
    props = serialize_node(feed)["props"]
    # JSON has no tuple — the window crosses as [start, end].
    assert props["window"] == [5, 25]
    assert isinstance(props["window"], list)
