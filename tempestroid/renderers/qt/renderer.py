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
import re
from collections.abc import Awaitable, Callable
from typing import Any, cast

from PySide6.QtCore import (
    QDate,
    QMetaObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    SignalInstance,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPixmap,
    QResizeEvent,
    QTextLayout,
    QTextLine,
    QTextOption,
)
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDateEdit,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QGraphicsEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
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
from tempestroid.renderers.qt.style_translator import (
    layout_alignment,
    self_alignment,
    to_qss,
)
from tempestroid.style import (
    Edge,
    JustifyContent,
    Position,
    Shadow,
    StackAlign,
    Style,
    TextAlign,
    TextOverflow,
)
from tempestroid.widgets import (
    DateChangeEvent,
    Event,
    FileSelectEvent,
    LongPressEvent,
    SlideEvent,
    SwipeDirection,
    SwipeEvent,
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    handler_accepts_event,
)

__all__ = ["QtRenderer"]

_CONTAINER_TYPES = frozenset({"Column", "Row", "Container", "ScrollView", "SafeArea"})

#: Approximate Android system-bar insets (logical px) the desktop simulator
#: reserves for a ``SafeArea``. The device queries the real
#: ``WindowInsets.safeDrawing`` (status bar, navigation bar, display cutout); the
#: simulator has no system bars, so it stands in with typical status-bar (top)
#: and gesture/nav-bar (bottom) heights and leaves the sides flush.
_SAFE_AREA_INSETS: dict[str, float] = {
    "top": 24.0,
    "right": 0.0,
    "bottom": 24.0,
    "left": 0.0,
}
#: Fallback edge set when a ``SafeArea`` carries no explicit ``edges`` prop.
_SAFE_AREA_EDGES_ALL: frozenset[str] = frozenset({"top", "right", "bottom", "left"})
_TOGGLE_TYPES = frozenset({"Checkbox", "Switch"})
_DATE_FORMAT = "yyyy-MM-dd"

_KEYBOARD_HINTS: dict[str, Qt.InputMethodHint] = {
    "number": Qt.InputMethodHint.ImhDigitsOnly,
    "email": Qt.InputMethodHint.ImhEmailCharactersOnly,
    "phone": Qt.InputMethodHint.ImhDialableCharactersOnly,
    "url": Qt.InputMethodHint.ImhUrlCharactersOnly,
}

#: Two-axis placement bands per :class:`StackAlign`: ``(horizontal, vertical)``
#: where horizontal ∈ ``start/center/end`` and vertical ∈ ``top/center/bottom``.
#: Used to position a ``Stack``'s non-positioned children inside its box.
_STACK_BANDS: dict[StackAlign, tuple[str, str]] = {
    StackAlign.TOP_START: ("start", "top"),
    StackAlign.TOP_CENTER: ("center", "top"),
    StackAlign.TOP_END: ("end", "top"),
    StackAlign.CENTER_START: ("start", "center"),
    StackAlign.CENTER: ("center", "center"),
    StackAlign.CENTER_END: ("end", "center"),
    StackAlign.BOTTOM_START: ("start", "bottom"),
    StackAlign.BOTTOM_CENTER: ("center", "bottom"),
    StackAlign.BOTTOM_END: ("end", "bottom"),
}

#: Gesture detection thresholds (logical pixels / milliseconds). A press held
#: past ``_LONG_PRESS_MS`` is a long-press; a release whose travel exceeds
#: ``_SWIPE_THRESHOLD`` is a swipe; smaller travel within ``_TAP_SLOP`` is a tap.
_LONG_PRESS_MS = 500
_SWIPE_THRESHOLD = 40.0
_TAP_SLOP = 12.0


def _band_offset(band: str, extent: int, child_extent: int) -> int:
    """Place a child of ``child_extent`` within ``extent`` along one axis band.

    Args:
        band: ``"start"``, ``"center"`` or ``"end"``.
        extent: The parent's extent on this axis.
        child_extent: The child's extent on this axis.

    Returns:
        The child's offset from the start edge.
    """
    if band == "center":
        return (extent - child_extent) // 2
    if band == "end":
        return extent - child_extent
    return 0


def _stack_geometry(
    widget: QWidget,
    style: Style | None,
    width: int,
    height: int,
    stack_align: StackAlign | None,
) -> QRect:
    """Compute a stacked child's geometry inside a ``width``×``height`` box.

    A child whose style sets ``position = ABSOLUTE`` is anchored by its insets
    (spanning the axis when both opposite insets are set); otherwise it is sized
    to its hint (or explicit ``width``/``height``) and aligned by ``stack_align``.

    Args:
        widget: The child widget (its size hint is the fallback extent).
        style: The child's style, or ``None``.
        width: The stack's content width.
        height: The stack's content height.
        stack_align: The stack's default alignment for non-positioned children.

    Returns:
        The child's geometry rectangle within the stack.
    """
    hint = widget.sizeHint()
    child_w, child_h = hint.width(), hint.height()
    if style is not None and style.width is not None:
        child_w = int(style.width)
    if style is not None and style.height is not None:
        child_h = int(style.height)
    if style is not None and style.position == Position.ABSOLUTE:
        left, right = style.left, style.right
        top, bottom = style.top, style.bottom
        if left is not None and right is not None:
            x, child_w = int(left), max(0, width - int(left) - int(right))
        elif left is not None:
            x = int(left)
        elif right is not None:
            x = width - int(right) - child_w
        else:
            x = 0
        if top is not None and bottom is not None:
            y, child_h = int(top), max(0, height - int(top) - int(bottom))
        elif top is not None:
            y = int(top)
        elif bottom is not None:
            y = height - int(bottom) - child_h
        else:
            y = 0
        return QRect(x, y, child_w, child_h)
    horizontal, vertical = _STACK_BANDS.get(
        stack_align or StackAlign.TOP_START, ("start", "top")
    )
    x = _band_offset(horizontal, width, child_w)
    y = _band_offset(vertical, height, child_h)
    return QRect(x, y, child_w, child_h)


def _matches_pattern(pattern: str, value: str) -> bool:
    """Whether ``value`` fully matches a regex ``pattern`` (anchored).

    Args:
        pattern: The regular expression to test (matched against the whole value).
        value: The current text value.

    Returns:
        ``True`` when the value fully matches; ``False`` on no match or a bad
        pattern (an invalid regex never blocks input, it just reads as invalid).
    """
    try:
        return re.fullmatch(pattern, value) is not None
    except re.error:
        return False


def _eye_icon(revealed: bool) -> QIcon:
    """Render a small open/closed-eye glyph into an icon for the reveal toggle.

    Args:
        revealed: Whether the password is currently revealed (open eye) or
            masked (closed eye).

    Returns:
        A 16×16 icon carrying the matching glyph.
    """
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setPen(QColor(90, 90, 90))
    font = QFont()
    font.setPixelSize(13)
    painter.setFont(font)
    glyph = "👁" if revealed else "🙈"
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    return QIcon(pixmap)


def _drop_shadow(shadow: Shadow, parent: QWidget) -> QGraphicsDropShadowEffect:
    """Build a ``QGraphicsDropShadowEffect`` approximating a CSS ``box-shadow``.

    The effect is parented to ``parent`` so Qt keeps it alive after this returns
    (an unparented PySide effect is garbage-collected once the local drops).

    Args:
        shadow: The shadow spec.
        parent: The widget the effect attaches to (its owner).

    Returns:
        The configured Qt drop-shadow effect.
    """
    effect = QGraphicsDropShadowEffect(parent)
    effect.setBlurRadius(shadow.blur)
    effect.setXOffset(shadow.offset_x)
    effect.setYOffset(shadow.offset_y)
    if shadow.color is not None:
        effect.setColor(
            QColor(shadow.color.r, shadow.color.g, shadow.color.b,
                   round(shadow.color.a * 255))
        )
    return effect


class _StackWidget(QWidget):
    """A container that overlaps its children, layered by insertion order.

    Children are direct Qt children (no box layout). On every resize — and
    whenever the renderer changes the child set or a child's style — each child's
    geometry is recomputed by :func:`_stack_geometry` (aligned by ``stack_align``
    or anchored by absolute insets), then raised in order so the last child paints
    on top. This is the Qt realization of the :class:`~tempestroid.widgets.Stack`
    overlay primitive.
    """

    def __init__(self) -> None:
        """Create an empty stack widget."""
        super().__init__()
        self._children: list[tuple[QWidget, Style | None]] = []
        self._stack_align: StackAlign | None = None

    def set_layers(
        self,
        children: list[tuple[QWidget, Style | None]],
        stack_align: StackAlign | None,
    ) -> None:
        """Replace the layered child set and re-lay it out.

        Args:
            children: The ordered ``(widget, style)`` layers, bottom first.
            stack_align: The stack's default alignment for non-positioned layers.
        """
        self._children = children
        self._stack_align = stack_align
        self._relayout()

    def _relayout(self) -> None:
        """Reposition and re-stack every child for the current size."""
        width, height = self.width(), self.height()
        for widget, style in self._children:
            widget.setGeometry(
                _stack_geometry(widget, style, width, height, self._stack_align)
            )
        for widget, _ in self._children:
            widget.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Re-lay the children whenever the stack is resized.

        Args:
            event: The Qt resize event (name mandated by the PySide override).
        """
        self._relayout()
        super().resizeEvent(event)

    def sizeHint(self) -> QSize:
        """Size to the largest non-positioned layer (Flutter-style content fit).

        Absolutely-positioned layers are excluded — they are anchored to the
        stack's own bounds, so they must not inflate it. The stack still expands
        to fill when a parent layout or a ``grow``/fixed size says so.

        Returns:
            The union of the non-positioned children's size hints.
        """
        width = height = 0
        for widget, style in self._children:
            if style is not None and style.position == Position.ABSOLUTE:
                continue
            hint = widget.sizeHint()
            width = max(width, hint.width())
            height = max(height, hint.height())
        return QSize(width, height)


class _GestureWidget(QWidget):
    """A single-child container that turns pointer activity into gesture events.

    A press starts a long-press timer; movement past the slop cancels it. On
    release the travel decides the gesture: past :data:`_SWIPE_THRESHOLD` it is a
    swipe (dominant axis → direction), otherwise a tap. Qt's native double-click
    drives ``on_double_tap``. Each recognized gesture is forwarded through
    :meth:`set_handlers`' dispatch callback, which carries the typed event into
    the matching Python handler (when one is wired).
    """

    def __init__(self) -> None:
        """Create the gesture widget and its single-child layout."""
        super().__init__()
        self._layout: QVBoxLayout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._handlers: dict[str, object] = {}
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None
        self._press_pos: QPoint | None = None
        self._moved: bool = False
        self._long_fired: bool = False
        self._long_timer: QTimer = QTimer(self)
        self._long_timer.setSingleShot(True)
        self._long_timer.setInterval(_LONG_PRESS_MS)
        self._long_timer.timeout.connect(self._fire_long_press)

    def set_handlers(
        self,
        handlers: dict[str, object],
        dispatch: Callable[[Any, Event], None],
    ) -> None:
        """Install the current gesture handlers and the dispatch callback.

        Args:
            handlers: Map of gesture prop name (``on_tap`` …) to its handler (or
                ``None`` when unset).
            dispatch: Callback invoked as ``dispatch(handler, event)`` to run a
                handler with its typed event on the renderer's loop.
        """
        self._handlers = handlers
        self._dispatch = dispatch

    def _emit(self, prop: str, event: Event) -> None:
        """Dispatch ``event`` to the handler bound at ``prop`` if present.

        Args:
            prop: The gesture prop name.
            event: The typed gesture event.
        """
        handler = self._handlers.get(prop)
        if handler is not None:
            self._dispatch(handler, event)

    def _fire_long_press(self) -> None:
        """Timer slot: emit a long-press once the hold threshold elapses."""
        if self._press_pos is None:
            return
        self._long_fired = True
        self._emit(
            "on_long_press",
            LongPressEvent(x=float(self._press_pos.x()), y=float(self._press_pos.y())),
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record the press start and arm the long-press timer.

        Args:
            event: The Qt mouse press event.
        """
        self._press_pos = event.position().toPoint()
        self._moved = False
        self._long_fired = False
        self._long_timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Cancel the long-press once the pointer leaves the tap slop.

        Args:
            event: The Qt mouse move event.
        """
        if self._press_pos is not None and not self._moved:
            delta = event.position().toPoint() - self._press_pos
            if abs(delta.x()) > _TAP_SLOP or abs(delta.y()) > _TAP_SLOP:
                self._moved = True
                self._long_timer.stop()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Classify the completed gesture (swipe vs tap) on release.

        Args:
            event: The Qt mouse release event.
        """
        self._long_timer.stop()
        if self._press_pos is None or self._long_fired:
            self._press_pos = None
            super().mouseReleaseEvent(event)
            return
        end = event.position().toPoint()
        dx = float(end.x() - self._press_pos.x())
        dy = float(end.y() - self._press_pos.y())
        if max(abs(dx), abs(dy)) >= _SWIPE_THRESHOLD:
            self._emit(
                "on_swipe",
                SwipeEvent(direction=_swipe_direction(dx, dy), dx=dx, dy=dy),
            )
        else:
            self._emit("on_tap", TapEvent(x=float(end.x()), y=float(end.y())))
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Emit a double-tap from Qt's native double-click.

        Args:
            event: The Qt double-click event.
        """
        self._long_timer.stop()
        point = event.position().toPoint()
        self._emit("on_double_tap", TapEvent(x=float(point.x()), y=float(point.y())))
        super().mouseDoubleClickEvent(event)


def _swipe_direction(dx: float, dy: float) -> SwipeDirection:
    """Classify a swipe's dominant cardinal direction from its travel.

    Args:
        dx: Horizontal travel (positive → rightward).
        dy: Vertical travel (positive → downward).

    Returns:
        The dominant :class:`SwipeDirection`.
    """
    if abs(dx) >= abs(dy):
        return SwipeDirection.RIGHT if dx > 0 else SwipeDirection.LEFT
    return SwipeDirection.DOWN if dy > 0 else SwipeDirection.UP


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
        # Live password-reveal toggle actions, keyed by line-edit id, so a secure
        # Input keeps a single eye action across idempotent re-applies.
        self._eye_actions: dict[int, QAction] = {}

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
        self._eye_actions.clear()
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
        # A justify change can switch a container in/out of SPACE_* distribution.
        self._sync_main_axis(node)
        # A stack's own ``stack_align`` change, or any child's position/inset/size
        # change, must re-lay the overlapping layers (geometry is renderer-driven).
        if node.type == "Stack":
            self._relayout_stack(node)
        if patch.path:
            parent = self._at(patch.path[:-1])
            if parent.type == "Stack":
                self._relayout_stack(parent)

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
        if parent.type == "Stack":
            new.widget.setParent(parent.widget)
            parent.children[index] = new
            self._purge_connections(old)
            self._discard(old.widget)
            self._relayout_stack(parent)
            return
        layout = self._require_layout(parent)
        layout.insertWidget(index, new.widget, self._stretch(new))
        self._place_alignment(parent, new)
        parent.children[index] = new
        self._discard(old.widget)

    def _apply_insert(self, patch: Insert) -> None:
        """Insert a new child subtree under a parent.

        Args:
            patch: The insert patch.
        """
        parent = self._at(patch.path)
        child = self._create(patch.node)
        if parent.type == "Stack":
            child.widget.setParent(parent.widget)
            parent.children.insert(patch.index, child)
            self._relayout_stack(parent)
            return
        layout = self._require_layout(parent)
        parent.children.insert(patch.index, child)
        layout.insertWidget(patch.index, child.widget, self._stretch(child))
        self._place_alignment(parent, child)

    def _apply_remove(self, patch: Remove) -> None:
        """Remove a child subtree from a parent.

        Args:
            patch: The remove patch.
        """
        parent = self._at(patch.path)
        child = parent.children.pop(patch.index)
        if parent.type == "Stack":
            self._purge_connections(child)
            self._discard(child.widget)
            self._relayout_stack(parent)
            return
        self._require_layout(parent).removeWidget(child.widget)
        self._discard(child.widget)

    def _apply_reorder(self, patch: Reorder) -> None:
        """Reorder a parent's children per a permutation.

        Args:
            patch: The reorder patch.
        """
        parent = self._at(patch.path)
        old_children = parent.children
        new_children = [old_children[old_index] for old_index in patch.order]
        if parent.type == "Stack":
            # Z-order follows the child list, so re-stacking is enough.
            parent.children = new_children
            self._relayout_stack(parent)
            return
        layout = self._require_layout(parent)
        # Drop spacers first so they don't survive interleaved in the new order.
        self._strip_spacers(layout)
        for child in old_children:
            layout.removeWidget(child.widget)
        for child in new_children:
            layout.addWidget(child.widget, self._stretch(child))
            self._place_alignment(parent, child)
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
            if rendered.type == "Stack":
                child.widget.setParent(rendered.widget)
            else:
                self._require_layout(rendered).addWidget(
                    child.widget, self._stretch(child)
                )
                self._place_alignment(rendered, child)
        if rendered.type == "Stack":
            self._relayout_stack(rendered)
        elif rendered.layout is not None:
            self._sync_main_axis(rendered)
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
        if node.type == "TextArea":
            return _Rendered(node.type, node.key, QPlainTextEdit(), None)
        if node.type in _TOGGLE_TYPES:
            return _Rendered(node.type, node.key, QCheckBox(), None)
        if node.type == "Slider":
            return _Rendered(
                node.type, node.key, QSlider(Qt.Orientation.Horizontal), None
            )
        if node.type in ("ProgressBar", "Spinner"):
            return _Rendered(node.type, node.key, QProgressBar(), None)
        if node.type == "Image":
            return _Rendered(node.type, node.key, QLabel(), None)
        if node.type == "Icon":
            return _Rendered(node.type, node.key, QLabel(), None)
        if node.type == "DatePicker":
            edit = QDateEdit()
            edit.setDisplayFormat(_DATE_FORMAT)
            edit.setCalendarPopup(True)
            return _Rendered(node.type, node.key, edit, None)
        if node.type == "FilePicker":
            return _Rendered(node.type, node.key, QPushButton(), None)
        if node.type == "ScrollView":
            return self._new_scrollview(node)
        if node.type == "Stack":
            return _Rendered(node.type, node.key, _StackWidget(), None)
        if node.type == "GestureDetector":
            gesture = _GestureWidget()
            return _Rendered(
                node.type, node.key, gesture, cast("QBoxLayout", gesture.layout())
            )
        if node.type in _CONTAINER_TYPES:
            widget = QWidget()
            layout: QBoxLayout = (
                QHBoxLayout(widget) if node.type == "Row" else QVBoxLayout(widget)
            )
            layout.setContentsMargins(0, 0, 0, 0)
            return _Rendered(node.type, node.key, widget, layout)
        raise ValueError(f"unknown node type: {node.type!r}")

    @staticmethod
    def _new_scrollview(node: Node) -> _Rendered:
        """Build a ``QScrollArea`` whose inner box layout receives the children.

        The rendered node's ``widget`` is the scroll area while its ``layout`` is
        the inner content layout, so the generic child-insertion path adds
        children into the scrollable content unchanged. Orientation is read from
        the node's ``horizontal`` prop at creation (a runtime flip is post-v1).

        Args:
            node: The ``ScrollView`` IR node.

        Returns:
            The rendered scroll view.
        """
        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        horizontal = bool(node.props.get("horizontal", False))
        layout: QBoxLayout = (
            QHBoxLayout(content) if horizontal else QVBoxLayout(content)
        )
        layout.setContentsMargins(0, 0, 0, 0)
        area.setWidget(content)
        return _Rendered(node.type, node.key, area, layout)

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
            if node.type == "SafeArea":
                self._apply_safe_area(
                    node.layout,
                    style,
                    cast("list[Any] | None", node.props.get("edges")),
                )
        if node.type == "Text":
            cast("QLabel", node.widget).setText(
                cast("str", node.props.get("content", ""))
            )
        elif node.type == "Image":
            self._apply_image(cast("QLabel", node.widget), node.props)
        elif node.type == "Icon":
            self._apply_icon(cast("QLabel", node.widget), node.props)
        elif node.type == "Input":
            self._apply_input(cast("QLineEdit", node.widget), node.props)
        elif node.type == "TextArea":
            self._apply_textarea(cast("QPlainTextEdit", node.widget), node.props)
        elif node.type in _TOGGLE_TYPES:
            self._apply_checkbox(cast("QCheckBox", node.widget), node.props)
        elif node.type == "Slider":
            self._apply_slider(cast("QSlider", node.widget), node.props)
        elif node.type == "ProgressBar":
            self._apply_progressbar(cast("QProgressBar", node.widget), node.props)
        elif node.type == "Spinner":
            self._apply_spinner(cast("QProgressBar", node.widget), node.props)
        elif node.type == "DatePicker":
            self._apply_datepicker(cast("QDateEdit", node.widget), node.props)
        elif node.type == "FilePicker":
            self._apply_filepicker(cast("QPushButton", node.widget), node.props)
        elif node.type == "Button":
            button = cast("QPushButton", node.widget)
            button.setText(cast("str", node.props.get("label", "")))
            self._bind_click(button, node.props.get("on_click"))
        elif node.type == "GestureDetector":
            self._bind_gestures(cast("_GestureWidget", node.widget), node.props)
        self._apply_letter_spacing(node.widget, style)
        self._apply_effects(node.widget, style)

    @staticmethod
    def _apply_letter_spacing(widget: QWidget, style: Style | None) -> None:
        """Apply ``letter_spacing`` via ``QFont`` (no QSS equivalent exists).

        Idempotent: resets to the default percentage spacing when unset, so an
        update that drops ``letter_spacing`` restores normal tracking.

        Args:
            widget: The target widget.
            style: The node's style, or ``None``.
        """
        font = widget.font()
        if style is not None and style.letter_spacing is not None:
            font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing, style.letter_spacing
            )
        else:
            font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100.0)
        widget.setFont(font)

    @staticmethod
    def _apply_effects(widget: QWidget, style: Style | None) -> None:
        """Apply ``shadow``/``opacity`` as a ``QGraphicsEffect``.

        Qt allows a widget only one graphics effect, so when both are set the
        shadow wins (documented limit); the simulator can't layer them the way
        Compose does. Idempotent: clears the effect when neither is set.

        Args:
            widget: The target widget.
            style: The node's style, or ``None``.
        """
        shadow = style.shadow if style is not None else None
        opacity = style.opacity if style is not None else None
        # Effects are parented to the widget: Qt takes ownership and keeps them
        # alive, otherwise the PySide wrapper is GC'd and the effect disappears.
        effect: QGraphicsEffect | None = None
        if shadow is not None:
            effect = _drop_shadow(shadow, widget)
        elif opacity is not None and opacity < 1.0:
            opacity_effect = QGraphicsOpacityEffect(widget)
            opacity_effect.setOpacity(opacity)
            effect = opacity_effect
        # Passing ``None`` clears any prior effect (Qt accepts a null effect); the
        # PySide stub types the param as non-optional, so scope the ignore here.
        widget.setGraphicsEffect(effect)  # pyright: ignore[reportArgumentType]

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

    @staticmethod
    def _apply_safe_area(
        layout: QBoxLayout,
        style: Style | None,
        edges: list[Any] | None,
    ) -> None:
        """Reserve approximate system-bar insets on a ``SafeArea``'s layout.

        Overrides the container margins with ``padding + inset`` on each selected
        edge, so the simulator keeps the child clear of where the status/nav bars
        would sit on a device (the device renderer uses the real
        ``WindowInsets.safeDrawing``). Idempotent.

        Args:
            layout: The safe-area container's box layout.
            style: The container's style (its ``padding`` is added under the inset).
            edges: The protected edges (edge strings/enums); ``None`` means all.
        """
        base = Edge()
        if style is not None and style.padding is not None:
            base = style.padding
        selected = (
            {str(edge) for edge in edges} if edges is not None else _SAFE_AREA_EDGES_ALL
        )

        def inset(side: str) -> float:
            return _SAFE_AREA_INSETS[side] if side in selected else 0.0

        layout.setContentsMargins(
            int(base.left + inset("left")),
            int(base.top + inset("top")),
            int(base.right + inset("right")),
            int(base.bottom + inset("bottom")),
        )

    @staticmethod
    def _strip_spacers(layout: QBoxLayout) -> None:
        """Remove every stretch spacer from a layout, leaving widgets contiguous.

        Stretch spacers are owned by the layout (not by any ``_Rendered``), so the
        structural patch methods strip them before touching widgets — that keeps a
        child's IR index equal to its layout slot — then re-add them via
        :meth:`_sync_main_axis`.

        Args:
            layout: The container's box layout.
        """
        for index in reversed(range(layout.count())):
            item = layout.itemAt(index)
            if item is not None and item.spacerItem() is not None:
                layout.takeAt(index)

    def _sync_main_axis(self, parent: _Rendered) -> None:
        """Realize a ``SPACE_*`` ``justify`` with stretch spacers around children.

        ``QBoxLayout`` has no native space-between/around/evenly distribution, so
        for those justify values the children are re-laid with stretch spacers:
        between each pair (``SPACE_BETWEEN``), or also at both ends
        (``SPACE_AROUND``/``SPACE_EVENLY``, the former weighting the inter-item
        gaps double so each child gets equal space *around* it). For every other
        justify value this only strips any stale spacers (e.g. after a justify
        change) and leaves the incremental layout untouched. ``grow`` stretch
        factors and ``align_self`` overrides are re-applied so the spaced layout
        matches the packed one.

        Args:
            parent: The container rendered node.
        """
        if parent.layout is None:
            return
        layout = parent.layout
        self._strip_spacers(layout)
        style = cast("Style | None", parent.props.get("style"))
        justify = style.justify if style is not None else None
        if justify not in _SPACE_JUSTIFY:
            return
        for child in parent.children:
            layout.removeWidget(child.widget)
        ends = justify in (JustifyContent.SPACE_AROUND, JustifyContent.SPACE_EVENLY)
        between = 2 if justify == JustifyContent.SPACE_AROUND else 1
        if ends:
            layout.addStretch(1)
        for index, child in enumerate(parent.children):
            if index > 0:
                layout.addStretch(between)
            layout.addWidget(child.widget, self._stretch(child))
            self._place_alignment(parent, child)
        if ends:
            layout.addStretch(1)

    def _relayout_stack(self, parent: _Rendered) -> None:
        """Push the current child layers + ``stack_align`` into a stack widget.

        Args:
            parent: The ``Stack`` rendered node.
        """
        widget = cast("_StackWidget", parent.widget)
        layers = [
            (child.widget, cast("Style | None", child.props.get("style")))
            for child in parent.children
        ]
        style = cast("Style | None", parent.props.get("style"))
        widget.set_layers(layers, style.stack_align if style is not None else None)

    def _bind_gestures(self, widget: _GestureWidget, props: dict[str, Any]) -> None:
        """(Re)install the gesture handlers on a ``GestureDetector`` widget.

        Args:
            widget: The gesture widget.
            props: The node's current props (handlers read by name).
        """
        handlers: dict[str, object] = {
            name: props.get(name)
            for name in ("on_tap", "on_double_tap", "on_long_press", "on_swipe")
        }
        widget.set_handlers(handlers, self._invoke)

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
        """Apply props to a single-line text input and wire its change handler.

        Handles secure (masked) mode with a reveal toggle, an optional character
        cap, soft-keyboard hints and regex validity reporting.

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
        max_length = props.get("max_length")
        widget.setMaxLength(int(max_length) if max_length is not None else 32767)
        widget.setInputMethodHints(
            _KEYBOARD_HINTS.get(
                cast("str", props.get("keyboard", "text")),
                Qt.InputMethodHint.ImhNone,
            )
        )
        self._apply_secure(widget, bool(props.get("secure", False)))
        pattern = cast("str | None", props.get("pattern"))
        self._bind_value(
            widget,
            widget.textChanged,
            props.get("on_change"),
            lambda value: TextChangeEvent(
                value=cast("str", value),
                valid=_matches_pattern(pattern, cast("str", value))
                if pattern is not None
                else None,
            ),
        )

    def _apply_secure(self, widget: QLineEdit, secure: bool) -> None:
        """Toggle password masking and the reveal ("eye") action on a line edit.

        When ``secure`` is set, the field masks its text and grows a single
        trailing toggle that flips between masked and revealed locally (no Python
        round-trip). When unset, any existing toggle is removed.

        Args:
            widget: The Qt line edit.
            secure: Whether the field should mask its text.
        """
        action = self._eye_actions.get(id(widget))
        if not secure:
            if action is not None:
                widget.removeAction(action)
                self._eye_actions.pop(id(widget), None)
            widget.setEchoMode(QLineEdit.EchoMode.Normal)
            return
        if action is not None:
            return
        widget.setEchoMode(QLineEdit.EchoMode.Password)
        toggle = QAction(_eye_icon(revealed=False), "Reveal password", widget)
        toggle.setCheckable(True)

        def _reveal(checked: bool) -> None:
            widget.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            toggle.setIcon(_eye_icon(revealed=checked))

        toggle.toggled.connect(_reveal)
        widget.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)
        self._eye_actions[id(widget)] = toggle

    def _apply_textarea(self, widget: QPlainTextEdit, props: dict[str, Any]) -> None:
        """Apply props to a multi-line text input and wire its change handler.

        Args:
            widget: The Qt plain-text edit.
            props: The node's current props.
        """
        widget.setPlaceholderText(cast("str", props.get("placeholder", "")))
        desired = cast("str", props.get("value", ""))
        if widget.toPlainText() != desired:
            widget.blockSignals(True)
            widget.setPlainText(desired)
            widget.blockSignals(False)
        rows = int(cast("int", props.get("rows", 3)))
        widget.setFixedHeight(max(rows, 1) * 22)
        handler = props.get("on_change")
        previous = self._value_conns.pop(id(widget), None)
        if previous is not None:
            previous[0].disconnect(previous[1])
        if handler is None:
            return
        callback = cast("Callable[..., Any]", handler)

        def _on_text() -> None:
            self._invoke(callback, TextChangeEvent(value=widget.toPlainText()))

        connection = widget.textChanged.connect(_on_text)
        self._value_conns[id(widget)] = (widget.textChanged, connection)

    def _apply_slider(self, widget: QSlider, props: dict[str, Any]) -> None:
        """Apply props to a slider and wire its change handler.

        The simulator's ``QSlider`` is integer-based, so fractional ``step`` and
        bounds are rounded here; the device's Compose ``Slider`` keeps full
        floating-point precision.

        Args:
            widget: The Qt slider.
            props: The node's current props.
        """
        widget.setMinimum(int(cast("float", props.get("min_value", 0.0))))
        widget.setMaximum(int(cast("float", props.get("max_value", 100.0))))
        widget.setSingleStep(max(int(cast("float", props.get("step", 1.0))), 1))
        desired = int(cast("float", props.get("value", 0.0)))
        if widget.value() != desired:
            widget.blockSignals(True)
            widget.setValue(desired)
            widget.blockSignals(False)
        self._bind_value(
            widget,
            widget.valueChanged,
            props.get("on_change"),
            lambda value: SlideEvent(value=float(cast("int", value))),
        )

    @staticmethod
    def _apply_progressbar(widget: QProgressBar, props: dict[str, Any]) -> None:
        """Apply props to a progress bar (determinate fraction or looping bar).

        Args:
            widget: The Qt progress bar.
            props: The node's current props.
        """
        if bool(props.get("indeterminate", False)):
            widget.setRange(0, 0)
            return
        widget.setRange(0, 100)
        widget.setValue(int(cast("float", props.get("value", 0.0)) * 100))

    @staticmethod
    def _apply_spinner(widget: QProgressBar, props: dict[str, Any]) -> None:
        """Apply props to a spinner (an always-indeterminate progress bar).

        Args:
            widget: The Qt progress bar standing in for the spinner.
            props: The node's current props.
        """
        widget.setRange(0, 0)
        widget.setTextVisible(False)
        size = props.get("size")
        if size is not None:
            widget.setFixedHeight(int(cast("float", size)))

    @staticmethod
    def _apply_image(widget: QLabel, props: dict[str, Any]) -> None:
        """Apply props to an image label, loading local sources best-effort.

        Remote (``http(s)``) sources are not fetched by the simulator — the
        ``alt`` text is shown instead; the device renderer loads them.

        Args:
            widget: The Qt label backing the image.
            props: The node's current props.
        """
        src = cast("str", props.get("src", ""))
        alt = cast("str", props.get("alt", ""))
        is_local = bool(src) and not src.startswith(("http://", "https://"))
        pixmap = QPixmap(src) if is_local else QPixmap()
        if pixmap.isNull():
            widget.setText(alt or src)
            return
        widget.setText("")
        widget.setPixmap(pixmap)
        widget.setScaledContents(cast("str", props.get("fit", "contain")) == "fill")

    @staticmethod
    def _apply_icon(widget: QLabel, props: dict[str, Any]) -> None:
        """Apply props to an icon label.

        The simulator shows the icon's ``name`` as text (no icon font is bundled);
        the device renders the real vector glyph from its icon set.

        Args:
            widget: The Qt label backing the icon.
            props: The node's current props.
        """
        widget.setText(cast("str", props.get("name", "")))
        size = props.get("size")
        if size is not None:
            font = widget.font()
            font.setPixelSize(int(cast("float", size)))
            widget.setFont(font)

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

    def _place_alignment(self, parent: _Rendered, child: _Rendered) -> None:
        """Apply a child's ``align_self`` cross-axis override in its parent layout.

        Args:
            parent: The parent rendered node (provides the main-axis direction).
            child: The freshly placed child rendered node.
        """
        if parent.layout is None:
            return
        style = cast("Style | None", child.props.get("style"))
        if style is None or style.align_self is None:
            return
        flag = self_alignment(
            is_row=parent.type == "Row", align_self=style.align_self
        )
        if flag is not None:
            parent.layout.setAlignment(child.widget, flag)

    @staticmethod
    def _discard(widget: QWidget) -> None:
        """Detach a widget from its parent and schedule deletion.

        Args:
            widget: The widget to discard.
        """
        widget.setParent(None)  # type: ignore[call-overload]
        widget.deleteLater()
