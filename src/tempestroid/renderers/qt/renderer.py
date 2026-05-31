"""The Qt leaf renderer: mount an IR node tree and apply patches to QWidgets.

The renderer owns a *host* widget whose single child is the app root, so even a
root :class:`Replace` is a uniform "swap a child" operation. It keeps a parallel
tree of :class:`_Rendered` nodes mirroring the IR, each holding its ``QWidget``
(and ``QBoxLayout`` for containers) plus the current props — so an
:class:`Update` re-applies the full merged visual idempotently, and structural
patches address widgets by the same path the reconciler used.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast

from PySide6.QtCore import QDate, QMetaObject, SignalInstance
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tempestroid.core.ir import (
    Insert,
    Node,
    Patch,
    Remove,
    Reorder,
    Replace,
    Update,
)
from tempestroid.renderers.qt.style_translator import layout_alignment, to_qss
from tempestroid.style import Style
from tempestroid.widgets import (
    DateChangeEvent,
    Event,
    FileSelectEvent,
    TextChangeEvent,
    ToggleEvent,
    handler_accepts_event,
)

__all__ = ["QtRenderer"]

_CONTAINER_TYPES = frozenset({"Column", "Row", "Container"})
_DATE_FORMAT = "yyyy-MM-dd"


class _Rendered:
    """A live Qt node mirroring one IR :class:`Node`.

    Attributes:
        type: The node type tag.
        key: The node key, if any.
        widget: The backing Qt widget.
        layout: The widget's box layout (containers only), else ``None``.
        props: The current, fully-merged props applied to the widget.
        children: The child rendered nodes, in order.
    """

    def __init__(
        self,
        node_type: str,
        key: str | None,
        widget: QWidget,
        layout: QBoxLayout | None,
    ) -> None:
        """Initialize a rendered node.

        Args:
            node_type: The node type tag.
            key: The node key, if any.
            widget: The backing Qt widget.
            layout: The container's box layout, or ``None`` for leaves.
        """
        self.type: str = node_type
        self.key: str | None = key
        self.widget: QWidget = widget
        self.layout: QBoxLayout | None = layout
        self.props: dict[str, Any] = {}
        self.children: list[_Rendered] = []


class QtRenderer:
    """Render an IR tree into Qt widgets and keep it in sync via patches."""

    def __init__(self) -> None:
        """Create the renderer and its empty host widget."""
        self.host: QWidget = QWidget()
        self._host_layout: QVBoxLayout = QVBoxLayout(self.host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._root: _Rendered | None = None
        # Track each button's live click connection so we can cleanly replace it
        # on update without poking signal internals.
        self._click_conns: dict[int, QMetaObject.Connection] = {}
        # Same for value widgets (Input/Checkbox/DatePicker change signals): keep
        # the live connection so updates can cleanly replace it. Paired with the
        # signal in ``_value_conns`` so we can disconnect without signal internals.
        self._value_conns: dict[int, tuple[SignalInstance, QMetaObject.Connection]] = {}
        # Strong refs to in-flight handler coroutines so the loop does not GC
        # them before they finish (structured cancellation is post-v1).
        self._pending: set[asyncio.Task[Any]] = set()

    def mount(self, root: Node) -> QWidget:
        """Build the initial widget tree and place it in the host.

        Args:
            root: The root IR node to render.

        Returns:
            The host widget to embed in a window or another layout.
        """
        self._root = self._create(root)
        self._host_layout.addWidget(self._root.widget)
        return self.host

    def remount(self, root: Node) -> QWidget:
        """Tear down the current tree and mount a fresh one (hot restart).

        Discards the old root widget, cancels in-flight handler tasks and clears
        stale click connections, then mounts ``root`` from scratch — clean state,
        as a hot *restart* should be.

        Args:
            root: The new root IR node to render.

        Returns:
            The host widget (unchanged across remounts).
        """
        for task in self._pending:
            task.cancel()
        self._pending.clear()
        self._click_conns.clear()
        self._value_conns.clear()
        if self._root is not None:
            self._host_layout.removeWidget(self._root.widget)
            self._discard(self._root.widget)
            self._root = None
        return self.mount(root)

    @property
    def root_widget(self) -> QWidget:
        """The current root widget.

        Returns:
            The root widget.

        Raises:
            RuntimeError: If nothing has been mounted yet.
        """
        if self._root is None:
            raise RuntimeError("nothing mounted")
        return self._root.widget

    def apply(self, patches: list[Patch]) -> None:
        """Apply a list of patches in order.

        Args:
            patches: The patches produced by the reconciler.
        """
        for patch in patches:
            self._apply_one(patch)

    # --- patch dispatch ----------------------------------------------------

    def _apply_one(self, patch: Patch) -> None:
        """Apply a single patch.

        Args:
            patch: The patch to apply.
        """
        if isinstance(patch, Update):
            self._apply_update(patch)
        elif isinstance(patch, Replace):
            self._apply_replace(patch)
        elif isinstance(patch, Insert):
            self._apply_insert(patch)
        elif isinstance(patch, Remove):
            self._apply_remove(patch)
        else:
            self._apply_reorder(patch)

    def _apply_update(self, patch: Update) -> None:
        """Merge prop changes into a node and re-apply its visual.

        Args:
            patch: The update patch.
        """
        node = self._at(patch.path)
        node.props.update(patch.set_props)
        for name in patch.unset_props:
            node.props.pop(name, None)
        self._apply_visual(node)

    def _apply_replace(self, patch: Replace) -> None:
        """Replace a whole subtree with a freshly built one.

        Args:
            patch: The replace patch.
        """
        new = self._create(patch.node)
        if not patch.path:
            old = self._root
            self._host_layout.insertWidget(0, new.widget)
            self._root = new
            if old is not None:
                self._discard(old.widget)
            return
        parent = self._at(patch.path[:-1])
        index = patch.path[-1]
        old = parent.children[index]
        layout = self._require_layout(parent)
        layout.insertWidget(index, new.widget, self._stretch(new))
        parent.children[index] = new
        self._discard(old.widget)

    def _apply_insert(self, patch: Insert) -> None:
        """Insert a new child subtree under a parent.

        Args:
            patch: The insert patch.
        """
        parent = self._at(patch.path)
        child = self._create(patch.node)
        layout = self._require_layout(parent)
        parent.children.insert(patch.index, child)
        layout.insertWidget(patch.index, child.widget, self._stretch(child))

    def _apply_remove(self, patch: Remove) -> None:
        """Remove a child subtree from a parent.

        Args:
            patch: The remove patch.
        """
        parent = self._at(patch.path)
        child = parent.children.pop(patch.index)
        self._require_layout(parent).removeWidget(child.widget)
        self._discard(child.widget)

    def _apply_reorder(self, patch: Reorder) -> None:
        """Reorder a parent's children per a permutation.

        Args:
            patch: The reorder patch.
        """
        parent = self._at(patch.path)
        layout = self._require_layout(parent)
        old_children = parent.children
        new_children = [old_children[old_index] for old_index in patch.order]
        for child in old_children:
            layout.removeWidget(child.widget)
        for child in new_children:
            layout.addWidget(child.widget, self._stretch(child))
        parent.children = new_children

    # --- tree construction -------------------------------------------------

    def _create(self, node: Node) -> _Rendered:
        """Recursively build a rendered subtree from an IR node.

        Args:
            node: The IR node to materialize.

        Returns:
            The rendered node.
        """
        rendered = self._new_rendered(node)
        rendered.props = dict(node.props)
        self._apply_visual(rendered)
        for child_node in node.children:
            child = self._create(child_node)
            rendered.children.append(child)
            self._require_layout(rendered).addWidget(
                child.widget, self._stretch(child)
            )
        return rendered

    def _new_rendered(self, node: Node) -> _Rendered:
        """Create the bare widget (and layout) for a node type.

        Args:
            node: The IR node.

        Returns:
            A rendered node with an empty widget/layout, no props applied yet.
        """
        if node.type == "Text":
            return _Rendered(node.type, node.key, QLabel(), None)
        if node.type == "Button":
            return _Rendered(node.type, node.key, QPushButton(), None)
        if node.type == "Input":
            return _Rendered(node.type, node.key, QLineEdit(), None)
        if node.type == "Checkbox":
            return _Rendered(node.type, node.key, QCheckBox(), None)
        if node.type == "DatePicker":
            edit = QDateEdit()
            edit.setDisplayFormat(_DATE_FORMAT)
            edit.setCalendarPopup(True)
            return _Rendered(node.type, node.key, edit, None)
        if node.type == "FilePicker":
            return _Rendered(node.type, node.key, QPushButton(), None)
        if node.type in _CONTAINER_TYPES:
            widget = QWidget()
            layout: QBoxLayout = (
                QHBoxLayout(widget) if node.type == "Row" else QVBoxLayout(widget)
            )
            layout.setContentsMargins(0, 0, 0, 0)
            return _Rendered(node.type, node.key, widget, layout)
        raise ValueError(f"unknown node type: {node.type!r}")

    # --- visual application ------------------------------------------------

    def _apply_visual(self, node: _Rendered) -> None:
        """Apply props (style, text, handlers) to a node's widget.

        Idempotent: re-applies the full current prop set, so updates need only
        merge into ``node.props`` and call this.

        Args:
            node: The rendered node to refresh.
        """
        style = cast("Style | None", node.props.get("style"))
        is_container = node.layout is not None
        node.widget.setStyleSheet(to_qss(style, with_padding=not is_container))
        if node.layout is not None:
            self._apply_container_layout(node.layout, node.type, style)
        if isinstance(node.widget, QLabel):
            node.widget.setText(cast("str", node.props.get("content", "")))
        elif node.type == "Input":
            self._apply_input(cast("QLineEdit", node.widget), node.props)
        elif node.type == "Checkbox":
            self._apply_checkbox(cast("QCheckBox", node.widget), node.props)
        elif node.type == "DatePicker":
            self._apply_datepicker(cast("QDateEdit", node.widget), node.props)
        elif node.type == "FilePicker":
            self._apply_filepicker(cast("QPushButton", node.widget), node.props)
        elif isinstance(node.widget, QPushButton):
            node.widget.setText(cast("str", node.props.get("label", "")))
            self._bind_click(node.widget, node.props.get("on_click"))

    def _apply_container_layout(
        self,
        layout: QBoxLayout,
        node_type: str,
        style: Style | None,
    ) -> None:
        """Apply gap, padding and alignment to a container's layout.

        Args:
            layout: The container's box layout.
            node_type: The container node type (``Row``/``Column``/``Container``).
            style: The container's style, or ``None``.
        """
        if style is None:
            return
        if style.gap is not None:
            layout.setSpacing(int(style.gap))
        if style.padding is not None:
            edge = style.padding
            layout.setContentsMargins(
                int(edge.left), int(edge.top), int(edge.right), int(edge.bottom)
            )
        alignment = layout_alignment(
            is_row=node_type == "Row",
            justify=style.justify,
            align=style.align,
        )
        if alignment is not None:
            layout.setAlignment(alignment)

    def _bind_click(self, button: QPushButton, handler: object) -> None:
        """(Re)connect a button's click signal to a handler.

        Args:
            button: The Qt button.
            handler: The click handler (sync or ``async``), or ``None``.
        """
        previous = self._click_conns.pop(id(button), None)
        if previous is not None:
            button.clicked.disconnect(previous)
        if handler is None:
            return
        callback = cast("Callable[[], Any]", handler)
        self._click_conns[id(button)] = button.clicked.connect(
            lambda: self._invoke(callback)
        )

    def _apply_input(self, widget: QLineEdit, props: dict[str, Any]) -> None:
        """Apply props to a text input and wire its change handler.

        Args:
            widget: The Qt line edit.
            props: The node's current props.
        """
        widget.setPlaceholderText(cast("str", props.get("placeholder", "")))
        desired = cast("str", props.get("value", ""))
        if widget.text() != desired:
            widget.blockSignals(True)
            widget.setText(desired)
            widget.blockSignals(False)
        self._bind_value(
            widget,
            widget.textChanged,
            props.get("on_change"),
            lambda value: TextChangeEvent(value=cast("str", value)),
        )

    def _apply_checkbox(self, widget: QCheckBox, props: dict[str, Any]) -> None:
        """Apply props to a checkbox and wire its toggle handler.

        Args:
            widget: The Qt checkbox.
            props: The node's current props.
        """
        widget.setText(cast("str", props.get("label", "")))
        desired = bool(props.get("checked", False))
        if widget.isChecked() != desired:
            widget.blockSignals(True)
            widget.setChecked(desired)
            widget.blockSignals(False)
        self._bind_value(
            widget,
            widget.toggled,
            props.get("on_change"),
            lambda checked: ToggleEvent(checked=bool(checked)),
        )

    def _apply_datepicker(self, widget: QDateEdit, props: dict[str, Any]) -> None:
        """Apply props to a date picker and wire its change handler.

        Args:
            widget: The Qt date edit.
            props: The node's current props.
        """
        value = cast("str", props.get("value", ""))
        parsed = QDate.fromString(value, _DATE_FORMAT) if value else QDate()
        if parsed.isValid() and widget.date() != parsed:
            widget.blockSignals(True)
            widget.setDate(parsed)
            widget.blockSignals(False)
        self._bind_value(
            widget,
            widget.dateChanged,
            props.get("on_change"),
            lambda qdate: DateChangeEvent(
                value=cast("QDate", qdate).toString(_DATE_FORMAT)
            ),
        )

    def _apply_filepicker(self, widget: QPushButton, props: dict[str, Any]) -> None:
        """Apply props to a file-picker button and wire its open-dialog click.

        Args:
            widget: The Qt button that opens the file dialog.
            props: The node's current props.
        """
        selected = cast("str", props.get("value", ""))
        label = cast("str", props.get("label", "Choose file"))
        widget.setText(f"{label}: {selected}" if selected else label)
        handler = props.get("on_select")
        previous = self._click_conns.pop(id(widget), None)
        if previous is not None:
            widget.clicked.disconnect(previous)
        if handler is None:
            return
        self._click_conns[id(widget)] = widget.clicked.connect(
            lambda: self._pick_file(cast("Callable[..., Any]", handler))
        )

    def _pick_file(self, handler: Callable[..., Any]) -> None:
        """Open the file dialog and dispatch a :class:`FileSelectEvent`.

        Args:
            handler: The ``on_select`` handler.
        """
        path, _ = QFileDialog.getOpenFileName(self.host, "Choose file")
        if not path:
            return
        name = path.rsplit("/", 1)[-1]
        self._invoke(handler, FileSelectEvent(uri=path, name=name))

    def _bind_value(
        self,
        widget: QWidget,
        signal: SignalInstance,
        handler: object,
        make_event: Callable[[Any], Event],
    ) -> None:
        """(Re)connect a value widget's change signal to its handler.

        Args:
            widget: The value widget (key for the connection registry).
            signal: The widget's change signal (e.g. ``textChanged``).
            handler: The change handler (sync or ``async``), or ``None``.
            make_event: Builds the typed event from the signal's emitted value.
        """
        previous = self._value_conns.pop(id(widget), None)
        if previous is not None:
            previous[0].disconnect(previous[1])
        if handler is None:
            return
        callback = cast("Callable[..., Any]", handler)

        def slot(value: Any = None) -> None:  # noqa: ANN401 — Qt signal payload is arbitrary (str, int, bool, …)
            self._invoke(callback, make_event(value))

        connection = signal.connect(slot)
        self._value_conns[id(widget)] = (signal, connection)

    def _invoke(self, handler: Callable[..., Any], event: Event | None = None) -> None:
        """Call a handler, scheduling coroutines on the running loop.

        Sync handlers run immediately. An ``async`` handler is scheduled as a
        task on the running asyncio loop and kept referenced until it finishes.
        With no running loop (e.g. a sync-only test), a returned coroutine is
        closed rather than leaked. The typed ``event`` is passed only to handlers
        that accept a positional argument (matching the device bridge contract).

        Args:
            handler: The handler to invoke.
            event: The typed event to pass, or ``None`` for zero-arg handlers.
        """
        if event is not None and handler_accepts_event(handler):
            result = handler(event)
        else:
            result = handler()
        if not inspect.iscoroutine(cast("object", result)):
            return
        coro = cast("Awaitable[Any]", result)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            cast("Any", coro).close()
            return
        task = loop.create_task(cast("Any", coro))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    # --- helpers -----------------------------------------------------------

    def _at(self, path: tuple[int, ...]) -> _Rendered:
        """Resolve a rendered node by its path from the root.

        Args:
            path: Child indices from the root.

        Returns:
            The rendered node at that path.

        Raises:
            RuntimeError: If nothing has been mounted yet.
        """
        if self._root is None:
            raise RuntimeError("nothing mounted")
        node = self._root
        for index in path:
            node = node.children[index]
        return node

    def _require_layout(self, node: _Rendered) -> QBoxLayout:
        """Return a container node's layout or fail loudly.

        Args:
            node: The rendered node, expected to be a container.

        Returns:
            The node's box layout.

        Raises:
            RuntimeError: If the node is a leaf with no layout.
        """
        if node.layout is None:
            raise RuntimeError(f"{node.type} is a leaf and cannot hold children")
        return node.layout

    @staticmethod
    def _stretch(node: _Rendered) -> int:
        """Compute a child's layout stretch factor from its ``grow`` style.

        Args:
            node: The rendered child.

        Returns:
            The integer stretch factor (0 when no ``grow`` is set).
        """
        style = cast("Style | None", node.props.get("style"))
        if style is None or style.grow is None:
            return 0
        return int(style.grow)

    @staticmethod
    def _discard(widget: QWidget) -> None:
        """Detach a widget from its parent and schedule deletion.

        Args:
            widget: The widget to discard.
        """
        widget.setParent(None)  # type: ignore[call-overload]
        widget.deleteLater()
