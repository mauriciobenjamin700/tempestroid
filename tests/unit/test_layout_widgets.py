"""Unit tests for the phase-E6 refined-layout surface.

Covers the new layout widgets (``Wrap`` / ``PageView`` / ``AspectRatio``), the
``PageChangeEvent`` boundary contract, the ``FlexWrap`` style field's Compose
translation, the ``Table`` / ``DataTable`` / ``CollapsingAppBar`` components
lowering to primitives, and the reconciler diffs for the new widget types.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tempestroid import (
    AspectRatio,
    CollapsingAppBar,
    DataTable,
    FlexWrap,
    PageChangeEvent,
    PageView,
    Style,
    Table,
    TableCell,
    TableRow,
    Text,
    Wrap,
    build,
    introspect,
    parse_event,
    to_compose,
)
from tempestroid.bridge import serialize_node
from tempestroid.core.introspection import WIDGET_TYPES
from tempestroid.core.reconciler import diff
from tempestroid.renderers.qt.style_translator import to_qss
from tempestroid.widgets.events import EventValidationError

# --- Wrap -------------------------------------------------------------------


def test_wrap_builds_and_exposes_children() -> None:
    """``Wrap`` builds to a ``Wrap`` node whose children are walkable."""
    wrap = Wrap(children=[Text(content="a"), Text(content="b")])
    assert [c.widget_type for c in wrap.child_nodes()] == ["Text", "Text"]
    node = build(wrap)
    assert node.type == "Wrap"
    assert len(node.children) == 2


def test_wrap_serializes_flex_wrap_into_style_spec() -> None:
    """A ``Wrap`` carrying ``flex_wrap`` serializes ``flexWrap`` in its style."""
    node = build(Wrap(style=Style(flex_wrap=FlexWrap.WRAP), children=[]))
    payload = serialize_node(node)
    assert payload["type"] == "Wrap"
    assert payload["props"]["style"]["flexWrap"] == "wrap"


def test_wrap_defaults_to_empty_children() -> None:
    """``Wrap`` defaults its children to an empty list, never ``None``."""
    assert Wrap().children == []
    assert Wrap().child_nodes() == []


# --- PageView ---------------------------------------------------------------


def test_page_view_event_schema_binds_on_page_change() -> None:
    """``PageView`` declares ``on_page_change`` → ``PageChangeEvent``."""
    assert PageView.event_schemas == {"on_page_change": PageChangeEvent}


def test_page_view_serializes_page_prop() -> None:
    """``PageView.page`` crosses the bridge as a plain int; pages are children."""
    view = PageView(page=2, children=[Text(content="p0"), Text(content="p1")])
    payload = serialize_node(build(view))
    assert payload["type"] == "PageView"
    assert payload["props"]["page"] == 2
    assert len(payload["children"]) == 2


def test_page_view_handler_token_present_when_wired() -> None:
    """A wired ``on_page_change`` handler serializes as a handler token."""

    def on_change(_event: PageChangeEvent) -> None:
        return None

    payload = serialize_node(build(PageView(on_page_change=on_change, children=[])))
    handler = payload["props"]["on_page_change"]
    assert handler["$handler"] == "root:on_page_change"
    assert handler["event"] == "PageChangeEvent"


# --- AspectRatio ------------------------------------------------------------


def test_aspect_ratio_builds_with_child() -> None:
    """``AspectRatio`` builds to a node carrying its ratio and single child."""
    node = build(AspectRatio(ratio=1.5, child=Text(content="x")))
    payload = serialize_node(node)
    assert payload["type"] == "AspectRatio"
    assert payload["props"]["ratio"] == 1.5
    assert len(payload["children"]) == 1


def test_aspect_ratio_rejects_non_positive_ratio() -> None:
    """``AspectRatio.ratio`` must be strictly positive."""
    with pytest.raises(ValueError):
        AspectRatio(ratio=0.0)


def test_aspect_ratio_without_child_has_no_children() -> None:
    """``AspectRatio`` with no child exposes no child nodes."""
    assert AspectRatio(ratio=2.0).child_nodes() == []


# --- PageChangeEvent --------------------------------------------------------


def test_parse_page_change_event_typed_roundtrip() -> None:
    """``parse_event`` validates a raw page-change payload into the typed event."""
    event = parse_event(PageChangeEvent, {"page": 3, "previous": 1})
    assert isinstance(event, PageChangeEvent)
    assert event.page == 3
    assert event.previous == 1


def test_parse_page_change_event_defaults_previous() -> None:
    """``previous`` defaults to 0 when omitted from the raw payload."""
    event = parse_event(PageChangeEvent, {"page": 5})
    assert event.previous == 0


def test_parse_page_change_event_invalid_raises_structured_error() -> None:
    """A non-integer ``page`` raises a structured ``EventValidationError``."""
    with pytest.raises(EventValidationError) as exc:
        parse_event(PageChangeEvent, {"page": "not-an-int"})
    assert exc.value.event_type is PageChangeEvent
    assert exc.value.errors


# --- FlexWrap → Compose -----------------------------------------------------


@pytest.mark.parametrize(
    "wrap,expected",
    [
        (FlexWrap.NOWRAP, "nowrap"),
        (FlexWrap.WRAP, "wrap"),
        (FlexWrap.WRAP_REVERSE, "wrapReverse"),
    ],
)
def test_flex_wrap_compose_spec(wrap: FlexWrap, expected: str) -> None:
    """Each ``FlexWrap`` member maps to the documented Compose-spec string."""
    spec = to_compose(Style(flex_wrap=wrap))
    assert spec["flexWrap"] == expected


def test_flex_wrap_absent_when_unset() -> None:
    """A style without ``flex_wrap`` emits no ``flexWrap`` key."""
    assert "flexWrap" not in to_compose(Style())


# --- introspection membership ----------------------------------------------


def test_new_widgets_in_widget_types() -> None:
    """The three new E6 layout widgets are registered in ``WIDGET_TYPES``."""
    names = {w.__name__ for w in WIDGET_TYPES}
    assert {"Wrap", "PageView", "AspectRatio"} <= names


def test_new_widgets_in_introspect() -> None:
    """The new widgets and event appear in the introspected contract."""
    catalog = introspect()
    for name in ("Wrap", "PageView", "AspectRatio"):
        assert name in catalog["widgets"]
    assert "PageChangeEvent" in catalog["events"]


# --- Table / DataTable components -------------------------------------------


def test_table_lowers_to_primitive_column() -> None:
    """``Table`` lowers to a primitive ``Column`` of rows of cells."""
    table = Table(
        headers=["Name", "Age"],
        rows=[
            TableRow(cells=[TableCell(content="Ana"), TableCell(content="30")]),
            TableRow(cells=[TableCell(content="Bo"), TableCell(content="25")]),
        ],
    )
    node = build(table)
    assert node.type == "Column"
    # 1 header row + 2 body rows.
    assert len(node.children) == 3
    assert all(row.type == "Row" for row in node.children)


def test_table_without_headers_omits_header_row() -> None:
    """A header-less ``Table`` lowers to only its body rows."""
    node = build(Table(rows=[TableRow(cells=[TableCell(content="x")])]))
    assert node.type == "Column"
    assert len(node.children) == 1


def test_data_table_lowers_to_primitives() -> None:
    """``DataTable`` lowers (via ``Table``) to a primitive ``Column``."""
    node = build(
        DataTable(columns=["A", "B"], rows=[["1", "2"], ["3", "4"]], sortable=True)
    )
    assert node.type == "Column"
    # header + two data rows.
    assert len(node.children) == 3


def test_data_table_serializes_without_callables_or_models() -> None:
    """A ``DataTable`` serializes to JSON-able primitives end to end."""
    payload = serialize_node(build(DataTable(columns=["A"], rows=[["1"]])))
    assert payload["type"] == "Column"
    # The header cell text reaches a Text leaf somewhere in the tree.
    assert payload["children"]


# --- CollapsingAppBar component ---------------------------------------------


def test_collapsing_app_bar_lowers_to_container() -> None:
    """``CollapsingAppBar`` lowers to a single primitive ``Container``."""
    node = build(CollapsingAppBar(title="Inbox"))
    assert node.type == "Container"


def test_collapsing_app_bar_height_tracks_scroll_offset() -> None:
    """The derived height eases from expanded to collapsed as the offset grows."""
    expanded = serialize_node(
        build(
            CollapsingAppBar(
                title="t", expanded_height=200, collapsed_height=56, scroll_offset=0
            )
        )
    )
    collapsed = serialize_node(
        build(
            CollapsingAppBar(
                title="t", expanded_height=200, collapsed_height=56, scroll_offset=500
            )
        )
    )
    assert expanded["props"]["style"]["height"] == 200.0
    # Fully scrolled past the collapse span clamps to the collapsed height.
    assert collapsed["props"]["style"]["height"] == 56.0


def test_collapsing_app_bar_intermediate_height() -> None:
    """``CollapsingAppBar`` derives a height linearly between extremes.

    A scroll_offset halfway through the collapse span must produce a height
    halfway between expanded and collapsed — the collapse math is pure Python
    in ``render()`` and must be renderer-independent.
    """
    bar = CollapsingAppBar(
        title="t", expanded_height=200.0, collapsed_height=56.0, scroll_offset=72.0
    )
    # span = 200 - 56 = 144; consumed = min(72, 144) = 72; height = 200 - 72 = 128
    payload = serialize_node(build(bar))
    assert payload["props"]["style"]["height"] == 128.0


# --- Reconciler diffs for E6 widgets ----------------------------------------


def test_wrap_child_update_diff() -> None:
    """Updating a child inside a ``Wrap`` produces a single ``Update`` patch."""
    from tempestroid.core.ir import Update

    w1 = Wrap(children=[Text(content="A"), Text(content="B")])
    w2 = Wrap(children=[Text(content="A"), Text(content="C")])
    patches = diff(build(w1), build(w2))
    update_patches = [p for p in patches if isinstance(p, Update)]
    assert update_patches, "expected an Update patch for the changed child"
    changed = update_patches[0]
    assert "content" in changed.set_props
    assert changed.set_props["content"] == "C"


def test_page_view_page_prop_diff_emits_update() -> None:
    """Changing ``PageView.page`` emits a single ``Update`` patch on the root.

    The reconciler must treat ``page`` as an ordinary prop update — no new IR
    kind, no special handling.
    """
    from tempestroid.core.ir import Update

    v1 = PageView(page=0, children=[Text(content="A")])
    v2 = PageView(page=1, children=[Text(content="A")])
    patches = diff(build(v1), build(v2))
    root_updates = [p for p in patches if isinstance(p, Update) and p.path == ()]
    assert len(root_updates) == 1, (
        "exactly one root Update expected when only the page prop changes"
    )
    assert root_updates[0].set_props["page"] == 1


def test_aspect_ratio_ratio_diff_emits_update() -> None:
    """Changing ``AspectRatio.ratio`` emits a single ``Update`` patch on the root."""
    from tempestroid.core.ir import Update

    a1 = AspectRatio(ratio=1.5, child=Text(content="x"))
    a2 = AspectRatio(ratio=2.0, child=Text(content="x"))
    patches = diff(build(a1), build(a2))
    root_updates = [p for p in patches if isinstance(p, Update) and p.path == ()]
    assert len(root_updates) == 1
    assert root_updates[0].set_props["ratio"] == 2.0


# --- Qt inertia for flex_wrap -----------------------------------------------


def test_flex_wrap_not_in_qss() -> None:
    """``Style.flex_wrap`` must not appear in the Qt QSS output (Qt is inert).

    The Qt translator does not react to ``flex_wrap`` — wrapping is realized by
    the custom ``_WrapWidget`` in the renderer, not by QSS. This test is the
    exact counterpart of the Compose-side test that asserts the field DOES appear
    in the spec. Both together pin the documented ``_COVERAGE["flex_wrap"] =
    (True, False)`` entry.
    """
    base_qss = to_qss(Style(), with_padding=True)
    for wrap_value in FlexWrap:
        qss = to_qss(Style(flex_wrap=wrap_value), with_padding=True)
        assert qss == base_qss, (
            f"FlexWrap.{wrap_value.name} changed the Qt QSS output to {qss!r}; "
            "flex_wrap must be Qt-inert per _COVERAGE['flex_wrap'] = (True, False)"
        )


# --- FlexWrap enum completeness ---------------------------------------------


def test_flex_wrap_enum_has_exactly_three_members() -> None:
    """``FlexWrap`` exposes exactly NOWRAP / WRAP / WRAP_REVERSE.

    A new member (e.g. ``INITIAL``) would require updating the Compose
    ``_FLEX_WRAP`` mapping — this test is the tripwire.
    """
    assert set(FlexWrap) == {FlexWrap.NOWRAP, FlexWrap.WRAP, FlexWrap.WRAP_REVERSE}, (
        "FlexWrap enum changed; update _FLEX_WRAP in compose/style_translator.py "
        "and regenerate the conformance golden"
    )


# --- EVENT_SCHEMAS completeness for E6 widgets ------------------------------


def test_wrap_and_aspect_ratio_absent_from_event_schemas() -> None:
    """``Wrap`` and ``AspectRatio`` have no event bindings and are absent from
    ``EVENT_SCHEMAS`` (they are structural containers, not interactive).

    This documents the intentional gap: adding an event to either widget
    requires updating both ``event_schemas`` on the class AND ``EVENT_SCHEMAS``
    in ``bridge/protocol.py``.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS

    assert "Wrap" not in EVENT_SCHEMAS, (
        "Wrap has no event_schemas; it must stay absent from EVENT_SCHEMAS "
        "until an actual event is added to the widget class"
    )
    assert "AspectRatio" not in EVENT_SCHEMAS, (
        "AspectRatio has no event_schemas; it must stay absent from EVENT_SCHEMAS "
        "until an actual event is added to the widget class"
    )


# --- Components NOT in WIDGET_TYPES -----------------------------------------


def test_components_absent_from_widget_types() -> None:
    """``Table``, ``DataTable``, and ``CollapsingAppBar`` are ``Component``s that
    lower to primitives — they must NOT appear in ``WIDGET_TYPES`` or
    ``introspect()['widgets']``.

    Components never cross the bridge as IR nodes; they are always expanded via
    ``render()`` before ``build()``. Including them in ``WIDGET_TYPES`` would
    misrepresent the on-wire contract.
    """
    widget_names = {w.__name__ for w in WIDGET_TYPES}
    for name in ("Table", "DataTable", "CollapsingAppBar"):
        assert name not in widget_names, (
            f"{name!r} is a Component and must not appear in WIDGET_TYPES; "
            "Components lower to primitives before reaching the wire"
        )

    catalog = introspect()
    for name in ("Table", "DataTable", "CollapsingAppBar"):
        assert name not in catalog["widgets"], (
            f"{name!r} is a Component and must not appear in introspect()['widgets']"
        )


# --- DataTable.sortable affordance ------------------------------------------


def test_data_table_sortable_appends_indicator_to_headers() -> None:
    """When ``sortable=True``, ``DataTable`` appends ``▾`` to each column header.

    The sort indicator is a pure-Python annotation; the renderers just display
    the text — no sort logic on the renderer side.
    """
    node = build(DataTable(columns=["Name", "Score"], rows=[], sortable=True))
    # The first child of the Column is the header Row.
    header_row = node.children[0]
    assert header_row.type == "Row"
    # Collect leaf Text contents.
    texts = [child.children[0].props["content"] for child in header_row.children]
    assert texts == ["Name ▾", "Score ▾"], (
        f"sortable header texts are {texts!r}; expected ['Name ▾', 'Score ▾']"
    )


def test_data_table_not_sortable_omits_indicator() -> None:
    """When ``sortable=False`` (default), column headers have no sort indicator."""
    node = build(DataTable(columns=["A", "B"], rows=[], sortable=False))
    header_row = node.children[0]
    texts = [child.children[0].props["content"] for child in header_row.children]
    assert texts == ["A", "B"]


# --- TableCell frozen -------------------------------------------------------


def test_table_cell_is_frozen() -> None:
    """``TableCell`` must be frozen (immutable) so it can be used safely in
    diffable IR trees.

    Mutating a ``TableCell`` after construction would silently invalidate any
    reconciler cache that holds a reference. Pydantic raises ``ValidationError``
    on attempted mutation when ``model_config = ConfigDict(frozen=True)``.
    """
    cell = TableCell(content="hello")
    with pytest.raises(ValidationError):
        cell.content = "world"  # type: ignore[misc]


def test_table_row_is_frozen() -> None:
    """``TableRow`` must be frozen — same rationale as ``TableCell``."""
    row = TableRow(cells=[TableCell(content="x")])
    with pytest.raises(ValidationError):
        row.style = Style()  # type: ignore[misc]


# --- Empty table edge cases -------------------------------------------------


def test_table_empty_rows_and_no_headers_is_empty_column() -> None:
    """An empty ``Table`` with no rows and no headers lowers to an empty
    ``Column`` — not a crash and not ``None``.
    """
    node = build(Table())
    assert node.type == "Column"
    assert node.children == []


def test_data_table_empty_builds_cleanly() -> None:
    """An empty ``DataTable`` (no columns, no rows) lowers without error."""
    node = build(DataTable())
    assert node.type == "Column"


# --- KeyboardAvoidingView (phase E8) ----------------------------------------


def test_keyboard_avoiding_view_builds_and_exposes_children() -> None:
    """``KeyboardAvoidingView`` builds to a node whose children are walkable."""
    from tempestroid import Input, KeyboardAvoidingView

    view = KeyboardAvoidingView(children=[Text(content="a"), Input()])
    assert [c.widget_type for c in view.child_nodes()] == ["Text", "Input"]
    node = build(view)
    assert node.type == "KeyboardAvoidingView"
    assert len(node.children) == 2


def test_keyboard_avoiding_view_in_introspect() -> None:
    """``KeyboardAvoidingView`` appears in the introspected widget catalog."""
    from tempestroid import KeyboardAvoidingView

    assert KeyboardAvoidingView.__name__ in introspect()["widgets"]


def test_keyboard_avoiding_view_child_update_diff() -> None:
    """Updating a child inside a ``KeyboardAvoidingView`` emits one ``Update``."""
    from tempestroid import KeyboardAvoidingView
    from tempestroid.core.ir import Update

    v1 = KeyboardAvoidingView(children=[Text(content="a")])
    v2 = KeyboardAvoidingView(children=[Text(content="b")])
    patches = diff(build(v1), build(v2))
    update_patches = [p for p in patches if isinstance(p, Update)]
    assert update_patches, "expected an Update patch for the changed child"


def test_keyboard_avoiding_view_child_insert_diff() -> None:
    """Adding a child to a ``KeyboardAvoidingView`` emits an ``Insert``."""
    from tempestroid import KeyboardAvoidingView
    from tempestroid.core.ir import Insert

    v1 = KeyboardAvoidingView(children=[Text(content="a")])
    v2 = KeyboardAvoidingView(children=[Text(content="a"), Text(content="b")])
    patches = diff(build(v1), build(v2))
    assert any(isinstance(p, Insert) for p in patches)


def test_keyboard_avoiding_view_serializes() -> None:
    """``KeyboardAvoidingView`` serializes to a JSON-able mount payload."""
    from tempestroid import Input, KeyboardAvoidingView

    payload = serialize_node(build(KeyboardAvoidingView(children=[Input()])))
    assert payload["type"] == "KeyboardAvoidingView"
    assert payload["children"][0]["type"] == "Input"
