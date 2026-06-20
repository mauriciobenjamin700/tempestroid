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
from pathlib import Path as FsPath
from typing import TYPE_CHECKING, Any, cast
from xml.sax import saxutils

from PySide6.QtCore import (
    QAbstractAnimation,
    QByteArray,
    QDate,
    QEasingCurve,
    QElapsedTimer,
    QEvent,
    QMetaObject,
    QMimeData,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTime,
    QTimer,
    QUrl,
    SignalInstance,
)
from PySide6.QtGui import (
    QAccessible,
    QAction,
    QBrush,
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QGuiApplication,
    QIcon,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QRegion,
    QResizeEvent,
    QTextLayout,
    QTextLine,
    QTextOption,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QFileDialog,
    QGesture,
    QGestureEvent,
    QGraphicsBlurEffect,
    QGraphicsDropShadowEffect,
    QGraphicsEffect,
    QGraphicsOpacityEffect,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPinchGesture,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QStyle,
    QStyleOption,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from tempest_core.core.ir import (
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
from tempest_core.icons import MATERIAL_ALIASES, Icons, icon_path
from tempest_core.style import (
    Border,
    ComponentState,
    Corners,
    Edge,
    FieldVariant,
    JustifyContent,
    Position,
    Shadow,
    Size,
    StackAlign,
    Style,
    TextAlign,
    TextOverflow,
    Variant,
)
from tempest_core.theme import MediaQueryData, Theme, ThemeMode
from tempest_core.variants import (
    ResponsiveSize,
    resolve_field_variant_states,
    resolve_selection_variant_states,
    resolve_slider_variant_states,
    resolve_variant_states,
)
from tempest_core.widgets import (
    DateChangeEvent,
    DismissEvent,
    EndReachedEvent,
    Event,
    FileSelectEvent,
    LongPressEvent,
    MenuItem,
    MenuSelectEvent,
    PageChangeEvent,
    PanEvent,
    RangeChangeEvent,
    ReorderEvent,
    RouteChangeEvent,
    ScaleEvent,
    ScrollEvent,
    SelectEvent,
    Semantics,
    SlideEvent,
    SubmitEvent,
    SwipeDirection,
    SwipeEvent,
    TapEvent,
    TextChangeEvent,
    TimeChangeEvent,
    ToggleEvent,
    handler_accepts_event,
)

from tempestroid.renderers.qt.style_translator import (
    layout_alignment,
    qss_background,
    self_alignment,
    state_layer_qss,
    to_qss,
)

if TYPE_CHECKING:
    from tempest_core.core.state import App

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

#: Advanced-gesture node types whose handlers bind through
#: :meth:`QtRenderer._bind_advanced_gestures` (the phase-E4 widgets).
_ADVANCED_GESTURE_TYPES = frozenset(
    {
        "PanHandler",
        "ScaleHandler",
        "DoubleTapHandler",
        "Draggable",
        "DragTarget",
        "Dismissible",
        "ReorderableList",
        "InteractiveViewer",
    }
)

#: Animation widget types whose backing widget is a box-layout container the
#: generic child path can drive. ``Animated``/``Hero`` wrap one child (the
#: ``view`` already interpolated ``Animated``'s style per frame, so the renderer
#: just mounts the child); ``AnimatedList`` lays children along its main axis and
#: animates inserts/removes via :class:`_AnimatedListWidget`.
_ANIM_CONTAINER_TYPES = frozenset({"Animated", "Hero", "AnimatedList"})

#: Default per-sweep duration (ms) for a ``Shimmer``/``Skeleton`` gradient loop.
_SHIMMER_DEFAULT_MS = 1200

#: E7 media/graphics wrappers whose single IR child flows through the generic
#: child-insertion path (a box-layout container, like ``Animated``); the effect
#: (blur) or mask (clip) is applied on top in ``_apply_visual``.
_E7_WRAPPER_TYPES = frozenset({"Blur", "BackdropFilter", "ClipPath"})

#: E7 widgets with no faithful Qt equivalent in the desktop simulator: they
#: render as a ``QLabel`` placeholder carrying an explicit ``device only`` notice.
#: The device (Compose) renderer realizes the real camera/scanner/map surface.
_E7_PLACEHOLDER_TYPES = frozenset({"CameraPreview", "QrScanner", "MapView"})

#: Per-type placeholder text shown by the simulator for ``_E7_PLACEHOLDER_TYPES``.
_E7_PLACEHOLDER_TEXT: dict[str, str] = {
    "CameraPreview": "[CameraPreview — device only]",
    "QrScanner": "[QrScanner — device only]",
    "MapView": "[MapView — device only]",
}


def _load_multimedia() -> tuple[type[Any], type[Any], type[Any]] | None:
    """Lazily import the Qt multimedia classes used by ``VideoPlayer``.

    ``QtMultimedia`` (and its multimedia backend) may be absent on headless or
    minimal Linux installs, so the import is deferred and failures degrade to a
    placeholder instead of crashing the whole renderer at module load.

    Returns:
        A ``(QMediaPlayer, QAudioOutput, QVideoWidget)`` tuple, or ``None`` when
        the multimedia stack is unavailable.
    """
    try:
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget
    except ImportError:
        return None
    return QMediaPlayer, QAudioOutput, QVideoWidget


def _load_web_engine() -> type[Any] | None:
    """Lazily import ``QWebEngineView`` (ships in a separate PySide6 wheel).

    Returns:
        The ``QWebEngineView`` class, or ``None`` when WebEngine is not
        installed (then ``WebView`` falls back to a placeholder label).
    """
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        return None
    return QWebEngineView


def _load_svg_renderer() -> type[Any] | None:
    """Lazily import ``QSvgRenderer`` from ``QtSvg``.

    Returns:
        The ``QSvgRenderer`` class, or ``None`` when ``QtSvg`` is unavailable.
    """
    try:
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        return None
    return QSvgRenderer


#: Repaint interval (ms) of the shimmer gradient loop (~30fps is plenty smooth
#: for the simulator's loading placeholder).
_SHIMMER_TICK_MS = 33

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

#: Field-family node types whose Chakra ``field_variant``/``size``/``color_scheme``
#: props the renderer re-resolves into M3 hover/focus/disabled state layers via
#: :func:`~tempest_core.variants.resolve_field_variant_states` (the input analogue
#: of the ``Button`` variant path). Each bakes its resting box into ``style``; the
#: renderer paints only the focus/invalid/hover/disabled paint deltas on top.
_FIELD_TYPES = frozenset(
    {
        "Input",
        "TextArea",
        "Dropdown",
        "Autocomplete",
        "MaskedInput",
        "PinInput",
        "DatePicker",
        "TimePicker",
        "FilePicker",
    }
)

#: Selection-family node types (checkbox/switch) whose accent tick, ring and box
#: dimension come from :func:`~tempest_core.variants.resolve_selection_variant_states`.
_SELECTION_TYPES = frozenset({"Checkbox", "Switch"})

#: Slider-family node types whose active/inactive track + thumb colors come from
#: :func:`~tempest_core.variants.resolve_slider_variant_states`.
_SLIDER_TYPES = frozenset({"Slider", "RangeSlider"})

#: Minimum M3 touch-target height (dp) the renderer pins on a checkbox/switch
#: *row* (the box dimension stays ~20dp on the ``::indicator`` sub-control).
_SELECTION_TOUCH_TARGET = 48

_DATE_FORMAT = "yyyy-MM-dd"
#: 24-hour display/parse format for ``TimePicker`` (matches ``"HH:MM"`` strings).
_TIME_FORMAT = "HH:mm"
#: Per-cell pixel width of a ``PinInput`` segment in the simulator.
_PIN_CELL_WIDTH = 40
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

#: Map a :class:`~tempestroid.widgets.Semantics` ``role`` hint to the Qt
#: accessible role the screen reader announces. Unknown roles fall through to no
#: explicit role (``QWidget``'s own default), mirroring the Compose translator
#: which only maps the roles it recognizes.
_ACCESSIBLE_ROLES: dict[str, QAccessible.Role] = {
    "button": QAccessible.Role.Button,
    "image": QAccessible.Role.Graphic,
    "heading": QAccessible.Role.StaticText,
    "text": QAccessible.Role.StaticText,
    "link": QAccessible.Role.Link,
    "checkbox": QAccessible.Role.CheckBox,
    "switch": QAccessible.Role.CheckBox,
    "slider": QAccessible.Role.Slider,
    "progressbar": QAccessible.Role.ProgressBar,
    "list": QAccessible.Role.List,
}

#: Light/dark base palettes (window background + text + button colors) the
#: simulator swaps wholesale when the active :class:`ThemeMode` resolves. These
#: are the Qt analogue of Compose's ``lightColorScheme``/``darkColorScheme`` — a
#: documented divergence: Qt uses a ``QPalette`` + a global stylesheet, Compose a
#: ``MaterialTheme``.
_LIGHT_PALETTE: dict[QPalette.ColorRole, tuple[int, int, int]] = {
    QPalette.ColorRole.Window: (245, 245, 245),
    QPalette.ColorRole.WindowText: (20, 20, 20),
    QPalette.ColorRole.Base: (255, 255, 255),
    QPalette.ColorRole.Text: (20, 20, 20),
    QPalette.ColorRole.Button: (230, 230, 230),
    QPalette.ColorRole.ButtonText: (20, 20, 20),
}
_DARK_PALETTE: dict[QPalette.ColorRole, tuple[int, int, int]] = {
    QPalette.ColorRole.Window: (30, 30, 30),
    QPalette.ColorRole.WindowText: (235, 235, 235),
    QPalette.ColorRole.Base: (45, 45, 45),
    QPalette.ColorRole.Text: (235, 235, 235),
    QPalette.ColorRole.Button: (60, 60, 60),
    QPalette.ColorRole.ButtonText: (235, 235, 235),
}

#: The QSS family the renderer registers a ``style.font_asset`` file under, kept
#: in lockstep with the family ``to_qss`` emits (``font-family: "CustomAsset"``).
_CUSTOM_FONT_FAMILY = "CustomAsset"

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


def _to_qt_input_mask(mask: str) -> str:
    r"""Translate the framework mask notation to Qt's ``setInputMask`` notation.

    The framework uses ``9`` for a required digit and ``A`` for a required
    letter; any other character is a fixed literal. Qt's ``QLineEdit`` input mask
    uses ``0`` for a required digit and ``A`` for a required letter, and treats
    its own metacharacters (``9 A a N X 0 D # H h B b > < ! \\``) specially — so a
    framework literal that happens to be one of those must be backslash-escaped.

    Args:
        mask: The framework mask (``9`` digit, ``A`` letter, else literal).

    Returns:
        The equivalent Qt input mask string.
    """
    qt_meta = set("0123456789AaNXDdHhBb#><!\\")
    out: list[str] = []
    for char in mask:
        if char == "9":
            out.append("0")  # Qt required digit
        elif char == "A":
            out.append("A")  # Qt required letter (same glyph)
        elif char in qt_meta:
            out.append("\\" + char)  # escape a literal that is a Qt metachar
        else:
            out.append(char)  # plain literal separator
    return "".join(out)


#: Cache of rendered vector-icon pixmaps keyed by ``(name, size, color_argb)`` so
#: a glyph is parsed/stroked once and reused across every label and line-edit
#: action that asks for the same name/size/color.
_ICON_PIXMAP_CACHE: dict[tuple[str, int, int], QPixmap] = {}

def _resolve_icon_name(name: str) -> str:
    """Map a Material-symbol alias to its curated icon name (else return as-is).

    Delegates to the engine's :data:`tempest_core.icons.MATERIAL_ALIASES` so the
    Qt simulator and the device renderer share one alias table (no Qt-local
    duplication) — a common Material name (``Icon(name="photo_camera")``) renders
    a curated glyph rather than the literal text fallback. A name that is already
    curated, registered via :func:`register_icon`, or unknown passes through
    unchanged (``icon_path`` already resolves curated/registered/aliased names, so
    this pre-resolution is a thin convenience for callers that build the SVG by
    name).

    Args:
        name: The requested icon name (curated, Material alias, or custom).

    Returns:
        The curated name to render, or the original name when no alias matches.
    """
    return MATERIAL_ALIASES.get(name, name)


def _icon_pixmap(name: str, size: int, color: QColor) -> QPixmap | None:
    """Build a stroked vector-icon pixmap from the curated icon set.

    Wraps the icon's single SVG ``d`` string (from :func:`icon_path`) in a tiny
    ``<svg viewBox="0 0 24 24">`` document with a stroked, fill-none path in the
    requested color and rasterizes it via ``QSvgRenderer`` (robust SVG path
    parsing, antialiased, round cap/join, stroke width ~2 on the 24 grid). The
    result is cached by ``(name, size, color)``.

    Args:
        name: A curated icon name (an :class:`Icons` member or raw string), or a
            common Material-symbol alias (resolved via the engine's
            :data:`~tempest_core.icons.MATERIAL_ALIASES`).
        size: The target square pixel size of the pixmap.
        color: The stroke color (the surrounding foreground/text color).

    Returns:
        A transparent ``QPixmap`` of ``size`` x ``size`` carrying the stroked
        glyph, or ``None`` when the name is unknown or ``QtSvg`` is unavailable
        (the caller falls back to text).
    """
    resolved = _resolve_icon_name(name)
    d = icon_path(resolved)
    if d is None:
        return None
    size = max(1, int(size))
    key = (resolved, size, color.rgba())
    cached = _ICON_PIXMAP_CACHE.get(key)
    if cached is not None:
        return cached
    renderer_cls = _load_svg_renderer()
    if renderer_cls is None:
        return None
    # Inline the d string in a minimal stroke-only SVG; escape the path data so a
    # stray ``<``/``&``/``"`` can never break the document or the quoted attribute
    # (curated paths have none, but a custom name's path is escaped defensively).
    safe_d = saxutils.escape(d, {'"': "&quot;"})
    stroke = color.name(QColor.NameFormat.HexRgb)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{size}" height="{size}">'
        f'<path d="{safe_d}" fill="none" stroke="{stroke}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    renderer = renderer_cls(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return None
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    _ICON_PIXMAP_CACHE[key] = pixmap
    return pixmap


def _icon_qicon(name: str, size: int, color: QColor) -> QIcon | None:
    """Build a :class:`QIcon` from a curated vector icon, or ``None`` if unknown.

    Args:
        name: A curated icon name (an :class:`Icons` member or raw string).
        size: The target square pixel size.
        color: The stroke color.

    Returns:
        A ``QIcon`` wrapping the stroked glyph, or ``None`` when unavailable.
    """
    pixmap = _icon_pixmap(name, size, color)
    if pixmap is None:
        return None
    return QIcon(pixmap)


def _eye_icon(revealed: bool, color: QColor) -> QIcon:
    """Render the reveal-toggle glyph as a modern stroked line icon.

    Uses the curated :data:`Icons.EYE` (revealed) / :data:`Icons.EYE_OFF`
    (masked) vector glyphs via :func:`_icon_qicon`. Falls back to an empty icon
    only when ``QtSvg`` is unavailable (no emoji).

    Args:
        revealed: Whether the password is currently revealed (open eye) or
            masked (crossed-out eye).
        color: The stroke color (the field's foreground color).

    Returns:
        A 16×16 icon carrying the matching line glyph.
    """
    name = Icons.EYE if revealed else Icons.EYE_OFF
    icon = _icon_qicon(str(name), 16, color)
    return icon if icon is not None else QIcon()


def _scoped_stylesheet(widget: QWidget, body: str) -> None:
    """Set a widget's stylesheet scoped to itself via an ``#objectName`` selector.

    A *bare* QSS body (e.g. ``"border: 1px solid …; border-radius: 8px"``) is
    treated by Qt as an implicit universal selector, so the declarations cascade
    onto the widget **and all its descendants** — a bordered card then draws a
    stray box around every text/icon child, and a child's own ``setStyleSheet``
    (color/font) does not reset the inherited border. Scoping the body to an
    ``#name`` selector keyed on the widget's object name confines the box
    decoration to the widget itself, leaving descendants untouched.

    Args:
        widget: The widget whose stylesheet is being set.
        body: The bare QSS declaration body (without a selector). An empty body
            clears the stylesheet (no selector wrapper, so Qt resets cleanly).
    """
    if not body:
        widget.setStyleSheet("")
        return
    name = widget.objectName() or f"tw_{id(widget):x}"
    widget.setObjectName(name)
    widget.setStyleSheet(f"#{name} {{ {body} }}")


def _clamp_radius_value(radius: float, w: int, h: int) -> float:
    """Clamp a uniform corner radius to half the smaller widget dimension.

    A radius larger than ``min(w, h) / 2`` cannot round the box any further — the
    pill sentinel (a very large value, e.g. ``999``) is meant to fully round the
    shorter axis. Clamping makes the pill/circle render as a true capsule/disc
    instead of leaving Qt's inconsistent handling of an over-large radius square
    off the corners.

    Args:
        radius: The requested uniform radius.
        w: The widget's width in pixels.
        h: The widget's height in pixels.

    Returns:
        The radius capped at ``min(w, h) / 2`` (unchanged when already smaller,
        or when the size is not yet known so no cap can be derived).
    """
    if w <= 0 or h <= 0:
        return radius
    return min(radius, min(w, h) / 2.0)


def _clamp_radius(radius: float | Corners, w: int, h: int) -> float | Corners:
    """Clamp a uniform or per-corner radius to half the smaller widget dimension.

    Per-corner radii are clamped component-wise, mirroring the uniform case so a
    ``Corners`` pill/circle is realized faithfully too.

    Args:
        radius: The requested uniform radius or per-corner :class:`Corners`.
        w: The widget's width in pixels.
        h: The widget's height in pixels.

    Returns:
        The clamped radius (same kind as the input).
    """
    if isinstance(radius, Corners):
        return Corners(
            top_left=_clamp_radius_value(radius.top_left, w, h),
            top_right=_clamp_radius_value(radius.top_right, w, h),
            bottom_right=_clamp_radius_value(radius.bottom_right, w, h),
            bottom_left=_clamp_radius_value(radius.bottom_left, w, h),
        )
    return _clamp_radius_value(radius, w, h)


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
                elided = metrics.elidedText(segment, Qt.TextElideMode.ElideRight, width)
                painter.drawText(QRectF(0.0, y, width, advance), h_flags, elided)
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
            QColor(
                shadow.color.r,
                shadow.color.g,
                shadow.color.b,
                round(shadow.color.a * 255),
            )
        )
    return effect


class _CanvasWidget(QWidget):
    """A drawing surface that interprets a JSON-able list of draw commands.

    The command list mirrors the IR contract emitted by the ``Canvas`` widget
    (and the ``to_compose`` spec): each command is a plain ``dict`` with a
    ``kind`` discriminator. Colors are ``[r, g, b, a]`` float arrays in ``[0, 1]``
    — never tuples — so the same list replays identically on both renderers.
    ``fill``/``stroke`` flush the path accumulated since the previous flush.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize an empty canvas.

        Args:
            parent: The optional parent widget.
        """
        super().__init__(parent)
        self._commands: list[dict[str, Any]] = []

    def set_commands(self, commands: list[dict[str, Any]]) -> None:
        """Replace the command list and schedule a repaint.

        Args:
            commands: The new draw-command dicts (each with a ``kind`` key).
        """
        self._commands = commands
        self.update()

    @staticmethod
    def _qcolor(color: list[float] | None) -> QColor:
        """Convert a ``[r, g, b, a]`` float array (in ``[0, 1]``) to a ``QColor``.

        Args:
            color: The color array, or ``None`` (defaults to opaque black).

        Returns:
            The equivalent ``QColor``.
        """
        if not color:
            return QColor(0, 0, 0, 255)
        r, g, b, a = (list(color) + [0.0, 0.0, 0.0, 1.0])[:4]
        return QColor(int(r * 255), int(g * 255), int(b * 255), int(a * 255))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        """Replay the draw commands onto the widget surface.

        Args:
            event: The Qt paint event (unused; the full list is replayed).
        """
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        for cmd in self._commands:
            kind = cmd.get("kind")
            if kind == "move_to":
                path.moveTo(cmd["x"], cmd["y"])
            elif kind == "line_to":
                path.lineTo(cmd["x"], cmd["y"])
            elif kind == "arc_to":
                path.arcTo(
                    cmd["x"],
                    cmd["y"],
                    cmd["width"],
                    cmd["height"],
                    cmd["start_angle"],
                    cmd["sweep_angle"],
                )
            elif kind == "close":
                path.closeSubpath()
            elif kind == "draw_rect":
                path.addRect(cmd["x"], cmd["y"], cmd["width"], cmd["height"])
            elif kind == "draw_oval":
                path.addEllipse(cmd["x"], cmd["y"], cmd["width"], cmd["height"])
            elif kind == "fill":
                painter.fillPath(path, QBrush(self._qcolor(cmd.get("color"))))
                path = QPainterPath()
            elif kind == "stroke":
                pen = QPen(self._qcolor(cmd.get("color")))
                pen.setWidthF(float(cmd.get("width", 1.0)))
                painter.strokePath(path, pen)
                path = QPainterPath()
            elif kind == "draw_text":
                painter.setPen(QPen(self._qcolor(cmd.get("color"))))
                font = painter.font()
                font.setPointSizeF(float(cmd.get("size", 14.0)))
                painter.setFont(font)
                painter.drawText(QPointF(cmd["x"], cmd["y"]), cmd["text"])
        painter.end()


class _ClipWidget(QWidget):
    """A single-child wrapper that masks itself to a predefined shape.

    Qt has no per-widget CSS ``clip-path``, so the mask is rebuilt from a
    ``QPainterPath`` on every resize and applied via ``setMask(QRegion(...))``.
    Supported shapes mirror the ``ClipShape`` enum: ``circle`` (centred disc),
    ``oval`` (full-bounds ellipse) and ``rounded_rect`` (radius from the prop).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the clip wrapper with a vertical content layout.

        Args:
            parent: The optional parent widget.
        """
        super().__init__(parent)
        self._shape: str = "rounded_rect"
        self._radius: float = 8.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

    def configure_clip(self, shape: str, radius: float) -> None:
        """Set the clip shape/radius and re-apply the mask.

        Args:
            shape: One of ``circle`` / ``oval`` / ``rounded_rect``.
            radius: The corner radius used by ``rounded_rect``.
        """
        self._shape = shape
        self._radius = radius
        self._apply_mask()

    def _apply_mask(self) -> None:
        """Rebuild the clip path from the current size and apply it as a mask."""
        rect = QRectF(0.0, 0.0, float(self.width()), float(self.height()))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        path = QPainterPath()
        if self._shape == "circle":
            diameter = min(rect.width(), rect.height())
            cx = (rect.width() - diameter) / 2.0
            cy = (rect.height() - diameter) / 2.0
            path.addEllipse(cx, cy, diameter, diameter)
        elif self._shape == "oval":
            path.addEllipse(rect)
        else:  # rounded_rect (default)
            # Clamp the corner radius to half the smaller side so an over-large
            # radius (pill sentinel) yields a true capsule instead of a malformed
            # mask rather than overshooting the box.
            radius = _clamp_radius_value(
                self._radius, int(rect.width()), int(rect.height())
            )
            path.addRoundedRect(rect, radius, radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        """Re-apply the mask whenever the widget is resized.

        Args:
            event: The Qt resize event.
        """
        super().resizeEvent(event)
        self._apply_mask()


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


class _WrapWidget(QWidget):
    """A flow-layout container that wraps its children onto new lines.

    Children are direct Qt children (no box layout). On every resize — and
    whenever the renderer changes the child set — they are reflowed left to
    right, breaking onto a new line once the current row would overflow the
    available width. The inter-child spacing (both horizontal and vertical) is
    the style ``gap``, and the surrounding ``padding`` becomes the widget's
    contents margins. This is the Qt realization of the
    :class:`~tempestroid.widgets.Wrap` primitive (Compose lowers it to a
    ``FlowRow``/``FlowColumn`` — a documented divergence).
    """

    def __init__(self) -> None:
        """Create an empty wrap container."""
        super().__init__()
        self._children: list[QWidget] = []
        self._gap: int = 0
        self._left: int = 0
        self._top: int = 0
        self._right: int = 0
        self._bottom: int = 0

    def set_children(self, children: list[QWidget]) -> None:
        """Replace the flowed child set and re-lay it out.

        Args:
            children: The ordered child widgets, flowed in order.
        """
        self._children = children
        for child in children:
            child.setParent(self)
            child.show()
        self._relayout()

    def add_child(self, widget: QWidget, index: int) -> None:
        """Insert a child at ``index`` and reflow.

        Args:
            widget: The child widget to add.
            index: The flow position to insert at.
        """
        widget.setParent(self)
        widget.show()
        self._children.insert(index, widget)
        self._relayout()

    def remove_child(self, widget: QWidget) -> None:
        """Detach a child from the flow and reflow.

        Args:
            widget: The child widget to remove (geometry only; the caller owns
                discarding the widget itself).
        """
        if widget in self._children:
            self._children.remove(widget)
        self._relayout()

    def set_spacing(self, gap: int, margins: tuple[int, int, int, int]) -> None:
        """Set the inter-child gap and the surrounding contents margins.

        Args:
            gap: The horizontal and vertical spacing between children, in pixels.
            margins: The ``(left, top, right, bottom)`` contents margins.
        """
        self._gap = gap
        self._left, self._top, self._right, self._bottom = margins
        self._relayout()

    def _flow(self, available_width: int) -> int:
        """Reflow the children for the given content width, returning the height.

        Args:
            available_width: The content width (excluding horizontal margins).

        Returns:
            The total content height the flow occupies (excluding margins).
        """
        x = 0
        y = 0
        line_height = 0
        for child in self._children:
            hint = child.sizeHint()
            w = hint.width()
            h = hint.height()
            if x > 0 and x + w > available_width:
                # Quebra de linha: o filho não cabe no resto da linha atual.
                x = 0
                y += line_height + self._gap
                line_height = 0
            child.setGeometry(self._left + x, self._top + y, w, h)
            x += w + self._gap
            line_height = max(line_height, h)
        return y + line_height

    def _relayout(self) -> None:
        """Reflow the children for the current width and update the geometry."""
        available = max(0, self.width() - self._left - self._right)
        self._flow(available)
        self.updateGeometry()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Reflow the children whenever the wrap is resized.

        Args:
            event: The Qt resize event (name mandated by the PySide override).
        """
        self._relayout()
        super().resizeEvent(event)

    def hasHeightForWidth(self) -> bool:
        """Report that the wrap's height depends on its width.

        Returns:
            Always ``True`` — a flow's height grows as the width shrinks.
        """
        return True

    def heightForWidth(self, width: int) -> int:
        """Compute the flow height for a candidate width without mutating layout.

        Args:
            width: The candidate widget width (including horizontal margins).

        Returns:
            The total height (including vertical margins) the flow needs.
        """
        available = max(0, width - self._left - self._right)
        x = 0
        y = 0
        line_height = 0
        for child in self._children:
            hint = child.sizeHint()
            w = hint.width()
            h = hint.height()
            if x > 0 and x + w > available:
                x = 0
                y += line_height + self._gap
                line_height = 0
            x += w + self._gap
            line_height = max(line_height, h)
        return self._top + y + line_height + self._bottom

    def sizeHint(self) -> QSize:
        """Size to a single-row width and the flow height at the current width.

        Returns:
            The preferred size: the natural single-row width and the wrapped
            height at the widget's current width.
        """
        width = (
            self._left
            + sum(child.sizeHint().width() for child in self._children)
            + self._gap * max(0, len(self._children) - 1)
            + self._right
        )
        height = self.heightForWidth(self.width() or width)
        return QSize(width, height)


class _PageViewWidget(QStackedWidget):
    """A paginated carousel: one full-size page visible, navigated by arrow keys.

    Wraps a :class:`QStackedWidget` whose pages are the carousel children. The
    left/right arrow keys move between pages; every settled page change invokes
    the wired callback with a :class:`PageChangeEvent` carrying the new and
    previous indices. This is the Qt stand-in for Compose's ``HorizontalPager``
    (the device gets real swipe gestures — a documented divergence).
    """

    def __init__(self) -> None:
        """Create an empty, focusable page view."""
        super().__init__()
        self._page: int = 0
        self._on_change: Callable[[PageChangeEvent], None] | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_on_change(self, callback: Callable[[PageChangeEvent], None] | None) -> None:
        """Install (or clear) the page-change callback.

        Args:
            callback: Invoked as ``callback(PageChangeEvent(...))`` whenever the
                active page changes, or ``None`` to disable notification.
        """
        self._on_change = callback

    def set_page(self, index: int) -> None:
        """Show page ``index``, emitting a :class:`PageChangeEvent` on a change.

        Clamps to the valid page range; a no-op (same page) emits nothing, so an
        app driving the index from its own state never triggers a feedback loop.

        Args:
            index: The page index to show (0-based).
        """
        count = self.count()
        if count == 0:
            self._page = 0
            return
        target = max(0, min(index, count - 1))
        if target == self.currentIndex():
            self._page = target
            return
        previous = self.currentIndex()
        self.setCurrentIndex(target)
        self._page = target
        if self._on_change is not None:
            self._on_change(PageChangeEvent(page=target, previous=previous))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Navigate pages with the left/right arrow keys.

        Args:
            event: The Qt key event (name mandated by the PySide override).
        """
        key = event.key()
        if key == Qt.Key.Key_Right:
            self.set_page(self.currentIndex() + 1)
            event.accept()
            return
        if key == Qt.Key.Key_Left:
            self.set_page(self.currentIndex() - 1)
            event.accept()
            return
        super().keyPressEvent(event)


class _AspectRatioWidget(QWidget):
    """A single-child box that constrains its content to a fixed width/height ratio.

    The ``ratio`` is ``width / height``. The widget reports
    :meth:`heightForWidth` so a parent box layout can size it, and on resize it
    centers a single child fitted to the largest rectangle of the right ratio
    inside the available bounds. This mirrors Compose's
    ``Modifier.aspectRatio`` (a documented divergence: Qt derives the box
    imperatively, Compose via a modifier).
    """

    def __init__(self, ratio: float) -> None:
        """Create the aspect-ratio box.

        Args:
            ratio: The ``width / height`` ratio to enforce (must be positive).
        """
        super().__init__()
        self._ratio: float = ratio if ratio > 0 else 1.0
        self._child: QWidget | None = None

    def set_child(self, widget: QWidget) -> None:
        """Set the single fitted child and lay it out.

        Args:
            widget: The child widget to fit to the ratio.
        """
        self._child = widget
        widget.setParent(self)
        widget.show()
        self._relayout()

    def clear_child(self) -> None:
        """Forget the current child (the caller owns discarding the widget)."""
        self._child = None

    def hasHeightForWidth(self) -> bool:
        """Report that the box's height is derived from its width.

        Returns:
            Always ``True``.
        """
        return True

    def heightForWidth(self, width: int) -> int:
        """Derive the height from the width and the fixed ratio.

        Args:
            width: The candidate width.

        Returns:
            ``width / ratio`` rounded to an integer.
        """
        return int(width / self._ratio)

    def _relayout(self) -> None:
        """Center the child fitted to the largest in-ratio rectangle."""
        if self._child is None:
            return
        width, height = self.width(), self.height()
        if width <= 0 or height <= 0:
            return
        fit_w = width
        fit_h = int(width / self._ratio)
        if fit_h > height:
            fit_h = height
            fit_w = int(height * self._ratio)
        x = (width - fit_w) // 2
        y = (height - fit_h) // 2
        self._child.setGeometry(x, y, fit_w, fit_h)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Re-fit the child whenever the box is resized.

        Args:
            event: The Qt resize event (name mandated by the PySide override).
        """
        self._relayout()
        super().resizeEvent(event)


class _KeyboardAvoidingWidget(QWidget):
    """A vertical container that recedes its content when the keyboard appears.

    Mirrors the :class:`~tempestroid.widgets.KeyboardAvoidingView` IR primitive.
    The widget lays its children along a ``QVBoxLayout`` (behaving exactly like a
    ``Column``) and listens to ``QGuiApplication.inputMethod().keyboardRectangle
    Changed``. When the virtual keyboard overlaps the widget, its bottom contents
    margin is inflated by the overlap so the content slides up clear of the
    keyboard; when the keyboard hides (or there is none — the desktop case) the
    bottom margin returns to its style-derived base, so the widget is a plain
    ``Column``. The device renderer uses ``Modifier.imePadding()`` via
    ``WindowInsets.ime`` — identical to the user, a documented divergence in how
    the inset is sourced.
    """

    def __init__(self) -> None:
        """Create the keyboard-avoiding container and wire the IME signal."""
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Margens base (vindas do ``padding`` do estilo); o teclado soma por cima.
        self._base_margins: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._keyboard_inset: int = 0
        QGuiApplication.inputMethod().keyboardRectangleChanged.connect(
            self._on_keyboard_rectangle_changed
        )

    def set_base_margins(self, margins: tuple[int, int, int, int]) -> None:
        """Set the style-derived contents margins (before any keyboard inset).

        Args:
            margins: The ``(left, top, right, bottom)`` base contents margins.
        """
        self._base_margins = margins
        self._apply_margins()

    def _on_keyboard_rectangle_changed(self) -> None:
        """Recompute the keyboard overlap and re-apply the contents margins."""
        keyboard = QGuiApplication.inputMethod().keyboardRectangle()
        if keyboard.height() <= 0:
            self._keyboard_inset = 0
            self._apply_margins()
            return
        # Quanto do teclado sobrepõe a base do widget (em coordenadas globais).
        widget_bottom = self.mapToGlobal(QPoint(0, self.height())).y()
        overlap = widget_bottom - int(keyboard.top())
        self._keyboard_inset = max(0, overlap)
        self._apply_margins()

    def _apply_margins(self) -> None:
        """Apply the base margins plus the current keyboard inset on the bottom."""
        layout = self.layout()
        if layout is None:
            return
        left, top, right, bottom = self._base_margins
        layout.setContentsMargins(left, top, right, bottom + self._keyboard_inset)


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


def _single_child_layout() -> QVBoxLayout:
    """Build a zero-margin vertical layout for a single-child gesture wrapper.

    Returns:
        A fresh ``QVBoxLayout`` with no contents margins (the child fills it).
    """
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    return layout


class _PanWidget(QWidget):
    """A single-child container that reports a continuous pan + fling velocity.

    A press records the start position and a high-resolution timer; movement
    accumulates the delta; release computes the average velocity (px/s) over the
    elapsed time and emits a :class:`PanEvent` carrying the total delta and the
    release velocity. The Qt simulator reports a single pan per press/release
    cycle (the device renderer streams per-frame deltas) — a documented
    divergence.
    """

    def __init__(self) -> None:
        """Create the pan widget and its single-child layout."""
        super().__init__()
        self._layout: QVBoxLayout = _single_child_layout()
        self.setLayout(self._layout)
        self._handlers: dict[str, object] = {}
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None
        self._press_pos: QPoint | None = None
        self._elapsed: QElapsedTimer = QElapsedTimer()

    def set_handlers(
        self,
        handlers: dict[str, object],
        dispatch: Callable[[Any, Event], None],
    ) -> None:
        """Install the current handlers and the dispatch callback.

        Args:
            handlers: Map of prop name (``on_pan``) to its handler (or ``None``).
            dispatch: Callback invoked as ``dispatch(handler, event)``.
        """
        self._handlers = handlers
        self._dispatch = dispatch

    def _emit(self, prop: str, event: Event) -> None:
        """Dispatch ``event`` to the handler bound at ``prop`` if present.

        Args:
            prop: The handler prop name.
            event: The typed event.
        """
        handler = self._handlers.get(prop)
        if handler is not None:
            self._dispatch(handler, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record the press start position and start the elapsed timer.

        Args:
            event: The Qt mouse press event.
        """
        self._press_pos = event.position().toPoint()
        self._elapsed.restart()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit the pan with its total delta and release velocity.

        Args:
            event: The Qt mouse release event.
        """
        if self._press_pos is not None:
            end = event.position().toPoint()
            dx = float(end.x() - self._press_pos.x())
            dy = float(end.y() - self._press_pos.y())
            elapsed_ms = max(self._elapsed.elapsed(), 1)
            seconds = elapsed_ms / 1000.0
            self._emit(
                "on_pan",
                PanEvent(dx=dx, dy=dy, vx=dx / seconds, vy=dy / seconds),
            )
            self._press_pos = None
        super().mouseReleaseEvent(event)


class _ScaleWidget(QWidget):
    """A single-child container that reports pinch scale/rotation and a double tap.

    Qt's :class:`QPinchGesture` requires touch hardware, which the desktop / WSL
    simulator lacks. To stay exercisable, the widget falls back to a synthetic
    pinch: ``Ctrl`` + the mouse wheel zooms (each notch scales by a fixed step,
    clamped to a sane range) — a documented divergence from the device's true
    multitouch pinch. A native double-click drives ``on_double_tap``.
    """

    #: Multiplicative zoom per wheel notch under the Ctrl fallback.
    _WHEEL_STEP = 1.15
    #: Clamp bounds for the synthetic cumulative scale.
    _MIN_SCALE = 0.2
    _MAX_SCALE = 8.0

    def __init__(self) -> None:
        """Create the scale widget, its layout, and grab the pinch gesture."""
        super().__init__()
        self._layout: QVBoxLayout = _single_child_layout()
        self.setLayout(self._layout)
        self._handlers: dict[str, object] = {}
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None
        self._scale: float = 1.0
        self.grabGesture(Qt.GestureType.PinchGesture)

    def set_handlers(
        self,
        handlers: dict[str, object],
        dispatch: Callable[[Any, Event], None],
    ) -> None:
        """Install the current handlers and the dispatch callback.

        Args:
            handlers: Map of prop name (``on_scale``/``on_double_tap``) to its
                handler (or ``None``).
            dispatch: Callback invoked as ``dispatch(handler, event)``.
        """
        self._handlers = handlers
        self._dispatch = dispatch

    def _emit(self, prop: str, event: Event) -> None:
        """Dispatch ``event`` to the handler bound at ``prop`` if present.

        Args:
            prop: The handler prop name.
            event: The typed event.
        """
        handler = self._handlers.get(prop)
        if handler is not None:
            self._dispatch(handler, event)

    def event(self, event: QEvent) -> bool:
        """Intercept native gesture events to emit a pinch scale.

        Args:
            event: The Qt event (a ``QGestureEvent`` is handled here).

        Returns:
            ``True`` when the gesture was consumed, else the base result.
        """
        if event.type() == QEvent.Type.Gesture:
            return self._gesture_event(cast("QGestureEvent", event))
        return super().event(event)

    def _gesture_event(self, event: QGestureEvent) -> bool:
        """Translate a pinch gesture into a :class:`ScaleEvent`.

        Args:
            event: The Qt gesture event.

        Returns:
            ``True`` when a pinch was found and consumed, else ``False``.
        """
        gesture: QGesture = event.gesture(Qt.GestureType.PinchGesture)
        if not isinstance(gesture, QPinchGesture):
            return False
        pinch = gesture
        center = pinch.centerPoint()
        self._emit(
            "on_scale",
            ScaleEvent(
                scale=float(pinch.totalScaleFactor()),
                focus_x=float(center.x()),
                focus_y=float(center.y()),
                rotation=float(pinch.totalRotationAngle()),
            ),
        )
        event.accept()
        return True

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom via ``Ctrl`` + wheel as the touch-free pinch fallback.

        Args:
            event: The Qt wheel event.
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = (
                self._WHEEL_STEP
                if event.angleDelta().y() > 0
                else 1.0 / self._WHEEL_STEP
            )
            self._scale = max(
                self._MIN_SCALE, min(self._MAX_SCALE, self._scale * factor)
            )
            pos = event.position()
            self._emit(
                "on_scale",
                ScaleEvent(
                    scale=self._scale,
                    focus_x=float(pos.x()),
                    focus_y=float(pos.y()),
                    rotation=0.0,
                ),
            )
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Emit a double tap from Qt's native double-click.

        Args:
            event: The Qt double-click event.
        """
        point = event.position().toPoint()
        self._emit("on_double_tap", TapEvent(x=float(point.x()), y=float(point.y())))
        super().mouseDoubleClickEvent(event)


class _DoubleTapWidget(QWidget):
    """A single-child container that reports only a double tap.

    A thin wrapper around Qt's native double-click for ``DoubleTapHandler``,
    with none of the press/swipe/long-press machinery of ``_GestureWidget``.
    """

    def __init__(self) -> None:
        """Create the double-tap widget and its single-child layout."""
        super().__init__()
        self._layout: QVBoxLayout = _single_child_layout()
        self.setLayout(self._layout)
        self._handlers: dict[str, object] = {}
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None

    def set_handlers(
        self,
        handlers: dict[str, object],
        dispatch: Callable[[Any, Event], None],
    ) -> None:
        """Install the current handlers and the dispatch callback.

        Args:
            handlers: Map of prop name (``on_double_tap``) to its handler.
            dispatch: Callback invoked as ``dispatch(handler, event)``.
        """
        self._handlers = handlers
        self._dispatch = dispatch

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Emit a double tap from Qt's native double-click.

        Args:
            event: The Qt double-click event.
        """
        handler = self._handlers.get("on_double_tap")
        if handler is not None:
            point = event.position().toPoint()
            self._dispatch(handler, TapEvent(x=float(point.x()), y=float(point.y())))
        super().mouseDoubleClickEvent(event)


class _DismissibleWidget(QWidget):
    """A single-child container that emits a dismiss on a swipe past threshold.

    Travel is measured along the configured :class:`SwipeDirection`; once the
    release exceeds :data:`_SWIPE_THRESHOLD` in that direction, a
    :class:`DismissEvent` is emitted and the child slides out (opacity fade +
    offset) via a :class:`QPropertyAnimation`. The app's handler typically
    removes the item from state, so the slide is purely cosmetic feedback.
    """

    def __init__(self) -> None:
        """Create the dismissible widget and its single-child layout."""
        super().__init__()
        self._layout: QVBoxLayout = _single_child_layout()
        self.setLayout(self._layout)
        self._handlers: dict[str, object] = {}
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None
        self._direction: SwipeDirection = SwipeDirection.LEFT
        self._press_pos: QPoint | None = None
        self._anim: QPropertyAnimation | None = None
        self._effect: QGraphicsOpacityEffect | None = None

    def set_handlers(
        self,
        handlers: dict[str, object],
        dispatch: Callable[[Any, Event], None],
        direction: SwipeDirection,
    ) -> None:
        """Install the dismiss handler, dispatch callback and trigger direction.

        Args:
            handlers: Map of prop name (``on_dismiss``) to its handler.
            dispatch: Callback invoked as ``dispatch(handler, event)``.
            direction: The swipe direction that triggers the dismiss.
        """
        self._handlers = handlers
        self._dispatch = dispatch
        self._direction = direction

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record the press start position.

        Args:
            event: The Qt mouse press event.
        """
        self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit a dismiss when the release passes the threshold in-direction.

        Args:
            event: The Qt mouse release event.
        """
        if self._press_pos is not None:
            end = event.position().toPoint()
            dx = float(end.x() - self._press_pos.x())
            dy = float(end.y() - self._press_pos.y())
            if self._past_threshold(dx, dy):
                handler = self._handlers.get("on_dismiss")
                if handler is not None:
                    self._dispatch(handler, DismissEvent(overlay_id=None))
                self._animate_out(dx, dy)
            self._press_pos = None
        super().mouseReleaseEvent(event)

    def _past_threshold(self, dx: float, dy: float) -> bool:
        """Report whether the travel clears the threshold in the trigger axis.

        Args:
            dx: Horizontal travel (positive → rightward).
            dy: Vertical travel (positive → downward).

        Returns:
            ``True`` when the directional travel exceeds the swipe threshold.
        """
        if self._direction is SwipeDirection.LEFT:
            return dx <= -_SWIPE_THRESHOLD
        if self._direction is SwipeDirection.RIGHT:
            return dx >= _SWIPE_THRESHOLD
        if self._direction is SwipeDirection.UP:
            return dy <= -_SWIPE_THRESHOLD
        return dy >= _SWIPE_THRESHOLD

    def _animate_out(self, dx: float, dy: float) -> None:
        """Fade the child out as cosmetic dismiss feedback.

        Args:
            dx: Horizontal travel (sign hints the slide direction).
            dy: Vertical travel (sign hints the slide direction).
        """
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._effect = effect
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(_NAV_ANIM_MS)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        self._anim = anim
        anim.start()


class _ReorderableWidget(QWidget):
    """A vertical (or horizontal) list whose items drag-and-drop to reorder.

    Press records the item index under the pointer; dragging past the slop
    starts a native :class:`QDrag` carrying the source index in its mime data.
    The drop computes the destination index from the drop position and emits a
    :class:`ReorderEvent` (``from_index`` → ``to_index``). The app's handler
    typically moves the item in state; the keyed A2 diff then emits a single
    ``Reorder`` patch.
    """

    #: Mime type used to carry the dragged source index across the drag session.
    _MIME = "application/x-tempest-reorder-index"

    def __init__(self, *, horizontal: bool = False) -> None:
        """Create the reorderable list and accept drops.

        Args:
            horizontal: Whether items lay out left-to-right (else top-to-bottom).
        """
        super().__init__()
        self._horizontal: bool = horizontal
        self._layout: QBoxLayout = (
            QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        )
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._handlers: dict[str, object] = {}
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None
        self._drag_index: int | None = None
        self.setAcceptDrops(True)

    def box_layout(self) -> QBoxLayout:
        """Return the item layout (the diffable child slot).

        Returns:
            The box layout the children are inserted into.
        """
        return self._layout

    def set_handlers(
        self,
        handlers: dict[str, object],
        dispatch: Callable[[Any, Event], None],
    ) -> None:
        """Install the reorder handler and the dispatch callback.

        Args:
            handlers: Map of prop name (``on_reorder``) to its handler.
            dispatch: Callback invoked as ``dispatch(handler, event)``.
        """
        self._handlers = handlers
        self._dispatch = dispatch

    def _index_at(self, pos: QPoint) -> int:
        """Resolve the item index nearest a position along the list axis.

        Args:
            pos: A local position.

        Returns:
            The index of the closest item (clamped to the item range).
        """
        count = self._layout.count()
        if count == 0:
            return 0
        coord = pos.x() if self._horizontal else pos.y()
        for index in range(count):
            item = self._layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is None:
                continue
            geom = widget.geometry()
            mid = (
                (geom.left() + geom.right()) / 2
                if self._horizontal
                else (geom.top() + geom.bottom()) / 2
            )
            if coord < mid:
                return index
        return count - 1

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record the item index under the press for a pending drag.

        Args:
            event: The Qt mouse press event.
        """
        self._drag_index = self._index_at(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Start a native drag carrying the source index once moving.

        Args:
            event: The Qt mouse move event.
        """
        if self._drag_index is None or not (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            super().mouseMoveEvent(event)
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(self._MIME, str(self._drag_index).encode("ascii"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept a drag that carries this list's reorder mime type.

        Args:
            event: The Qt drag-enter event.
        """
        if event.mimeData().hasFormat(self._MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Keep accepting the drag as it moves over the list.

        Args:
            event: The Qt drag-move event.
        """
        if event.mimeData().hasFormat(self._MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Compute the destination index and emit a :class:`ReorderEvent`.

        Args:
            event: The Qt drop event.
        """
        mime = event.mimeData()
        if not mime.hasFormat(self._MIME):
            super().dropEvent(event)
            return
        from_index = int(bytes(mime.data(self._MIME).data()).decode("ascii"))
        to_index = self._index_at(event.position().toPoint())
        if from_index != to_index:
            handler = self._handlers.get("on_reorder")
            if handler is not None:
                self._dispatch(
                    handler, ReorderEvent(from_index=from_index, to_index=to_index)
                )
        event.acceptProposedAction()

    def report_reorder(self, from_index: int, to_index: int) -> None:
        """Emit a :class:`ReorderEvent` directly (test/headless entry point).

        The native drag/drop loop is hard to drive headlessly, so this offers a
        deterministic way to exercise the reorder dispatch.

        Args:
            from_index: The source item index.
            to_index: The destination item index.
        """
        handler = self._handlers.get("on_reorder")
        if handler is not None:
            self._dispatch(
                handler, ReorderEvent(from_index=from_index, to_index=to_index)
            )


class _InteractiveViewerWidget(QGraphicsView):
    """A pannable, zoomable view of a single child via a :class:`QGraphicsScene`.

    The child is embedded through a :class:`QGraphicsProxyWidget`; the wheel
    zooms (clamped to ``min_scale``/``max_scale``) and a left-drag pans. Each
    interaction emits a :class:`ScaleEvent` with the current cumulative scale and
    the pointer-anchored focal point. Qt uses ``QGraphicsView`` + a transform;
    the device renderer uses ``Modifier.graphicsLayer`` — a documented
    divergence.
    """

    #: Multiplicative zoom per wheel notch.
    _WHEEL_STEP = 1.15

    def __init__(self) -> None:
        """Create the graphics view, its scene and the embedding proxy."""
        super().__init__()
        self._scene: QGraphicsScene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._proxy: QGraphicsProxyWidget | None = None
        self._handlers: dict[str, object] = {}
        self._dispatch: Callable[[Any, Event], None] = lambda handler, event: None
        self._scale: float = 1.0
        self._min_scale: float = 0.5
        self._max_scale: float = 4.0
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def set_child(self, child: QWidget) -> None:
        """Embed ``child`` as the single scene item.

        Args:
            child: The widget to pan and zoom.
        """
        if self._proxy is not None:
            self._scene.removeItem(self._proxy)
        self._proxy = self._scene.addWidget(child)

    def take_child(self) -> QWidget | None:
        """Detach and return the embedded child widget, if any.

        Returns:
            The embedded child, or ``None`` when nothing is mounted.
        """
        if self._proxy is None:
            return None
        widget = self._proxy.widget()
        self._scene.removeItem(self._proxy)
        self._proxy = None
        return widget

    def set_handlers(
        self,
        handlers: dict[str, object],
        dispatch: Callable[[Any, Event], None],
        min_scale: float,
        max_scale: float,
    ) -> None:
        """Install the interaction handler, dispatch callback and scale bounds.

        Args:
            handlers: Map of prop name (``on_interaction``) to its handler.
            dispatch: Callback invoked as ``dispatch(handler, event)``.
            min_scale: The minimum allowed zoom factor.
            max_scale: The maximum allowed zoom factor.
        """
        self._handlers = handlers
        self._dispatch = dispatch
        self._min_scale = min_scale
        self._max_scale = max_scale

    def _emit_interaction(self, focus: QPointF) -> None:
        """Dispatch the current scale and focal point as a :class:`ScaleEvent`.

        Args:
            focus: The pointer-anchored focal point in view coordinates.
        """
        handler = self._handlers.get("on_interaction")
        if handler is not None:
            self._dispatch(
                handler,
                ScaleEvent(
                    scale=self._scale,
                    focus_x=float(focus.x()),
                    focus_y=float(focus.y()),
                    rotation=0.0,
                ),
            )

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom on the wheel, clamped to the configured scale bounds.

        Args:
            event: The Qt wheel event.
        """
        factor = (
            self._WHEEL_STEP if event.angleDelta().y() > 0 else 1.0 / self._WHEEL_STEP
        )
        target = max(self._min_scale, min(self._max_scale, self._scale * factor))
        applied = target / self._scale if self._scale != 0 else 1.0
        self._scale = target
        if applied != 1.0:
            self.scale(applied, applied)
        self._emit_interaction(event.position())
        event.accept()


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


def _qcolor(color: Any) -> QColor:  # noqa: ANN401 — a tempestroid Color value object
    """Convert a tempestroid ``Color`` value object to a ``QColor``.

    Args:
        color: A :class:`~tempestroid.style.Color` (duck-typed: ``r``/``g``/``b``
            ints and a float ``a``).

    Returns:
        The equivalent ``QColor`` (alpha scaled 0..255).
    """
    return QColor(int(color.r), int(color.g), int(color.b), round(float(color.a) * 255))


class _ShimmerMixin(QWidget):
    """Shared moving-gradient paint loop for ``Shimmer`` and ``Skeleton``.

    Holds the base/highlight colors, the sweep duration and a self-restarting
    :class:`QTimer` that advances a normalized phase ``0..1`` and repaints. The
    gradient band slides from left to right across the widget on each loop, the
    simulator's stand-in for Compose's ``InfiniteTransition`` + animated
    ``Brush.linearGradient`` (a documented divergence). Subclasses paint the band
    in their own ``paintEvent`` via :meth:`_shimmer_brush`.
    """

    def __init__(self) -> None:
        """Create the widget with a stopped shimmer loop and default colors."""
        super().__init__()
        self._base: QColor = QColor(224, 224, 224)
        self._highlight: QColor = QColor(245, 245, 245)
        self._phase: float = 0.0
        self._steps: int = max(1, _SHIMMER_DEFAULT_MS // _SHIMMER_TICK_MS)
        self._timer: QTimer = QTimer(self)
        self._timer.setInterval(_SHIMMER_TICK_MS)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def configure_shimmer(
        self, base: QColor, highlight: QColor, duration_ms: int
    ) -> None:
        """Set the gradient colors and per-sweep duration, then repaint.

        Args:
            base: The resting tone of the gradient.
            highlight: The moving highlight tone.
            duration_ms: Duration of one full sweep, in milliseconds.
        """
        self._base = base
        self._highlight = highlight
        self._steps = max(1, int(duration_ms) // _SHIMMER_TICK_MS)
        self.update()

    def _advance(self) -> None:
        """Timer slot: advance the sweep phase and request a repaint."""
        self._phase = (self._phase + 1.0 / self._steps) % 1.0
        self.update()

    def _shimmer_brush(self, width: int) -> QBrush:
        """Build the moving-highlight gradient brush for the current phase.

        Args:
            width: The widget width the band sweeps across.

        Returns:
            A linear-gradient brush with the highlight centered at the phase.
        """
        gradient = QLinearGradient(0.0, 0.0, float(max(width, 1)), 0.0)
        center = self._phase
        lo = max(0.0, center - 0.25)
        hi = min(1.0, center + 0.25)
        gradient.setColorAt(0.0, self._base)
        gradient.setColorAt(lo, self._base)
        gradient.setColorAt(center, self._highlight)
        gradient.setColorAt(hi, self._base)
        gradient.setColorAt(1.0, self._base)
        return QBrush(gradient)


class _ShimmerWidget(_ShimmerMixin):
    """A single-child container painting a moving gradient behind its child.

    The child is laid out in a zero-margin box; the shimmer band is painted in the
    widget background on every timer tick. Used to realize
    :class:`~tempestroid.widgets.Shimmer`.
    """

    def __init__(self) -> None:
        """Create the shimmer container with its single-child layout."""
        super().__init__()
        self._layout: QVBoxLayout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def box_layout(self) -> QVBoxLayout:
        """Return the inner single-child layout.

        Returns:
            The zero-margin vertical layout holding the wrapped child.
        """
        return self._layout

    def paintEvent(self, arg__1: QPaintEvent) -> None:
        """Paint the moving gradient band behind the child.

        Args:
            arg__1: The Qt paint event (name mandated by the PySide override).
        """
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._shimmer_brush(self.width()))
        painter.end()
        super().paintEvent(arg__1)


class _SkeletonWidget(_ShimmerMixin):
    """A childless rounded rectangle painting a moving gradient.

    Realizes :class:`~tempestroid.widgets.Skeleton`: a clipped rounded rect filled
    with the same sweeping gradient as :class:`_ShimmerWidget`, used as a content
    placeholder while data loads.
    """

    def __init__(self) -> None:
        """Create the skeleton with a default corner radius."""
        super().__init__()
        self._radius: float = 4.0

    def set_radius(self, radius: float) -> None:
        """Set the corner radius and repaint.

        Args:
            radius: The corner radius in logical pixels.
        """
        self._radius = radius
        self.update()

    def paintEvent(self, arg__1: QPaintEvent) -> None:
        """Paint the rounded gradient rectangle.

        Args:
            arg__1: The Qt paint event (name mandated by the PySide override).
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._shimmer_brush(self.width()))
        painter.drawRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        painter.end()


class _AnimatedListWidget(QWidget):
    """A flex container that animates children in on insert and out on remove.

    Children are placed in a ``QVBoxLayout``/``QHBoxLayout`` like a Column/Row;
    when the renderer inserts a child it fades and expands it in, and when it
    removes one it fades and collapses it out before discarding it. This is the Qt
    stand-in for Compose's ``AnimatedVisibility`` (a documented divergence).
    """

    def __init__(self, *, horizontal: bool) -> None:
        """Create the animated-list container.

        Args:
            horizontal: ``True`` to lay children left-to-right (a row), ``False``
                for top-to-bottom (a column).
        """
        super().__init__()
        layout: QBoxLayout = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._box: QBoxLayout = layout
        self._horizontal: bool = horizontal
        # Strong refs to in-flight enter/exit animations so Qt does not GC them.
        self._anims: set[QAbstractAnimation] = set()

    def box_layout(self) -> QBoxLayout:
        """Return the children's box layout.

        Returns:
            The container's box layout.
        """
        return self._box

    def animate_in(self, widget: QWidget, duration_ms: int) -> None:
        """Fade + expand a freshly inserted child into view.

        Args:
            widget: The just-inserted child widget.
            duration_ms: The enter animation duration in milliseconds.
        """
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        target = widget.sizeHint().height() or widget.height() or 1
        widget.setMaximumHeight(0)
        fade = QPropertyAnimation(effect, b"opacity", widget)
        fade.setDuration(duration_ms)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        grow = QPropertyAnimation(widget, b"maximumHeight", widget)
        grow.setDuration(duration_ms)
        grow.setStartValue(0)
        grow.setEndValue(int(target))
        grow.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start(fade)
        self._start(grow, on_done=lambda: widget.setMaximumHeight(_QT_SIZE_MAX))

    def animate_out(
        self, widget: QWidget, duration_ms: int, on_done: Callable[[], None]
    ) -> None:
        """Fade + collapse a child out, then run ``on_done`` to discard it.

        Args:
            widget: The child widget leaving the list.
            duration_ms: The exit animation duration in milliseconds.
            on_done: Invoked once the collapse finishes (removes/deletes the
                widget).
        """
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        start_h = widget.height() or widget.sizeHint().height() or 1
        fade = QPropertyAnimation(effect, b"opacity", widget)
        fade.setDuration(duration_ms)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InCubic)
        shrink = QPropertyAnimation(widget, b"maximumHeight", widget)
        shrink.setDuration(duration_ms)
        shrink.setStartValue(int(start_h))
        shrink.setEndValue(0)
        shrink.setEasingCurve(QEasingCurve.Type.InCubic)
        self._start(fade)
        self._start(shrink, on_done=on_done)

    def _start(
        self, anim: QPropertyAnimation, on_done: Callable[[], None] | None = None
    ) -> None:
        """Start an animation, keeping a strong ref until it settles.

        Args:
            anim: The configured animation to start.
            on_done: Optional callback fired when the animation finishes.
        """
        self._anims.add(anim)

        def _finish() -> None:
            self._anims.discard(anim)
            if on_done is not None:
                on_done()

        anim.finished.connect(_finish)
        anim.start()


class _RangeSliderWidget(QWidget):
    """A dual-handle range slider built from two side-by-side ``QSlider``s.

    PySide6 ships no native range slider, so the simulator stands in with a low
    and a high integer ``QSlider`` that constrain each other (``low <= high``).
    Whenever either handle settles, :meth:`set_on_change` is invoked with the
    current ``(low, high)`` pair so the renderer can emit a ``RangeChangeEvent``.
    The device renderer uses Compose's native Material 3 ``RangeSlider`` (a
    documented Qt-vs-Compose divergence; the emitted event is identical).
    """

    def __init__(self) -> None:
        """Create the two stacked sliders and wire their mutual clamping."""
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._low_slider: QSlider = QSlider(Qt.Orientation.Horizontal)
        self._high_slider: QSlider = QSlider(Qt.Orientation.Horizontal)
        layout.addWidget(self._low_slider)
        layout.addWidget(self._high_slider)
        self._on_change: Callable[[int, int], None] | None = None
        self._low_slider.valueChanged.connect(self._clamp_low)
        self._high_slider.valueChanged.connect(self._clamp_high)

    def sliders(self) -> tuple[QSlider, QSlider]:
        """Return the two backing handle sliders for track styling.

        Returns:
            The ``(low, high)`` :class:`QSlider` pair so the renderer can paint
            the resolved active/inactive track QSS onto both handles.
        """
        return self._low_slider, self._high_slider

    def configure_range(self, minimum: int, maximum: int, step: int) -> None:
        """Set the shared bounds and step of both handles.

        Args:
            minimum: The lowest selectable value.
            maximum: The highest selectable value.
            step: The single-step increment (clamped to at least ``1``).
        """
        for slider in (self._low_slider, self._high_slider):
            slider.setMinimum(minimum)
            slider.setMaximum(maximum)
            slider.setSingleStep(max(step, 1))

    def set_values(self, low: int, high: int) -> None:
        """Set both handles without emitting a change.

        Args:
            low: The lower-bound value.
            high: The upper-bound value.
        """
        self._low_slider.blockSignals(True)
        self._high_slider.blockSignals(True)
        self._low_slider.setValue(low)
        self._high_slider.setValue(max(high, low))
        self._low_slider.blockSignals(False)
        self._high_slider.blockSignals(False)

    def set_on_change(self, callback: Callable[[int, int], None] | None) -> None:
        """Install (or clear) the range-change callback.

        Args:
            callback: A callable receiving ``(low, high)``, or ``None``.
        """
        self._on_change = callback

    def values(self) -> tuple[int, int]:
        """Return the current ``(low, high)`` pair.

        Returns:
            The current lower and upper bounds.
        """
        return self._low_slider.value(), self._high_slider.value()

    def _clamp_low(self, value: int) -> None:
        """Keep the low handle at or below the high handle, then notify.

        Args:
            value: The low slider's new value.
        """
        if value > self._high_slider.value():
            self._high_slider.blockSignals(True)
            self._high_slider.setValue(value)
            self._high_slider.blockSignals(False)
        self._notify()

    def _clamp_high(self, value: int) -> None:
        """Keep the high handle at or above the low handle, then notify.

        Args:
            value: The high slider's new value.
        """
        if value < self._low_slider.value():
            self._low_slider.blockSignals(True)
            self._low_slider.setValue(value)
            self._low_slider.blockSignals(False)
        self._notify()

    def _notify(self) -> None:
        """Forward the current pair to the installed callback (if any)."""
        if self._on_change is not None:
            self._on_change(self._low_slider.value(), self._high_slider.value())


class _PinInputWidget(QWidget):
    """A segmented PIN/OTP entry of single-character ``QLineEdit`` cells.

    Each cell holds one character and auto-advances focus to the next as it is
    filled (and steps back on backspace into an empty cell). On every edit the
    installed change callback receives the concatenated value; once every cell is
    filled the complete callback fires. The device renderer uses chained Compose
    ``BasicTextField``s with a ``FocusRequester`` (a documented divergence; the
    emitted events match).
    """

    def __init__(self) -> None:
        """Create an empty PIN widget (cells are built by :meth:`configure`)."""
        super().__init__()
        self._layout: QHBoxLayout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._cells: list[QLineEdit] = []
        self._on_change: Callable[[str], None] | None = None
        self._on_complete: Callable[[str], None] | None = None
        self._secure: bool = False

    def configure(self, length: int, secure: bool) -> None:
        """(Re)build the cells for ``length`` and the masking mode.

        Rebuilds only when the count changes; otherwise just refreshes masking so
        the typed value is preserved across idempotent updates.

        Args:
            length: The number of single-character cells.
            secure: Whether each cell masks its character.
        """
        self._secure = secure
        if len(self._cells) != max(length, 1):
            self._rebuild(max(length, 1))
        echo = QLineEdit.EchoMode.Password if secure else QLineEdit.EchoMode.Normal
        for cell in self._cells:
            cell.setEchoMode(echo)

    def set_value(self, value: str) -> None:
        """Distribute ``value`` across the cells without emitting a change.

        Args:
            value: The concatenated value to spread one character per cell.
        """
        for index, cell in enumerate(self._cells):
            char = value[index] if index < len(value) else ""
            if cell.text() != char:
                cell.blockSignals(True)
                cell.setText(char)
                cell.blockSignals(False)

    def set_callbacks(
        self,
        on_change: Callable[[str], None] | None,
        on_complete: Callable[[str], None] | None,
    ) -> None:
        """Install (or clear) the change and complete callbacks.

        Args:
            on_change: Invoked with the concatenated value on every edit.
            on_complete: Invoked with the value once all cells are filled.
        """
        self._on_change = on_change
        self._on_complete = on_complete

    def value(self) -> str:
        """Return the concatenated value across all cells.

        Returns:
            The current PIN/OTP string.
        """
        return "".join(cell.text() for cell in self._cells)

    def _rebuild(self, length: int) -> None:
        """Tear down and recreate ``length`` single-character cells.

        Args:
            length: The number of cells to create.
        """
        for cell in self._cells:
            cell.setParent(None)
            cell.deleteLater()
        self._cells = []
        for index in range(length):
            cell = QLineEdit()
            cell.setMaxLength(1)
            cell.setFixedWidth(_PIN_CELL_WIDTH)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.textChanged.connect(self._make_cell_slot(index))
            self._layout.addWidget(cell)
            self._cells.append(cell)

    def _make_cell_slot(self, index: int) -> Callable[[str], None]:
        """Build the ``textChanged`` slot for the cell at ``index``.

        A factory (rather than an inline lambda) so the slot's ``text`` parameter
        is typed for the strict checker.

        Args:
            index: The cell's position.

        Returns:
            A one-argument slot forwarding edits to :meth:`_on_cell_changed`.
        """

        def slot(text: str) -> None:
            self._on_cell_changed(index, text)

        return slot

    def _on_cell_changed(self, index: int, text: str) -> None:
        """Auto-advance focus and forward the value after a cell edit.

        Args:
            index: The edited cell's position.
            text: The cell's new text.
        """
        if text and index + 1 < len(self._cells):
            self._cells[index + 1].setFocus()
        elif not text and index > 0:
            self._cells[index - 1].setFocus()
        value = self.value()
        if self._on_change is not None:
            self._on_change(value)
        if self._on_complete is not None and len(value) == len(self._cells):
            self._on_complete(value)


class _FormFieldWidget(QWidget):
    """A labelled wrapper around one input with an inline error line.

    Lays out a label above the wrapped input and a red error label below it. The
    wrapped input is the form field's single IR child, so it is mounted into
    :attr:`content_layout` through the renderer's generic child path. The error
    label is hidden while the field is valid (its message is the empty string).
    Mirrors Compose's ``Column(label / child / red error Text)``.
    """

    def __init__(self) -> None:
        """Create the label, child slot and (hidden) error line."""
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        self._label: QLabel = QLabel()
        self._label.setVisible(False)
        outer.addWidget(self._label)
        #: The slot the wrapped input is mounted into (the field's IR child).
        self.content_layout: QVBoxLayout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.content_layout)
        self._error: QLabel = QLabel()
        _scoped_stylesheet(self._error, "color: #d32f2f")
        self._error.setVisible(False)
        outer.addWidget(self._error)

    def set_label(self, text: str) -> None:
        """Set the field label, hiding it when empty.

        Args:
            text: The label text (``""`` hides the label line).
        """
        self._label.setText(text)
        self._label.setVisible(bool(text))

    def set_error(self, text: str) -> None:
        """Set the error message, hiding the line when valid.

        Args:
            text: The validation message (``""`` hides the error line).
        """
        self._error.setText(text)
        self._error.setVisible(bool(text))

    def error_text(self) -> str:
        """Return the currently shown error message (for tests/introspection).

        Returns:
            The error label's text (``""`` when the field is valid).
        """
        return self._error.text()

    def error_visible(self) -> bool:
        """Whether the error line is currently shown (independent of the window).

        Uses the widget's local visibility flag (``isVisibleTo`` its parent)
        rather than effective visibility, so it reports correctly under the
        offscreen platform where the host window is never shown.

        Returns:
            ``True`` when an error message is visible.
        """
        return self._error.isVisibleTo(self)


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


class _HostWidget(QWidget):
    """The renderer's host widget; reports its size on resize for MediaQuery.

    The host is the single window-filling surface whose child is the app root, so
    its size *is* the viewport. On every resize it forwards the new logical size
    (and the screen's device-pixel ratio) to a callback the renderer wires to
    ``App._update_media`` — the desktop analogue of Compose reading
    ``LocalConfiguration`` on a configuration change.
    """

    def __init__(self) -> None:
        """Create the host with no resize observer wired yet."""
        super().__init__()
        self._on_resize: Callable[[int, int], None] = lambda _w, _h: None

    def set_resize_observer(self, observer: Callable[[int, int], None]) -> None:
        """Install the resize callback invoked with the new ``(width, height)``.

        Args:
            observer: Called as ``observer(width, height)`` on each resize.
        """
        self._on_resize = observer

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        """Forward the new size to the observer, then chain to the base.

        Args:
            event: The Qt resize event (carries the new size).
        """
        super().resizeEvent(event)
        size = event.size()
        self._on_resize(size.width(), size.height())


class QtRenderer:
    """Render an IR tree into Qt widgets and keep it in sync via patches."""

    def __init__(self) -> None:
        """Create the renderer and its empty host widget."""
        self.host: _HostWidget = _HostWidget()
        self.host.set_resize_observer(self._on_host_resize)
        self._host_layout: QVBoxLayout = QVBoxLayout(self.host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._root: _Rendered | None = None
        # The live app, wired by ``set_app`` so the renderer can read the active
        # theme/locale/media context (E9). ``None`` when the renderer runs
        # standalone in a unit test that mounts a bare node tree.
        self._app: App[Any] | None = None
        # The current layout direction, mirrored from ``app.locale.rtl`` so every
        # ``to_qss`` call passes a consistent ``rtl`` flag without re-reading the
        # app each time.
        self._rtl: bool = False
        # The last theme mode applied to the ``QApplication`` palette, so a no-op
        # rebuild (same mode) does not repaint the whole tree needlessly.
        self._applied_theme: ThemeMode | None = None
        # Bundle root used to resolve a relative ``style.font_asset`` path; defaults
        # to the current working directory (overridable via ``set_bundle_root``).
        self._bundle_root: FsPath = FsPath.cwd()
        # Custom font assets already probed (resolved path → loaded family name,
        # empty when the file was missing/unloadable), so each file loads exactly
        # once across the app's lifetime.
        self._loaded_fonts: dict[str, str] = {}
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
        # Live leading/trailing vector-icon slot actions, keyed by line-edit id,
        # so an ``leading_icon``/``trailing_icon`` change replaces (never stacks)
        # the in-field glyph and a ``None`` removes it. Each entry tracks the
        # current ``(icon_name, QAction)`` per edge.
        self._leading_icons: dict[int, tuple[str, QAction]] = {}
        self._trailing_icons: dict[int, tuple[str, QAction]] = {}
        # A second value connection per widget, for the few controls that wire two
        # distinct signals (``Autocomplete``: ``textChanged`` via ``_value_conns``
        # plus the completer's ``activated`` here). Keyed by the line-edit id.
        self._select_conns: dict[
            int, tuple[SignalInstance, QMetaObject.Connection]
        ] = {}
        # Live ``QCompleter`` options per autocomplete line-edit, so an ``options``
        # change rebuilds the completer cleanly without re-reading the Qt model.
        self._completer_options: dict[int, list[str]] = {}

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

    def set_app(self, app: App[Any]) -> None:
        """Wire the live app so the renderer can read its theme/locale/media.

        The app runner passes the running :class:`~tempestroid.core.state.App`
        here. The renderer reads ``app.theme.mode`` (to swap the palette),
        ``app.locale.rtl`` (to set the layout direction and pass ``rtl`` to every
        ``to_qss`` call) and forwards resize events to ``app._update_media``. With
        no app wired the renderer runs standalone (bare-node unit tests): the
        theme/RTL features default to light/LTR.

        Args:
            app: The running app providing the theme/locale/media context.
        """
        self._app = app
        self.sync_context()

    def set_bundle_root(self, root: FsPath) -> None:
        """Set the directory a relative ``style.font_asset`` path resolves against.

        Args:
            root: The bundle root (typically the app file's directory).
        """
        self._bundle_root = root

    def sync_context(self) -> None:
        """Re-read the app's theme/locale and apply the palette + direction.

        Idempotent and cheap: applying the same theme twice is a no-op, and the
        layout direction is only touched when it actually flips. The app runner
        calls this after each rebuild so a ``set_theme`` / ``set_locale`` (which
        only schedules a rebuild) takes visual effect.
        """
        if self._app is None:
            return
        platform_dark = self._app.media.platform_dark_mode
        mode = self._app.theme.mode
        self._apply_theme(mode, platform_dark_mode=platform_dark)
        rtl = self._app.locale.rtl
        if rtl != self._rtl:
            self._rtl = rtl
            direction = (
                Qt.LayoutDirection.RightToLeft
                if rtl
                else Qt.LayoutDirection.LeftToRight
            )
            self.host.setLayoutDirection(direction)
            # Re-apply the QSS box model so mirrored padding/borders follow the
            # new direction (``to_qss`` reads ``rtl`` at apply time).
            if self._root is not None:
                self._reapply_visuals(self._root)

    def _reapply_visuals(self, node: _Rendered) -> None:
        """Re-run ``_apply_visual`` across a subtree (after an RTL flip).

        Args:
            node: The root of the rendered subtree to refresh.
        """
        self._apply_visual(node)
        for child in node.children:
            self._reapply_visuals(child)

    def _apply_theme(
        self, mode: ThemeMode, *, platform_dark_mode: bool = False
    ) -> None:
        """Swap the ``QApplication`` palette to the resolved light/dark scheme.

        ``SYSTEM`` resolves against the platform: PySide6 ≥ 6.5 exposes
        ``QStyleHints.colorScheme()``; older builds (or when it is unknown) fall
        back to the ``platform_dark_mode`` flag the media query carries. Applying
        the same mode twice is a no-op so an unrelated rebuild never repaints.

        Args:
            mode: The active theme mode.
            platform_dark_mode: The OS dark-mode flag used to resolve ``SYSTEM``.
        """
        if mode is ThemeMode.SYSTEM:
            dark = self._system_dark(fallback=platform_dark_mode)
        else:
            dark = mode is ThemeMode.DARK
        resolved = ThemeMode.DARK if dark else ThemeMode.LIGHT
        if resolved is self._applied_theme:
            return
        self._applied_theme = resolved
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        palette = QPalette()
        scheme = _DARK_PALETTE if dark else _LIGHT_PALETTE
        for role, (r, g, b) in scheme.items():
            palette.setColor(role, QColor(r, g, b))
        app.setPalette(palette)
        # Repaint the whole host so already-styled leaves pick up the new palette
        # roles (QSS rules a node sets still win — the palette is the base).
        self.host.update()

    @staticmethod
    def _system_dark(*, fallback: bool) -> bool:
        """Resolve the OS dark-mode setting for ``ThemeMode.SYSTEM``.

        Args:
            fallback: The value to use when the platform cannot report a scheme
                (older PySide6, or an ``Unknown`` color scheme).

        Returns:
            ``True`` when the OS reports a dark color scheme.
        """
        hints = QGuiApplication.styleHints()
        color_scheme = getattr(hints, "colorScheme", None)
        if color_scheme is None:
            return fallback
        try:
            scheme = color_scheme()
        except (RuntimeError, TypeError):
            return fallback
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
        return fallback

    def _on_host_resize(self, width: int, height: int) -> None:
        """Forward a host resize to ``App._update_media`` as a fresh snapshot.

        Builds a :class:`MediaQueryData` from the new logical size, the screen's
        device-pixel ratio, and the orientation derived from the aspect, carrying
        the existing text-scale and platform-dark flags forward. Pushing it
        through ``App._update_media`` schedules a coalesced rebuild so the view
        can lay out responsively. A no-op when no app is wired.

        Args:
            width: The host's new logical width in pixels.
            height: The host's new logical height in pixels.
        """
        if self._app is None:
            return
        # ``devicePixelRatioF`` on the widget reflects its current screen's DPR
        # without the stub's never-None ``screen()`` narrowing complaint.
        dpr = self.host.devicePixelRatioF()
        previous = self._app.media
        snapshot = MediaQueryData(
            width=float(width),
            height=float(height),
            device_pixel_ratio=dpr,
            text_scale_factor=previous.text_scale_factor,
            platform_dark_mode=previous.platform_dark_mode,
            orientation="landscape" if width >= height else "portrait",
        )
        # ``_update_media`` is the documented renderer→App entry point per the E9
        # contract (the renderer is its sole caller). Resolve it dynamically so
        # the intentional cross-class call reads as the contract sanctions it.
        update_media = cast(
            "Callable[[MediaQueryData], None]",
            getattr(self._app, "_update_media"),  # noqa: B009
        )
        update_media(snapshot)

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
        self._apply_focus_order()
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
        self._leading_icons.clear()
        self._trailing_icons.clear()
        self._select_conns.clear()
        self._completer_options.clear()
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
        if patches:
            # A structural change (or a focus_order prop update) may have moved
            # the focus chain; recompute the explicit tab order once per batch.
            self._apply_focus_order()

    def _apply_focus_order(self) -> None:
        """Chain widgets with an explicit ``focus_order`` into ascending tab order.

        Walks the rendered root tree, collects every node carrying a
        ``focus_order`` prop, sorts them ascending, and wires consecutive pairs
        with ``QWidget.setTabOrder`` so Tab moves through them in that order.
        Nodes without ``focus_order`` keep Qt's natural (creation-order) tabbing.
        A no-op when fewer than two nodes declare an order.
        """
        if self._root is None:
            return
        ordered: list[tuple[int, QWidget]] = []
        self._collect_focus_order(self._root, ordered)
        ordered.sort(key=lambda pair: pair[0])
        for (_, first), (_, second) in zip(ordered, ordered[1:], strict=False):
            QWidget.setTabOrder(first, second)

    def _collect_focus_order(
        self, node: _Rendered, out: list[tuple[int, QWidget]]
    ) -> None:
        """Accumulate ``(focus_order, widget)`` pairs across a rendered subtree.

        Args:
            node: The subtree root to walk.
            out: The accumulator list to append matching pairs to.
        """
        order = node.props.get("focus_order")
        if isinstance(order, int):
            out.append((order, node.widget))
        for child in node.children:
            self._collect_focus_order(child, out)

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

    def _replace_overlay(self, index: int, old: _Rendered, patch: Replace) -> None:
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

    def _show_dialog_surface(self, overlay: _Rendered, dialog: _DismissDialog) -> None:
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
            y = anchor.y() if anchor is not None else host_global.y() + 24
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

    def _make_select(self, overlay: _Rendered, item: MenuItem) -> Callable[[], None]:
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
        if parent.type == "Wrap":
            cast("_WrapWidget", parent.widget).remove_child(old.widget)
            new.widget.setParent(parent.widget)
            parent.children[index] = new
            self._purge_connections(old)
            self._discard(old.widget)
            self._sync_wrap(parent)
            return
        if parent.type == "PageView":
            page_view = cast("_PageViewWidget", parent.widget)
            page_view.removeWidget(old.widget)
            page_view.insertWidget(index, new.widget)
            parent.children[index] = new
            self._purge_connections(old)
            self._discard(old.widget)
            self._sync_page_view(parent)
            return
        if parent.type == "AspectRatio":
            cast("_AspectRatioWidget", parent.widget).clear_child()
            cast("_AspectRatioWidget", parent.widget).set_child(new.widget)
            parent.children[index] = new
            self._purge_connections(old)
            self._discard(old.widget)
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
        self._animate_heroes(old, new)
        host.animate_to(host.current_page, transition, forward)
        self._purge_connections(old)

    def _collect_heroes(self, node: _Rendered) -> dict[str, _Rendered]:
        """Map ``hero_tag`` → rendered ``Hero`` node within a subtree.

        Args:
            node: The subtree root to scan.

        Returns:
            A dict keyed by hero tag; later duplicates win (last one wins).
        """
        found: dict[str, _Rendered] = {}

        def _walk(current: _Rendered) -> None:
            if current.type == "Hero":
                tag = cast("str", current.props.get("hero_tag", ""))
                if tag:
                    found[tag] = current
            for child in current.children:
                _walk(child)

        _walk(node)
        return found

    def _animate_heroes(self, old: _Rendered, new: _Rendered) -> None:
        """Interpolate geometry between matching heroes across a screen swap.

        For every ``hero_tag`` present in *both* the outgoing and incoming
        screens, the incoming hero widget is animated from the outgoing hero's
        on-screen rectangle to its own — a shared-element transition. The
        simulator approximates Compose's ``SharedTransitionLayout`` with a
        ``QPropertyAnimation`` on ``geometry`` (a documented divergence). Heroes
        present on only one side are left to the page transition.

        Args:
            old: The outgoing screen rendered node.
            new: The incoming screen rendered node.
        """
        old_heroes = self._collect_heroes(old)
        new_heroes = self._collect_heroes(new)
        for tag, new_hero in new_heroes.items():
            old_hero = old_heroes.get(tag)
            if old_hero is None:
                continue
            start = old_hero.widget.geometry()
            if start.width() <= 0 or start.height() <= 0:
                continue
            target = new_hero.widget
            anim = QPropertyAnimation(target, b"geometry", target)
            anim.setDuration(_NAV_ANIM_MS)
            anim.setStartValue(QRect(start))
            anim.setEndValue(target.geometry())
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._start_hero_anim(anim)

    def _start_hero_anim(self, anim: QPropertyAnimation) -> None:
        """Start a hero geometry animation, holding a strong ref until it ends.

        Args:
            anim: The configured geometry animation.
        """
        self._pending_anims.add(anim)
        anim.finished.connect(lambda: self._pending_anims.discard(anim))
        anim.start()

    def _apply_insert(self, patch: Insert) -> None:
        """Insert a new child subtree under a parent.

        Args:
            patch: The insert patch.
        """
        parent = self._at(patch.path)
        child = self._create(patch.node)
        if parent.type in ("Stack", "RouteDrawer", "LazyGrid", "Wrap"):
            child.widget.setParent(parent.widget)
            parent.children.insert(patch.index, child)
            if parent.type == "RouteDrawer":
                self._sync_drawer(parent)
            elif parent.type == "LazyGrid":
                self._relayout_grid(parent)
            elif parent.type == "Wrap":
                self._sync_wrap(parent)
            else:
                self._relayout_stack(parent)
            return
        if parent.type == "PageView":
            page_view = cast("_PageViewWidget", parent.widget)
            page_view.insertWidget(patch.index, child.widget)
            parent.children.insert(patch.index, child)
            self._sync_page_view(parent)
            return
        if parent.type == "AspectRatio":
            cast("_AspectRatioWidget", parent.widget).set_child(child.widget)
            parent.children.insert(patch.index, child)
            return
        layout = self._require_layout(parent)
        # Strip spacers so the IR index maps to the layout slot for the insert.
        self._strip_spacers(layout)
        parent.children.insert(patch.index, child)
        layout.insertWidget(patch.index, child.widget, self._stretch(child))
        self._place_alignment(parent, child)
        self._sync_main_axis(parent)
        if parent.type == "AnimatedList":
            cast("_AnimatedListWidget", parent.widget).animate_in(
                child.widget,
                int(cast("int", parent.props.get("enter_duration_ms", 300))),
            )
        if parent.type == "SectionList":
            self._sync_sticky_header(parent)

    def _apply_remove(self, patch: Remove) -> None:
        """Remove a child subtree from a parent.

        Args:
            patch: The remove patch.
        """
        parent = self._at(patch.path)
        child = parent.children.pop(patch.index)
        if parent.type in ("Stack", "RouteDrawer", "LazyGrid", "Wrap"):
            if parent.type == "Wrap":
                cast("_WrapWidget", parent.widget).remove_child(child.widget)
            self._purge_connections(child)
            self._discard(child.widget)
            if parent.type == "RouteDrawer":
                self._sync_drawer(parent)
            elif parent.type == "LazyGrid":
                self._relayout_grid(parent)
            elif parent.type == "Wrap":
                self._sync_wrap(parent)
            else:
                self._relayout_stack(parent)
            return
        if parent.type == "PageView":
            cast("_PageViewWidget", parent.widget).removeWidget(child.widget)
            self._purge_connections(child)
            self._discard(child.widget)
            self._sync_page_view(parent)
            return
        if parent.type == "AspectRatio":
            cast("_AspectRatioWidget", parent.widget).clear_child()
            self._purge_connections(child)
            self._discard(child.widget)
            return
        if parent.type == "AnimatedList":
            self._purge_connections(child)
            list_widget = cast("_AnimatedListWidget", parent.widget)
            target = child.widget
            list_widget.animate_out(
                target,
                int(cast("int", parent.props.get("exit_duration_ms", 300))),
                on_done=lambda: self._finish_animated_remove(list_widget, target),
            )
            self._sync_main_axis(parent)
            return
        self._require_layout(parent).removeWidget(child.widget)
        self._purge_connections(child)
        self._discard(child.widget)
        self._sync_main_axis(parent)
        if parent.type == "SectionList":
            self._sync_sticky_header(parent)

    @staticmethod
    def _finish_animated_remove(
        list_widget: _AnimatedListWidget, widget: QWidget
    ) -> None:
        """Remove and delete a child once its exit animation has settled.

        Args:
            list_widget: The animated-list container the child left.
            widget: The collapsed child widget to discard.
        """
        list_widget.box_layout().removeWidget(widget)
        widget.setParent(None)  # type: ignore[call-overload]
        widget.deleteLater()

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
        if parent.type == "Wrap":
            parent.children = new_children
            self._sync_wrap(parent)
            return
        if parent.type == "PageView":
            page_view = cast("_PageViewWidget", parent.widget)
            for child in old_children:
                page_view.removeWidget(child.widget)
            for child in new_children:
                page_view.addWidget(child.widget)
            parent.children = new_children
            self._sync_page_view(parent)
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
            if rendered.type == "InteractiveViewer":
                # The child is embedded in a QGraphicsScene via a proxy, not a
                # box layout — pan/zoom act on the scene transform.
                cast("_InteractiveViewerWidget", rendered.widget).set_child(
                    child.widget
                )
            elif rendered.type in ("Stack", "RouteDrawer", "LazyGrid", "Wrap"):
                # Direct children (no box layout): geometry is renderer-driven.
                child.widget.setParent(rendered.widget)
            elif rendered.type == "PageView":
                # Each child is a carousel page stacked in the QStackedWidget.
                cast("_PageViewWidget", rendered.widget).addWidget(child.widget)
            elif rendered.type == "AspectRatio":
                # A single fitted child centered to the ratio (renderer-driven).
                cast("_AspectRatioWidget", rendered.widget).set_child(child.widget)
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
        elif rendered.type == "Wrap":
            self._sync_wrap(rendered)
        elif rendered.type == "PageView":
            self._sync_page_view(rendered)
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
        if node.type == "IconButton":
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
        if node.type == "Dropdown":
            return _Rendered(node.type, node.key, QComboBox(), None)
        if node.type == "TimePicker":
            edit = QTimeEdit()
            edit.setDisplayFormat(_TIME_FORMAT)
            return _Rendered(node.type, node.key, edit, None)
        if node.type == "RangeSlider":
            return _Rendered(node.type, node.key, _RangeSliderWidget(), None)
        if node.type == "Autocomplete":
            return _Rendered(node.type, node.key, QLineEdit(), None)
        if node.type == "PinInput":
            return _Rendered(node.type, node.key, _PinInputWidget(), None)
        if node.type == "MaskedInput":
            return _Rendered(node.type, node.key, QLineEdit(), None)
        if node.type == "FormField":
            field = _FormFieldWidget()
            # The wrapped input (the field's IR child) flows into the content slot
            # through the generic child path, so expose it as the node's layout.
            return _Rendered(node.type, node.key, field, field.content_layout)
        if node.type == "Form":
            form = QWidget()
            form_layout: QBoxLayout = QVBoxLayout(form)
            form_layout.setContentsMargins(0, 0, 0, 0)
            return _Rendered(node.type, node.key, form, form_layout)
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
        if node.type == "PanHandler":
            pan = _PanWidget()
            return _Rendered(node.type, node.key, pan, cast("QBoxLayout", pan.layout()))
        if node.type == "ScaleHandler":
            scaler = _ScaleWidget()
            return _Rendered(
                node.type, node.key, scaler, cast("QBoxLayout", scaler.layout())
            )
        if node.type == "DoubleTapHandler":
            dbl = _DoubleTapWidget()
            return _Rendered(node.type, node.key, dbl, cast("QBoxLayout", dbl.layout()))
        if node.type == "Dismissible":
            dismissible = _DismissibleWidget()
            return _Rendered(
                node.type,
                node.key,
                dismissible,
                cast("QBoxLayout", dismissible.layout()),
            )
        if node.type in ("Draggable", "DragTarget"):
            # Plain single-child wrappers: the Qt simulator carries the child
            # untouched and binds the drag/drop handlers, but native
            # cross-widget QDrag wiring between a free-floating Draggable and a
            # DragTarget is a documented v1 gap (the device renderer realizes
            # the full drag-and-drop).
            wrap = QWidget()
            wrap_layout: QBoxLayout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            return _Rendered(node.type, node.key, wrap, wrap_layout)
        if node.type == "ReorderableList":
            reorderable = _ReorderableWidget()
            return _Rendered(node.type, node.key, reorderable, reorderable.box_layout())
        if node.type == "InteractiveViewer":
            return _Rendered(node.type, node.key, _InteractiveViewerWidget(), None)
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
            label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            _scoped_stylesheet(
                label,
                "background: rgba(33, 33, 33, 0.92); color: white;"
                " padding: 8px 14px; border-radius: 8px",
            )
            return _Rendered(node.type, node.key, label, None)
        if node.type in ("Animated", "Hero"):
            # A single-child wrapper: the ``view`` already interpolated the child's
            # style per frame (Animated) — the renderer just mounts it.
            wrapper = QWidget()
            wrap_layout = QVBoxLayout(wrapper)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            return _Rendered(node.type, node.key, wrapper, wrap_layout)
        if node.type == "AnimatedList":
            horizontal = str(node.props.get("direction", "column")) == "row"
            anim_list = _AnimatedListWidget(horizontal=horizontal)
            return _Rendered(node.type, node.key, anim_list, anim_list.box_layout())
        if node.type == "Shimmer":
            shimmer = _ShimmerWidget()
            return _Rendered(node.type, node.key, shimmer, shimmer.box_layout())
        if node.type == "Skeleton":
            return _Rendered(node.type, node.key, _SkeletonWidget(), None)
        if node.type == "Wrap":
            # Direct-children flow container: geometry is renderer-driven, so it
            # carries no box layout (layout=None) like Stack/LazyGrid.
            return _Rendered(node.type, node.key, _WrapWidget(), None)
        if node.type == "PageView":
            return _Rendered(node.type, node.key, _PageViewWidget(), None)
        if node.type == "AspectRatio":
            ratio = float(cast("float", node.props.get("ratio", 1.0)))
            return _Rendered(node.type, node.key, _AspectRatioWidget(ratio), None)
        if node.type == "Canvas":
            return _Rendered(node.type, node.key, _CanvasWidget(), None)
        if node.type == "VideoPlayer":
            return _Rendered(node.type, node.key, self._new_video_widget(), None)
        if node.type == "WebView":
            return _Rendered(node.type, node.key, self._new_web_view(), None)
        if node.type == "Svg":
            return _Rendered(node.type, node.key, QLabel(), None)
        if node.type in ("Blur", "BackdropFilter"):
            # Single-child wrapper: the child flows through the generic child
            # path into the box layout; the blur effect is applied in
            # ``_apply_visual``.
            wrapper = QWidget()
            blur_layout: QBoxLayout = QVBoxLayout(wrapper)
            blur_layout.setContentsMargins(0, 0, 0, 0)
            return _Rendered(node.type, node.key, wrapper, blur_layout)
        if node.type == "ClipPath":
            clip = _ClipWidget()
            return _Rendered(
                node.type, node.key, clip, cast("QBoxLayout", clip.layout())
            )
        if node.type in _E7_PLACEHOLDER_TYPES:
            return _Rendered(node.type, node.key, QLabel(), None)
        if node.type == "KeyboardAvoidingView":
            avoiding = _KeyboardAvoidingWidget()
            return _Rendered(
                node.type, node.key, avoiding, cast("QBoxLayout", avoiding.layout())
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
    def _new_video_widget() -> QWidget:
        """Build the backing widget for a ``VideoPlayer``.

        When the Qt multimedia stack is available a ``QVideoWidget`` is returned
        with its ``QMediaPlayer`` and ``QAudioOutput`` parented to it (so Qt
        keeps them alive) and stashed as ``_player`` / ``_audio`` attributes for
        ``_apply_visual``. When multimedia is unavailable (headless/minimal Qt)
        a placeholder ``QLabel`` is returned instead — the device renderer plays
        the real stream via Media3/ExoPlayer.

        Returns:
            A ``QVideoWidget`` (with player attached) or a placeholder ``QLabel``.
        """
        loaded = _load_multimedia()
        if loaded is None:
            label = QLabel("[VideoPlayer — multimedia backend unavailable]")
            return label
        media_player_cls, audio_output_cls, video_widget_cls = loaded
        video = cast("QWidget", video_widget_cls())
        player = media_player_cls(video)
        audio = audio_output_cls(video)
        player.setAudioOutput(audio)
        player.setVideoOutput(video)
        # Stash on the widget so ``_apply_visual`` can re-configure the source.
        video._player = player  # pyright: ignore[reportAttributeAccessIssue]
        video._audio = audio  # pyright: ignore[reportAttributeAccessIssue]
        return video

    @staticmethod
    def _new_web_view() -> QWidget:
        """Build the backing widget for a ``WebView``.

        Uses ``QWebEngineView`` when the (separately packaged) WebEngine wheel is
        installed; otherwise falls back to a placeholder ``QLabel`` so the
        simulator never crashes on a minimal PySide6 install.

        Returns:
            A ``QWebEngineView`` or a placeholder ``QLabel``.
        """
        web_view_cls = _load_web_engine()
        if web_view_cls is None:
            return QLabel("[WebView — QtWebEngine unavailable]")
        return cast("QWidget", web_view_cls())

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
        # Register a custom font asset (once) and learn its real family name so
        # the renderer can bind it to the widget's font — QSS cannot alias a
        # loaded font to the ``"CustomAsset"`` family ``to_qss`` references, so the
        # widget font is the faithful channel for the custom typeface.
        custom_family = self._ensure_font_asset(style)
        qss_style = style
        if node.type in _SELECTION_TYPES and style is not None:
            # A selection control's resolved ``background`` (accent fill when
            # checked) / ``border`` (the empty ring) / ``color`` (the tick) belong
            # to the ``::indicator`` box, painted by ``_apply_selection_states`` —
            # NOT to the whole QCheckBox body, where ``background`` would fill the
            # entire row with the accent (a solid bar instead of a box + label).
            # Strip them from the widget's resting QSS; the label then uses the
            # default palette color and the accent lands only on the indicator.
            qss_style = style.model_copy(
                update={"background": None, "border": None, "color": None}
            )
        qss = self._node_qss(
            qss_style, is_container=is_container, custom_family=custom_family
        )
        # Scope the QSS to the widget itself (``#objectName``) so box decoration
        # (border/background/radius) never cascades onto descendants — a bare body
        # acts as a universal selector in Qt and would tint/box every child.
        _scoped_stylesheet(node.widget, qss)
        if style is not None and (
            style.background is not None
            or style.radius is not None
            or style.margin is not None
        ):
            # Qt only clips a QSS ``background-color`` to ``border-radius`` when the
            # widget paints a styled background; without a border, a rounded
            # background-only box renders square unless this attribute is set. The
            # same styled-background pass is what makes a QSS ``margin`` render as
            # true outer space (the box paints inside the margin), so set it when a
            # margin is present too.
            node.widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_custom_font(node.widget, custom_family)
        self._apply_accessibility(node)
        if node.layout is not None:
            self._apply_container_layout(node.layout, node.type, style)
            if node.type == "SafeArea":
                self._apply_safe_area(
                    node.layout,
                    style,
                    cast("list[Any] | None", node.props.get("edges")),
                )
            elif node.type == "KeyboardAvoidingView":
                # ``_apply_container_layout`` set the padding margins; hand them to
                # the widget as the *base* so the keyboard inset adds on top.
                margins = node.layout.contentsMargins()
                cast("_KeyboardAvoidingWidget", node.widget).set_base_margins(
                    (
                        margins.left(),
                        margins.top(),
                        margins.right(),
                        margins.bottom(),
                    )
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
        elif node.type == "Dropdown":
            self._apply_dropdown(cast("QComboBox", node.widget), node.props)
        elif node.type == "TimePicker":
            self._apply_timepicker(cast("QTimeEdit", node.widget), node.props)
        elif node.type == "RangeSlider":
            self._apply_range_slider(
                cast("_RangeSliderWidget", node.widget), node.props
            )
        elif node.type == "Autocomplete":
            self._apply_autocomplete(cast("QLineEdit", node.widget), node.props)
        elif node.type == "PinInput":
            self._apply_pin_input(cast("_PinInputWidget", node.widget), node.props)
        elif node.type == "MaskedInput":
            self._apply_masked_input(cast("QLineEdit", node.widget), node.props)
        elif node.type == "FormField":
            self._apply_form_field(cast("_FormFieldWidget", node.widget), node.props)
        elif node.type == "Button":
            button = cast("QPushButton", node.widget)
            button.setText(cast("str", node.props.get("label", "")))
            self._bind_click(button, node.props.get("on_click"))
        elif node.type == "IconButton":
            self._apply_icon_button(cast("QPushButton", node.widget), node.props)
        elif node.type == "GestureDetector":
            self._bind_gestures(cast("_GestureWidget", node.widget), node.props)
        elif node.type in _ADVANCED_GESTURE_TYPES:
            self._bind_advanced_gestures(node)
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
        elif node.type == "Wrap":
            self._sync_wrap(node)
        elif node.type == "PageView":
            self._apply_page_view(node)
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
        elif node.type == "Hero":
            # Stamp the shared-element tag on the widget so a Navigator screen
            # swap can pair the outgoing/incoming hero and interpolate geometry.
            node.widget.setProperty(
                "tempest_hero_tag", cast("str", node.props.get("hero_tag", ""))
            )
        elif node.type in ("Shimmer", "Skeleton"):
            self._apply_shimmer(node)
        elif node.type in ("Toast", "Tooltip"):
            label = cast("QLabel", node.widget)
            label.setText(cast("str", node.props.get("message", "")))
            # ``_apply_visual`` wiped the constructor QSS with the (usually empty)
            # node style; restore the floating-pill look (a custom style still
            # wins via the merged QSS set above when one is provided).
            if style is None:
                label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                _scoped_stylesheet(
                    label,
                    "background: rgba(33, 33, 33, 0.92); color: white;"
                    " padding: 8px 14px; border-radius: 8px",
                )
        elif node.type == "Canvas":
            self._apply_canvas(cast("_CanvasWidget", node.widget), node.props)
        elif node.type == "VideoPlayer":
            self._apply_video_player(node.widget, node.props)
        elif node.type == "WebView":
            self._apply_web_view(node.widget, node.props)
        elif node.type == "Svg":
            self._apply_svg(cast("QLabel", node.widget), node.props)
        elif node.type == "ClipPath":
            self._apply_clip_path(cast("_ClipWidget", node.widget), node.props)
        elif node.type in _E7_PLACEHOLDER_TYPES:
            cast("QLabel", node.widget).setText(_E7_PLACEHOLDER_TEXT[node.type])
        self._apply_letter_spacing(node.widget, style)
        self._apply_sizing(node.widget, style)
        if node.type == "Skeleton":
            # Skeleton carries its own ``width``/``height`` props (not via
            # ``Style``); apply them after ``_apply_sizing`` so they win over its
            # flexible-size reset.
            self._apply_skeleton_size(cast("_SkeletonWidget", node.widget), node.props)
        # Now that the widget's size is pinned, clamp an over-large radius (pill
        # sentinel, circle) to ``min(w, h) / 2`` so the corners round fully
        # instead of leaving Qt's square-off of an out-of-range radius.
        self._clamp_node_radius(node.widget, style, custom_family, is_container)
        if node.type in ("Button", "IconButton"):
            # Append the M3 state-layer pseudo-state blocks AFTER the radius clamp,
            # which re-sets the (single-block) scoped stylesheet from the
            # size-adjusted style — so the hover/pressed/focus/disabled blocks are
            # emitted onto the final, clamped base body and never get clobbered.
            # ``IconButton`` is ``Variant``-based exactly like ``Button``, so it
            # reuses the same state-layer pass.
            # IconButton is a fixed square (``width==height``): strip the inherited
            # text-button ``padding`` + ``min_height`` from the resting QSS body so
            # Qt does not compute a ``min-height: content + padding`` larger than the
            # ``setFixedHeight`` square (min > max → min wins, ovalling the disc).
            # The glyph is centered by the QPushButton regardless of padding; the
            # state-layer blocks only paint bg/color/border, so they need no change.
            base_style = style
            if (
                node.type == "IconButton"
                and style is not None
                and style.width is not None
                and style.height is not None
            ):
                base_style = style.model_copy(
                    update={"padding": None, "min_height": None}
                )
            self._apply_button_states(
                cast("QPushButton", node.widget),
                node.props,
                self._button_base_qss(node.widget, base_style, custom_family),
            )
            if (
                node.type == "IconButton"
                and style is not None
                and style.width is not None
                and style.height is not None
            ):
                node.widget.setFixedSize(int(style.width), int(style.height))
        elif node.type in _FIELD_TYPES:
            # The field's resting box (OUTLINE/FILLED/FLUSHED) is already painted by
            # the scoped base block above; append the focus/invalid/hover/disabled
            # paint deltas the engine resolves for the field variant.
            self._apply_field_states(node.widget, node.props)
        elif node.type in _SELECTION_TYPES:
            self._apply_selection_states(cast("QCheckBox", node.widget), node.props)
        elif node.type in _SLIDER_TYPES:
            self._apply_slider_track(node.widget, node.props)
        self._apply_effects(node.widget, style)
        if node.type in ("Blur", "BackdropFilter"):
            # Blur is the wrapper's whole purpose, so it owns the single Qt
            # graphics-effect slot — applied after ``_apply_effects`` so it is
            # never clobbered by the (usually absent) shadow/opacity effect.
            self._apply_blur(node.widget, node.props)

    def _node_qss(
        self,
        style: Style | None,
        *,
        is_container: bool,
        custom_family: str | None,
    ) -> str:
        """Build a node's QSS body, rewriting the custom-font placeholder family.

        Factored out of :meth:`_apply_visual` so the radius-clamp pass can rebuild
        the same body from a size-adjusted style without duplicating the
        ``"CustomAsset"`` → real-family rewrite.

        Args:
            style: The node's style, or ``None``.
            is_container: Whether the node is a container (padding goes to the
                layout's ``contentsMargins`` instead of the QSS body).
            custom_family: The loaded custom-font family name, or ``None``.

        Returns:
            The bare (unscoped) QSS declaration body.
        """
        qss = to_qss(style, with_padding=not is_container, rtl=self._rtl)
        if custom_family is not None:
            # QSS ``font-family`` wins over the widget's ``QFont``, and the
            # placeholder family ``to_qss`` emits (``"CustomAsset"``) is not a real
            # font name — rewrite it to the loaded asset's actual family so the
            # custom typeface renders. (The renderer is the only place that knows
            # the real family, since it loaded the file.)
            qss = qss.replace(
                f'font-family: "{_CUSTOM_FONT_FAMILY}"',
                f'font-family: "{custom_family}"',
            )
        return qss

    def _clamp_node_radius(
        self,
        widget: QWidget,
        style: Style | None,
        custom_family: str | None,
        is_container: bool,
    ) -> None:
        """Re-apply the node's QSS with the radius clamped to the widget size.

        ``border-radius`` is left untouched when it already fits inside the box;
        an over-large radius (pill sentinel / circle) is capped at ``min(w, h)/2``
        so the corners round fully. The effective size prefers the style's fixed
        ``width``/``height`` (known immediately) and falls back to the widget's
        current geometry. When no size is known yet the raw radius stands and a
        later resize re-runs ``_apply_visual`` through the normal patch path.

        Args:
            widget: The styled widget carrying the radius.
            style: The node's style, or ``None``.
            custom_family: The loaded custom-font family name, or ``None``.
            is_container: Whether the node is a container (padding routing).
        """
        if style is None or style.radius is None:
            return
        w = int(style.width) if style.width is not None else widget.width()
        h = int(style.height) if style.height is not None else widget.height()
        if w <= 0 or h <= 0:
            return
        clamped = _clamp_radius(style.radius, w, h)
        if clamped == style.radius:
            return
        adjusted = style.model_copy(update={"radius": clamped})
        body = self._node_qss(
            adjusted, is_container=is_container, custom_family=custom_family
        )
        _scoped_stylesheet(widget, body)

    def _ensure_font_asset(self, style: Style | None) -> str | None:
        """Register a ``style.font_asset`` file with ``QFontDatabase`` (once).

        The asset path is resolved relative to the bundle root and loaded exactly
        once per resolved path; the loaded font's real family name is cached and
        returned so the renderer can bind it to the widget. A missing or
        unloadable file yields ``None`` — Qt then falls back to the default font
        (the simulator must never crash on a bad asset).

        Args:
            style: The node's style, or ``None``.

        Returns:
            The loaded font's real family name, or ``None`` when there is no
            asset (or it could not be loaded).
        """
        if style is None or style.font_asset is None:
            return None
        candidate = FsPath(style.font_asset)
        path = candidate if candidate.is_absolute() else self._bundle_root / candidate
        resolved = str(path)
        cached = self._loaded_fonts.get(resolved)
        if cached is not None:
            return cached or None
        family = ""
        if path.is_file():
            font_id = QFontDatabase.addApplicationFont(resolved)
            families = QFontDatabase.applicationFontFamilies(font_id)
            if font_id != -1 and families:
                family = families[0]
        # Cache even a failed load (empty string) so a missing asset is probed
        # only once rather than on every idempotent re-apply.
        self._loaded_fonts[resolved] = family
        return family or None

    @staticmethod
    def _apply_custom_font(widget: QWidget, family: str | None) -> None:
        """Bind a loaded custom-font ``family`` to a widget's ``QFont``.

        Applied after the QSS so the loaded typeface wins over the QSS
        ``font-family: "CustomAsset"`` rule (Qt cannot alias an application font
        to that name). A ``None`` family leaves the widget's font untouched.

        Args:
            widget: The target widget.
            family: The real family name of the loaded font, or ``None``.
        """
        if family is None:
            return
        font = widget.font()
        font.setFamily(family)
        widget.setFont(font)

    def _apply_accessibility(self, node: _Rendered) -> None:
        """Apply ``semantics`` + ``focusable`` to a node's widget (idempotent).

        ``semantics.label`` → accessible name, ``semantics.hint`` → accessible
        description (and tooltip), ``semantics.role`` → the widget's accessible
        role via :data:`_ACCESSIBLE_ROLES`. ``focusable`` toggles the focus
        policy (``True`` → ``StrongFocus``, ``False`` → ``NoFocus``); ``None``
        leaves the widget's natural focusability untouched. Re-applying with the
        fields cleared resets name/description/tooltip so an update that drops
        ``semantics`` restores the default.

        Args:
            node: The rendered node whose widget to annotate.
        """
        widget = node.widget
        semantics = cast("Semantics | None", node.props.get("semantics"))
        if semantics is not None:
            widget.setAccessibleName(semantics.label or "")
            widget.setAccessibleDescription(semantics.hint or "")
            if semantics.hint:
                widget.setToolTip(semantics.hint)
            if semantics.role is not None:
                role = _ACCESSIBLE_ROLES.get(semantics.role.lower())
                if role is not None:
                    # ``AccessibleRole`` is a dynamic property Qt's accessibility
                    # bridge reads; setting it keeps the role swappable on update.
                    widget.setProperty("tempest_a11y_role", int(role.value))
        else:
            widget.setAccessibleName("")
            widget.setAccessibleDescription("")
        focusable = node.props.get("focusable")
        if focusable is True:
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        elif focusable is False:
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

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
                style is not None and style.text_overflow is TextOverflow.ELLIPSIS
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
        (a documented divergence). When **both** dimensions are fixed the size
        policy is pinned to ``Fixed``/``Fixed`` as well, otherwise a parent
        ``QBoxLayout``'s cross-axis stretch overrides ``setFixedWidth/Height`` and
        a square box (icon disc, avatar) renders oval. Idempotent: an unset
        dimension is restored to Qt's flexible ``[0, QWIDGETSIZE_MAX]`` range and
        the size policy back to ``Preferred``/``Preferred``.

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
        if width is not None and height is not None:
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        else:
            widget.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
            )

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

    def _sync_wrap(self, parent: _Rendered) -> None:
        """Push the current child set + ``gap``/``padding`` into a wrap widget.

        ``Wrap`` flows its children imperatively, so the renderer hands the live
        child widget list to the :class:`_WrapWidget` and maps the style ``gap``
        to the inter-child spacing and ``padding`` to its contents margins.

        Args:
            parent: The ``Wrap`` rendered node.
        """
        widget = cast("_WrapWidget", parent.widget)
        style = cast("Style | None", parent.props.get("style"))
        gap = int(style.gap) if style is not None and style.gap is not None else 0
        margins = (0, 0, 0, 0)
        if style is not None and style.padding is not None:
            edge = style.padding
            margins = (
                int(edge.left),
                int(edge.top),
                int(edge.right),
                int(edge.bottom),
            )
        widget.set_spacing(gap, margins)
        widget.set_children([child.widget for child in parent.children])

    def _sync_page_view(self, parent: _Rendered) -> None:
        """Wire the page-change callback and show the active page.

        Args:
            parent: The ``PageView`` rendered node.
        """
        widget = cast("_PageViewWidget", parent.widget)
        handler = parent.props.get("on_page_change")
        if handler is None:
            widget.set_on_change(None)
        else:
            callback = cast("Callable[..., Any]", handler)
            widget.set_on_change(lambda event: self._invoke(callback, event))
        self._apply_page_view(parent)

    def _apply_page_view(self, parent: _Rendered) -> None:
        """Show the page named by the node's ``page`` prop.

        Args:
            parent: The ``PageView`` rendered node.
        """
        widget = cast("_PageViewWidget", parent.widget)
        widget.set_page(int(cast("int", parent.props.get("page", 0))))

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

    def _bind_advanced_gestures(self, node: _Rendered) -> None:
        """(Re)install handlers on an advanced-gesture widget (phase E4).

        Routes each phase-E4 widget's typed-event handlers (and any non-handler
        config props) into its backing Qt widget. ``Draggable``/``DragTarget``
        are single-child wrappers in the Qt simulator: their handlers are kept on
        the node but native cross-widget drag-and-drop is a documented v1 gap.

        Args:
            node: The advanced-gesture rendered node.
        """
        props = node.props
        if node.type == "PanHandler":
            pan = cast("_PanWidget", node.widget)
            pan.set_handlers({"on_pan": props.get("on_pan")}, self._invoke)
        elif node.type == "ScaleHandler":
            scaler = cast("_ScaleWidget", node.widget)
            scaler.set_handlers(
                {
                    "on_scale": props.get("on_scale"),
                    "on_double_tap": props.get("on_double_tap"),
                },
                self._invoke,
            )
        elif node.type == "DoubleTapHandler":
            dbl = cast("_DoubleTapWidget", node.widget)
            dbl.set_handlers(
                {"on_double_tap": props.get("on_double_tap")}, self._invoke
            )
        elif node.type == "Dismissible":
            dismissible = cast("_DismissibleWidget", node.widget)
            raw = props.get("direction", SwipeDirection.LEFT)
            direction = (
                raw if isinstance(raw, SwipeDirection) else SwipeDirection(str(raw))
            )
            dismissible.set_handlers(
                {"on_dismiss": props.get("on_dismiss")}, self._invoke, direction
            )
        elif node.type == "ReorderableList":
            reorderable = cast("_ReorderableWidget", node.widget)
            reorderable.set_handlers(
                {"on_reorder": props.get("on_reorder")}, self._invoke
            )
        elif node.type == "InteractiveViewer":
            viewer = cast("_InteractiveViewerWidget", node.widget)
            viewer.set_handlers(
                {"on_interaction": props.get("on_interaction")},
                self._invoke,
                float(cast("float", props.get("min_scale", 0.5))),
                float(cast("float", props.get("max_scale", 4.0))),
            )
        # Draggable / DragTarget keep their handlers on the node; no Qt-sim wiring.

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

    def _button_base_qss(
        self, widget: QWidget, style: Style | None, custom_family: str | None
    ) -> str:
        """Rebuild a button's resting QSS body, matching the radius-clamp pass.

        :meth:`_clamp_node_radius` may re-render the scoped base block from a
        radius-clamped style copy (a pill/circle button). This recomputes the same
        body so :meth:`_apply_button_states` appends its pseudo-state blocks onto
        the exact resting body the widget currently shows. A button is a leaf, so
        padding is part of the body (``is_container=False``).

        Args:
            widget: The button widget (for its current geometry, used to clamp).
            style: The button's style, or ``None``.
            custom_family: The loaded custom-font family name, or ``None``.

        Returns:
            The bare (unscoped, radius-clamped) QSS body.
        """
        effective = style
        if style is not None and style.radius is not None:
            w = int(style.width) if style.width is not None else widget.width()
            h = int(style.height) if style.height is not None else widget.height()
            if w > 0 and h > 0:
                clamped = _clamp_radius(style.radius, w, h)
                if clamped != style.radius:
                    effective = style.model_copy(update={"radius": clamped})
        return self._node_qss(
            effective, is_container=False, custom_family=custom_family
        )

    def _apply_button_states(
        self, button: QPushButton, props: dict[str, Any], base_qss: str
    ) -> None:
        """Emit M3 hover/pressed/focus/disabled state layers as QSS pseudo-states.

        The resting (``DEFAULT``) style is already painted by the scoped base block
        :meth:`_apply_visual` set. This augments that scoped stylesheet with
        ``#name:hover`` / ``:pressed`` / ``:focus`` / ``:disabled`` blocks so the
        button shows the Material 3 state layers on real pointer/focus events —
        the desktop analogue of the Compose renderer's ``InteractionSource`` state
        layers.

        The per-state styles are re-resolved **exactly** via
        :func:`~tempest_core.variants.resolve_variant_states`, using the node's
        ``variant`` / ``size`` / ``color_scheme`` props and the live app's
        :class:`~tempest_core.theme.Theme` (so a dark app theme yields dark state
        layers, and the M3 disabled *container* fade — which needs the theme's
        surface color, not recoverable from the baked base alone — is exact). With
        no app wired (a bare-node unit test) it falls back to the baseline
        :class:`~tempest_core.theme.Theme`, so the simulator still shows the right
        layers standalone. A button carrying only a hand-set ``style`` (no variant
        API, e.g. a custom ``color_scheme`` outside
        :data:`~tempest_core.variants.VALID_COLOR_SCHEMES`) keeps just the base
        block — there is no variant table to resolve.

        Note: the resting block is the button's *baked* ``style`` (resolved at
        build time against the button's own ``theme`` prop); the layers are
        resolved against the app theme. These agree in the common case (both the
        baseline theme, or the app sets a theme the buttons inherit). A divergence
        documented for conformance: a button hand-pinned to a theme different from
        the live app theme paints its base from the former and its layers from the
        latter.

        Args:
            button: The Qt button to style.
            props: The button node's current props (carry ``variant``/``size``/
                ``color_scheme``; ``theme``/``media`` are excluded from the IR).
            base_qss: The resting QSS body already scoped onto the widget, kept as
                the ``#name { … }`` block the pseudo-state blocks append to.
        """
        variant = props.get("variant")
        size = props.get("size")
        color_scheme = props.get("color_scheme")
        name = button.objectName() or f"tw_{id(button):x}"
        button.setObjectName(name)
        blocks: list[str] = [f"#{name} {{ {base_qss} }}"] if base_qss else []
        if (
            not isinstance(variant, Variant)
            or not isinstance(size, (Size, dict))
            or not isinstance(color_scheme, str)
        ):
            button.setStyleSheet("\n".join(blocks))
            return
        theme = self._app.theme if self._app is not None else Theme()
        platform_dark = (
            self._app.media.platform_dark_mode if self._app is not None else False
        )
        try:
            states = resolve_variant_states(
                variant=variant,
                size=cast("ResponsiveSize", size),
                color_scheme=color_scheme,
                theme=theme,
                platform_dark_mode=platform_dark,
            )
        except ValueError:
            # An out-of-scheme ``color_scheme`` (or malformed responsive size) has
            # no variant table — keep just the resting base block.
            button.setStyleSheet("\n".join(blocks))
            return
        # Qt selector ordering: later, equally-specific blocks win, so the focus
        # block is emitted before pressed/hover (a pressed/hovered button reads as
        # active rather than merely focused). ``:disabled`` last so it overrides
        # the lot when the button is disabled.
        for state, pseudo in (
            (ComponentState.FOCUS, "focus"),
            (ComponentState.HOVER, "hover"),
            (ComponentState.PRESSED, "pressed"),
            (ComponentState.DISABLED, "disabled"),
        ):
            body = state_layer_qss(states[state])
            if body:
                blocks.append(f"#{name}:{pseudo} {{ {body} }}")
        button.setStyleSheet("\n".join(blocks))

    def _theme_and_dark(self) -> tuple[Theme, bool]:
        """Return the live app's theme + platform dark-mode flag (or baselines).

        The variant resolvers need the live :class:`~tempest_core.theme.Theme` so a
        dark app theme yields dark state layers (and the M3 disabled fade is exact).
        With no app wired (a bare-node unit test) this falls back to the baseline
        :class:`~tempest_core.theme.Theme` and light mode, so the simulator still
        shows the right layers standalone — mirroring the ``Button`` path.

        Returns:
            A ``(theme, platform_dark_mode)`` pair.
        """
        if self._app is None:
            return Theme(), False
        return self._app.theme, self._app.media.platform_dark_mode

    @staticmethod
    def _variant_props(
        props: dict[str, Any],
    ) -> tuple[ResponsiveSize, str] | None:
        """Extract a ``(size, color_scheme)`` pair from a field/selection/slider node.

        Returns ``None`` when the node carries no resolvable Chakra variant props
        (a hand-styled widget with no ``size``/``color_scheme``), so the caller
        keeps just the baked resting style with no state-layer pass.

        Args:
            props: The node's current props.

        Returns:
            The ``(size, color_scheme)`` pair, or ``None`` when not resolvable.
        """
        size = props.get("size")
        color_scheme = props.get("color_scheme")
        if not isinstance(size, (Size, dict)) or not isinstance(color_scheme, str):
            return None
        return cast("ResponsiveSize", size), color_scheme

    def _apply_field_states(self, widget: QWidget, props: dict[str, Any]) -> None:
        """Emit M3 focus/invalid/hover/disabled state layers for a field widget.

        The resting box (OUTLINE all-sides border, FILLED background, FLUSHED
        bottom-only ``SideBorder`` + radius 0) is already painted by the scoped
        base block :meth:`_apply_visual` set from the field's baked ``style``. This
        augments that scoped stylesheet with ``#name:focus`` / ``:hover`` /
        ``:disabled`` blocks re-resolved **exactly** via
        :func:`~tempest_core.variants.resolve_field_variant_states`, so the
        simulator shows the same focus ring (2px role border), invalid border
        (error role — the resolver bakes ``invalid=bool(error)``), hover border
        (on-surface-variant) and 38%-faded disabled state Compose paints natively.

        A field carrying no resolvable variant props (hand-styled) keeps just the
        base block. Pressed maps onto Qt's focus pseudo-state (a focused field is
        the desktop analogue of the M3 pressed/active field), so no ``:pressed``
        block is emitted.

        Args:
            widget: The field's backing Qt widget.
            props: The field node's current props (carry ``field_variant``/``size``/
                ``color_scheme``/``error``).
        """
        name = widget.objectName() or f"tw_{id(widget):x}"
        widget.setObjectName(name)
        base = widget.styleSheet()
        variant_props = self._variant_props(props)
        field_variant = props.get("field_variant")
        if variant_props is None or not isinstance(field_variant, FieldVariant):
            return
        size, color_scheme = variant_props
        theme, platform_dark = self._theme_and_dark()
        invalid = bool(props.get("error"))
        try:
            states = resolve_field_variant_states(
                variant=field_variant,
                size=size,
                color_scheme=color_scheme,
                theme=theme,
                invalid=invalid,
                platform_dark_mode=platform_dark,
            )
        except ValueError:
            # An out-of-scheme ``color_scheme`` has no variant table.
            return
        blocks: list[str] = [base] if base else []
        # ``:focus`` first, then ``:hover``, ``:disabled`` last — equally-specific
        # later blocks win in Qt, so a focused field reads as focused (not merely
        # hovered) and a disabled field's fade overrides everything.
        for state, pseudo in (
            (ComponentState.FOCUS, "focus"),
            (ComponentState.HOVER, "hover"),
            (ComponentState.DISABLED, "disabled"),
        ):
            body = state_layer_qss(states[state])
            if body:
                blocks.append(f"#{name}:{pseudo} {{ {body} }}")
        widget.setStyleSheet("\n".join(blocks))

    def _apply_selection_states(
        self, widget: QCheckBox, props: dict[str, Any]
    ) -> None:
        """Paint the resolved M3 accent/ring/box onto a checkbox or switch.

        The engine resolves, per checked state: ``color`` = accent tick,
        ``background`` = accent fill when checked, ``border`` = ring when unchecked,
        ``width``/``height`` = box dimension. The renderer maps these onto the
        ``::indicator`` sub-control (the box) — a checked indicator gets the accent
        ``background-color``, an unchecked one the ring ``border`` — plus
        ``:hover``/``:disabled`` state layers as the M3 state-layer halo. The
        **≥48dp touch target stays on the row** (the widget's ``min-height`` from
        the baked style), never the box; only the indicator carries the box dim.

        A selection carrying no resolvable variant props keeps the baked base only.

        Args:
            widget: The Qt checkbox standing in for the checkbox/switch.
            props: The node's current props (carry ``size``/``color_scheme``/
                ``checked``).
        """
        name = widget.objectName() or f"tw_{id(widget):x}"
        widget.setObjectName(name)
        base = widget.styleSheet()
        variant_props = self._variant_props(props)
        if variant_props is None:
            return
        size, color_scheme = variant_props
        theme, platform_dark = self._theme_and_dark()
        checked = bool(props.get("checked", False))
        # The baked selection style's ``width``/``height`` is the *box* dimension
        # (~20dp), which ``_apply_sizing`` would otherwise pin onto the whole row —
        # collapsing the touch target. Undo that here: the row flexes with a >=48dp
        # minimum height (the M3 touch target stays on the row), while the box
        # dimension lands only on the ``::indicator`` sub-control below.
        widget.setMinimumWidth(0)
        widget.setMaximumWidth(_QT_SIZE_MAX)
        widget.setMaximumHeight(_QT_SIZE_MAX)
        widget.setMinimumHeight(_SELECTION_TOUCH_TARGET)
        widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        try:
            states = resolve_selection_variant_states(
                size=size,
                color_scheme=color_scheme,
                theme=theme,
                checked=checked,
                platform_dark_mode=platform_dark,
            )
        except ValueError:
            return
        default = states[ComponentState.DEFAULT]
        box = self._selection_indicator_qss(default, checked)
        # Pin the >=48dp M3 touch target on the *row* block (the box dimension goes
        # only on the indicator below). Mirror the imperative ``setMinimumHeight``
        # in QSS so the resting body declares it.
        row_qss = f"min-height: {float(_SELECTION_TOUCH_TARGET)}px"
        base_body = base.split("{", 1)[1].rsplit("}", 1)[0].strip() if base else ""
        merged = f"{base_body}; {row_qss}".strip("; ") if base_body else row_qss
        blocks: list[str] = [f"#{name} {{ {merged} }}"]
        if box:
            blocks.append(f"#{name}::indicator {{ {box} }}")
        for state, pseudo in (
            (ComponentState.HOVER, "hover"),
            (ComponentState.DISABLED, "disabled"),
        ):
            box = self._selection_indicator_qss(states[state], checked)
            if box:
                blocks.append(f"#{name}::indicator:{pseudo} {{ {box} }}")
        widget.setStyleSheet("\n".join(blocks))

    @staticmethod
    def _selection_indicator_qss(style: Style, checked: bool) -> str:
        """Render a selection box (``::indicator``) QSS body from a per-state style.

        Maps the resolved accent/ring/box-dim onto the indicator: the accent
        ``background`` fills a checked box, the ``border`` rings an unchecked one,
        and ``width``/``height`` pin the box dimension (not the row). The accent
        tick ``color`` is the indicator's foreground.

        Args:
            style: The per-state selection style from the engine.
            checked: Whether the control is checked (drives fill vs ring).

        Returns:
            A ``"; "``-joined QSS declaration body for the indicator sub-control.
        """
        rules: list[str] = []
        if style.width is not None:
            rules.append(f"width: {style.width}px")
        if style.height is not None:
            rules.append(f"height: {style.height}px")
        if checked and style.background is not None:
            rules.append(f"background-color: {qss_background(style.background)}")
        if style.border is not None and isinstance(style.border, Border):
            color = (
                style.border.color.to_rgba_string()
                if style.border.color is not None
                else "black"
            )
            rules.append(f"border: {style.border.width}px solid {color}")
        if style.color is not None:
            rules.append(f"color: {style.color.to_rgba_string()}")
        return "; ".join(rules)

    def _apply_slider_track(self, widget: QWidget, props: dict[str, Any]) -> None:
        """Paint the resolved active/inactive track + thumb onto a slider.

        The engine resolves ``color`` = active track + thumb, ``background`` =
        inactive track, ``height`` = track thickness. The renderer maps these onto
        the ``::sub-page`` (filled/active) + handle (active color) and
        ``::add-page`` (inactive) sub-controls, plus a ``:disabled`` faded state.
        Applied to both the single :class:`QSlider` and each handle of a
        :class:`_RangeSliderWidget`.

        Args:
            widget: The slider widget (a ``QSlider`` or ``_RangeSliderWidget``).
            props: The node's current props (carry ``size``/``color_scheme``).
        """
        variant_props = self._variant_props(props)
        if variant_props is None:
            return
        size, color_scheme = variant_props
        theme, platform_dark = self._theme_and_dark()
        try:
            states = resolve_slider_variant_states(
                size=size,
                color_scheme=color_scheme,
                theme=theme,
                platform_dark_mode=platform_dark,
            )
        except ValueError:
            return
        if isinstance(widget, _RangeSliderWidget):
            for slider in widget.sliders():
                self._paint_slider_track(slider, states)
        else:
            self._paint_slider_track(cast("QSlider", widget), states)

    @staticmethod
    def _paint_slider_track(
        slider: QSlider, states: dict[ComponentState, Style]
    ) -> None:
        """Set a single ``QSlider``'s groove/sub-page/handle QSS from the states.

        Args:
            slider: The Qt slider to style.
            states: The per-state slider styles resolved by the engine.
        """
        default = states[ComponentState.DEFAULT]
        disabled = states[ComponentState.DISABLED]
        active = default.color.to_rgba_string() if default.color is not None else None
        inactive = (
            qss_background(default.background)
            if default.background is not None
            else None
        )
        thickness = int(default.height) if default.height is not None else 4
        name = slider.objectName() or f"tw_{id(slider):x}"
        slider.setObjectName(name)
        blocks: list[str] = []
        if inactive is not None:
            blocks.append(
                f"#{name}::groove:horizontal {{ height: {thickness}px;"
                f" background: {inactive}; border-radius: {thickness // 2}px }}"
            )
            blocks.append(f"#{name}::add-page:horizontal {{ background: {inactive} }}")
        if active is not None:
            blocks.append(f"#{name}::sub-page:horizontal {{ background: {active} }}")
            handle = max(thickness * 3, 16)
            blocks.append(
                f"#{name}::handle:horizontal {{ background: {active};"
                f" width: {handle}px; height: {handle}px;"
                f" margin: -{handle // 2}px 0; border-radius: {handle // 2}px }}"
            )
        if disabled.color is not None:
            faded = disabled.color.to_rgba_string()
            blocks.append(
                f"#{name}::sub-page:horizontal:disabled {{ background: {faded} }}"
            )
            blocks.append(
                f"#{name}::handle:horizontal:disabled {{ background: {faded} }}"
            )
        slider.setStyleSheet("\n".join(blocks))

    def _apply_icon_button(self, widget: QPushButton, props: dict[str, Any]) -> None:
        """Apply props to an icon-only button (square, circular, glyph-only).

        Renders the resolved curated glyph (``icon`` name → :func:`_icon_pixmap`,
        engine alias-resolved) as the button's icon at the baked square size, in
        the foreground ``color`` of the baked style, with no text. The ``label``
        prop is the accessible name (a11y) — set so the icon-only control is still
        announced. The M3 state-layer pass (``Variant``-based, shared with
        ``Button``) runs from :meth:`_apply_visual` after sizing/radius clamp.

        Args:
            widget: The Qt button backing the icon button.
            props: The node's current props (carry ``icon``/``label``/``variant``/
                ``size``/``color_scheme``).
        """
        widget.setText("")
        name = cast("str", props.get("icon", ""))
        style = cast("Style | None", props.get("style"))
        glyph_size = (
            int(style.font_size) if style is not None and style.font_size is not None
            else 20
        )
        color = (
            _qcolor(style.color)
            if style is not None and style.color is not None
            else widget.palette().color(QPalette.ColorRole.ButtonText)
        )
        pixmap = _icon_pixmap(name, glyph_size, color) if name else None
        if pixmap is not None:
            widget.setIcon(QIcon(pixmap))
            widget.setIconSize(pixmap.size())
        else:
            # Unknown glyph / no QtSvg: honest text fallback so the control is not
            # invisible (mirrors ``_apply_icon``).
            widget.setIcon(QIcon())
            widget.setText(name)
        label = cast("str", props.get("label", ""))
        if label:
            widget.setAccessibleName(label)
            widget.setToolTip(label)
        self._bind_click(widget, props.get("on_click"))

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
        self._apply_input_icons(widget, props)
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
        color = widget.palette().color(QPalette.ColorRole.Text)
        toggle = QAction(
            _eye_icon(revealed=False, color=color), "Reveal password", widget
        )
        toggle.setCheckable(True)

        def _reveal(checked: bool) -> None:
            widget.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            toggle.setIcon(_eye_icon(revealed=checked, color=color))

        toggle.toggled.connect(_reveal)
        widget.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)
        self._eye_actions[id(widget)] = toggle

    def _apply_input_icons(self, widget: QLineEdit, props: dict[str, Any]) -> None:
        """Place/refresh the in-field leading and trailing vector-icon slots.

        ``leading_icon`` is shown on the start edge and ``trailing_icon`` on the
        end edge (start/end follow the renderer's RTL flag — Qt mirrors the
        leading/trailing action positions automatically with the layout
        direction). Each edge tracks its current ``(name, QAction)`` per
        line-edit id so an unchanged name is a no-op, a changed name replaces the
        action (never stacks), and ``None`` removes any existing slot.

        Args:
            widget: The Qt line edit.
            props: The node's current props (carry ``leading_icon`` /
                ``trailing_icon`` as curated icon names or ``None``).
        """
        color = widget.palette().color(QPalette.ColorRole.Text)
        self._apply_input_icon_edge(
            widget,
            cast("str | None", props.get("leading_icon")),
            QLineEdit.ActionPosition.LeadingPosition,
            self._leading_icons,
            color,
        )
        self._apply_input_icon_edge(
            widget,
            cast("str | None", props.get("trailing_icon")),
            QLineEdit.ActionPosition.TrailingPosition,
            self._trailing_icons,
            color,
        )

    @staticmethod
    def _apply_input_icon_edge(
        widget: QLineEdit,
        name: str | None,
        position: QLineEdit.ActionPosition,
        slots: dict[int, tuple[str, QAction]],
        color: QColor,
    ) -> None:
        """Reconcile a single leading/trailing icon slot on a line edit.

        Args:
            widget: The Qt line edit.
            name: The desired curated icon name, or ``None`` to clear the slot.
            position: The Qt action position (leading/trailing edge).
            slots: The per-edge tracking dict (``id -> (name, action)``).
            color: The stroke color for the rendered glyph.
        """
        wid = id(widget)
        existing = slots.get(wid)
        if name is None:
            if existing is not None:
                widget.removeAction(existing[1])
                slots.pop(wid, None)
            return
        if existing is not None:
            if existing[0] == name:
                return  # unchanged — keep the live action
            widget.removeAction(existing[1])
            slots.pop(wid, None)
        icon = _icon_qicon(name, 16, color)
        if icon is None:
            return  # unknown name / no QtSvg → no slot, no crash
        action = QAction(icon, name, widget)
        action.setEnabled(False)  # decorative slot, not clickable
        widget.addAction(action, position)
        slots[wid] = (name, action)

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
    def _apply_shimmer(node: _Rendered) -> None:
        """Configure a ``Shimmer``/``Skeleton`` node's gradient loop.

        Reads the node's ``base_color``/``highlight_color``/``duration_ms`` props
        (and ``radius`` for a skeleton) and pushes them into the backing
        shimmer widget so its repaint loop sweeps the right colors at the right
        cadence. Idempotent.

        Args:
            node: The rendered ``Shimmer``/``Skeleton`` node.
        """
        widget = cast("_ShimmerMixin", node.widget)
        props = node.props
        base = props.get("base_color")
        highlight = props.get("highlight_color")
        base_q = _qcolor(base) if base is not None else QColor(224, 224, 224)
        highlight_q = (
            _qcolor(highlight) if highlight is not None else QColor(245, 245, 245)
        )
        duration = int(cast("int", props.get("duration_ms", _SHIMMER_DEFAULT_MS)))
        widget.configure_shimmer(base_q, highlight_q, duration)
        if node.type == "Skeleton":
            cast("_SkeletonWidget", widget).set_radius(
                float(cast("float", props.get("radius", 4.0)))
            )

    @staticmethod
    def _apply_skeleton_size(widget: _SkeletonWidget, props: dict[str, Any]) -> None:
        """Pin a ``Skeleton``'s own ``width``/``height`` props (not via ``Style``).

        Idempotent: an unset dimension is restored to Qt's flexible range so a
        later update that drops it lets the skeleton flex again.

        Args:
            widget: The skeleton widget.
            props: The node's current props (``width``/``height``).
        """
        width = props.get("width")
        height = props.get("height")
        if width is not None:
            widget.setFixedWidth(int(cast("float", width)))
        else:
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(_QT_SIZE_MAX)
        if height is not None:
            widget.setFixedHeight(int(cast("float", height)))
        else:
            widget.setMinimumHeight(0)
            widget.setMaximumHeight(_QT_SIZE_MAX)

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

    def _apply_canvas(self, widget: _CanvasWidget, props: dict[str, Any]) -> None:
        """Push the Canvas draw commands (and optional fixed size) to the widget.

        The IR carries ``commands`` as a list of frozen ``DrawCommand`` Pydantic
        models; they are lowered to plain JSON-able dicts here so the
        ``_CanvasWidget`` paint loop never depends on the IR types (the same
        dict shape the device renderer replays).

        Args:
            widget: The backing canvas widget.
            props: The node's current props.
        """
        raw = cast("list[Any]", props.get("commands", []))
        commands: list[dict[str, Any]] = []
        for cmd in raw:
            if isinstance(cmd, dict):
                commands.append(cast("dict[str, Any]", cmd))
            else:
                # Frozen ``DrawCommand`` Pydantic model → JSON-able dict.
                commands.append(cast("dict[str, Any]", cmd.model_dump()))
        widget.set_commands(commands)
        width = props.get("width")
        height = props.get("height")
        if width is not None:
            widget.setFixedWidth(int(cast("float", width)))
        if height is not None:
            widget.setFixedHeight(int(cast("float", height)))

    @staticmethod
    def _apply_video_player(widget: QWidget, props: dict[str, Any]) -> None:
        """Configure a ``VideoPlayer``'s source and playback flags.

        No-op when the widget is the placeholder ``QLabel`` (multimedia stack
        unavailable). Loading a real stream in headless CI may emit a backend
        warning but never raises; the test only asserts the widget mounts.

        Args:
            widget: The backing video widget (or placeholder label).
            props: The node's current props.
        """
        player = getattr(widget, "_player", None)
        audio = getattr(widget, "_audio", None)
        if player is None:
            return
        src = cast("str", props.get("src", ""))
        if src:
            player.setSource(QUrl(src))
        if audio is not None:
            audio.setMuted(bool(props.get("muted", False)))
        loops = -1 if bool(props.get("loop", False)) else 1
        player.setLoops(loops)
        if bool(props.get("autoplay", False)):
            player.play()

    @staticmethod
    def _apply_web_view(widget: QWidget, props: dict[str, Any]) -> None:
        """Load a ``WebView``'s URL (and toggle JavaScript when supported).

        No-op when the widget is the placeholder ``QLabel`` (WebEngine absent).

        Args:
            widget: The backing web view (or placeholder label).
            props: The node's current props.
        """
        if not hasattr(widget, "load"):
            return
        view = cast("Any", widget)
        if hasattr(widget, "settings"):
            try:
                from PySide6.QtWebEngineCore import QWebEngineSettings

                view.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.JavascriptEnabled,
                    bool(props.get("javascript_enabled", True)),
                )
            except ImportError:
                pass
        url = cast("str", props.get("url", ""))
        if url:
            view.load(QUrl(url))

    @staticmethod
    def _apply_svg(widget: QLabel, props: dict[str, Any]) -> None:
        """Render a local SVG source into the label's pixmap.

        Uses ``QSvgRenderer`` to rasterize the SVG onto a transparent pixmap.
        Remote (``http(s)``) sources and missing/invalid files fall back to the
        source string as text — the device renderer fetches remote SVGs. No-op
        crash path: a null renderer just shows the source text.

        Args:
            widget: The label backing the SVG.
            props: The node's current props.
        """
        src = cast("str", props.get("src", ""))
        renderer_cls = _load_svg_renderer()
        is_local = bool(src) and not src.startswith(("http://", "https://"))
        if renderer_cls is None or not is_local:
            widget.setText(src)
            return
        svg = renderer_cls(src)
        if not svg.isValid():
            widget.setText(src)
            return
        size = svg.defaultSize()
        if size.width() <= 0 or size.height() <= 0:
            size = QSize(64, 64)
        pixmap = QPixmap(size)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        svg.render(painter)
        painter.end()
        widget.setText("")
        widget.setPixmap(pixmap)
        widget.setScaledContents(cast("str", props.get("fit", "contain")) == "fill")

    def _apply_blur(self, widget: QWidget, props: dict[str, Any]) -> None:
        """Apply a Gaussian blur effect to a ``Blur``/``BackdropFilter`` wrapper.

        Qt cannot blur the layers *behind* a widget, so ``BackdropFilter`` is
        approximated identically to ``Blur`` (blurring the wrapper's own child)
        — a documented Qt-vs-Compose divergence.

        Args:
            widget: The wrapper widget.
            props: The node's current props (carries ``radius``).
        """
        radius = float(cast("float", props.get("radius", 8.0)))
        effect = QGraphicsBlurEffect(widget)
        effect.setBlurRadius(radius)
        widget.setGraphicsEffect(effect)

    @staticmethod
    def _apply_clip_path(widget: _ClipWidget, props: dict[str, Any]) -> None:
        """Configure a ``ClipPath`` wrapper's mask shape and radius.

        Args:
            widget: The clip wrapper widget.
            props: The node's current props (``shape`` + ``radius``).
        """
        shape = props.get("shape", "rounded_rect")
        shape_value = getattr(shape, "value", shape)
        radius = float(cast("float", props.get("radius", 8.0)))
        widget.configure_clip(str(shape_value), radius)

    @staticmethod
    def _apply_icon(widget: QLabel, props: dict[str, Any]) -> None:
        """Apply props to an icon label.

        When the ``name`` resolves to a curated vector glyph (:func:`icon_path`),
        the stroked line icon is rendered into the label's pixmap at ``size``
        (default 20px), colored from the label's palette text color. An unknown
        name falls back to showing the name as text (no exception).

        Args:
            widget: The Qt label backing the icon.
            props: The node's current props.
        """
        name = cast("str", props.get("name", ""))
        size_prop = props.get("size")
        size = int(cast("float", size_prop)) if size_prop is not None else 20
        color = widget.palette().color(QPalette.ColorRole.Text)
        pixmap = _icon_pixmap(name, size, color) if name else None
        if pixmap is not None:
            widget.setText("")
            widget.setPixmap(pixmap)
            return
        # Unknown name (or no QtSvg): keep the legacy text fallback.
        widget.setPixmap(QPixmap())
        widget.setText(name)
        if size_prop is not None:
            font = widget.font()
            font.setPixelSize(size)
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

    # --- selection / form controls -----------------------------------------

    def _apply_dropdown(self, widget: QComboBox, props: dict[str, Any]) -> None:
        """Apply props to a dropdown and wire its selection handler.

        Re-populates the option list only when it changed, then sets the current
        index to match ``value`` without re-emitting. The selection handler
        receives a :class:`SelectEvent` carrying the chosen option and its index.

        Args:
            widget: The Qt combo box.
            props: The node's current props.
        """
        options = [str(opt) for opt in cast("list[Any]", props.get("options", []))]
        current = [widget.itemText(i) for i in range(widget.count())]
        if current != options:
            widget.blockSignals(True)
            widget.clear()
            widget.addItems(options)
            widget.blockSignals(False)
        value = props.get("value")
        desired = options.index(str(value)) if value in options else -1
        if widget.currentIndex() != desired:
            widget.blockSignals(True)
            widget.setCurrentIndex(desired)
            widget.blockSignals(False)
        self._bind_value(
            widget,
            widget.currentIndexChanged,
            props.get("on_select"),
            lambda index: SelectEvent(
                value=widget.itemText(cast("int", index)),
                index=int(cast("int", index)),
            ),
        )

    def _apply_timepicker(self, widget: QTimeEdit, props: dict[str, Any]) -> None:
        """Apply props to a time picker and wire its change handler.

        Args:
            widget: The Qt time edit.
            props: The node's current props.
        """
        value = cast("str", props.get("value", ""))
        parsed = QTime.fromString(value, _TIME_FORMAT) if value else QTime()
        if parsed.isValid() and widget.time() != parsed:
            widget.blockSignals(True)
            widget.setTime(parsed)
            widget.blockSignals(False)
        self._bind_value(
            widget,
            widget.timeChanged,
            props.get("on_change"),
            lambda qtime: TimeChangeEvent(
                value=cast("QTime", qtime).toString(_TIME_FORMAT)
            ),
        )

    def _apply_range_slider(
        self, widget: _RangeSliderWidget, props: dict[str, Any]
    ) -> None:
        """Apply props to a dual-handle range slider and wire its change handler.

        The simulator's sliders are integer-based, so fractional bounds/values are
        rounded here (the device keeps full float precision); both bounds are kept
        ordered (``low <= high``). Emits a :class:`RangeChangeEvent` with both
        bounds as floats whenever either handle moves.

        Args:
            widget: The custom range-slider widget.
            props: The node's current props.
        """
        widget.configure_range(
            int(cast("float", props.get("min_value", 0.0))),
            int(cast("float", props.get("max_value", 100.0))),
            int(cast("float", props.get("step", 1.0))),
        )
        widget.set_values(
            int(cast("float", props.get("low", 0.0))),
            int(cast("float", props.get("high", 100.0))),
        )
        handler = props.get("on_change")
        if handler is None:
            widget.set_on_change(None)
            return
        callback = cast("Callable[..., Any]", handler)
        widget.set_on_change(
            lambda low, high: self._invoke(
                callback, RangeChangeEvent(low=float(low), high=float(high))
            )
        )

    def _apply_autocomplete(self, widget: QLineEdit, props: dict[str, Any]) -> None:
        """Apply props to an autocomplete field and wire both its handlers.

        Sets the text without re-emitting, (re)builds the :class:`QCompleter` from
        ``options`` only when they changed, and wires two distinct signals: the
        line edit's ``textChanged`` → :class:`TextChangeEvent` (``on_change``) and
        the completer's ``activated`` → :class:`SelectEvent` (``on_select``).

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
        options = [str(opt) for opt in cast("list[Any]", props.get("options", []))]
        if self._completer_options.get(id(widget)) != options:
            completer = QCompleter(options)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            widget.setCompleter(completer)
            self._completer_options[id(widget)] = options
            previous_select = self._select_conns.pop(id(widget), None)
            if previous_select is not None:
                previous_select[0].disconnect(previous_select[1])
            on_select = props.get("on_select")
            if on_select is not None:
                select_cb = cast("Callable[..., Any]", on_select)

                def _on_activated(text: object = "") -> None:
                    chosen = text if isinstance(text, str) else str(text)
                    index = options.index(chosen) if chosen in options else -1
                    self._invoke(select_cb, SelectEvent(value=chosen, index=index))

                # ``QCompleter.activated`` is overloaded (QModelIndex | str); pick
                # the str overload at runtime by indexing the signal (the PySide6
                # stub types it as a plain ``SignalInstance`` with no ``__getitem__``).
                str_signal = cast(
                    "SignalInstance", cast("Any", completer.activated)[str]
                )
                conn = str_signal.connect(_on_activated)
                self._select_conns[id(widget)] = (str_signal, conn)
        self._apply_input_icons(widget, props)
        self._bind_value(
            widget,
            widget.textChanged,
            props.get("on_change"),
            lambda value: TextChangeEvent(value=cast("str", value)),
        )

    def _apply_pin_input(self, widget: _PinInputWidget, props: dict[str, Any]) -> None:
        """Apply props to a PIN/OTP entry and wire its change/complete handlers.

        Args:
            widget: The custom PIN widget.
            props: The node's current props.
        """
        widget.configure(
            int(cast("int", props.get("length", 6))),
            bool(props.get("secure", False)),
        )
        widget.set_value(cast("str", props.get("value", "")))
        on_change = props.get("on_change")
        on_complete = props.get("on_complete")
        change_cb = cast("Callable[..., Any] | None", on_change)
        complete_cb = cast("Callable[..., Any] | None", on_complete)
        widget.set_callbacks(
            (lambda value: self._invoke(change_cb, TextChangeEvent(value=value)))
            if change_cb is not None
            else None,
            (lambda value: self._invoke(complete_cb, SubmitEvent(values={})))
            if complete_cb is not None
            else None,
        )

    def _apply_masked_input(self, widget: QLineEdit, props: dict[str, Any]) -> None:
        """Apply props to a masked input and wire its change handler.

        Translates the framework mask (``9`` digit, ``A`` letter, else literal) to
        Qt's input-mask notation and installs it, then wires ``textChanged`` to a
        :class:`TextChangeEvent`.

        Args:
            widget: The Qt line edit.
            props: The node's current props.
        """
        widget.setPlaceholderText(cast("str", props.get("placeholder", "")))
        mask = cast("str", props.get("mask", ""))
        qt_mask = _to_qt_input_mask(mask)
        if widget.inputMask() != qt_mask:
            widget.setInputMask(qt_mask)
        widget.setInputMethodHints(
            _KEYBOARD_HINTS.get(
                cast("str", props.get("keyboard", "text")),
                Qt.InputMethodHint.ImhNone,
            )
        )
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

    @staticmethod
    def _apply_form_field(widget: _FormFieldWidget, props: dict[str, Any]) -> None:
        """Apply props to a form field: its label and (red) error line.

        The wrapped input is mounted as the field's IR child through the generic
        child path; this only sets the label and the inline error message (the
        error line is hidden while the field is valid).

        Args:
            widget: The custom form-field widget.
            props: The node's current props.
        """
        widget.set_label(cast("str", props.get("label", "")))
        widget.set_error(cast("str", props.get("error", "")))

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
        flag = self_alignment(is_row=parent.type == "Row", align_self=style.align_self)
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
        self._leading_icons.pop(widget_id, None)
        self._trailing_icons.pop(widget_id, None)
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
