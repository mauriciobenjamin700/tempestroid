# Virtualized-list tests reach into the renderer's private scroll-area classes
# to assert their window/sticky behaviour — internal by design.
# pyright: reportPrivateUsage=false
import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateEdit,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from tempestroid import (
    Button,
    Checkbox,
    Column,
    Container,
    DatePicker,
    EndReachedEvent,
    FilePicker,
    Input,
    LazyColumn,
    LazyGrid,
    RefreshControl,
    Row,
    ScrollEvent,
    SectionHeader,
    SectionList,
    Text,
    build,
    diff,
)
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.renderer import (
    _LazyGridArea,
    _LazyScrollArea,
)

pytestmark = pytest.mark.usefixtures("qapp")


def _labels(widget: QWidget) -> list[str]:
    """Collect the text of every QLabel under a widget, depth-first."""
    return [child.text() for child in widget.findChildren(QLabel)]


def _ordered_labels(container: QWidget) -> list[str]:
    """Return QLabel texts in visual (layout) order for a container widget."""
    layout = container.layout()
    assert layout is not None
    out: list[str] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        assert item is not None
        child = item.widget()
        if isinstance(child, QLabel):
            out.append(child.text())
    return out


def test_mount_builds_widget_tree():
    renderer = QtRenderer()
    host = renderer.mount(build(Column(children=[Text(content="hello")])))
    assert isinstance(host, QWidget)
    assert _labels(host) == ["hello"]


def test_mount_button_label():
    renderer = QtRenderer()
    renderer.mount(build(Button(label="Tap me")))
    buttons = renderer.root_widget.findChildren(QPushButton)
    # the root itself is the button
    assert isinstance(renderer.root_widget, QPushButton)
    assert renderer.root_widget.text() == "Tap me"
    assert buttons == []


def test_update_changes_label_text():
    renderer = QtRenderer()
    old = build(Text(content="a"))
    renderer.mount(old)
    new = build(Text(content="b"))
    renderer.apply(diff(old, new))
    assert isinstance(renderer.root_widget, QLabel)
    assert renderer.root_widget.text() == "b"


def test_insert_adds_child_widget():
    renderer = QtRenderer()
    old = build(Column(children=[Text(content="a")]))
    renderer.mount(old)
    new = build(Column(children=[Text(content="a"), Text(content="b")]))
    renderer.apply(diff(old, new))
    assert _ordered_labels(renderer.root_widget) == ["a", "b"]


def test_remove_drops_child_widget():
    renderer = QtRenderer()
    old = build(Column(children=[Text(content="a"), Text(content="b")]))
    renderer.mount(old)
    new = build(Column(children=[Text(content="a")]))
    renderer.apply(diff(old, new))
    assert _ordered_labels(renderer.root_widget) == ["a"]


def test_replace_swaps_widget_type():
    renderer = QtRenderer()
    old = build(Column(children=[Text(content="a")]))
    renderer.mount(old)
    new = build(Column(children=[Button(label="a")]))
    renderer.apply(diff(old, new))
    assert renderer.root_widget.findChildren(QPushButton)
    assert _labels(renderer.root_widget) == []


def test_root_replace_swaps_root():
    renderer = QtRenderer()
    old = build(Text(content="a"))
    renderer.mount(old)
    new = build(Button(label="now a button"))
    renderer.apply(diff(old, new))
    assert isinstance(renderer.root_widget, QPushButton)
    assert renderer.root_widget.text() == "now a button"


def test_reorder_changes_visual_order():
    renderer = QtRenderer()
    old = build(
        Column(children=[Text(content="a", key="a"), Text(content="b", key="b")])
    )
    renderer.mount(old)
    new = build(
        Column(children=[Text(content="b", key="b"), Text(content="a", key="a")])
    )
    patches = diff(old, new)
    renderer.apply(patches)
    assert _ordered_labels(renderer.root_widget) == ["b", "a"]


def test_keyed_mixed_diff_applies_end_to_end():
    # The keyed diff (remove + reorder + insert in one pass) must compose under
    # sequential patch application in the real renderer: old -> new exactly.
    renderer = QtRenderer()
    old = build(
        Column(
            children=[
                Text(content="a", key="a"),
                Text(content="b", key="b"),
                Text(content="c", key="c"),
            ]
        )
    )
    renderer.mount(old)
    new = build(
        Column(
            children=[
                Text(content="c", key="c"),
                Text(content="a2", key="a"),
                Text(content="d", key="d"),
            ]
        )
    )
    renderer.apply(diff(old, new))
    # "b" gone, "c"/"a" reordered, "d" inserted, "a" updated to "a2".
    assert _ordered_labels(renderer.root_widget) == ["c", "a2", "d"]


def test_button_click_invokes_sync_handler():
    clicks: list[int] = []
    renderer = QtRenderer()
    renderer.mount(build(Button(label="x", on_click=lambda: clicks.append(1))))
    assert isinstance(renderer.root_widget, QPushButton)
    renderer.root_widget.click()
    assert clicks == [1]


def test_update_rebinds_handler():
    calls: list[str] = []
    renderer = QtRenderer()
    old = Button(label="x", on_click=lambda: calls.append("old"))
    renderer.mount(build(old))
    new = Button(label="x", on_click=lambda: calls.append("new"))
    renderer.apply(diff(build(old), build(new)))
    assert isinstance(renderer.root_widget, QPushButton)
    renderer.root_widget.click()
    assert calls == ["new"]


def test_input_renders_value_and_placeholder():
    renderer = QtRenderer()
    renderer.mount(build(Input(value="hi", placeholder="name")))
    widget = renderer.root_widget
    assert isinstance(widget, QLineEdit)
    assert widget.text() == "hi"
    assert widget.placeholderText() == "name"


def test_input_change_invokes_handler_with_typed_value():
    changes: list[str] = []
    renderer = QtRenderer()
    renderer.mount(
        build(Input(value="", on_change=lambda event: changes.append(event.value)))
    )
    widget = renderer.root_widget
    assert isinstance(widget, QLineEdit)
    widget.setText("typed")
    assert changes == ["typed"]


def test_checkbox_renders_label_and_state():
    renderer = QtRenderer()
    renderer.mount(build(Checkbox(label="agree", checked=True)))
    widget = renderer.root_widget
    assert isinstance(widget, QCheckBox)
    assert widget.text() == "agree"
    assert widget.isChecked() is True


def test_checkbox_toggle_invokes_handler():
    toggles: list[bool] = []
    renderer = QtRenderer()
    renderer.mount(
        build(
            Checkbox(
                label="x", on_change=lambda event: toggles.append(event.checked)
            )
        )
    )
    widget = renderer.root_widget
    assert isinstance(widget, QCheckBox)
    widget.setChecked(True)
    assert toggles == [True]


def test_datepicker_renders_value():
    renderer = QtRenderer()
    renderer.mount(build(DatePicker(value="2026-05-31")))
    widget = renderer.root_widget
    assert isinstance(widget, QDateEdit)
    assert widget.date().toString("yyyy-MM-dd") == "2026-05-31"


def test_filepicker_renders_label_as_button():
    renderer = QtRenderer()
    renderer.mount(build(FilePicker(label="Upload")))
    widget = renderer.root_widget
    assert isinstance(widget, QPushButton)
    assert widget.text() == "Upload"


def test_input_value_update_applies():
    renderer = QtRenderer()
    old = Input(value="a")
    renderer.mount(build(old))
    new = Input(value="b")
    renderer.apply(diff(build(old), build(new)))
    widget = renderer.root_widget
    assert isinstance(widget, QLineEdit)
    assert widget.text() == "b"


def test_nested_container_renders():
    renderer = QtRenderer()
    tree = build(
        Column(
            children=[
                Row(children=[Text(content="x"), Text(content="y")]),
                Container(child=Text(content="z")),
            ]
        )
    )
    renderer.mount(tree)
    assert _labels(renderer.root_widget) == ["x", "y", "z"]


# --- virtualized lists (E1b) ------------------------------------------------


def _item(index: int) -> Text:
    """Build a trivial text item for a virtualized list."""
    return Text(content=str(index))


def test_lazy_column_renders_materialized_window(qapp: QApplication) -> None:
    # E1 contract: build() materializes the visible window into keyed children;
    # the Qt renderer mounts those children directly into a scroll area, never
    # self-materializing from item_count.
    renderer = QtRenderer()
    node = build(LazyColumn(item_count=100, item_builder=_item))
    host = renderer.mount(node)
    area = renderer.root_widget
    assert isinstance(area, _LazyScrollArea)
    host.resize(300, 600)
    host.show()
    qapp.processEvents()
    # The default window is [0, window_size) — the renderer renders exactly the
    # children the IR carried, never the full 100.
    materialized = area.item_widgets()
    assert len(materialized) == len(node.children)
    assert 0 < len(materialized) < 100


def test_lazy_column_applies_window_slide_child_patches(qapp: QApplication) -> None:
    # Sliding the window is a keyed diff (remove/reorder/insert) on the children;
    # the renderer applies it through the generic container path.
    renderer = QtRenderer()
    old = build(LazyColumn(item_count=100, item_builder=_item, window=(0, 10)))
    host = renderer.mount(old)
    area = renderer.root_widget
    assert isinstance(area, _LazyScrollArea)
    host.resize(300, 600)
    host.show()
    qapp.processEvents()

    def window_labels() -> list[str]:
        return [
            widget.text()
            for widget in area.item_widgets()
            if isinstance(widget, QLabel)
        ]

    assert window_labels() == [str(i) for i in range(10)]
    # The app slid the window [0,10) -> [5,15); the renderer applies the patches.
    new = build(LazyColumn(item_count=100, item_builder=_item, window=(5, 15)))
    renderer.apply(diff(old, new))
    qapp.processEvents()
    assert window_labels() == [str(i) for i in range(5, 15)]


def test_lazy_column_emits_scroll_and_end_reached(qapp: QApplication) -> None:
    scrolls: list[ScrollEvent] = []
    ends: list[EndReachedEvent] = []
    renderer = QtRenderer()
    node = build(
        LazyColumn(
            item_count=100,
            item_builder=_item,
            window=(0, 60),
            on_scroll=scrolls.append,
            on_end_reached=ends.append,
            end_reached_threshold=0.8,
        )
    )
    host = renderer.mount(node)
    area = renderer.root_widget
    assert isinstance(area, _LazyScrollArea)
    host.resize(300, 200)
    host.show()
    qapp.processEvents()
    bar = area.verticalScrollBar()
    bar.setValue(bar.maximum())
    qapp.processEvents()
    assert scrolls, "scroll handler should fire on scrollbar movement"
    assert scrolls[-1].direction == "vertical"
    assert ends, "end-reached should fire past the threshold"


def test_lazy_column_update_item_count_applies_window_patches(
    qapp: QApplication,
) -> None:
    # Pagination: item_count grows but the window children change via the keyed
    # diff. The renderer accepts the child patches without raising (the bug the
    # old xfail tracked: it used to treat LazyColumn as a leaf).
    renderer = QtRenderer()
    old = build(LazyColumn(item_count=10, item_builder=_item))
    host = renderer.mount(old)
    area = renderer.root_widget
    assert isinstance(area, _LazyScrollArea)
    host.resize(300, 600)
    host.show()
    qapp.processEvents()
    # item_count grows from 10 to 1000; the window stays its default size, so the
    # materialized window is still small (virtualization preserved).
    new = build(LazyColumn(item_count=1000, item_builder=_item))
    renderer.apply(diff(old, new))
    qapp.processEvents()
    assert len(area.item_widgets()) == len(new.children)
    assert 0 < len(area.item_widgets()) < 100


def test_lazy_grid_renders_window(qapp: QApplication) -> None:
    renderer = QtRenderer()
    node = build(LazyGrid(item_count=500, columns=3, item_builder=_item))
    host = renderer.mount(node)
    area = renderer.root_widget
    assert isinstance(area, _LazyGridArea)
    host.resize(300, 600)
    host.show()
    qapp.processEvents()
    materialized = area.item_widgets()
    assert len(materialized) == len(node.children)
    assert 0 < len(materialized) < 500


def test_section_list_renders_sticky_header(qapp: QApplication) -> None:
    renderer = QtRenderer()
    sections = [
        SectionHeader(
            title="A",
            item_count=3,
            item_builder=_item,
            header_builder=lambda: Text(content="Header A"),
        ),
        SectionHeader(
            title="B",
            item_count=2,
            item_builder=_item,
            header_builder=lambda: Text(content="Header B"),
        ),
    ]
    node = build(SectionList(sections=sections))
    renderer.mount(node)
    area = renderer.root_widget
    assert isinstance(area, _LazyScrollArea)
    # The first section's title pins the sticky header (Qt stand-in for Compose's
    # native stickyHeader — a documented divergence).
    assert area.sticky.text() == "A"


def test_refresh_control_busy_when_refreshing():
    renderer = QtRenderer()
    node = build(RefreshControl(refreshing=True))
    renderer.mount(node)
    widget = renderer.root_widget
    assert isinstance(widget, QProgressBar)
    # An active refresh shows an indeterminate (busy) bar: range collapses to 0.
    assert widget.minimum() == 0
    assert widget.maximum() == 0
