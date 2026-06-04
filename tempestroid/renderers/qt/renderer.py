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
    QAbstractAnimation,
    QDate,
    QEasingCurve,
    QMetaObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
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
    QDialog,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QGraphicsEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSlider,
    QStackedWidget,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from tempestroid.core.ir import (
    Insert,
    Node,
    Patch,
    Path,
    Remove,
    Reorder,
    Replace,
    Scene,
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
    DismissEvent,
    EndReachedEvent,
    Event,
    FileSelectEvent,
    LongPressEvent,
    MenuItem,
    MenuSelectEvent,
    RouteChangeEvent,
    ScrollEvent,
    SlideEvent,
    SwipeDirection,
    SwipeEvent,
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    handler_accepts_event,
)

__all__ = ["QtRenderer"]

#: The reserved leading path step that addresses the :class:`Scene` overlay
#: layer (mirrors ``reconciler.OVERLAY_STEP``). A patch whose path starts with
#: this token targets the floating overlay layer, not the root tree.
_OVERLAY_STEP = "overlay"

#: Overlay node types the renderer realizes as a floating top-level surface
#: (``QDialog``/``QMenu``/``QLabel``) rather than a child of the root tree.
_OVERLAY_TYPES = frozenset(
    {"Dialog", "BottomSheet", "Toast", "Tooltip", "Menu", "Popover", "ActionSheet"}
)

#: Toast fade-out duration (ms) — the QLabel fades just before the Python-side
#: ``loop.call_later`` removes it; the Python timer stays authoritative.
_TOAST_FADE_MS = 350

_CONTAINER_TYPES = frozenset({"Column", "Row", "Container", "ScrollView", "SafeArea"})

#: Virtual-list node types the renderer renders the *materialized window* for.
#: Since the E1 core change these nodes are **not leaves**: ``build`` already
#: materialized the visible window into ``node.children`` (each keyed by its
#: absolute index), so the renderer mounts those children directly into a scroll
#: area and applies child patches through the generic container path — it never
#: self-materializes from ``item_count`` anymore.
_LAZY_LIST_TYPES = frozenset({"LazyColumn", "LazyRow", "SectionList"})
_LAZY_TYPES = frozenset({"LazyColumn", "LazyRow", "LazyGrid", "SectionList"})

#: Key prefix marking a :class:`SectionList` header child (``sec:<title>:header``);
#: used to pin the sticky header to the topmost visible section.
_SECTION_HEADER_SUFFIX = ":header"
_SECTION_KEY_PREFIX = "sec:"

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
#: Qt's "no maximum" sentinel for widget sizes (``QWIDGETSIZE_MAX``); resetting a
#: fixed dimension restores min 0 / max this so the widget flexes again.
_QT_SIZE_MAX = 16_777_215

#: Main-axis ``justify`` values that distribute *space* between children rather
#: than packing them to one alignment edge. These have no single ``QBoxLayout``
#: alignment flag, so the renderer realizes them with stretch spacers instead.
_SPACE_JUSTIFY: frozenset[JustifyContent] = frozenset(
    {
        JustifyContent.SPACE_BETWEEN,
        JustifyContent.SPACE_AROUND,
        JustifyContent.SPACE_EVENLY,
    }
)

#: Horizontal text-alignment flags per :class:`TextAlign` (combined with a
#: vertical-centre flag when applied to a ``QLabel``).
_TEXT_ALIGN: dict[TextAlign, Qt.AlignmentFlag] = {
    TextAlign.LEFT: Qt.AlignmentFlag.AlignLeft,
    TextAlign.CENTER: Qt.AlignmentFlag.AlignHCenter,
    TextAlign.RIGHT: Qt.AlignmentFlag.AlignRight,
    TextAlign.JUSTIFY: Qt.AlignmentFlag.AlignJustify,
}

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


def _child_index(step: int | str) -> int:
    """Narrow a (re-based) path step to the integer child index it must be.

    Both the root tree and a re-based overlay subtree are addressed by integer
    child indices — the reserved ``"overlay"`` token is stripped by
    :meth:`QtRenderer._apply_overlay` before a patch reaches here. This guards the
    boundary so a stray overlay token fails loudly instead of mis-indexing.

    Args:
        step: A path step from a (root-tree or re-based overlay) patch.

    Returns:
        The integer child index.

    Raises:
        RuntimeError: If ``step`` is unexpectedly the reserved overlay token.
    """
    if not isinstance(step, int):
        raise RuntimeError(f"unexpected non-integer path step {step!r}")
    return step


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


class _TextLabel(QLabel):
    """A ``QLabel`` that honours ``max_lines``, ``text_overflow`` and ``line_height``.

    Plain ``QLabel`` has no notion of a line cap, custom leading or per-overflow
    eliding, so when any of those style fields is set the label paints its text
    itself via a ``QTextLayout``: it lays out every wrapped line, draws only the
    first ``max_lines``, applies ``line_height`` as a leading multiplier, and —
    when the text is clipped and ``text_overflow`` is ``ELLIPSIS`` — replaces the
    last visible line with an elided variant. With none of those fields set it
    falls straight back to the stock ``QLabel`` paint so the common case is
    untouched (and QSS-styled exactly as before).
    """

    def __init__(self) -> None:
        """Create the label with no text-flow constraints (stock behaviour)."""
        super().__init__()
        self._max_lines: int | None = None
        self._line_height: float | None = None
        self._ellipsis: bool = False
        self._flow_align: Qt.AlignmentFlag = (
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._text_color: QColor | None = None

    def configure_text_flow(
        self,
        *,
        max_lines: int | None,
        line_height: float | None,
        ellipsis: bool,
        align: Qt.AlignmentFlag,
        color: QColor | None,
    ) -> None:
        """Set the text-flow constraints and refresh the label.

        Args:
            max_lines: Maximum rendered lines, or ``None`` for unlimited.
            line_height: Leading as a multiple of the font height, or ``None``.
            ellipsis: Whether clipped text ends in an ellipsis.
            align: The combined horizontal/vertical alignment flag.
            color: The resolved text color used for custom painting, or ``None``.
        """
        self._max_lines = max_lines
        self._line_height = line_height
        self._ellipsis = ellipsis
        self._flow_align = align
        self._text_color = color
        if self._needs_custom_paint():
            self.setWordWrap(True)
        self.setAlignment(align)
        self.update()

    def _needs_custom_paint(self) -> bool:
        """Whether the custom text layout is required (vs. stock ``QLabel``)."""
        return self._max_lines is not None or self._line_height is not None

    def paintEvent(self, arg__1: QPaintEvent) -> None:
        """Paint the label, using the custom text layout only when needed.

        Args:
            arg__1: The Qt paint event (name mandated by the PySide override).
        """
        if not self._needs_custom_paint():
            super().paintEvent(arg__1)
            return
        painter = QPainter(self)
        # Draw the QSS background/border first — overriding paintEvent skips the
        # style's own widget primitive, so do it explicitly to keep box decoration.
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_Widget, option, painter, self
        )
        pen_color = self._text_color or self.palette().color(
            QPalette.ColorRole.WindowText
        )
        painter.setPen(pen_color)
        self._paint_flowed_text(painter)
        painter.end()

    def _paint_flowed_text(self, painter: QPainter) -> None:
        """Lay out and draw the wrapped text under the flow constraints.

        Args:
            painter: The active painter bound to this widget.
        """
        text = self.text()
        metrics = QFontMetricsF(self.font())
        advance = (
            self._line_height * metrics.height()
            if self._line_height is not None
            else metrics.lineSpacing()
        )
        width = float(max(self.width(), 1))
        option = QTextOption(self._flow_align)
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout = QTextLayout(text, self.font(), painter.device())
        layout.setTextOption(option)
        lines: list[QTextLine] = []
        layout.beginLayout()
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            lines.append(line)
        layout.endLayout()
        visible = lines[: self._max_lines] if self._max_lines is not None else lines
        truncated = len(visible) < len(lines)
        total_height = advance * len(visible)
        top = self._vertical_offset(total_height)
        h_flags = int(self._flow_align & Qt.AlignmentFlag.AlignHorizontal_Mask)
        for index, line in enumerate(visible):
            y = top + index * advance
            is_last = index == len(visible) - 1
            if is_last and truncated and self._ellipsis:
                segment = text[line.textStart() :]
                elided = metrics.elidedText(
                    segment, Qt.TextElideMode.ElideRight, width
                )
                painter.drawText(
                    QRectF(0.0, y, width, advance), h_flags, elided
                )
            else:
                line.draw(painter, QPointF(0.0, y))

    def _vertical_offset(self, total_height: float) -> float:
        """Compute the top y for the text block per the vertical alignment.

        Args:
            total_height: The total height the visible lines occupy.

        Returns:
            The y coordinate at which the first line starts.
        """
        if self._flow_align & Qt.AlignmentFlag.AlignVCenter:
            return max(0.0, (self.height() - total_height) / 2)
        if self._flow_align & Qt.AlignmentFlag.AlignBottom:
            return max(0.0, self.height() - total_height)
        return 0.0


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


#: Duration (ms) of a navigation/drawer transition animation.
_NAV_ANIM_MS = 220


def _new_page() -> tuple[QWidget, QVBoxLayout]:
    """Build a fresh stack page: a widget with a zero-margin single-child layout.

    Returns:
        The page widget and its inner layout (where the screen child is placed).
    """
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    return page, layout


class _NavHost(QWidget):
    """A navigation host wrapping a ``QStackedWidget`` of single-screen pages.

    The ``QStackedWidget`` shows exactly one page at a time; a screen swap adds a
    fresh page, animates it in (slide or fade) over the outgoing one, then drops
    the old page. The renderer's diffable child slot is the *current* page's inner
    layout, so screen-internal patches (``Update``/``Insert``…) flow through the
    generic container path unchanged — only a screen ``Replace`` is intercepted
    to animate. This realizes both :class:`~tempestroid.widgets.Navigator` and
    :class:`~tempestroid.widgets.TabView` (the latter stacks a tab strip above).
    """

    def __init__(self, *, with_tab_bar: bool) -> None:
        """Create the host with an empty initial page.

        Args:
            with_tab_bar: When ``True`` a tab strip is reserved above the stack
                (a ``TabView``); otherwise the stack fills the host (a
                ``Navigator``).
        """
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.tab_bar: _TabBarWidget | None = None
        if with_tab_bar:
            self.tab_bar = _TabBarWidget()
            outer.addWidget(self.tab_bar)
        self.stack: QStackedWidget = QStackedWidget()
        outer.addWidget(self.stack, 1)
        page, layout = _new_page()
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)
        self.current_page: QWidget = page
        self.content_layout: QVBoxLayout = layout
        #: Last navigation depth seen, to tell a push (deeper) from a pop.
        self.nav_depth: int = 0
        # Strong refs to in-flight transition animations so Qt does not GC them
        # mid-flight (mirrors the renderer's _pending task set).
        self._anims: set[QAbstractAnimation] = set()

    def new_content_page(self) -> QVBoxLayout:
        """Add a fresh page to the stack and make it the diffable content slot.

        Returns:
            The new page's inner layout for the renderer to place the screen in.
        """
        page, layout = _new_page()
        self.stack.addWidget(page)
        self.current_page = page
        self.content_layout = layout
        return layout

    def animate_to(self, new_page: QWidget, transition: str, forward: bool) -> None:
        """Animate ``new_page`` in over the current page, then drop the old one.

        Args:
            new_page: The freshly built page already added to the stack.
            transition: ``"slide"``, ``"fade"`` or ``"none"``.
            forward: ``True`` for a push (slide left/in), ``False`` for a pop.
        """
        # Stubs type currentWidget() as non-optional, but it is None on an empty
        # stack — keep the runtime guard.
        old_page = cast("QWidget | None", self.stack.currentWidget())
        width = self.stack.width() or self.width() or 1
        if transition == "none" or old_page is None or old_page is new_page:
            self._finish(new_page, old_page)
            return
        self.stack.setCurrentWidget(new_page)
        if transition == "fade":
            self._animate_fade(new_page, old_page)
        else:
            self._animate_slide(new_page, old_page, width, forward)

    def _animate_slide(
        self, new_page: QWidget, old_page: QWidget, width: int, forward: bool
    ) -> None:
        """Slide the incoming page in from the side (direction by ``forward``).

        Args:
            new_page: The incoming page.
            old_page: The outgoing page.
            width: The slide distance (the stack width).
            forward: ``True`` to slide in from the right (push), else from left.
        """
        start_x = width if forward else -width
        new_page.move(start_x, 0)
        anim = QPropertyAnimation(new_page, b"pos", self)
        anim.setDuration(_NAV_ANIM_MS)
        anim.setStartValue(QPoint(start_x, 0))
        anim.setEndValue(QPoint(0, 0))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._run(anim, new_page, old_page)

    def _animate_fade(self, new_page: QWidget, old_page: QWidget) -> None:
        """Cross-fade the incoming page in by animating its window opacity.

        Args:
            new_page: The incoming page.
            old_page: The outgoing page.
        """
        effect = QGraphicsOpacityEffect(new_page)
        new_page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(_NAV_ANIM_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._run(anim, new_page, old_page)

    def _run(
        self, anim: QPropertyAnimation, new_page: QWidget, old_page: QWidget
    ) -> None:
        """Start a one-shot transition animation, dropping the old page on finish.

        Args:
            anim: The configured animation.
            new_page: The incoming page.
            old_page: The outgoing page to remove when the animation settles.
        """
        self._anims.add(anim)

        def _done() -> None:
            self._anims.discard(anim)
            self._finish(new_page, old_page)

        anim.finished.connect(_done)
        anim.start()

    def _finish(self, new_page: QWidget, old_page: QWidget | None) -> None:
        """Settle the transition: show the new page and discard the old one.

        Args:
            new_page: The incoming page (becomes current).
            old_page: The outgoing page to remove, if distinct.
        """
        new_page.move(0, 0)
        new_page.setGraphicsEffect(None)  # pyright: ignore[reportArgumentType]
        self.stack.setCurrentWidget(new_page)
        if old_page is not None and old_page is not new_page:
            self.stack.removeWidget(old_page)
            old_page.setParent(None)  # type: ignore[call-overload]
            old_page.deleteLater()


class _TabBarWidget(QWidget):
    """A horizontal strip of tab buttons emitting a typed route-change on tap.

    The active tab is rendered pressed/flat; tapping any tab forwards a
    :class:`~tempestroid.widgets.RouteChangeEvent` (with ``params["index"]``)
    through the renderer's dispatch callback into the bound handler.
    """

    def __init__(self) -> None:
        """Create an empty tab strip."""
        super().__init__()
        self._layout: QHBoxLayout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._buttons: list[QPushButton] = []
        self._handler: object | None = None
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None

    def configure(
        self,
        tabs: list[str],
        active: int,
        handler: object,
        dispatch: Callable[[Any, Event], None],
    ) -> None:
        """Rebuild the tab buttons and install the change handler.

        Idempotent: the strip is rebuilt from the labels each call, so an
        ``Update`` to ``tabs``/``active`` re-renders cleanly.

        Args:
            tabs: The ordered tab labels.
            active: The selected tab index.
            handler: The change handler (or ``None``).
            dispatch: Callback invoked as ``dispatch(handler, event)``.
        """
        self._handler = handler
        self._dispatch = dispatch
        for button in self._buttons:
            self._layout.removeWidget(button)
            button.setParent(None)  # type: ignore[call-overload]
            button.deleteLater()
        self._buttons = []
        for index, label in enumerate(tabs):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(index == active)
            button.clicked.connect(self._make_tap(index, label))
            self._layout.addWidget(button, 1)
            self._buttons.append(button)

    def _make_tap(self, index: int, label: str) -> Callable[[], None]:
        """Build a click slot that emits the route-change for ``index``.

        Args:
            index: The tab's index.
            label: The tab's label (used as the route name).

        Returns:
            A zero-argument slot suitable for ``clicked.connect``.
        """

        def _tap() -> None:
            if self._handler is not None:
                self._dispatch(
                    self._handler,
                    RouteChangeEvent(name=label, params={"index": index}),
                )

        return _tap


class _DrawerHost(QWidget):
    """A drawer-as-route host: content under a side panel that slides on toggle.

    The content widget fills the host; the drawer panel is a direct child laid
    over the right portion. Toggling ``open`` slides the panel in/out with a
    one-shot :class:`QPropertyAnimation`; a scrim swallows taps on the content
    while open. This is the Qt realization of
    :class:`~tempestroid.widgets.RouteDrawer`.
    """

    #: Drawer panel width as a fraction of the host width.
    _PANEL_FRACTION = 0.7

    def __init__(self) -> None:
        """Create the host with placeholders for the content and drawer."""
        super().__init__()
        self.content: QWidget | None = None
        self.drawer: QWidget | None = None
        self._open: bool = False
        self._anims: set[QAbstractAnimation] = set()

    def set_children(self, content: QWidget, drawer: QWidget) -> None:
        """Adopt the content and drawer widgets as direct children.

        Args:
            content: The main content widget (fills the host).
            drawer: The slide-over panel widget.
        """
        self.content = content
        self.drawer = drawer
        content.setParent(self)
        drawer.setParent(self)
        content.lower()
        drawer.raise_()
        self._relayout(animate=False)

    def set_open(self, is_open: bool) -> None:
        """Open or close the drawer, animating the panel position.

        Args:
            is_open: The desired open state.
        """
        changed = is_open != self._open
        self._open = is_open
        self._relayout(animate=changed)

    def _panel_width(self) -> int:
        """Return the drawer panel width for the current host width."""
        return max(1, int(self.width() * self._PANEL_FRACTION))

    def _relayout(self, *, animate: bool) -> None:
        """Position the content and the drawer panel for the current state.

        Args:
            animate: When ``True``, slide the panel to its target x; otherwise
                snap it.
        """
        if self.content is not None:
            self.content.setGeometry(0, 0, self.width(), self.height())
        if self.drawer is None:
            return
        panel_w = self._panel_width()
        self.drawer.resize(panel_w, self.height())
        self.drawer.raise_()
        target_x = self.width() - panel_w if self._open else self.width()
        if not animate:
            self.drawer.move(target_x, 0)
            self.drawer.setVisible(self._open or self.drawer.x() < self.width())
            return
        anim = QPropertyAnimation(self.drawer, b"pos", self)
        anim.setDuration(_NAV_ANIM_MS)
        anim.setStartValue(self.drawer.pos())
        anim.setEndValue(QPoint(target_x, 0))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.drawer.setVisible(True)
        self._anims.add(anim)
        anim.finished.connect(lambda: self._anims.discard(anim))
        anim.start()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Re-lay the content and panel on resize.

        Args:
            event: The Qt resize event (name mandated by the PySide override).
        """
        self._relayout(animate=False)
        super().resizeEvent(event)


class _RefreshOverlay(QWidget):
    """A thin pull-to-refresh banner pinned to the top of a virtualized list.

    Hidden by default; shown (with a busy progress bar) while the node's
    ``refreshing`` prop is ``True``. The device renderer uses Material's
    ``PullToRefreshBox`` — the simulator stands in with this manual overlay
    (a documented Qt-vs-Compose divergence).
    """

    _HEIGHT = 28

    def __init__(self, parent: QWidget) -> None:
        """Create the overlay parented to a scroll area's viewport.

        Args:
            parent: The widget the overlay floats over (the scroll viewport).
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self._bar: QProgressBar = QProgressBar()
        self._bar.setRange(0, 0)  # busy/indeterminate
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        layout.addWidget(self._bar)
        self.setVisible(False)

    def set_refreshing(self, refreshing: bool) -> None:
        """Show or hide the refresh banner.

        Args:
            refreshing: Whether the list is currently refreshing.
        """
        self.setVisible(refreshing)
        parent = self.parentWidget()
        if refreshing and parent is not None:
            self.resize(parent.width(), self._HEIGHT)
            self.move(0, 0)
            self.raise_()


class _LazyScrollArea(QScrollArea):
    """A scroll area that renders the materialized window of a virtual list.

    Since the E1 core change a ``LazyColumn``/``LazyRow``/``SectionList`` arrives
    at the renderer with its visible window already materialized into the IR
    ``children`` (each keyed by absolute index). This area is therefore an
    ordinary scrollable box container: the renderer mounts those children into the
    inner content layout (exposed as the rendered node's ``layout``) through the
    generic container path, and child patches (insert/remove/reorder/update) — the
    minimal patch sequence the keyed diff produces when the application slides the
    window — apply unchanged.

    On top of that it wires virtual-list behaviour: the scrollbar's movement is
    forwarded as a :class:`~tempestroid.widgets.events.ScrollEvent` offset (the
    application turns that offset into a new ``window`` via
    :meth:`~tempestroid.core.state.App.slide_window`), an
    :class:`~tempestroid.widgets.events.EndReachedEvent` fires once the scroll
    crosses ``end_reached_threshold``, and a refresh overlay shows while
    ``refreshing`` is set. The window is **never** computed here — the app owns it.
    """

    def __init__(self, *, horizontal: bool) -> None:
        """Create the area with an empty content widget and its scroll wiring.

        Args:
            horizontal: ``True`` for a ``LazyRow`` (items laid left-to-right),
                ``False`` for a ``LazyColumn``/``SectionList`` (top-to-bottom).
        """
        super().__init__()
        self.setWidgetResizable(True)
        self._horizontal: bool = horizontal
        content = QWidget()
        self._content: QWidget = content
        layout: QBoxLayout = (
            QHBoxLayout(content) if horizontal else QVBoxLayout(content)
        )
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.content_layout: QBoxLayout = layout
        self.setWidget(content)
        self._on_scroll: Callable[[float], None] | None = None
        self._on_end_reached: Callable[[], None] | None = None
        self._threshold: float = 0.8
        self._end_fired: bool = False
        self.overlay: _RefreshOverlay = _RefreshOverlay(self)
        #: Sticky section header floated over the viewport top (``SectionList``
        #: only; hidden for plain lazy lists). The simulator's stand-in for
        #: Compose's native ``stickyHeader`` (a documented divergence).
        self.sticky: QLabel = QLabel(self.viewport())
        self.sticky.setAutoFillBackground(True)
        self.sticky.setVisible(False)
        #: ``(header-widget, section-title)`` anchors used to pick the sticky title.
        self._sticky_anchors: list[tuple[QWidget, str]] = []
        self._scrollbar().valueChanged.connect(self._on_scrollbar_value)

    def _scrollbar(self) -> QScrollBar:
        """Return the scroll axis' scrollbar (horizontal or vertical)."""
        if self._horizontal:
            return self.horizontalScrollBar()
        return self.verticalScrollBar()

    def configure_scroll(
        self,
        *,
        threshold: float,
        on_scroll: Callable[[float], None] | None,
        on_end_reached: Callable[[], None] | None,
    ) -> None:
        """Install the scroll/end-reached callbacks and the end threshold.

        Idempotent: re-applied on every ``Update`` to the list node so handler
        changes take effect without rebuilding the area.

        Args:
            threshold: Fraction ``0..1`` of total scroll firing ``on_end_reached``.
            on_scroll: Callback receiving the current scroll offset (logical px).
            on_end_reached: Callback fired once the threshold is crossed.
        """
        self._threshold = threshold
        self._on_scroll = on_scroll
        self._on_end_reached = on_end_reached
        self._end_fired = False

    def set_sticky_anchors(self, anchors: list[tuple[QWidget, str]]) -> None:
        """Install the section header anchors and seed the sticky label.

        Args:
            anchors: Ordered ``(header-widget, section-title)`` pairs for each
                section in the flattened list (empty for a plain lazy list).
        """
        self._sticky_anchors = anchors
        if not anchors:
            self.sticky.setVisible(False)
            return
        self.sticky.setText(anchors[0][1])
        self.sticky.setVisible(True)
        self.sticky.adjustSize()
        self.sticky.resize(self.viewport().width(), self.sticky.height())
        self.sticky.move(0, 0)
        self.sticky.raise_()

    def _update_sticky(self) -> None:
        """Pin the sticky label to the topmost section at the current offset."""
        if not self._sticky_anchors:
            return
        offset = self.verticalScrollBar().value()
        current = self._sticky_anchors[0][1]
        for header, title in self._sticky_anchors:
            if header.y() <= offset:
                current = title
            else:
                break
        if self.sticky.text() != current:
            self.sticky.setText(current)
            self.sticky.adjustSize()
            self.sticky.resize(self.viewport().width(), self.sticky.height())
        self.sticky.raise_()

    def _on_scrollbar_value(self, _value: int) -> None:
        """Scrollbar slot: emit the scroll offset and the end-reached crossing.

        Args:
            _value: The new scrollbar value (unused; read directly for clarity).
        """
        bar = self._scrollbar()
        offset = float(bar.value())
        if self._on_scroll is not None:
            self._on_scroll(offset)
        maximum = bar.maximum()
        fraction = offset / maximum if maximum > 0 else 0.0
        if fraction >= self._threshold and maximum > 0:
            if not self._end_fired and self._on_end_reached is not None:
                self._end_fired = True
                self._on_end_reached()
        else:
            self._end_fired = False
        self._update_sticky()

    def item_widgets(self) -> list[QWidget]:
        """Return the currently materialized window item widgets, in order.

        Returns:
            The window item widgets the inner content layout holds (skipping any
            stretch spacers the main-axis sync may have inserted).
        """
        widgets: list[QWidget] = []
        for index in range(self.content_layout.count()):
            item = self.content_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widgets.append(widget)
        return widgets

    def resizeEvent(self, arg__1: QResizeEvent) -> None:
        """Keep the refresh overlay and sticky header spanning the viewport width.

        Args:
            arg__1: The Qt resize event (name mandated by the PySide override).
        """
        super().resizeEvent(arg__1)
        if self.overlay.isVisible():
            self.overlay.resize(self.viewport().width(), self.overlay.height())
        if self.sticky.isVisible():
            self.sticky.resize(self.viewport().width(), self.sticky.height())
            self.sticky.move(0, 0)
            self.sticky.raise_()


class _LazyGridArea(QScrollArea):
    """A scroll area that renders a virtual grid's materialized window.

    Like :class:`_LazyScrollArea` but lays the window children in a fixed-column
    ``QGridLayout`` (filling left-to-right, top-to-bottom). Because a grid is not a
    ``QBoxLayout``, the renderer does **not** drive it through the generic
    container path: it owns the child ordering in the ``_Rendered`` node and calls
    :meth:`set_items` to re-place every window child on each structural patch
    (mirroring how the renderer drives a ``Stack``).
    """

    def __init__(self) -> None:
        """Create the grid area with an empty content widget and scroll wiring."""
        super().__init__()
        self.setWidgetResizable(True)
        content = QWidget()
        self._content: QWidget = content
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self._grid: QGridLayout = grid
        self.setWidget(content)
        self._columns: int = 2
        self._items: list[QWidget] = []
        self._on_scroll: Callable[[float], None] | None = None
        self._on_end_reached: Callable[[], None] | None = None
        self._threshold: float = 0.8
        self._end_fired: bool = False
        self.verticalScrollBar().valueChanged.connect(self._on_scrollbar_value)

    def configure_scroll(
        self,
        *,
        columns: int,
        threshold: float,
        on_scroll: Callable[[float], None] | None,
        on_end_reached: Callable[[], None] | None,
    ) -> None:
        """Install the column count and the scroll/end-reached callbacks.

        Idempotent. A ``columns`` change re-flows the current window children.

        Args:
            columns: Fixed number of grid columns.
            threshold: Fraction ``0..1`` of total scroll firing ``on_end_reached``.
            on_scroll: Callback receiving the current scroll offset (logical px).
            on_end_reached: Callback fired once the threshold is crossed.
        """
        self._threshold = threshold
        self._on_scroll = on_scroll
        self._on_end_reached = on_end_reached
        self._end_fired = False
        if columns != self._columns:
            self._columns = max(1, columns)
            self._reflow()

    def set_items(self, widgets: list[QWidget]) -> None:
        """Replace the grid's window children and re-flow them.

        Args:
            widgets: The materialized window item widgets, in window order.
        """
        self._items = widgets
        self._reflow()

    def _reflow(self) -> None:
        """Re-place the current window children in a ``columns``-wide grid."""
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)  # type: ignore[call-overload]
        for index, widget in enumerate(self._items):
            widget.setParent(self._content)
            self._grid.addWidget(widget, index // self._columns, index % self._columns)

    def _on_scrollbar_value(self, _value: int) -> None:
        """Scrollbar slot: emit the scroll offset and the end-reached crossing.

        Args:
            _value: The new scrollbar value (unused; read directly for clarity).
        """
        bar = self.verticalScrollBar()
        offset = float(bar.value())
        if self._on_scroll is not None:
            self._on_scroll(offset)
        maximum = bar.maximum()
        fraction = offset / maximum if maximum > 0 else 0.0
        if fraction >= self._threshold and maximum > 0:
            if not self._end_fired and self._on_end_reached is not None:
                self._end_fired = True
                self._on_end_reached()
        else:
            self._end_fired = False

    def item_widgets(self) -> list[QWidget]:
        """Return the currently placed window item widgets, in window order.

        Returns:
            The grid's window item widgets.
        """
        return list(self._items)

class _ScrimWidget(QWidget):
    """A semi-transparent barrier drawn over the root while an overlay is open.

    Parented to the renderer's host, raised above the root tree, and stretched to
    cover it. It paints a ``rgba(0,0,0,0.4)`` veil and swallows mouse presses so
    taps never reach the blocked content behind it; a press on the scrim invokes
    the dismiss callback (the Qt analogue of the device's ``__dismiss__:<id>``
    barrier tap). Hidden whenever no barrier overlay is open.
    """

    def __init__(self, parent: QWidget) -> None:
        """Create the scrim parented to (and covering) the host.

        Args:
            parent: The host widget the scrim veils.
        """
        super().__init__(parent)
        self.setStyleSheet("background: rgba(0, 0, 0, 0.4);")
        self.setVisible(False)
        self._on_tap: Callable[[], None] = lambda: None

    def configure(self, on_tap: Callable[[], None]) -> None:
        """Install the barrier-tap callback (dismiss the topmost barrier overlay).

        Args:
            on_tap: Invoked when the user taps the scrim.
        """
        self._on_tap = on_tap

    def cover(self) -> None:
        """Stretch the scrim to fill its parent and raise it above the root."""
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), parent.height())
        self.raise_()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Swallow the press and dismiss the barrier overlay.

        Args:
            event: The Qt mouse press event (consumed, not forwarded).
        """
        self._on_tap()
        event.accept()


class _DismissDialog(QDialog):
    """A ``QDialog`` that reports its close (X / Esc) through a callback.

    Used for ``Dialog``/``BottomSheet``/``Popover`` overlays: closing the dialog
    by any host-owned means (the title-bar close, ``Esc``, or a programmatic
    ``close``) fires the dismiss callback once, so the renderer can route it to
    ``on_dismiss`` + ``App.dismiss`` exactly like the device's barrier tap.
    """

    def __init__(self) -> None:
        """Create the dialog with no dismiss callback yet."""
        super().__init__()
        self._on_dismiss: Callable[[], None] = lambda: None
        self._suppress: bool = False

    def configure_dismiss(self, on_dismiss: Callable[[], None]) -> None:
        """Install the dismiss callback fired on a user-initiated close.

        Args:
            on_dismiss: Invoked once when the dialog is closed by the user.
        """
        self._on_dismiss = on_dismiss

    def close_silently(self) -> None:
        """Close the dialog without firing the dismiss callback.

        Used when the overlay leaves via a ``Remove`` patch (the app already
        dismissed it), so the dialog tears down without re-entering dismiss.
        """
        self._suppress = True
        self.close()

    def closeEvent(self, arg__1: Any) -> None:  # noqa: ANN401 — Qt close event
        """Fire the dismiss callback on a user-initiated close, then close.

        Args:
            arg__1: The Qt close event (name mandated by the PySide override).
        """
        if not self._suppress:
            self._on_dismiss()
        super().closeEvent(arg__1)


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
        # The floating overlay layer, parallel to ``Scene.overlays`` (ascending
        # z-order). Each overlay's backing widget is a top-level surface
        # (QDialog/QMenu/QLabel), not a child of the host tree.
        self._overlays: list[_Rendered] = []
        # Shared barrier scrim drawn over the root when a ``barrier`` overlay is
        # open; tapping it dismisses the topmost barrier overlay.
        self._scrim: _ScrimWidget = _ScrimWidget(self.host)
        # Callback invoked to remove an overlay from the app layer (the Qt
        # analogue of the device's ``__dismiss__:<id>`` token). Wired by
        # ``run_qt``/``Simulator`` to ``App.dismiss``; a no-op otherwise so the
        # renderer works standalone in unit tests (it still tears the widget down
        # when the matching ``Remove`` patch arrives).
        self._dismiss_overlay: Callable[[str], None] = lambda _overlay_id: None
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
        # Strong refs to in-flight overlay animations (bottom-sheet slide) so Qt
        # does not GC them mid-flight.
        self._pending_anims: set[QAbstractAnimation] = set()
        # Live password-reveal toggle actions, keyed by line-edit id, so a secure
        # Input keeps a single eye action across idempotent re-applies.
        self._eye_actions: dict[int, QAction] = {}

    def set_dismiss_overlay(self, dismiss: Callable[[str], None]) -> None:
        """Wire the callback that removes an overlay from the app layer.

        The app runner (``run_qt``/``Simulator``) passes ``App.dismiss`` here so a
        host-owned overlay dismissal (a dialog closed, a menu selected, the scrim
        tapped) removes the overlay from the floating layer — the Qt analogue of
        the device bridge routing ``__dismiss__:<id>`` to ``App.dismiss``.

        Args:
            dismiss: Callback taking an overlay id to remove.
        """
        self._dismiss_overlay = dismiss

    @staticmethod
    def _as_scene(root: Node | Scene) -> Scene:
        """Coerce a bare root node into a :class:`Scene` with no overlays.

        The runtime always mounts a :class:`Scene`; tests (and any caller with
        only a root tree) may pass a bare :class:`Node`, which is wrapped into an
        overlay-free scene so both call shapes work.

        Args:
            root: A :class:`Scene`, or a bare root :class:`Node`.

        Returns:
            The scene to mount.
        """
        return root if isinstance(root, Scene) else Scene(root=root)

    def mount(self, root: Node | Scene) -> QWidget:
        """Build the initial scene (root tree + overlay layer) into the host.

        Args:
            root: The :class:`Scene` to render — its root tree fills the host and
                its overlay layer is realized as floating top-level surfaces. A
                bare :class:`Node` is accepted too (wrapped as an overlay-free
                scene) for callers/tests that only have a root tree.

        Returns:
            The host widget to embed in a window or another layout.
        """
        scene = self._as_scene(root)
        self._root = self._create(scene.root)
        self._host_layout.addWidget(self._root.widget)
        for index, overlay_node in enumerate(scene.overlays):
            self._mount_overlay(index, overlay_node)
        self._sync_scrim()
        return self.host

    def remount(self, root: Node | Scene) -> QWidget:
        """Tear down the current scene and mount a fresh one (hot restart).

        Discards the old root widget and any open overlays, cancels in-flight
        handler tasks and clears stale click connections, then mounts the scene
        from scratch — clean state, as a hot *restart* should be.

        Args:
            root: The new :class:`Scene` to render (a bare :class:`Node` is
                accepted too).

        Returns:
            The host widget (unchanged across remounts).
        """
        for task in self._pending:
            task.cancel()
        self._pending.clear()
        self._click_conns.clear()
        self._value_conns.clear()
        self._eye_actions.clear()
        for overlay in self._overlays:
            self._teardown_overlay(overlay)
        self._overlays = []
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
        """Apply a single patch, routing overlay-layer patches separately.

        A patch whose path starts with the reserved ``"overlay"`` token targets
        the floating overlay layer; everything else flows through the root-tree
        path unchanged.

        Args:
            patch: The patch to apply.
        """
        if patch.path and patch.path[0] == _OVERLAY_STEP:
            self._apply_overlay(patch)
            return
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

    # --- overlay layer -----------------------------------------------------

    def _apply_overlay(self, patch: Patch) -> None:
        """Apply a patch whose path targets the floating overlay layer.

        Three shapes are handled, mirroring ``diff_scene``'s overlay paths:

        * ``("overlay",)`` — a layer-level structural patch (insert/remove/reorder
          an overlay).
        * ``("overlay", i)`` — an :class:`Update`/:class:`Replace` of overlay
          ``i`` itself.
        * ``("overlay", i, ...)`` — a patch inside overlay ``i``'s subtree.

        Args:
            patch: The overlay-layer patch (its path starts with ``"overlay"``).
        """
        if len(patch.path) == 1:
            self._apply_overlay_layer(patch)
            return
        index = _child_index(patch.path[1])
        overlay = self._overlays[index]
        # Re-base the patch onto the overlay subtree: drop the ("overlay", i)
        # prefix and run the standard machinery with the overlay as the root.
        rebased = self._rebase(patch)
        if len(patch.path) == 2 and isinstance(patch, Replace):
            self._replace_overlay(index, overlay, patch)
            return
        if len(patch.path) == 2 and isinstance(patch, Update):
            self._update_overlay(overlay, patch)
            return
        saved = self._root
        self._root = overlay
        try:
            self._apply_one(rebased)
        finally:
            self._root = saved

    @staticmethod
    def _rebase(patch: Patch) -> Patch:
        """Strip the leading ``("overlay", i)`` prefix from a patch's path.

        Args:
            patch: An overlay patch whose path is ``("overlay", i, ...)``.

        Returns:
            A copy of the patch with the two-step overlay prefix removed, so the
            standard root-tree machinery can apply it against the overlay subtree.
        """
        return patch.model_copy(update={"path": patch.path[2:]})

    def _apply_overlay_layer(self, patch: Patch) -> None:
        """Apply an ``("overlay",)`` layer-level insert/remove/reorder.

        Args:
            patch: The layer-level patch.
        """
        if isinstance(patch, Insert):
            self._mount_overlay(patch.index, patch.node)
        elif isinstance(patch, Remove):
            overlay = self._overlays.pop(patch.index)
            self._teardown_overlay(overlay)
        elif isinstance(patch, Reorder):
            self._overlays = [self._overlays[old] for old in patch.order]
            self._restack_overlays()
        self._sync_scrim()

    def _update_overlay(self, overlay: _Rendered, patch: Update) -> None:
        """Update an overlay node's own props (title/items/barrier/handlers).

        Args:
            overlay: The rendered overlay node.
            patch: The update patch (its path is ``("overlay", i)``).
        """
        overlay.props.update(patch.set_props)
        for name in patch.unset_props:
            overlay.props.pop(name, None)
        self._refresh_overlay(overlay)
        self._sync_scrim()

    def _replace_overlay(
        self, index: int, old: _Rendered, patch: Replace
    ) -> None:
        """Replace a whole overlay (type/key changed) at ``index``.

        Args:
            index: The overlay's z-order index.
            old: The outgoing rendered overlay.
            patch: The replace patch carrying the new overlay node.
        """
        self._teardown_overlay(old)
        self._overlays.pop(index)
        self._mount_overlay(index, patch.node)
        self._sync_scrim()

    def _mount_overlay(self, index: int, node: Node) -> None:
        """Build an overlay subtree and show its top-level surface.

        Args:
            index: The z-order index to insert the overlay at.
            node: The overlay IR node (carries ``barrier`` + the widget props).
        """
        overlay = self._create(node)
        self._overlays.insert(index, overlay)
        self._present_overlay(overlay)

    def _overlay_id(self, overlay: _Rendered) -> str:
        """Return an overlay's stable id (its ``key``), or the empty string.

        Args:
            overlay: The rendered overlay node.

        Returns:
            The overlay id used to route a dismiss back to ``App.dismiss``.
        """
        return overlay.key or ""

    def _dismiss(self, overlay: _Rendered, handler: object) -> None:
        """Route a host-owned overlay dismissal: handler + ``App.dismiss``.

        Invokes the overlay's ``on_dismiss`` handler (when wired) with a typed
        :class:`DismissEvent`, then removes it from the app layer via the wired
        ``App.dismiss`` — mirroring the device bridge's ``__dismiss__:<id>``
        routing. Both are idempotent, so a handler that already dismisses is safe.

        Args:
            overlay: The rendered overlay being dismissed.
            handler: The overlay's ``on_dismiss`` handler, or ``None``.
        """
        overlay_id = self._overlay_id(overlay)
        if handler is not None:
            self._invoke(
                cast("Callable[..., Any]", handler),
                DismissEvent(overlay_id=overlay_id or None),
            )
        self._dismiss_overlay(overlay_id)

    def _select(self, overlay: _Rendered, item: MenuItem) -> None:
        """Route a menu/action-sheet selection: ``on_select`` + dismiss.

        Args:
            overlay: The rendered menu/action-sheet overlay.
            item: The selected item.
        """
        handler = overlay.props.get("on_select")
        if handler is not None:
            self._invoke(
                cast("Callable[..., Any]", handler),
                MenuSelectEvent(value=item.value, label=item.label),
            )
        self._dismiss_overlay(self._overlay_id(overlay))

    def _present_overlay(self, overlay: _Rendered) -> None:
        """Show an overlay's top-level surface for the first time.

        ``QDialog``-backed overlays are shown non-modally (the scrim provides the
        barrier so the asyncio loop keeps running); ``QMenu`` overlays pop up at
        their anchor/cursor; the ``QLabel`` toast floats over the host.

        Args:
            overlay: The freshly created rendered overlay.
        """
        widget = overlay.widget
        if isinstance(widget, _DismissDialog):
            self._show_dialog_surface(overlay, widget)
        elif isinstance(widget, QMenu):
            self._popup_menu(overlay, widget)
        elif overlay.type in ("Toast", "Tooltip"):
            self._float_label(overlay, cast("QLabel", widget))

    def _show_dialog_surface(
        self, overlay: _Rendered, dialog: _DismissDialog
    ) -> None:
        """Position and show a ``Dialog``/``BottomSheet``/``Popover`` surface.

        A ``BottomSheet`` is anchored to the host's bottom edge and slides up; a
        ``Popover`` is placed near its anchor; a ``Dialog`` centres on the host.

        Args:
            overlay: The rendered overlay.
            dialog: The backing dialog widget.
        """
        dialog.show()
        host_geom = self.host.geometry()
        host_global = self.host.mapToGlobal(QPoint(0, 0))
        dialog.adjustSize()
        if overlay.type == "BottomSheet":
            width = host_geom.width()
            dialog.setFixedWidth(max(width, 1))
            target_y = host_global.y() + host_geom.height() - dialog.height()
            start = QPoint(host_global.x(), host_global.y() + host_geom.height())
            dialog.move(start)
            anim = QPropertyAnimation(dialog, b"pos", dialog)
            anim.setDuration(_NAV_ANIM_MS)
            anim.setStartValue(start)
            anim.setEndValue(QPoint(host_global.x(), target_y))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            # Keep a strong ref so Qt does not GC the animation mid-slide.
            self._pending_anims.add(anim)
            anim.finished.connect(lambda: self._pending_anims.discard(anim))
        elif overlay.type == "Popover":
            anchor = self._anchor_global(overlay)
            dialog.move(anchor if anchor is not None else host_global)
        else:
            x = host_global.x() + (host_geom.width() - dialog.width()) // 2
            y = host_global.y() + (host_geom.height() - dialog.height()) // 2
            dialog.move(x, y)

    def _popup_menu(self, overlay: _Rendered, menu: QMenu) -> None:
        """Pop up a ``Menu``/``ActionSheet`` at its anchor (or the cursor).

        ``exec`` is intentionally avoided (it spins a nested modal loop that would
        block the qasync loop); ``popup`` shows the menu non-blocking and the
        ``triggered`` signal (wired at creation) carries the selection back.

        Args:
            overlay: The rendered menu overlay.
            menu: The backing ``QMenu``.
        """
        anchor = self._anchor_global(overlay)
        if anchor is None:
            host_global = self.host.mapToGlobal(QPoint(0, 0))
            anchor = host_global
        menu.popup(anchor)

    def _float_label(self, overlay: _Rendered, label: QLabel) -> None:
        """Float a toast/tooltip label over the host and (for toasts) fade it.

        Args:
            overlay: The rendered overlay.
            label: The backing label widget.
        """
        label.adjustSize()
        host_geom = self.host.geometry()
        host_global = self.host.mapToGlobal(QPoint(0, 0))
        x = host_global.x() + (host_geom.width() - label.width()) // 2
        if overlay.type == "Toast":
            y = host_global.y() + host_geom.height() - label.height() - 24
        else:
            anchor = self._anchor_global(overlay)
            y = (anchor.y() if anchor is not None else host_global.y() + 24)
        label.move(x, y)
        label.show()
        if overlay.type == "Toast":
            self._schedule_toast_fade(overlay, label)

    def _schedule_toast_fade(self, overlay: _Rendered, label: QLabel) -> None:
        """Fade a toast out just before the app-side timer removes it.

        The Python ``App.toast`` ``loop.call_later`` stays authoritative for the
        actual removal (a ``Remove`` patch); this only adds a visual fade so the
        toast does not vanish abruptly.

        Args:
            overlay: The rendered toast overlay.
            label: The toast label.
        """
        duration_s = float(cast("float", overlay.props.get("duration_s", 2.5)))
        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", label)
        anim.setDuration(_TOAST_FADE_MS)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        timer = QTimer(label)
        timer.setSingleShot(True)
        start_after = max(int(duration_s * 1000) - _TOAST_FADE_MS, 0)
        timer.setInterval(start_after)
        timer.timeout.connect(anim.start)
        timer.start()

    def _anchor_global(self, overlay: _Rendered) -> QPoint | None:
        """Resolve an overlay's anchor key to a global screen point.

        Args:
            overlay: The rendered overlay (its ``anchor`` prop names a widget key).

        Returns:
            The bottom-left corner of the anchor widget in global coords, or
            ``None`` when the overlay has no anchor or the key is not found.
        """
        anchor_key = cast("str | None", overlay.props.get("anchor"))
        if anchor_key is None or self._root is None:
            return None
        target = self._find_by_key(self._root, anchor_key)
        if target is None:
            return None
        return target.widget.mapToGlobal(QPoint(0, target.widget.height()))

    def _find_by_key(self, node: _Rendered, key: str) -> _Rendered | None:
        """Depth-first search the root subtree for a node with ``key``.

        Args:
            node: The subtree root to search.
            key: The target node key.

        Returns:
            The matching rendered node, or ``None``.
        """
        if node.key == key:
            return node
        for child in node.children:
            found = self._find_by_key(child, key)
            if found is not None:
                return found
        return None

    def _fill_menu(self, overlay: _Rendered, menu: QMenu) -> None:
        """(Re)build a ``QMenu`` from an overlay's ``items`` and wire selection.

        Idempotent: the menu is cleared and rebuilt each call so an ``Update`` to
        ``items``/``title`` re-renders cleanly. An ``ActionSheet`` title becomes a
        disabled section header at the top.

        Args:
            overlay: The rendered ``Menu``/``ActionSheet`` overlay.
            menu: The backing ``QMenu``.
        """
        menu.clear()
        title = cast("str | None", overlay.props.get("title"))
        if title:
            menu.addSection(title)
        items = cast("list[MenuItem]", overlay.props.get("items", []))
        for item in items:
            action = menu.addAction(item.label)
            action.triggered.connect(self._make_select(overlay, item))

    def _make_select(
        self, overlay: _Rendered, item: MenuItem
    ) -> Callable[[], None]:
        """Build a triggered slot that selects ``item`` from ``overlay``.

        Args:
            overlay: The rendered menu overlay.
            item: The item the action represents.

        Returns:
            A zero-argument slot for ``QAction.triggered``.
        """
        return lambda: self._select(overlay, item)

    def _refresh_overlay(self, overlay: _Rendered) -> None:
        """Re-apply an overlay node's own visual after a prop ``Update``.

        ``_apply_visual`` already re-renders the overlay's content (menu items,
        toast text, dialog title) and re-wires its handlers idempotently, so this
        is a thin delegation kept distinct for the dismiss/scrim re-sync around it.

        Args:
            overlay: The rendered overlay node.
        """
        self._apply_visual(overlay)

    def _restack_overlays(self) -> None:
        """Re-raise overlay surfaces in ascending z-order after a reorder."""
        for overlay in self._overlays:
            widget = overlay.widget
            if widget.isWindow():
                widget.raise_()

    def _teardown_overlay(self, overlay: _Rendered) -> None:
        """Close and discard an overlay's top-level surface and connections.

        Args:
            overlay: The rendered overlay leaving the layer (via ``Remove`` or a
                hot remount).
        """
        self._purge_connections(overlay)
        widget = overlay.widget
        if isinstance(widget, _DismissDialog):
            widget.close_silently()
        elif isinstance(widget, QMenu):
            widget.close()
        self._discard(widget)

    def _sync_scrim(self) -> None:
        """Show/hide and position the barrier scrim under the topmost barrier.

        The scrim sits directly below the topmost ``barrier`` overlay's surface
        and dismisses that overlay when tapped. With no barrier overlay open it is
        hidden.
        """
        barrier_overlays = [
            overlay
            for overlay in self._overlays
            if bool(overlay.props.get("barrier", False))
        ]
        if not barrier_overlays:
            self._scrim.setVisible(False)
            return
        topmost = barrier_overlays[-1]
        handler = topmost.props.get("on_dismiss")
        self._scrim.configure(lambda: self._dismiss(topmost, handler))
        self._scrim.cover()
        self._scrim.setVisible(True)

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
                self._purge_connections(old)
                self._discard(old.widget)
            return
        parent = self._at(patch.path[:-1])
        index = _child_index(patch.path[-1])
        old = parent.children[index]
        if parent.type in ("Navigator", "TabView"):
            self._replace_screen(parent, index, old, new)
            return
        if parent.type == "RouteDrawer":
            new.widget.setParent(parent.widget)
            parent.children[index] = new
            self._purge_connections(old)
            self._discard(old.widget)
            self._sync_drawer(parent)
            return
        if parent.type == "Stack":
            new.widget.setParent(parent.widget)
            parent.children[index] = new
            self._purge_connections(old)
            self._discard(old.widget)
            self._relayout_stack(parent)
            return
        if parent.type == "LazyGrid":
            new.widget.setParent(parent.widget)
            parent.children[index] = new
            self._purge_connections(old)
            self._discard(old.widget)
            self._relayout_grid(parent)
            return
        layout = self._require_layout(parent)
        # Strip spacers so the IR index maps to the layout slot for the insert.
        self._strip_spacers(layout)
        layout.insertWidget(index, new.widget, self._stretch(new))
        self._place_alignment(parent, new)
        parent.children[index] = new
        self._purge_connections(old)
        self._discard(old.widget)
        self._sync_main_axis(parent)
        if parent.type == "SectionList":
            self._sync_sticky_header(parent)

    def _replace_screen(
        self, parent: _Rendered, index: int, old: _Rendered, new: _Rendered
    ) -> None:
        """Swap the on-screen child of a Navigator/TabView with a transition.

        Builds a fresh stack page for ``new``, places it, animates it in (slide
        direction inferred from the navigator's ``depth`` delta, or fade/none per
        ``transition``), and updates the host's diffable content slot to the new
        page so screen-internal patches keep flowing through the generic path.

        Args:
            parent: The Navigator/TabView rendered node.
            index: The child index being replaced (always ``0`` for a screen).
            old: The outgoing screen rendered node.
            new: The incoming screen rendered node.
        """
        host = cast("_NavHost", parent.widget)
        transition = cast("str", parent.props.get("transition", "slide"))
        new_depth = int(cast("int", parent.props.get("depth", host.nav_depth)))
        forward = new_depth >= host.nav_depth
        host.nav_depth = new_depth
        layout = host.new_content_page()
        layout.addWidget(new.widget, self._stretch(new))
        self._place_alignment(parent, new)
        parent.layout = layout
        parent.children[index] = new
        host.animate_to(host.current_page, transition, forward)
        self._purge_connections(old)

    def _apply_insert(self, patch: Insert) -> None:
        """Insert a new child subtree under a parent.

        Args:
            patch: The insert patch.
        """
        parent = self._at(patch.path)
        child = self._create(patch.node)
        if parent.type in ("Stack", "RouteDrawer", "LazyGrid"):
            child.widget.setParent(parent.widget)
            parent.children.insert(patch.index, child)
            if parent.type == "RouteDrawer":
                self._sync_drawer(parent)
            elif parent.type == "LazyGrid":
                self._relayout_grid(parent)
            else:
                self._relayout_stack(parent)
            return
        layout = self._require_layout(parent)
        # Strip spacers so the IR index maps to the layout slot for the insert.
        self._strip_spacers(layout)
        parent.children.insert(patch.index, child)
        layout.insertWidget(patch.index, child.widget, self._stretch(child))
        self._place_alignment(parent, child)
        self._sync_main_axis(parent)
        if parent.type == "SectionList":
            self._sync_sticky_header(parent)

    def _apply_remove(self, patch: Remove) -> None:
        """Remove a child subtree from a parent.

        Args:
            patch: The remove patch.
        """
        parent = self._at(patch.path)
        child = parent.children.pop(patch.index)
        if parent.type in ("Stack", "RouteDrawer", "LazyGrid"):
            self._purge_connections(child)
            self._discard(child.widget)
            if parent.type == "RouteDrawer":
                self._sync_drawer(parent)
            elif parent.type == "LazyGrid":
                self._relayout_grid(parent)
            else:
                self._relayout_stack(parent)
            return
        self._require_layout(parent).removeWidget(child.widget)
        self._purge_connections(child)
        self._discard(child.widget)
        self._sync_main_axis(parent)
        if parent.type == "SectionList":
            self._sync_sticky_header(parent)

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
        if parent.type == "RouteDrawer":
            parent.children = new_children
            self._sync_drawer(parent)
            return
        if parent.type == "LazyGrid":
            parent.children = new_children
            self._relayout_grid(parent)
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
        self._sync_main_axis(parent)
        if parent.type == "SectionList":
            self._sync_sticky_header(parent)

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
        if rendered.type in ("Navigator", "TabView"):
            # Seed the host's last-seen depth so the first push/pop after mount
            # picks the right slide direction (updates never touch it again).
            cast("_NavHost", rendered.widget).nav_depth = int(
                cast("int", node.props.get("depth", 0))
            )
        for child_node in node.children:
            child = self._create(child_node)
            rendered.children.append(child)
            if rendered.type in ("Stack", "RouteDrawer", "LazyGrid"):
                # Direct children (no box layout): geometry is renderer-driven.
                child.widget.setParent(rendered.widget)
            elif rendered.type in ("Toast", "Tooltip", "Menu", "ActionSheet"):
                # Leaf overlays render their content from props (message/items),
                # not from a child box layout — keep the child node for the IR
                # mirror but do not add it to a (non-existent) layout.
                continue
            else:
                # LazyColumn/LazyRow/SectionList expose their scroll-area content
                # layout, so the materialized window children flow through the
                # generic container path exactly like a Column/Row.
                self._require_layout(rendered).addWidget(
                    child.widget, self._stretch(child)
                )
                self._place_alignment(rendered, child)
        if rendered.type == "Stack":
            self._relayout_stack(rendered)
        elif rendered.type == "RouteDrawer":
            self._sync_drawer(rendered)
        elif rendered.type == "LazyGrid":
            self._relayout_grid(rendered)
        elif rendered.type in _LAZY_LIST_TYPES:
            self._sync_main_axis(rendered)
            if rendered.type == "SectionList":
                self._sync_sticky_header(rendered)
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
            return _Rendered(node.type, node.key, _TextLabel(), None)
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
        if node.type in _LAZY_LIST_TYPES:
            area = _LazyScrollArea(horizontal=node.type == "LazyRow")
            # The scroll area's inner content layout is the diffable child slot, so
            # the materialized window children flow through the generic path.
            return _Rendered(node.type, node.key, area, area.content_layout)
        if node.type == "LazyGrid":
            return _Rendered(node.type, node.key, _LazyGridArea(), None)
        if node.type == "RefreshControl":
            return _Rendered(node.type, node.key, QProgressBar(), None)
        if node.type in ("Navigator", "TabView"):
            host = _NavHost(with_tab_bar=node.type == "TabView")
            return _Rendered(node.type, node.key, host, host.content_layout)
        if node.type == "TabBar":
            return _Rendered(node.type, node.key, _TabBarWidget(), None)
        if node.type == "RouteDrawer":
            return _Rendered(node.type, node.key, _DrawerHost(), None)
        if node.type == "Stack":
            return _Rendered(node.type, node.key, _StackWidget(), None)
        if node.type == "GestureDetector":
            gesture = _GestureWidget()
            return _Rendered(
                node.type, node.key, gesture, cast("QBoxLayout", gesture.layout())
            )
        if node.type in ("Dialog", "BottomSheet", "Popover"):
            dialog = _DismissDialog()
            layout = QVBoxLayout(dialog)
            if node.type == "Dialog":
                dialog.setWindowFlag(Qt.WindowType.Dialog, True)
            else:
                # Frameless for sheet/popover; the scrim provides the barrier.
                dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            return _Rendered(node.type, node.key, dialog, layout)
        if node.type in ("Menu", "ActionSheet"):
            return _Rendered(node.type, node.key, QMenu(), None)
        if node.type in ("Toast", "Tooltip"):
            label = QLabel()
            label.setWindowFlags(
                Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
            )
            label.setStyleSheet(
                "background: rgba(33, 33, 33, 0.92); color: white;"
                " padding: 8px 14px; border-radius: 8px;"
            )
            return _Rendered(node.type, node.key, label, None)
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
            label = cast("_TextLabel", node.widget)
            label.setText(cast("str", node.props.get("content", "")))
            self._apply_text_flow(label, style)
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
        elif node.type == "TabBar":
            self._apply_tab_bar(cast("_TabBarWidget", node.widget), node.props)
        elif node.type == "TabView":
            host = cast("_NavHost", node.widget)
            if host.tab_bar is not None:
                self._apply_tab_bar(host.tab_bar, node.props)
        elif node.type == "RouteDrawer":
            cast("_DrawerHost", node.widget).set_open(
                bool(node.props.get("open", False))
            )
        elif node.type in _LAZY_LIST_TYPES:
            self._apply_lazy_list(node)
            if node.type == "SectionList":
                self._sync_sticky_header(node)
        elif node.type == "LazyGrid":
            self._apply_lazy_grid(node)
        elif node.type == "RefreshControl":
            self._apply_refresh_control(cast("QProgressBar", node.widget), node.props)
        elif node.type in ("Dialog", "BottomSheet", "Popover"):
            dialog = cast("_DismissDialog", node.widget)
            if node.type == "Dialog":
                dialog.setWindowTitle(cast("str", node.props.get("title", "") or ""))
            dialog.configure_dismiss(
                lambda: self._dismiss(node, node.props.get("on_dismiss"))
            )
        elif node.type in ("Menu", "ActionSheet"):
            self._fill_menu(node, cast("QMenu", node.widget))
        elif node.type in ("Toast", "Tooltip"):
            label = cast("QLabel", node.widget)
            label.setText(cast("str", node.props.get("message", "")))
            # ``_apply_visual`` wiped the constructor QSS with the (usually empty)
            # node style; restore the floating-pill look (a custom style still
            # wins via the merged QSS set above when one is provided).
            if style is None:
                label.setStyleSheet(
                    "background: rgba(33, 33, 33, 0.92); color: white;"
                    " padding: 8px 14px; border-radius: 8px;"
                )
        self._apply_letter_spacing(node.widget, style)
        self._apply_sizing(node.widget, style)
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
    def _text_alignment(style: Style | None) -> Qt.AlignmentFlag:
        """Resolve a Text node's combined alignment flag from ``text_align``.

        ``text_align`` only sets the horizontal half; the vertical half stays a
        centre flag (QLabel's natural baseline). Defaults to left when unset.

        Args:
            style: The Text node's style, or ``None``.

        Returns:
            The combined horizontal | ``AlignVCenter`` alignment flag.
        """
        horizontal = Qt.AlignmentFlag.AlignLeft
        if style is not None and style.text_align is not None:
            horizontal = _TEXT_ALIGN[style.text_align]
        return horizontal | Qt.AlignmentFlag.AlignVCenter

    def _apply_text_flow(self, label: _TextLabel, style: Style | None) -> None:
        """Push a Text node's alignment and text-flow constraints onto its label.

        Args:
            label: The text label to configure.
            style: The Text node's style, or ``None``.
        """
        color: QColor | None = None
        if style is not None and style.color is not None:
            c = style.color
            color = QColor(c.r, c.g, c.b, round(c.a * 255))
        label.configure_text_flow(
            max_lines=style.max_lines if style is not None else None,
            line_height=style.line_height if style is not None else None,
            ellipsis=(
                style is not None
                and style.text_overflow is TextOverflow.ELLIPSIS
            ),
            align=self._text_alignment(style),
            color=color,
        )

    @staticmethod
    def _apply_sizing(widget: QWidget, style: Style | None) -> None:
        """Apply fixed ``width``/``height``/``aspect_ratio`` to a widget.

        Qt stylesheets cannot reliably pin a widget's ``width``/``height`` (only
        ``min``/``max`` map cleanly to QSS), so a fixed size is set imperatively
        here. ``aspect_ratio`` derives the missing dimension from the fixed one
        (``height = width / ratio`` or ``width = height * ratio``); with neither
        dimension fixed it has no anchor in Qt and is left to the device renderer
        (a documented divergence). Idempotent: an unset dimension is restored to
        Qt's flexible ``[0, QWIDGETSIZE_MAX]`` range.

        Args:
            widget: The target widget.
            style: The node's style, or ``None``.
        """
        width = style.width if style is not None else None
        height = style.height if style is not None else None
        ratio = style.aspect_ratio if style is not None else None
        if ratio is not None:
            if width is not None and height is None:
                height = width / ratio
            elif height is not None and width is None:
                width = height * ratio
        if width is not None:
            widget.setFixedWidth(int(width))
        else:
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(_QT_SIZE_MAX)
        if height is not None:
            widget.setFixedHeight(int(height))
        else:
            widget.setMinimumHeight(0)
            widget.setMaximumHeight(_QT_SIZE_MAX)

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

    def _sync_drawer(self, parent: _Rendered) -> None:
        """Push the content/drawer children and ``open`` state into the host.

        Args:
            parent: The ``RouteDrawer`` rendered node.
        """
        host = cast("_DrawerHost", parent.widget)
        if len(parent.children) >= 2:
            host.set_children(parent.children[0].widget, parent.children[1].widget)
        host.set_open(bool(parent.props.get("open", False)))

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

    def _apply_tab_bar(self, widget: _TabBarWidget, props: dict[str, Any]) -> None:
        """Rebuild a tab strip from its props and wire the change handler.

        Args:
            widget: The tab-strip widget.
            props: The node's current props (``tabs``/``active``/``on_change``).
        """
        tabs = cast("list[str]", props.get("tabs", []))
        active = int(cast("int", props.get("active", 0)))
        widget.configure(tabs, active, props.get("on_change"), self._invoke)

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

    # --- virtualized lists -------------------------------------------------

    def _scroll_handler(
        self, node: _Rendered, direction: str
    ) -> Callable[[float], None] | None:
        """Build the offset callback that forwards a list's ``on_scroll``.

        The renderer reports only the raw scroll *offset*; the application turns
        it into a new visible ``window`` (via
        :meth:`~tempestroid.core.state.App.slide_window`) and rebuilds, so the
        keyed diff slides the materialized children. The renderer never computes
        the window itself.

        Args:
            node: The rendered virtual-list node.
            direction: The scroll axis (``"vertical"``/``"horizontal"``).

        Returns:
            A callback taking the scroll offset, or ``None`` when no handler is
            wired.
        """
        on_scroll = node.props.get("on_scroll")
        if on_scroll is None:
            return None
        callback = cast("Callable[..., Any]", on_scroll)
        return lambda offset: self._invoke(
            callback, ScrollEvent(offset=offset, direction=direction)
        )

    def _end_reached_handler(self, node: _Rendered) -> Callable[[], None] | None:
        """Build the callback that forwards a list's ``on_end_reached``.

        Args:
            node: The rendered virtual-list node.

        Returns:
            A zero-argument callback, or ``None`` when no handler is wired.
        """
        on_end_reached = node.props.get("on_end_reached")
        if on_end_reached is None:
            return None
        callback = cast("Callable[..., Any]", on_end_reached)
        return lambda: self._invoke(callback, EndReachedEvent())

    def _apply_lazy_list(self, node: _Rendered) -> None:
        """Wire scroll/end-reached/refresh on a lazy list (column/row/section).

        The materialized window children are mounted through the generic container
        path (this node's ``layout`` is the scroll area's content layout), so this
        only installs the scroll behaviour. Idempotent: re-applied on every
        ``Update`` so handler/threshold/refresh changes take effect in place.

        Args:
            node: The rendered ``LazyColumn``/``LazyRow``/``SectionList`` node.
        """
        area = cast("_LazyScrollArea", node.widget)
        props = node.props
        direction = "horizontal" if node.type == "LazyRow" else "vertical"
        area.configure_scroll(
            threshold=float(cast("float", props.get("end_reached_threshold", 0.8))),
            on_scroll=self._scroll_handler(node, direction),
            on_end_reached=self._end_reached_handler(node),
        )
        area.overlay.set_refreshing(bool(props.get("refreshing", False)))

    def _apply_lazy_grid(self, node: _Rendered) -> None:
        """Wire scroll/end-reached and the column count on a ``LazyGrid``.

        The window children are placed by :meth:`_relayout_grid` (the grid is not a
        box layout, so the renderer owns its child ordering); this installs the
        scroll behaviour and the column count.

        Args:
            node: The rendered ``LazyGrid`` node.
        """
        area = cast("_LazyGridArea", node.widget)
        props = node.props
        area.configure_scroll(
            columns=int(cast("int", props.get("columns", 2))),
            threshold=float(cast("float", props.get("end_reached_threshold", 0.8))),
            on_scroll=self._scroll_handler(node, "vertical"),
            on_end_reached=self._end_reached_handler(node),
        )

    def _relayout_grid(self, node: _Rendered) -> None:
        """Push the current window children into the grid in window order.

        Args:
            node: The rendered ``LazyGrid`` node.
        """
        area = cast("_LazyGridArea", node.widget)
        area.set_items([child.widget for child in node.children])

    @staticmethod
    def _is_section_header(child: _Rendered) -> bool:
        """Whether a flattened ``SectionList`` child is a section header.

        Args:
            child: A materialized ``SectionList`` child rendered node.

        Returns:
            ``True`` when the child's key marks it as a section header
            (``sec:<title>:header``).
        """
        return (
            child.key is not None
            and child.key.startswith(_SECTION_KEY_PREFIX)
            and child.key.endswith(_SECTION_HEADER_SUFFIX)
        )

    def _sync_sticky_header(self, node: _Rendered) -> None:
        """Pin the first section's title into the area's sticky header label.

        The simulator stands in for Compose's native ``stickyHeader`` by floating
        a label over the top of the scroll viewport (a documented Qt-vs-Compose
        divergence). The label tracks the topmost visible section as the list
        scrolls; here it is seeded/refreshed to the first section after a
        structural change.

        Args:
            node: The rendered ``SectionList`` node.
        """
        area = cast("_LazyScrollArea", node.widget)
        anchors = [
            (child.widget, self._section_title(child))
            for child in node.children
            if self._is_section_header(child)
        ]
        area.set_sticky_anchors(anchors)

    @staticmethod
    def _section_title(child: _Rendered) -> str:
        """Recover a section title from a header child's key.

        Args:
            child: A ``SectionList`` header rendered node (key ``sec:<title>:header``).

        Returns:
            The section title, or the empty string when the key is unexpected.
        """
        key = child.key or ""
        body = key[len(_SECTION_KEY_PREFIX) : -len(_SECTION_HEADER_SUFFIX)]
        return body

    @staticmethod
    def _apply_refresh_control(widget: QProgressBar, props: dict[str, Any]) -> None:
        """Apply props to a standalone ``RefreshControl`` (busy bar when active).

        Args:
            widget: The Qt progress bar standing in for the refresh control.
            props: The node's current props.
        """
        refreshing = bool(props.get("refreshing", False))
        widget.setRange(0, 0 if refreshing else 1)
        widget.setTextVisible(False)
        widget.setVisible(refreshing)

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

    def _at(self, path: Path) -> _Rendered:
        """Resolve a rendered node by its path from the current base.

        ``self._root`` is temporarily re-pointed at an overlay subtree by
        :meth:`_apply_overlay` while applying within-overlay patches (whose path
        has had the ``("overlay", i)`` prefix stripped), so the same traversal
        serves both the root tree and overlay subtrees.

        Args:
            path: Child-index steps from the current base.

        Returns:
            The rendered node at that path.

        Raises:
            RuntimeError: If nothing has been mounted yet.
        """
        if self._root is None:
            raise RuntimeError("nothing mounted")
        node = self._root
        for step in path:
            node = node.children[_child_index(step)]
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

    def _purge_connections(self, rendered: _Rendered) -> None:
        """Drop tracked signal connections for a discarded subtree.

        The click/value/eye registries are keyed by ``id(widget)``. ``deleteLater``
        only *schedules* a widget's destruction, so without this the entries
        outlive the widget — a slow leak across remove/replace churn, and a
        correctness hazard once CPython recycles the ``id`` for a fresh widget.
        Walks the whole ``_Rendered`` subtree since handler-bearing widgets may
        sit anywhere below the discarded node.

        Args:
            rendered: The root of the rendered subtree being discarded.
        """
        widget_id = id(rendered.widget)
        self._click_conns.pop(widget_id, None)
        self._value_conns.pop(widget_id, None)
        self._eye_actions.pop(widget_id, None)
        for child in rendered.children:
            self._purge_connections(child)

    @staticmethod
    def _discard(widget: QWidget) -> None:
        """Detach a widget from its parent and schedule deletion.

        Args:
            widget: The widget to discard.
        """
        widget.setParent(None)  # type: ignore[call-overload]
        widget.deleteLater()
