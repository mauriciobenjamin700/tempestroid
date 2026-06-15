package org.tempestroid.host

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.ExperimentalSharedTransitionApi
import androidx.compose.animation.SharedTransitionLayout
import androidx.compose.animation.SharedTransitionScope
import androidx.compose.animation.core.InfiniteRepeatableSpec
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowColumn
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.util.VelocityTracker
import kotlin.math.abs
import kotlin.math.roundToInt
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.RangeSlider
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.material3.TooltipBox
import androidx.compose.material3.PlainTooltip
import androidx.compose.material3.TooltipDefaults
import androidx.compose.material3.rememberTooltipState
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberDrawerState
import androidx.compose.animation.AnimatedVisibilityScope
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.viewinterop.AndroidView
import android.graphics.Paint as NativePaint
import android.graphics.Path as NativePath
import android.graphics.RectF
import android.webkit.WebView as AndroidWebView
import androidx.compose.foundation.focusable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.foundation.clickable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.itemsIndexed as gridItemsIndexed
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.snapshotFlow
import kotlinx.coroutines.flow.collectLatest
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Done
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Warning
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalContentColor
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import coil.compose.AsyncImage
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import androidx.compose.ui.unit.IntOffset
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneOffset
import org.json.JSONObject

/**
 * Renders a serialized tempestroid [TempestNode] tree with Jetpack Compose, and
 * routes widget callbacks back to Python via [onEvent].
 *
 * This is the Kotlin counterpart of the `Style → Compose` translator: it turns
 * the JSON-able style spec (`arrangement` / `alignment` / `padding` / `background`
 * / font hints …) into `Arrangement` / `Alignment` / `Modifier` at runtime.
 *
 * @param node the node to render.
 * @param onEvent invoked as `(token, payloadJson)` when a widget fires (the token
 *   comes straight from the serialized handler ref `{"$handler": token}`).
 */
@Composable
fun RenderNode(node: TempestNode, onEvent: (String, String) -> Unit) {
    // E9 RTL: a node may carry a `locale_rtl` flag (the root does, when the Python
    // serializer emits it). When present, flip LocalLayoutDirection for this subtree
    // so Compose orders children and resolves start/end-aware modifiers right-to-left
    // — complementing the box-model values Python already mirrors in to_compose(rtl).
    // Absent (the common case) → render with the inherited direction, no extra wrap.
    val rtl = node.props["locale_rtl"] as? Boolean
    // Contrast tracking: when this node paints its own `background`, publish the
    // color that reads legibly against it (white on a dark fill, black on a light
    // one) so descendant Text/labels that declare no explicit color stay visible —
    // independent of the OS-driven Material theme (which may be light while the app
    // paints a dark surface, the case where unstyled text would otherwise vanish).
    val bg = colorOf(styleOf(node), "background")
    val body: @Composable () -> Unit = { RenderAccessible(node, onEvent) }
    val direction = rtl?.let { if (it) LayoutDirection.Rtl else LayoutDirection.Ltr }
    when {
        direction != null && bg != null -> CompositionLocalProvider(
            LocalLayoutDirection provides direction,
            LocalContrastColor provides contrastColorFor(bg),
        ) { body() }
        direction != null -> CompositionLocalProvider(
            LocalLayoutDirection provides direction,
        ) { body() }
        bg != null -> CompositionLocalProvider(
            LocalContrastColor provides contrastColorFor(bg),
        ) { body() }
        else -> body()
    }
}

/**
 * The color that reads legibly against the nearest ancestor's painted background
 * (E9-style contrast tracking). Seeded at the root from the Material on-surface
 * color and overridden by any node that declares a `Style.background`, so an
 * unstyled [Text]/label always contrasts with the surface it actually sits on —
 * even when the OS Material theme (light/dark) disagrees with the app's palette.
 */
private val LocalContrastColor = compositionLocalOf<Color?> { null }

/**
 * Pick a high-contrast foreground color for a background [bg]: white on a dark
 * fill, near-black on a light fill, by perceptual luminance (Rec. 601 weights).
 */
private fun contrastColorFor(bg: Color): Color {
    val luminance = 0.299f * bg.red + 0.587f * bg.green + 0.114f * bg.blue
    return if (luminance < 0.5f) Color.White else Color(0xFF1A1A1A)
}

/**
 * The default foreground color for text/labels that declare no explicit color:
 * the tracked [LocalContrastColor] (the nearest painted background's contrast),
 * or the Material on-surface color when no background has been tracked.
 */
@Composable
private fun defaultTextColor(): Color =
    LocalContrastColor.current ?: MaterialTheme.colorScheme.onSurface

/**
 * E9 accessibility wrapper: if the node declares `semantics` / `focusable` /
 * `focus_order`, wrap its rendered body in a [Box] carrying the corresponding
 * [Modifier.semantics] (contentDescription + role) and [Modifier.focusable]. The
 * wrapper is added only when at least one of the three is present, so the common
 * (untagged) node renders with zero extra layout. This is the Compose counterpart
 * of the Qt `QAccessible.setAccessibleName` / `setFocusPolicy` path.
 *
 * `semantics` arrives as the serialized `{label, role, hint}` map (when the Python
 * serializer lowers the `Semantics` model — see gaps if it currently drops it).
 * `focus_order` is honoured insofar as a focusable node participates in the
 * traversal; explicit next/previous wiring via FocusRequester is left to the
 * (rare) ordered-focus case and documented as a divergence.
 */
@Composable
private fun RenderAccessible(node: TempestNode, onEvent: (String, String) -> Unit) {
    @Suppress("UNCHECKED_CAST")
    val semantics = node.props["semantics"] as? Map<String, Any?>
    val focusable = node.props["focusable"] as? Boolean
    if (semantics == null && focusable == null) {
        RenderNodeBody(node, onEvent)
        return
    }
    val label = semantics?.get("label") as? String
    val role = roleFor(semantics?.get("role") as? String)
    val isHeading = (semantics?.get("role") as? String) == "heading"
    var m: Modifier = Modifier
    if (semantics != null) {
        m = m.semantics {
            if (label != null) contentDescription = label
            if (role != null) this.role = role
            if (isHeading) heading()
        }
    }
    if (focusable == true) {
        m = m.focusable(true)
    } else if (focusable == false) {
        m = m.focusable(false)
    }
    Box(modifier = m) { RenderNodeBody(node, onEvent) }
}

/** Map a serialized semantics `role` string to a Compose [Role], or `null` when
 *  the role has no direct Compose equivalent (e.g. "heading" → handled separately). */
internal fun roleFor(role: String?): Role? = when (role) {
    "button" -> Role.Button
    "checkbox" -> Role.Checkbox
    "switch" -> Role.Switch
    "radio" -> Role.RadioButton
    "tab" -> Role.Tab
    "image" -> Role.Image
    "dropdown" -> Role.DropdownList
    else -> null
}

/** The body of [RenderNode]: dispatches by node type. Split out so [RenderNode]
 *  can wrap it in an RTL [CompositionLocalProvider] without duplicating the when. */
@Composable
private fun RenderNodeBody(node: TempestNode, onEvent: (String, String) -> Unit) {
    val style = styleOf(node)
    when (node.type) {
        "Text" -> Text(
            text = node.props["content"] as? String ?: "",
            // When the Style declares no explicit color, fall back to a CONTRASTING
            // default (NOT Color.Unspecified, which inherits LocalContentColor and
            // reads near-black on a dark app surface, so unstyled text vanishes).
            // LocalContrastColor tracks the nearest painted background's contrast
            // (white on dark, black on light); absent any tracked background it
            // falls back to the Material on-surface color.
            color = colorOf(style, "color") ?: defaultTextColor(),
            // E9 text scale: Style.text_scale (serialized "textScale") multiplies the
            // declared font size, mirroring the Qt translator (which folds it into
            // font-size). Compose's own LocalDensity.fontScale (the OS accessibility
            // setting) still applies on top of this, since the result is an `sp`.
            fontSize = scaledFontSize(style),
            fontWeight = (style["fontWeight"] as? Number)?.let { FontWeight(it.toInt()) },
            // E9 custom font: Style.font_asset (serialized "fontAsset") loads a bundled
            // typeface from the app assets; null falls back to the platform default.
            fontFamily = fontFamilyOf(style),
            textAlign = textAlignOf(style),
            modifier = baseModifier(style),
        )

        "Button" -> {
            // Map Style → Material button: background/color become the button's
            // own container/content colors (NOT a Modifier.background box behind
            // it, which would let the Material default paint over the declared
            // background), radius → shape, padding → contentPadding.
            val container = colorOf(style, "background")
            val content = colorOf(style, "color")
            val radius = (style["radius"] as? Number)?.toFloat() ?: 0f
            val colors = if (container != null) {
                ButtonDefaults.buttonColors(
                    containerColor = container,
                    contentColor = content ?: Color.White,
                )
            } else {
                ButtonDefaults.buttonColors()
            }
            Button(
                onClick = { handlerToken(node, "on_click")?.let { onEvent(it, "{}") } },
                modifier = sizeModifier(style),
                shape = RoundedCornerShape(radius.dp),
                colors = colors,
                contentPadding = edgeOf(style, "padding") ?: ButtonDefaults.ContentPadding,
            ) {
                Text(
                    text = node.props["label"] as? String ?: "",
                    fontSize = scaledFontSize(style),
                    fontWeight = (style["fontWeight"] as? Number)?.let { FontWeight(it.toInt()) },
                    fontFamily = fontFamilyOf(style),
                )
            }
        }

        "Column" -> Column(
            modifier = baseModifier(style),
            verticalArrangement = verticalArrangement(style),
            horizontalAlignment = horizontalAlignment(style),
        ) {
            node.children.forEach { RenderNode(it, onEvent) }
        }

        "Row" -> Row(
            modifier = baseModifier(style),
            horizontalArrangement = horizontalArrangement(style),
            verticalAlignment = verticalAlignment(style),
        ) {
            node.children.forEach { RenderNode(it, onEvent) }
        }

        "SafeArea" -> {
            // Inset the child away from the real system intrusions (status bar,
            // navigation bar, display cutout/notch). The `edges` prop selects
            // which sides are protected; absent → all four. Requires the host to
            // draw edge-to-edge (see MainActivity.enableEdgeToEdge), otherwise
            // the system already consumes these insets and safeDrawing is empty.
            @Suppress("UNCHECKED_CAST")
            val selected = (node.props["edges"] as? List<*>)
                ?.mapNotNull { it as? String }?.toSet()
                ?: setOf("top", "right", "bottom", "left")
            var sides: WindowInsetsSides? = null
            fun add(s: WindowInsetsSides) { sides = sides?.plus(s) ?: s }
            if ("top" in selected) add(WindowInsetsSides.Top)
            if ("bottom" in selected) add(WindowInsetsSides.Bottom)
            if ("left" in selected) add(WindowInsetsSides.Left)
            if ("right" in selected) add(WindowInsetsSides.Right)
            val insets = sides?.let { WindowInsets.safeDrawing.only(it) }
                ?: WindowInsets(0, 0, 0, 0)
            Box(modifier = baseModifier(style).windowInsetsPadding(insets)) {
                node.children.forEach { RenderNode(it, onEvent) }
            }
        }

        "Stack" -> Box(
            modifier = baseModifier(style),
            contentAlignment = stackAlignmentOf(style),
        ) {
            // Children overlap in declaration order (first = bottom layer). A child
            // with position=absolute fills the box inset by its edges; the rest are
            // aligned by the stack's contentAlignment.
            node.children.forEach { child ->
                val childStyle = styleOf(child)
                if (childStyle["position"] == "absolute") {
                    Box(modifier = absoluteModifier(childStyle)) { RenderNode(child, onEvent) }
                } else {
                    RenderNode(child, onEvent)
                }
            }
        }

        "GestureDetector" -> RenderGestureDetector(node, style, onEvent)

        "PanHandler" -> RenderPanHandler(node, style, onEvent)

        "ScaleHandler" -> RenderScaleHandler(node, style, onEvent)

        "DoubleTapHandler" -> RenderDoubleTapHandler(node, style, onEvent)

        "Draggable" -> RenderDraggable(node, style, onEvent)

        "DragTarget" -> RenderDragTarget(node, style, onEvent)

        "Dismissible" -> RenderDismissible(node, style, onEvent)

        "ReorderableList" -> RenderReorderableList(node, style, onEvent)

        "InteractiveViewer" -> RenderInteractiveViewer(node, style, onEvent)

        "Input" -> RenderInput(node, style, onEvent)

        "TextArea" -> RenderTextArea(node, style, onEvent)

        "Checkbox" -> RenderCheckbox(node, style, onEvent)

        "Switch" -> RenderSwitch(node, style, onEvent)

        "Slider" -> RenderSlider(node, style, onEvent)

        "ProgressBar" -> RenderProgressBar(node, style)

        "Spinner" -> RenderSpinner(node, style)

        "Image" -> RenderImage(node, style)

        "Icon" -> RenderIcon(node, style)

        "ScrollView" -> RenderScrollView(node, style, onEvent)

        "DatePicker" -> RenderDatePicker(node, style, onEvent)

        "FilePicker" -> RenderFilePicker(node, style, onEvent)

        "Dropdown", "Select" -> RenderDropdown(node, style, onEvent)

        "TimePicker" -> RenderTimePicker(node, style, onEvent)

        "RangeSlider" -> RenderRangeSlider(node, style, onEvent)

        "Autocomplete" -> RenderAutocomplete(node, style, onEvent)

        "PinInput" -> RenderPinInput(node, style, onEvent)

        "MaskedInput" -> RenderMaskedInput(node, style, onEvent)

        "FormField" -> RenderFormField(node, style, onEvent)

        "Form" -> RenderForm(node, style, onEvent)

        "Navigator" -> RenderNavigator(node, style, onEvent)

        "TabView" -> RenderTabView(node, style, onEvent)

        "TabBar" -> RenderTabBar(node, style, onEvent)

        "RouteDrawer" -> RenderRouteDrawer(node, style, onEvent)

        "LazyColumn" -> RenderLazyList(node, style, onEvent, horizontal = false)

        "LazyRow" -> RenderLazyList(node, style, onEvent, horizontal = true)

        "LazyGrid" -> RenderLazyGrid(node, style, onEvent)

        "SectionList" -> RenderSectionList(node, style, onEvent)

        "RefreshControl" -> RenderRefreshControl(node, style, onEvent)

        "Animated" -> RenderAnimated(node, style, onEvent)

        "AnimatedList" -> RenderAnimatedList(node, style, onEvent)

        "Shimmer" -> RenderShimmer(node, style, onEvent)

        "Skeleton" -> RenderSkeleton(node, style)

        "Hero" -> RenderHero(node, onEvent)

        "Wrap" -> RenderWrap(node, style, onEvent)

        "PageView" -> RenderPageView(node, style, onEvent)

        "AspectRatio" -> RenderAspectRatio(node, style, onEvent)

        "Canvas" -> RenderCanvas(node, style)

        "VideoPlayer" -> RenderVideoPlayer(node, style)

        "WebView" -> RenderWebView(node, style)

        "Svg" -> RenderSvg(node, style)

        "CameraPreview" -> RenderCameraPreview(node, style)

        "QrScanner" -> RenderQrScanner(node, style, onEvent)

        "MapView" -> RenderMapView(node, style)

        "KeyboardAvoidingView" -> RenderKeyboardAvoidingView(node, style, onEvent)

        "Blur", "BackdropFilter" -> RenderBlur(node, style, onEvent)

        "ClipPath" -> RenderClipPath(node, style, onEvent)

        else -> Box(modifier = baseModifier(style)) {
            node.children.forEach { RenderNode(it, onEvent) }
        }
    }
}

/**
 * Render one floating overlay node (E2) above the root tree — the Kotlin
 * counterpart of the Qt overlay layer. Dispatches by [TempestNode.type] to the
 * platform-native surface (Material3 `AlertDialog`/`ModalBottomSheet`/
 * `DropdownMenu`, or a `Popup`).
 *
 * Each overlay's [TempestNode.key] is its stable Python overlay id; a host-owned
 * dismiss (barrier/scrim tap, swipe-down, timer expiry, away tap) is reported back
 * to Python as the reserved `__dismiss__:<id>` event via [emitDismiss], which the
 * bridge routes to `App.dismiss`. Material3 `AlertDialog`/`ModalBottomSheet` open
 * their own platform window and manage their own `WindowInsets.safeDrawing`, so
 * they are NOT wrapped in `safeDrawingPadding` (no double inset).
 *
 * @param node the overlay node to render.
 * @param onEvent the event sink back to Python (token, payloadJson).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RenderOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    when (node.type) {
        "Dialog" -> RenderDialogOverlay(node, onEvent)
        "BottomSheet" -> RenderBottomSheetOverlay(node, onEvent)
        "ActionSheet" -> RenderActionSheetOverlay(node, onEvent)
        "Toast" -> RenderToastOverlay(node, onEvent)
        "Menu" -> RenderMenuOverlay(node, onEvent)
        "Popover" -> RenderPopoverOverlay(node, onEvent)
        "Tooltip" -> RenderTooltipOverlay(node, onEvent)
        // Unknown overlay type: render its children inside a centered Popup so a
        // forward-compat overlay still shows something rather than vanishing.
        else -> Popup(alignment = Alignment.Center) {
            Column { node.children.forEach { RenderNode(it, onEvent) } }
        }
    }
}

/**
 * A modal dialog (M3 [AlertDialog]). The barrier/scrim is built into AlertDialog;
 * tapping it (or system back) calls [onDismissRequest], which reports the dismiss
 * to Python. The serialized body widgets render as the dialog text content.
 */
@Composable
private fun RenderDialogOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    val title = node.props["title"] as? String
    AlertDialog(
        onDismissRequest = { emitDismiss(node, onEvent) },
        title = if (title != null) ({ Text(text = title) }) else null,
        text = {
            Column { node.children.forEach { RenderNode(it, onEvent) } }
        },
        // Python owns the dialog lifecycle: there is no implicit confirm button.
        // The dialog body provides its own actionable widgets (Buttons), so the
        // confirm slot just mirrors the dismiss affordance for accessibility.
        confirmButton = {
            TextButton(onClick = { emitDismiss(node, onEvent) }) { Text(text = "Close") }
        },
    )
}

/**
 * A bottom sheet (M3 [ModalBottomSheet]). It slides up from the bottom edge,
 * draws its own scrim, and respects the bottom system inset natively — so it is
 * NOT wrapped in `safeDrawingPadding`. A scrim tap or swipe-down calls
 * [onDismissRequest], reporting the dismiss to Python.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderBottomSheetOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    val sheetState = rememberModalBottomSheetState()
    ModalBottomSheet(
        onDismissRequest = { emitDismiss(node, onEvent) },
        sheetState = sheetState,
    ) {
        Column { node.children.forEach { RenderNode(it, onEvent) } }
    }
}

/**
 * An action sheet (M3 [ModalBottomSheet] holding a list of selectable items). A
 * tap on an item fires `on_select` with a [MenuSelectEvent]-shaped payload; a
 * scrim tap or swipe-down reports a dismiss.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderActionSheetOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    val sheetState = rememberModalBottomSheetState()
    val title = node.props["title"] as? String
    ModalBottomSheet(
        onDismissRequest = { emitDismiss(node, onEvent) },
        sheetState = sheetState,
    ) {
        if (title != null) {
            Text(text = title, modifier = Modifier.padding(16.dp), fontWeight = FontWeight.Bold)
        }
        LazyColumn(modifier = Modifier.fillMaxWidth()) {
            val items = menuItemsOf(node)
            itemsIndexed(items) { _, item ->
                DropdownMenuItem(
                    text = { Text(text = item.label) },
                    onClick = { emitMenuSelect(node, item, onEvent) },
                )
            }
        }
    }
}

/**
 * A transient toast: a [Popup] pinned to the bottom of the screen. A
 * [LaunchedEffect] waits `duration_s` then reports a dismiss to Python — Python's
 * own `loop.call_later` is authoritative, but mirroring the timer here removes
 * the visual snappily. Python confirms by removing the overlay via a patch.
 */
@Composable
private fun RenderToastOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    val durationSeconds = (node.props["duration_s"] as? Number)?.toDouble() ?: 2.5
    Popup(alignment = Alignment.BottomCenter) {
        Box(
            modifier = Modifier
                .padding(bottom = 48.dp)
                .background(Color(0xDD323232), RoundedCornerShape(8.dp))
                .padding(horizontal = 16.dp, vertical = 12.dp),
        ) {
            Text(text = node.props["message"] as? String ?: "", color = Color.White)
        }
    }
    LaunchedEffect(node.key) {
        delay((durationSeconds * 1000).toLong())
        emitDismiss(node, onEvent)
    }
}

/**
 * An anchored menu (M3 [DropdownMenu]). Without a resolved anchor widget position,
 * it opens top-start; tapping an item fires `on_select`. Dismissing (tap away)
 * reports the overlay dismiss to Python.
 */
@Composable
private fun RenderMenuOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    // A DropdownMenu must be anchored inside a parent box; we use a zero-size Box
    // at top-start as the anchor (Python carries the logical `anchor` key, but the
    // device positions menus at the layer origin for v1 — documented divergence).
    Box {
        DropdownMenu(
            expanded = true,
            onDismissRequest = { emitDismiss(node, onEvent) },
        ) {
            menuItemsOf(node).forEach { item ->
                DropdownMenuItem(
                    text = { Text(text = item.label) },
                    onClick = { emitMenuSelect(node, item, onEvent) },
                )
            }
        }
    }
}

/**
 * A popover panel (a [Popup] anchored top-start, dismissible by tapping outside).
 * Its single child renders inside; an outside tap reports the dismiss to Python.
 */
@Composable
private fun RenderPopoverOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    Popup(
        alignment = Alignment.TopStart,
        offset = IntOffset(0, 0),
        onDismissRequest = { emitDismiss(node, onEvent) },
        properties = PopupProperties(focusable = true),
    ) {
        Box(
            modifier = Modifier
                .background(Color.White, RoundedCornerShape(8.dp))
                .padding(8.dp),
        ) {
            Column { node.children.forEach { RenderNode(it, onEvent) } }
        }
    }
}

/**
 * A tooltip (M3 [TooltipBox]) wrapping its single child; the hint shows on
 * long-press of the anchored child. Toolltips have no dismiss handler (Python
 * removes them on its own schedule).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderTooltipOverlay(node: TempestNode, onEvent: (String, String) -> Unit) {
    val message = node.props["message"] as? String ?: ""
    val child = node.children.firstOrNull()
    TooltipBox(
        positionProvider = TooltipDefaults.rememberPlainTooltipPositionProvider(),
        tooltip = { PlainTooltip { Text(text = message) } },
        state = rememberTooltipState(),
    ) {
        if (child != null) RenderNode(child, onEvent) else Text(text = message)
    }
}

/** The serialized `items` of a Menu/ActionSheet as plain (label,value,icon) data. */
private fun menuItemsOf(node: TempestNode): List<MenuItemData> {
    @Suppress("UNCHECKED_CAST")
    val raw = node.props["items"] as? List<*> ?: return emptyList()
    return raw.mapNotNull { entry ->
        val map = entry as? Map<*, *> ?: return@mapNotNull null
        val label = map["label"] as? String ?: return@mapNotNull null
        val value = map["value"] as? String ?: return@mapNotNull null
        MenuItemData(label = label, value = value, icon = map["icon"] as? String)
    }
}

/** A decoded menu item from the serialized `items` array. */
private data class MenuItemData(val label: String, val value: String, val icon: String?)

/**
 * Report a menu/action-sheet selection back to Python as a [MenuSelectEvent]
 * payload `{value, label}` on the node's `on_select` handler.
 */
private fun emitMenuSelect(
    node: TempestNode,
    item: MenuItemData,
    onEvent: (String, String) -> Unit,
) {
    handlerToken(node, "on_select")?.let { token ->
        val payload = JSONObject().put("value", item.value).put("label", item.label)
        onEvent(token, payload.toString())
    }
}

/**
 * Report a host-owned overlay dismiss to Python via the reserved
 * `__dismiss__:<overlay_id>` event, where `overlay_id` is the node's [key]. The
 * bridge (`jni._on_event` / `DeviceApp.handle_event`) routes this to `App.dismiss`
 * — no new patch kind and no new JNI entry (B6 pattern).
 */
private fun emitDismiss(node: TempestNode, onEvent: (String, String) -> Unit) {
    val id = node.key ?: return
    onEvent("$DISMISS_TOKEN_PREFIX:$id", "{}")
}

/**
 * Reserved event-token prefix (E2) for a host-owned overlay dismiss. Must stay in
 * sync with `tempestroid.bridge.protocol.DISMISS_TOKEN_PREFIX`.
 */
private const val DISMISS_TOKEN_PREFIX = "__dismiss__"

/**
 * The enclosing [SharedTransitionScope] (E3d), published by [RenderNavigator]'s
 * `SharedTransitionLayout`. A [RenderHero] descendant reads it to register its
 * child as a shared element; `null` outside any Navigator (then `Hero` renders
 * its child plainly, with no shared-element animation — a documented divergence).
 */
@OptIn(ExperimentalSharedTransitionApi::class)
private val LocalSharedTransitionScope = compositionLocalOf<SharedTransitionScope?> { null }

/**
 * The enclosing [AnimatedVisibilityScope] (E3d) of the current route slot,
 * published by [RenderNavigator]'s `AnimatedContent`. `Modifier.sharedElement`
 * needs both this and [LocalSharedTransitionScope]; `null` outside a Navigator.
 */
private val LocalAnimatedVisibilityScope = compositionLocalOf<AnimatedVisibilityScope?> { null }

/**
 * Render an [Animated] wrapper (E3c). The interpolation already happened in the
 * Python core: `App.view` read the `AnimationController.value`, applied the
 * `Tween`, and built the single serialized child with its style already at the
 * current frame's target. So the device just renders that child — every frame
 * arrives as an `Update` patch carrying the next interpolated style.
 *
 * This is the documented Qt/Compose divergence in action: rather than driving a
 * second, native `animate*AsState` engine (which would fight the core clock and
 * double-animate), the Compose leaf faithfully paints the per-frame props the
 * core computed. The serialized `transition` spec (durationMs/curve) is carried
 * on the child's style for parity, but the core owns the cadence.
 */
@Composable
private fun RenderAnimated(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val child = node.children.firstOrNull()
    Box(modifier = baseModifier(style)) {
        if (child != null) RenderNode(child, onEvent)
    }
}

/**
 * Render an [AnimatedList] (E3c): a column/row whose children animate in/out
 * natively via [AnimatedVisibility] (`fadeIn`+`expandVertically` on enter,
 * `fadeOut`+`shrinkVertically` on exit). Unlike [RenderAnimated], the entry/exit
 * choreography IS owned by the Compose engine here (the Qt leaf uses
 * `QPropertyAnimation` instead — the documented divergence).
 *
 * Each child is keyed by its reconciler `key`; a `LaunchedEffect` flips its
 * visibility to `true` on first appearance so the enter transition plays. A
 * child removed from `node.children` is dropped by the reconciler's `Remove`
 * patch; Compose's keyed slot machinery plays the exit transition as it leaves.
 */
@Composable
private fun RenderAnimatedList(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val enterMs = (node.props["enter_duration_ms"] as? Number)?.toInt() ?: 300
    val exitMs = (node.props["exit_duration_ms"] as? Number)?.toInt() ?: 300
    val horizontal = (node.props["direction"] as? String) == "row"
    val children = node.children.toList()
    val content: @Composable () -> Unit = {
        children.forEachIndexed { index, child ->
            val itemKey = child.key ?: index.toString()
            androidx.compose.runtime.key(itemKey) {
                val visible = remember(itemKey) { mutableStateOf(false) }
                LaunchedEffect(itemKey) { visible.value = true }
                AnimatedVisibility(
                    visible = visible.value,
                    enter = fadeIn(tween(enterMs)) + expandVertically(tween(enterMs)),
                    exit = fadeOut(tween(exitMs)) + shrinkVertically(tween(exitMs)),
                ) {
                    RenderNode(child, onEvent)
                }
            }
        }
    }
    if (horizontal) {
        Row(modifier = baseModifier(style)) { content() }
    } else {
        Column(modifier = baseModifier(style)) { content() }
    }
}

/**
 * Render a [Shimmer] (E3c): wrap the single child in a [Box] painted with a
 * left-to-right [Brush.linearGradient] that sweeps between `base_color` and
 * `highlight_color`, driven by an [rememberInfiniteTransition] looping over
 * `duration_ms`. The native infinite loop is the device clock here (the Qt leaf
 * animates a `QLinearGradient` instead — the documented divergence), so this
 * needs no Python `__frame__` ticks.
 */
@Composable
private fun RenderShimmer(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val durationMs = (node.props["duration_ms"] as? Number)?.toInt() ?: 1200
    val base = colorFromProp(node.props["base_color"]) ?: Color(0xFFE0E0E0)
    val highlight = colorFromProp(node.props["highlight_color"]) ?: Color(0xFFF5F5F5)
    val brush = shimmerBrush(durationMs, base, highlight)
    val child = node.children.firstOrNull()
    Box(modifier = baseModifier(style).background(brush)) {
        if (child != null) RenderNode(child, onEvent)
    }
}

/**
 * Render a [Skeleton] (E3c): a childless rounded placeholder rectangle painted
 * with the same sweeping shimmer [Brush] as [RenderShimmer]. Sizes to its
 * `width`/`height` props (height defaults to a single text-line band).
 */
@Composable
private fun RenderSkeleton(node: TempestNode, style: Map<String, Any?>) {
    val durationMs = (node.props["duration_ms"] as? Number)?.toInt() ?: 1200
    val radius = (node.props["radius"] as? Number)?.toFloat() ?: 4f
    val width = (node.props["width"] as? Number)?.toFloat()
    val height = (node.props["height"] as? Number)?.toFloat() ?: 16f
    val base = colorFromProp(node.props["base_color"]) ?: Color(0xFFE0E0E0)
    val highlight = colorFromProp(node.props["highlight_color"]) ?: Color(0xFFF5F5F5)
    val brush = shimmerBrush(durationMs, base, highlight)
    var m: Modifier = if (width != null) Modifier.width(width.dp) else Modifier.fillMaxWidth()
    m = m.height(height.dp).clip(RoundedCornerShape(radius.dp)).background(brush)
    Box(modifier = m)
}

/**
 * Build the looping shimmer [Brush]: a horizontal gradient
 * `base → highlight → base` whose highlight band slides across via an
 * [rememberInfiniteTransition] animating its start/end offsets over [durationMs].
 */
@Composable
private fun shimmerBrush(durationMs: Int, base: Color, highlight: Color): Brush {
    val transition = rememberInfiniteTransition(label = "shimmer")
    val translate by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = InfiniteRepeatableSpec(
            animation = tween(durationMillis = durationMs.coerceAtLeast(1), easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "shimmerTranslate",
    )
    val span = 600f
    val x = translate * (span * 2) - span
    return Brush.linearGradient(
        colors = listOf(base, highlight, base),
        start = Offset(x, 0f),
        end = Offset(x + span, 0f),
    )
}

/**
 * Render a [Hero] (E3d): tag its single child as a shared element so it animates
 * across a Navigator route swap. Resolves the [SharedTransitionScope] and the
 * route slot's [AnimatedVisibilityScope] from the CompositionLocals
 * [RenderNavigator] publishes; both must be present. When either is absent (a
 * `Hero` used outside any Navigator), the child renders plainly — a documented
 * divergence (Qt interpolates geometry by hero_tag on the page swap).
 */
@OptIn(ExperimentalSharedTransitionApi::class)
@Composable
private fun RenderHero(node: TempestNode, onEvent: (String, String) -> Unit) {
    val child = node.children.firstOrNull()
    val tag = node.props["hero_tag"] as? String
    val sharedScope = LocalSharedTransitionScope.current
    val visibilityScope = LocalAnimatedVisibilityScope.current
    if (child == null) return
    if (tag != null && sharedScope != null && visibilityScope != null) {
        with(sharedScope) {
            Box(
                modifier = Modifier.sharedElement(
                    rememberSharedContentState(key = tag),
                    animatedVisibilityScope = visibilityScope,
                ),
            ) {
                RenderNode(child, onEvent)
            }
        }
    } else {
        RenderNode(child, onEvent)
    }
}

/**
 * Render a [KeyboardAvoidingView] (E8): a [Column] that recedes its content above
 * the soft keyboard (IME) when it appears — the Compose counterpart of the Qt
 * `_KeyboardAvoidingWidget` (which listens to
 * `QApplication.inputMethod().keyboardRectangleChanged` and adjusts margins).
 *
 * [Modifier.imePadding] applies bottom padding equal to the visible IME inset
 * (`WindowInsets.ime`), animating in lockstep with the keyboard show/hide, so the
 * children stay above it. When the keyboard is hidden (or on a device with a
 * hardware keyboard) the inset is zero and it behaves like a plain Column.
 *
 * Documented divergence: Qt resizes via `keyboardRectangleChanged` margins (no-op
 * on the desktop sim, where there is no soft keyboard); Compose uses the native
 * `Modifier.imePadding()`. The user-visible behaviour is identical.
 */
@Composable
private fun RenderKeyboardAvoidingView(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    Column(
        modifier = baseModifier(style).imePadding(),
        verticalArrangement = verticalArrangement(style),
        horizontalAlignment = horizontalAlignment(style),
    ) {
        node.children.forEach { RenderNode(it, onEvent) }
    }
}

/**
 * Render a [Wrap] (E6): a flow-layout container whose children wrap to the next
 * line/column when the main axis is full — the Kotlin counterpart of the Qt
 * `_WrapWidget`.
 *
 * The direction comes from the serialized style `direction` (`"column"` →
 * [FlowColumn], anything else → [FlowRow], the default). The `flexWrap` style spec
 * (`"nowrap"` / `"wrap"` / `"wrapReverse"`, from `Style.flex_wrap` via the Compose
 * translator) selects the wrap policy: `"nowrap"` pins `maxItemsInEachRow`/`Column`
 * to [Int.MAX_VALUE] (one line, never wraps); `"wrap"`/`"wrapReverse"` let it flow.
 * `gap` and `arrangement` drive the main- and cross-axis spacing the same way as a
 * plain Column/Row.
 *
 * Documented divergence: Qt reflows children manually in `_WrapWidget.resizeEvent`;
 * Compose uses the native `FlowRow`/`FlowColumn`. Both honour `Style.gap`.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun RenderWrap(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val column = style["direction"] == "column"
    // A nowrap policy collapses the flow to a single line by capping the per-line
    // item count; wrap/wrapReverse (and an absent flexWrap) flow freely.
    val nowrap = style["flexWrap"] == "nowrap"
    val maxPerLine = if (nowrap) 1 else Int.MAX_VALUE
    if (column) {
        FlowColumn(
            modifier = baseModifier(style),
            verticalArrangement = verticalArrangement(style),
            horizontalArrangement = horizontalArrangement(style),
            maxItemsInEachColumn = maxPerLine,
        ) {
            node.children.forEach { RenderNode(it, onEvent) }
        }
    } else {
        FlowRow(
            modifier = baseModifier(style),
            horizontalArrangement = horizontalArrangement(style),
            verticalArrangement = verticalArrangement(style),
            maxItemsInEachRow = maxPerLine,
        ) {
            node.children.forEach { RenderNode(it, onEvent) }
        }
    }
}

/**
 * Render a [PageView] (E6): a horizontally paginated carousel — the Kotlin
 * counterpart of the Qt `_PageViewWidget` (`QStackedWidget` + prev/next).
 *
 * The active page lives in Python (`node.props["page"]`); a [rememberPagerState]
 * seeds its initial page from that prop and counts pages from `node.children`. A
 * [LaunchedEffect] keyed on the declared page scrolls the pager when Python pushes
 * a new page (declarative state drives the pager). A second [LaunchedEffect] keyed
 * on the settled `currentPage` reports a [PageChangeEvent]-shaped payload
 * `{"page": i, "previous": j}` on `on_page_change`, but only when the swipe settled
 * away from the declared page (so a programmatic scroll-to does not echo).
 *
 * Documented divergence: Qt swaps `QStackedWidget` pages via prev/next buttons (no
 * swipe hardware); Compose uses a native swipeable `HorizontalPager`. Both emit the
 * same `PageChangeEvent`.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun RenderPageView(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val declared = (node.props["page"] as? Number)?.toInt() ?: 0
    val pageCount = node.children.size
    if (pageCount == 0) return
    val pagerState = rememberPagerState(
        initialPage = declared.coerceIn(0, pageCount - 1),
        pageCount = { pageCount },
    )
    // Declarative state drives the pager: when Python pushes a new active page,
    // animate the pager to it (a no-op when already there).
    LaunchedEffect(declared) {
        val target = declared.coerceIn(0, pageCount - 1)
        if (pagerState.currentPage != target) pagerState.animateScrollToPage(target)
    }
    // Report a user-driven page change back to Python. Keying on currentPage runs
    // after the swipe settles; only emit when the settled page differs from what
    // Python last declared, so a programmatic scroll-to (above) does not echo.
    LaunchedEffect(pagerState.currentPage) {
        val current = pagerState.currentPage
        if (current != declared) {
            handlerToken(node, "on_page_change")?.let { token ->
                val payload = JSONObject().put("page", current).put("previous", declared)
                onEvent(token, payload.toString())
            }
        }
    }
    HorizontalPager(
        state = pagerState,
        modifier = baseModifier(style).fillMaxWidth(),
    ) { page ->
        node.children.getOrNull(page)?.let { RenderNode(it, onEvent) }
    }
}

/**
 * Render an [AspectRatio] (E6): a single-child box whose width/height ratio is
 * fixed by the `ratio` prop (width / height) via [Modifier.aspectRatio] — the
 * Kotlin counterpart of the Qt `_AspectRatioWidget` (`heightForWidth`).
 *
 * Distinct from the `Style.aspect_ratio` field (also Compose-only): this is the
 * explicit wrapper widget where the ratio is the container's sole purpose. A
 * non-positive or missing ratio renders the child without the constraint.
 */
@Composable
private fun RenderAspectRatio(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val ratio = (node.props["ratio"] as? Number)?.toFloat() ?: 1f
    val child = node.children.firstOrNull()
    val modifier = if (ratio > 0f) baseModifier(style).aspectRatio(ratio) else baseModifier(style)
    Box(modifier = modifier) {
        if (child != null) RenderNode(child, onEvent)
    }
}

/**
 * Render a [Canvas] (E7): a drawing surface that replays a serialized list of
 * draw commands — the Kotlin counterpart of the Qt `_CanvasWidget.paintEvent`.
 *
 * Each command is a plain JSON map carrying a `kind` discriminator (`move_to`,
 * `line_to`, `arc_to`, `close`, `fill`, `stroke`, `draw_text`, `draw_rect`,
 * `draw_oval`). Colors arrive as JSON float arrays `[r,g,b,a]` in `[0,1]`. The
 * commands accumulate into a native [NativePath]; a `fill`/`stroke` flushes that
 * path with the given paint (then resets it), exactly mirroring the Qt renderer
 * so the same command list draws identically on both leaves (the strong E7
 * conformance item).
 */
@Composable
private fun RenderCanvas(node: TempestNode, style: Map<String, Any?>) {
    @Suppress("UNCHECKED_CAST")
    val commands = (node.props["commands"] as? List<*>)
        ?.mapNotNull { it as? Map<String, Any?> } ?: emptyList()
    val width = (node.props["width"] as? Number)?.toFloat()
    val height = (node.props["height"] as? Number)?.toFloat()
    var m = baseModifier(style)
    if (width != null) m = m.width(width.dp)
    if (height != null) m = m.height(height.dp)
    // A Canvas with no size hint and no Style size would collapse to zero; give a
    // sensible default fill so the drawing is visible.
    if (width == null && height == null) m = m.fillMaxSize()
    Canvas(modifier = m) {
        drawIntoCanvas { canvas -> interpretCanvasCommands(canvas.nativeCanvas, commands) }
    }
}

/** Decode a `[r,g,b,a]` float list (channels in `[0,1]`) into an ARGB int. */
private fun argbFromList(value: Any?, fallback: Int = 0xFF000000.toInt()): Int {
    @Suppress("UNCHECKED_CAST")
    val list = (value as? List<*>)?.mapNotNull { (it as? Number)?.toFloat() } ?: return fallback
    if (list.size < 3) return fallback
    val r = (list[0].coerceIn(0f, 1f) * 255).toInt()
    val g = (list[1].coerceIn(0f, 1f) * 255).toInt()
    val b = (list[2].coerceIn(0f, 1f) * 255).toInt()
    val a = (list.getOrNull(3)?.coerceIn(0f, 1f) ?: 1f) * 255
    return (a.toInt() shl 24) or (r shl 16) or (g shl 8) or b
}

/** Replay one serialized canvas command list onto a native [android.graphics.Canvas]. */
private fun interpretCanvasCommands(
    canvas: android.graphics.Canvas,
    commands: List<Map<String, Any?>>,
) {
    var path = NativePath()
    fun f(cmd: Map<String, Any?>, key: String): Float = (cmd[key] as? Number)?.toFloat() ?: 0f
    for (cmd in commands) {
        when (cmd["kind"] as? String) {
            "move_to" -> path.moveTo(f(cmd, "x"), f(cmd, "y"))
            "line_to" -> path.lineTo(f(cmd, "x"), f(cmd, "y"))
            "arc_to" -> {
                val rect = RectF(
                    f(cmd, "x"), f(cmd, "y"),
                    f(cmd, "x") + f(cmd, "width"), f(cmd, "y") + f(cmd, "height"),
                )
                path.arcTo(rect, f(cmd, "start_angle"), f(cmd, "sweep_angle"))
            }
            "close" -> path.close()
            "draw_rect" -> path.addRect(
                f(cmd, "x"), f(cmd, "y"),
                f(cmd, "x") + f(cmd, "width"), f(cmd, "y") + f(cmd, "height"),
                NativePath.Direction.CW,
            )
            "draw_oval" -> path.addOval(
                RectF(
                    f(cmd, "x"), f(cmd, "y"),
                    f(cmd, "x") + f(cmd, "width"), f(cmd, "y") + f(cmd, "height"),
                ),
                NativePath.Direction.CW,
            )
            "fill" -> {
                val paint = NativePaint(NativePaint.ANTI_ALIAS_FLAG).apply {
                    style = NativePaint.Style.FILL
                    color = argbFromList(cmd["color"])
                }
                canvas.drawPath(path, paint)
                path = NativePath()
            }
            "stroke" -> {
                val paint = NativePaint(NativePaint.ANTI_ALIAS_FLAG).apply {
                    style = NativePaint.Style.STROKE
                    color = argbFromList(cmd["color"])
                    strokeWidth = f(cmd, "width").takeIf { it > 0f } ?: 1f
                }
                canvas.drawPath(path, paint)
                path = NativePath()
            }
            "draw_text" -> {
                val paint = NativePaint(NativePaint.ANTI_ALIAS_FLAG).apply {
                    color = argbFromList(cmd["color"])
                    textSize = (cmd["size"] as? Number)?.toFloat() ?: 14f
                }
                canvas.drawText(cmd["text"] as? String ?: "", f(cmd, "x"), f(cmd, "y"), paint)
            }
        }
    }
}

/**
 * Render a [WebView] (E7): an `android.webkit.WebView` hosted in [AndroidView] —
 * the Compose counterpart of the Qt `QWebEngineView`. JavaScript is gated by the
 * `javascript_enabled` prop; the `url` is loaded once at factory time and on
 * subsequent url changes via the update block.
 */
@Composable
private fun RenderWebView(node: TempestNode, style: Map<String, Any?>) {
    val url = node.props["url"] as? String ?: "about:blank"
    val jsEnabled = node.props["javascript_enabled"] as? Boolean ?: true
    AndroidView(
        modifier = baseModifier(style),
        factory = { ctx ->
            AndroidWebView(ctx).apply {
                settings.javaScriptEnabled = jsEnabled
                loadUrl(url)
            }
        },
        update = { webView ->
            webView.settings.javaScriptEnabled = jsEnabled
            if (webView.url != url) webView.loadUrl(url)
        },
    )
}

/**
 * Render an [Svg] (E7): a Coil [AsyncImage] pointed at the `src` — the Compose
 * counterpart of the Qt `QSvgRenderer`. Coil decodes raster sources and remote
 * SVGs by URL out of the box; a local-asset SVG would additionally need the
 * `coil-svg` decoder (documented as a follow-up — not bundled to keep deps lean).
 */
@Composable
private fun RenderSvg(node: TempestNode, style: Map<String, Any?>) {
    val src = node.props["src"] as? String ?: return
    AsyncImage(
        model = src,
        contentDescription = null,
        contentScale = contentScaleOf(node.props["fit"] as? String),
        modifier = baseModifier(style),
    )
}

/** Map the serialized `fit` value to a Compose [ContentScale]. */
private fun contentScaleOf(fit: String?): ContentScale = when (fit) {
    "cover" -> ContentScale.Crop
    "fill" -> ContentScale.FillBounds
    "none" -> ContentScale.None
    else -> ContentScale.Fit
}

/**
 * Render a [MapView] (E7) — DOCUMENTED PLACEHOLDER, independent of the feature
 * set. Google Maps Compose would require a `google-services.json` + a Maps API
 * key in the manifest, without which the APK does not build; that config is out
 * of scope for the host skeleton, so the widget renders an explicit placeholder
 * on both leaves (mirrors the Qt sim PLACEHOLDER). The `maps` feature reserves
 * the name; wiring `maps-compose` is a documented post-phase follow-up, at which
 * point this moves to `src/feat_maps` like the other features.
 */
@Composable
private fun RenderMapView(node: TempestNode, style: Map<String, Any?>) {
    val lat = (node.props["latitude"] as? Number)?.toDouble() ?: 0.0
    val lng = (node.props["longitude"] as? Number)?.toDouble() ?: 0.0
    Box(
        modifier = baseModifier(style)
            .background(Color(0xFFE0E0E0), RoundedCornerShape(8.dp))
            .padding(16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = "MapView — configure Google Maps API key ($lat, $lng)")
    }
}

/**
 * Render a [Blur] / [BackdropFilter] (E7): a single-child [Box] with
 * [Modifier.blur] applied at `radius` dp — the Compose counterpart of the Qt
 * `QGraphicsBlurEffect`. `BackdropFilter` shares the same path (blur over the
 * content below); both are wrappers carrying one `child`.
 */
@Composable
private fun RenderBlur(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val radius = (node.props["radius"] as? Number)?.toFloat() ?: 8f
    val child = node.children.firstOrNull()
    Box(modifier = baseModifier(style).blur(radius.dp)) {
        if (child != null) RenderNode(child, onEvent)
    }
}

/**
 * Render a [ClipPath] (E7): a single-child [Box] clipped to a predefined shape via
 * [Modifier.clip] — the Compose counterpart of the Qt `QPainterPath` mask. `circle`
 * → [CircleShape]; `oval` → [CircleShape] (closest stock shape); `rounded_rect` →
 * [RoundedCornerShape] of `radius` dp.
 */
@Composable
private fun RenderClipPath(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val radius = (node.props["radius"] as? Number)?.toFloat() ?: 8f
    val shape = when (node.props["shape"] as? String) {
        "circle", "oval" -> CircleShape
        else -> RoundedCornerShape(radius.dp)
    }
    val child = node.children.firstOrNull()
    Box(modifier = baseModifier(style).clip(shape)) {
        if (child != null) RenderNode(child, onEvent)
    }
}

/** Parse a serialized color prop (a `#rrggbb`/`#aarrggbb` hex string) to a [Color]. */
internal fun colorFromProp(value: Any?): Color? =
    (value as? String)?.let { parseHexColor(it) }

/**
 * A navigation-stack host that animates the swap of its single top screen — the
 * Kotlin counterpart of the Qt `_NavHost` (Navigator path, no tab strip).
 *
 * The top screen is `node.children[0]`. A push/pop is observed as that child's
 * `key` (or, lacking a key, the `depth` prop) changing; the slide direction comes
 * from the delta of `depth` against the last depth seen (deeper → push, slide in
 * from the right; shallower → pop, slide in from the left). The `transition` prop
 * picks the animation: `"fade"` cross-fades, `"none"` swaps instantly, anything
 * else (default `"slide"`) slides horizontally.
 */
@OptIn(ExperimentalSharedTransitionApi::class)
@Composable
private fun RenderNavigator(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val child = node.children.firstOrNull()
    val depth = (node.props["depth"] as? Number)?.toInt() ?: 0
    val transition = node.props["transition"] as? String ?: "slide"
    // Remember the last depth to tell a push (deeper) from a pop (shallower); the
    // initial render has no previous screen, so it must not animate a direction.
    var lastDepth by remember { mutableStateOf(depth) }
    val forward = depth >= lastDepth
    // Drive AnimatedContent off a stable per-screen key so a same-typed screen
    // swap (diffed as an Update on this Navigator) still triggers the animation.
    val targetKey = child?.key ?: "depth:$depth"
    // E3d: wrap the AnimatedContent in a SharedTransitionLayout so a `Hero` node
    // present on both the outgoing and incoming screen (matched by hero_tag)
    // animates as one shared element across the route swap. The
    // SharedTransitionScope is published to descendants via a CompositionLocal so
    // the (deeply nested) `Hero` case can resolve it without threading it through
    // every RenderNode call (mirrors the Qt "interpolate geometry by hero_tag").
    Box(modifier = baseModifier(style)) {
        SharedTransitionLayout {
            CompositionLocalProvider(LocalSharedTransitionScope provides this) {
                AnimatedContent(
                    targetState = targetKey,
                    transitionSpec = {
                        when (transition) {
                            "fade" -> fadeIn() togetherWith fadeOut()
                            "none" -> EnterTransition.None togetherWith ExitTransition.None
                            else -> {
                                val sign = if (forward) 1 else -1
                                (slideInHorizontally { full -> sign * full } togetherWith
                                    slideOutHorizontally { full -> -sign * full })
                            }
                        }
                    },
                    label = "navigator",
                ) { key ->
                    // Publish this AnimatedContent's AnimatedVisibilityScope so a
                    // `Hero` descendant can call `sharedElement(...)` with the
                    // required scope. `key` keys the slot so Compose keeps the
                    // outgoing/incoming subtrees distinct during the transition.
                    CompositionLocalProvider(LocalAnimatedVisibilityScope provides this) {
                        if (child != null && key == targetKey) {
                            RenderNode(child, onEvent)
                        }
                    }
                }
            }
        }
    }
    // Record the depth *after* this composition so the next swap compares against it.
    LaunchedEffect(depth) { lastDepth = depth }
}

/**
 * A tabbed host: a [TabRow] strip above the active tab's content — the Kotlin
 * counterpart of the Qt `_NavHost` with a tab strip plus `_TabBarWidget`.
 *
 * `tabs` are the labels, `active` the selected index, and `node.children[0]` the
 * active tab's content. Tapping tab `i` emits the same `RouteChangeEvent` payload
 * as the Qt `_TabBarWidget._make_tap`: `{"name": label, "params": {"index": i}}`.
 */
@Composable
private fun RenderTabView(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val active = (node.props["active"] as? Number)?.toInt() ?: 0
    val child = node.children.firstOrNull()
    // The tab strip must sit FLUSH under the status bar (which the root Surface
    // already insets). The host's Style background/size go on the outer Column,
    // but its padding is moved to the CONTENT slot only — applying it above the
    // strip would push the TabRow down and leave a (dark) gap between the status
    // bar and the strip, making it look detached.
    Column(modifier = backgroundSizeModifier(style)) {
        TabStrip(node, active, onEvent)
        AnimatedContent(
            targetState = active,
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            label = "tabview",
        ) { selected ->
            // The content is built by Python for the active tab; key the slot by
            // the selected index so a tab swap cross-fades the new content.
            if (child != null && selected == active) {
                Box(modifier = paddingModifier(style)) { RenderNode(child, onEvent) }
            }
        }
    }
}

/**
 * A standalone tab strip (no content) — the Kotlin counterpart of the Qt
 * `_TabBarWidget` used on its own. Same tap payload as [RenderTabView].
 */
@Composable
private fun RenderTabBar(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val active = (node.props["active"] as? Number)?.toInt() ?: 0
    Box(modifier = baseModifier(style)) {
        TabStrip(node, active, onEvent)
    }
}

/**
 * Render the shared tab strip for [RenderTabView]/[RenderTabBar].
 *
 * Reads `tabs` (labels) and highlights `active`. Tapping tab `i` with label
 * `label` fires `handlerToken(node, "on_change")` with the
 * `RouteChangeEvent`-shaped JSON `{"name": label, "params": {"index": i}}`.
 */
@Composable
private fun TabStrip(
    node: TempestNode,
    active: Int,
    onEvent: (String, String) -> Unit,
) {
    @Suppress("UNCHECKED_CAST")
    val tabs = (node.props["tabs"] as? List<*>)?.mapNotNull { it as? String } ?: emptyList()
    if (tabs.isEmpty()) return
    val selected = active.coerceIn(0, tabs.size - 1)
    TabRow(selectedTabIndex = selected) {
        tabs.forEachIndexed { index, label ->
            Tab(
                selected = index == selected,
                onClick = {
                    handlerToken(node, "on_change")?.let { token ->
                        val payload = JSONObject()
                            .put("name", label)
                            .put("params", JSONObject().put("index", index))
                        onEvent(token, payload.toString())
                    }
                },
                text = { Text(text = label) },
            )
        }
    }
}

/**
 * A drawer-as-route host: main content with a slide-over side panel — the Kotlin
 * counterpart of the Qt `_DrawerHost`, realized with Material3's
 * [ModalNavigationDrawer].
 *
 * The open/closed state lives in Python (`node.props["open"]`); a unidirectional
 * [LaunchedEffect] drives the internal [rememberDrawerState] to match, so the
 * Compose-internal drag/scrim never fights the declared state. `node.children[0]`
 * is the content, `node.children[1]` is the drawer panel. Dismissing the drawer
 * (scrim tap or back gesture) emits `{"name": "drawer", "params": {"open": false}}`
 * so the Python handler can flip the flag.
 */
@Composable
private fun RenderRouteDrawer(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val open = node.props["open"] as? Boolean ?: false
    val content = node.children.getOrNull(0)
    val drawer = node.children.getOrNull(1)
    val drawerState = rememberDrawerState(
        initialValue = if (open) DrawerValue.Open else DrawerValue.Closed,
    )
    // Unidirectional sync: the declared `open` flag drives the internal state.
    LaunchedEffect(open) {
        if (open) drawerState.open() else drawerState.close()
    }
    // A user-driven dismiss (scrim tap / back) settles the internal state to
    // Closed; when that happens while Python still declares it open, report the
    // toggle-off so the declarative flag follows the gesture. Keying on
    // currentValue re-runs the effect each time the drawer settles.
    LaunchedEffect(drawerState.currentValue) {
        snapshotIsClosedThenReport(
            isClosed = drawerState.currentValue == DrawerValue.Closed,
            declaredOpen = open,
            node = node,
            onEvent = onEvent,
        )
    }
    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet {
                if (drawer != null) RenderNode(drawer, onEvent)
            }
        },
        modifier = baseModifier(style),
    ) {
        Box(modifier = Modifier) {
            if (content != null) RenderNode(content, onEvent)
        }
    }
}

/**
 * Report a user-driven drawer dismiss back to Python.
 *
 * When the internal drawer state has become closed while Python still believes it
 * is open (a scrim tap or back gesture), emit the toggle-off `RouteChangeEvent`.
 *
 * @param isClosed whether the internal drawer state is currently closed.
 * @param declaredOpen the open flag Python last declared.
 * @param node the RouteDrawer node (for its `on_change` handler token).
 * @param onEvent the event sink back to Python.
 */
private fun snapshotIsClosedThenReport(
    isClosed: Boolean,
    declaredOpen: Boolean,
    node: TempestNode,
    onEvent: (String, String) -> Unit,
) {
    if (isClosed && declaredOpen) {
        handlerToken(node, "on_change")?.let { token ->
            val payload = JSONObject()
                .put("name", "drawer")
                .put("params", JSONObject().put("open", false))
            onEvent(token, payload.toString())
        }
    }
}

/**
 * A controlled text field: the value lives in Python; each edit sends a
 * `TextChangeEvent`. Renders the curated `leading_icon`/`trailing_icon` slots.
 *
 * A `secure` field masks its text via [PasswordVisualTransformation] and shows a
 * modern eye / eye-off reveal toggle (the curated `eye`/`eye-off` icons) that
 * flips to [VisualTransformation.None] locally — the visibility is host-side UI
 * state only and never crosses the bridge. An explicit `trailing_icon` wins over
 * the reveal toggle when both are set.
 */
@Composable
private fun RenderInput(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val secure = node.props["secure"] as? Boolean ?: false
    var revealed by remember { mutableStateOf(false) }
    val leading = iconSlot(node, "leading_icon", "leadingIconPath")
    val explicitTrailing = iconSlot(node, "trailing_icon", "trailingIconPath")
    val trailing: (@Composable () -> Unit)? = when {
        explicitTrailing != null -> explicitTrailing
        secure -> {
            {
                IconButton(onClick = { revealed = !revealed }) {
                    val d = curatedIconPath(if (revealed) "eye-off" else "eye")
                    if (d != null) {
                        CuratedIcon(
                            name = if (revealed) "eye-off" else "eye",
                            d = d,
                            tint = null,
                        )
                    }
                }
            }
        }
        else -> null
    }
    OutlinedTextField(
        value = node.props["value"] as? String ?: "",
        onValueChange = { text ->
            handlerToken(node, "on_change")?.let {
                onEvent(it, JSONObject().put("value", text).toString())
            }
        },
        placeholder = { Text(text = node.props["placeholder"] as? String ?: "") },
        singleLine = true,
        leadingIcon = leading,
        trailingIcon = trailing,
        visualTransformation =
            if (secure && !revealed) PasswordVisualTransformation() else VisualTransformation.None,
        modifier = baseModifier(style),
    )
}

/** A labelled checkbox; each toggle sends a `ToggleEvent`. */
@Composable
private fun RenderCheckbox(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    Row(
        modifier = baseModifier(style),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(
            checked = node.props["checked"] as? Boolean ?: false,
            onCheckedChange = { checked ->
                handlerToken(node, "on_change")?.let {
                    onEvent(it, JSONObject().put("checked", checked).toString())
                }
            },
        )
        // The label carries no per-label color in the IR, so paint it with the
        // tracked contrast color rather than the inherited default (which reads
        // near-black on a dark app background and disappears).
        Text(
            text = node.props["label"] as? String ?: "",
            color = defaultTextColor(),
        )
    }
}

/** A button opening a Material date dialog; confirming sends an ISO `DateChangeEvent`. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderDatePicker(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    val value = node.props["value"] as? String ?: ""
    val label = node.props["label"] as? String ?: ""
    Button(
        onClick = { open = true },
        modifier = sizeModifier(style),
        colors = pickerButtonColors(style),
    ) {
        Text(text = if (value.isNotEmpty()) value else if (label.isNotEmpty()) label else "Pick date")
    }
    if (open) {
        val state = rememberDatePickerState()
        DatePickerDialog(
            onDismissRequest = { open = false },
            confirmButton = {
                TextButton(onClick = {
                    open = false
                    state.selectedDateMillis?.let { millis ->
                        val iso = Instant.ofEpochMilli(millis)
                            .atZone(ZoneOffset.UTC)
                            .toLocalDate()
                            .toString()
                        handlerToken(node, "on_change")?.let {
                            onEvent(it, JSONObject().put("value", iso).toString())
                        }
                    }
                }) { Text(text = "OK") }
            },
            dismissButton = {
                TextButton(onClick = { open = false }) { Text(text = "Cancel") }
            },
        ) {
            DatePicker(state = state)
        }
    }
}

/** A button opening the system file picker; a pick sends a `FileSelectEvent`. */
@Composable
private fun RenderFilePicker(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val context = LocalContext.current
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent(),
    ) { uri: Uri? ->
        if (uri != null) {
            val payload = JSONObject().put("uri", uri.toString())
            val name = displayName(context, uri) ?: uri.lastPathSegment
            if (name != null) payload.put("name", name)
            handlerToken(node, "on_select")?.let { onEvent(it, payload.toString()) }
        }
    }
    val value = node.props["value"] as? String ?: ""
    val label = node.props["label"] as? String ?: "Choose file"
    Button(
        onClick = { launcher.launch("*/*") },
        modifier = sizeModifier(style),
        colors = pickerButtonColors(style),
    ) {
        Text(text = if (value.isNotEmpty()) "$label: $value" else label)
    }
}

/**
 * Container/content colors for a picker trigger ([RenderDatePicker] /
 * [RenderFilePicker]). When the node's Style declares a `background`, honour it
 * (matching a regular tempestroid [Button]); otherwise fall back to the theme's
 * NEUTRAL `secondaryContainer` instead of the Material primary — so a picker
 * trigger does not show raw Material purple clashing with the app's palette.
 */
@Composable
private fun pickerButtonColors(style: Map<String, Any?>): androidx.compose.material3.ButtonColors {
    val container = colorOf(style, "background")
    val content = colorOf(style, "color")
    return if (container != null) {
        ButtonDefaults.buttonColors(
            containerColor = container,
            contentColor = content ?: Color.White,
        )
    } else {
        ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer,
            contentColor = content ?: MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}

/**
 * Neutral, contrast-aware colors for a read-only trigger [TextField] (Dropdown /
 * Select). Mirrors [pickerButtonColors]/#80: honour the node's `Style.background`/
 * `color` when given, otherwise fall back to the theme's neutral `surfaceVariant`
 * container + a contrast-tracked text color (NOT the Material default lavender,
 * which reads light-on-light over a dark app surface). Applied to BOTH the focused
 * and unfocused states so the field never flashes the default tint.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun neutralTextFieldColors(style: Map<String, Any?>): androidx.compose.material3.TextFieldColors {
    val container = colorOf(style, "background") ?: MaterialTheme.colorScheme.surfaceVariant
    val text = colorOf(style, "color") ?: defaultTextColor()
    return TextFieldDefaults.colors(
        focusedContainerColor = container,
        unfocusedContainerColor = container,
        disabledContainerColor = container,
        focusedTextColor = text,
        unfocusedTextColor = text,
        disabledTextColor = text,
        focusedTrailingIconColor = text,
        unfocusedTrailingIconColor = text,
    )
}

/** Resolve a content URI's human-readable display name, or null. */
private fun displayName(context: Context, uri: Uri): String? {
    val cursor = context.contentResolver.query(uri, null, null, null, null) ?: return null
    cursor.use {
        val index = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (index >= 0 && it.moveToFirst()) {
            return it.getString(index)
        }
    }
    return null
}

/**
 * A dropdown / select (E5). Material3 [ExposedDropdownMenuBox] anchoring a
 * read-only [TextField] whose trailing chevron toggles the menu. Each
 * [DropdownMenuItem] tap fires `on_select` with a [SelectEvent]-shaped payload
 * `{"value": opt, "index": i}`.
 *
 * Documented divergence: Qt uses a native `QComboBox`; both emit the same
 * `SelectEvent`. The displayed value lives in Python (`node.props["value"]`).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderDropdown(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    @Suppress("UNCHECKED_CAST")
    val options = (node.props["options"] as? List<*>)?.mapNotNull { it as? String } ?: emptyList()
    val value = node.props["value"] as? String ?: ""
    val placeholder = node.props["placeholder"] as? String ?: ""
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = baseModifier(style),
    ) {
        TextField(
            value = value.ifEmpty { placeholder },
            onValueChange = {},
            readOnly = true,
            leadingIcon = iconSlot(node, "leading_icon", "leadingIconPath"),
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            // Neutral + contrast-aware colors (NOT the Material lavender default,
            // which reads light-on-light over a dark app surface). See #80.
            colors = neutralTextFieldColors(style),
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable),
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            options.forEachIndexed { i, opt ->
                DropdownMenuItem(
                    text = { Text(text = opt) },
                    onClick = {
                        expanded = false
                        handlerToken(node, "on_select")?.let {
                            val payload = JSONObject().put("value", opt).put("index", i)
                            onEvent(it, payload.toString())
                        }
                    },
                )
            }
        }
    }
}

/**
 * A time picker (E5). A read-only [OutlinedTextField] opens a modal
 * [AlertDialog] hosting the Material3 [TimePicker]; Confirm fires `on_change`
 * with a [TimeChangeEvent]-shaped payload `{"value": "HH:MM"}` (zero-padded
 * 24-hour). The displayed value lives in Python (`node.props["value"]`).
 *
 * Documented divergence: Qt uses an inline `QTimeEdit` spinner; Compose uses a
 * modal `TimePicker` dialog. Both emit the same `TimeChangeEvent`.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderTimePicker(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val value = node.props["value"] as? String ?: ""
    val label = node.props["label"] as? String ?: ""
    var showDialog by remember { mutableStateOf(false) }
    // Seed the picker from the current "HH:MM" value when present.
    val parts = value.split(":")
    val initialHour = parts.getOrNull(0)?.toIntOrNull()?.coerceIn(0, 23) ?: 0
    val initialMinute = parts.getOrNull(1)?.toIntOrNull()?.coerceIn(0, 59) ?: 0
    OutlinedTextField(
        value = value,
        onValueChange = {},
        readOnly = true,
        enabled = false,
        label = if (label.isNotEmpty()) ({ Text(text = label) }) else null,
        placeholder = { Text(text = "HH:MM") },
        modifier = baseModifier(style).clickable { showDialog = true },
    )
    if (showDialog) {
        val state = rememberTimePickerState(
            initialHour = initialHour,
            initialMinute = initialMinute,
            is24Hour = true,
        )
        AlertDialog(
            onDismissRequest = { showDialog = false },
            confirmButton = {
                TextButton(onClick = {
                    showDialog = false
                    val hh = state.hour.toString().padStart(2, '0')
                    val mm = state.minute.toString().padStart(2, '0')
                    handlerToken(node, "on_change")?.let {
                        onEvent(it, JSONObject().put("value", "$hh:$mm").toString())
                    }
                }) { Text(text = "OK") }
            },
            dismissButton = {
                TextButton(onClick = { showDialog = false }) { Text(text = "Cancel") }
            },
            text = { TimePicker(state = state) },
        )
    }
}

/**
 * A dual-handle range slider (E5). Material3 [RangeSlider] over
 * `[min_value, max_value]`; on release `on_change` fires a
 * [RangeChangeEvent]-shaped payload `{"low": <float>, "high": <float>}`.
 *
 * Documented divergence: Qt uses a custom dual-handle widget; Compose uses the
 * native M3 `RangeSlider`. Both emit `RangeChangeEvent(low, high)` as plain
 * floats (never a tuple).
 */
@Composable
private fun RenderRangeSlider(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val min = (node.props["min_value"] as? Number)?.toFloat() ?: 0f
    val max = (node.props["max_value"] as? Number)?.toFloat() ?: 100f
    val low = (node.props["low"] as? Number)?.toFloat() ?: min
    val high = (node.props["high"] as? Number)?.toFloat() ?: max
    val step = (node.props["step"] as? Number)?.toFloat() ?: 0f
    val steps =
        if (step > 0f && max > min) (((max - min) / step).toInt() - 1).coerceAtLeast(0)
        else 0
    var range by remember(low, high) {
        mutableStateOf(low.coerceIn(min, max)..high.coerceIn(min, max))
    }
    // Neutral + contrast-aware track/thumb colors: honour the node's `Style.color`
    // as the active accent when given, otherwise the theme primary; the inactive
    // track follows the tracked contrast color so the slider stays visible over a
    // dark app surface (NOT the Material lavender default). Mirrors #80.
    val accent = colorOf(style, "color") ?: MaterialTheme.colorScheme.primary
    val inactive = defaultTextColor().copy(alpha = 0.3f)
    RangeSlider(
        value = range,
        onValueChange = { range = it },
        valueRange = min..max,
        steps = steps,
        onValueChangeFinished = {
            handlerToken(node, "on_change")?.let {
                val payload = JSONObject()
                    .put("low", range.start.toDouble())
                    .put("high", range.endInclusive.toDouble())
                onEvent(it, payload.toString())
            }
        },
        colors = SliderDefaults.colors(
            thumbColor = accent,
            activeTrackColor = accent,
            inactiveTrackColor = inactive,
        ),
        modifier = baseModifier(style),
    )
}

/**
 * An autocomplete text field (E5): an [OutlinedTextField] backed by a filterable
 * [DropdownMenu]. Typing fires `on_change` with a [TextChangeEvent] payload; a
 * suggestion tap fires `on_select` with a [SelectEvent] payload `{value, index}`
 * (the index is into the *full* options list, matching the Qt `QCompleter`).
 *
 * Documented divergence: Qt uses a native `QCompleter` popup; Compose builds a
 * filterable `DropdownMenu`. Both emit `TextChangeEvent` + `SelectEvent`.
 */
@Composable
private fun RenderAutocomplete(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    @Suppress("UNCHECKED_CAST")
    val options = (node.props["options"] as? List<*>)?.mapNotNull { it as? String } ?: emptyList()
    val value = node.props["value"] as? String ?: ""
    val placeholder = node.props["placeholder"] as? String ?: ""
    var text by remember(value) { mutableStateOf(value) }
    var expanded by remember { mutableStateOf(false) }
    Box(modifier = baseModifier(style)) {
        OutlinedTextField(
            value = text,
            onValueChange = { typed ->
                text = typed
                expanded = typed.isNotEmpty()
                handlerToken(node, "on_change")?.let {
                    onEvent(it, JSONObject().put("value", typed).toString())
                }
            },
            placeholder = { Text(text = placeholder) },
            singleLine = true,
            leadingIcon = iconSlot(node, "leading_icon", "leadingIconPath"),
            trailingIcon = iconSlot(node, "trailing_icon", "trailingIconPath"),
            modifier = Modifier.fillMaxWidth(),
        )
        val matches = options.filter { it.contains(text, ignoreCase = true) }
        DropdownMenu(
            expanded = expanded && matches.isNotEmpty(),
            onDismissRequest = { expanded = false },
            properties = PopupProperties(focusable = false),
        ) {
            matches.forEach { opt ->
                val index = options.indexOf(opt)
                DropdownMenuItem(
                    text = { Text(text = opt) },
                    onClick = {
                        text = opt
                        expanded = false
                        handlerToken(node, "on_select")?.let {
                            val payload = JSONObject().put("value", opt).put("index", index)
                            onEvent(it, payload.toString())
                        }
                    },
                )
            }
        }
    }
}

/**
 * A segmented PIN / OTP input (E5): a [Row] of `length` single-character
 * [BasicTextField]s with auto-advance via [FocusRequester]. Each keystroke fires
 * `on_change` with a [TextChangeEvent] payload `{"value": <combined>}`; once all
 * cells are filled, `on_complete` fires a [SubmitEvent] payload `{}`.
 *
 * Documented divergence: Qt uses chained `QLineEdit`s with auto tab-advance;
 * Compose uses `BasicTextField` + `FocusRequester`. Both emit `TextChangeEvent`
 * per edit plus `SubmitEvent` when full. The combined value lives in Python
 * (`node.props["value"]`).
 */
@Composable
private fun RenderPinInput(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val length = (node.props["length"] as? Number)?.toInt()?.coerceAtLeast(1) ?: 6
    val secure = node.props["secure"] as? Boolean ?: false
    val value = node.props["value"] as? String ?: ""
    val digits = remember(value, length) {
        mutableStateListOf<String>().apply {
            for (i in 0 until length) add(value.getOrNull(i)?.toString() ?: "")
        }
    }
    val focusRequesters = remember(length) { List(length) { FocusRequester() } }
    // Neutral, contrast-aware cell colors: honour the node's `Style.background`/
    // `color` when given, otherwise the theme's neutral `surfaceVariant` cell +
    // a contrast-tracked glyph color — NOT a hardcoded light box, which over a
    // dark app surface renders near-invisible light-on-light. Mirrors #80.
    val cellBackground = colorOf(style, "background") ?: MaterialTheme.colorScheme.surfaceVariant
    val cellTextColor = colorOf(style, "color") ?: defaultTextColor()
    Row(
        modifier = baseModifier(style),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        for (i in 0 until length) {
            BasicTextField(
                value = digits[i],
                textStyle = TextStyle(color = cellTextColor),
                cursorBrush = SolidColor(cellTextColor),
                onValueChange = { raw ->
                    // Keep only the last typed char; advance/retreat focus.
                    val ch = raw.takeLast(1).filter { it.isLetterOrDigit() }
                    digits[i] = ch
                    if (ch.isNotEmpty() && i < length - 1) {
                        focusRequesters[i + 1].requestFocus()
                    }
                    val combined = digits.joinToString("")
                    handlerToken(node, "on_change")?.let {
                        onEvent(it, JSONObject().put("value", combined).toString())
                    }
                    if (combined.length == length && digits.none { it.isEmpty() }) {
                        handlerToken(node, "on_complete")?.let {
                            onEvent(it, JSONObject().put("values", JSONObject()).toString())
                        }
                    }
                },
                singleLine = true,
                maxLines = 1,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                visualTransformation =
                    if (secure) PasswordVisualTransformation() else VisualTransformation.None,
                modifier = Modifier
                    .width(40.dp)
                    .background(cellBackground, RoundedCornerShape(6.dp))
                    .padding(12.dp)
                    .focusRequester(focusRequesters[i]),
            )
        }
    }
}

/**
 * A masked text input (E5): an [OutlinedTextField] whose displayed text is run
 * through a [MaskTransformation] (e.g. `999.999.999-99` for a CPF). `on_change`
 * fires a [TextChangeEvent] carrying ONLY the raw editable characters (no mask
 * separators), so Python's stored value stays separator-free.
 *
 * Mask grammar (matches the Python `MaskedInput`): `9` = digit, `A` = letter,
 * anything else = a fixed literal separator. The cursor `OffsetMapping` is
 * computed by walking the mask so the caret lands correctly past separators.
 */
@Composable
private fun RenderMaskedInput(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val mask = node.props["mask"] as? String ?: ""
    val value = node.props["value"] as? String ?: ""
    val placeholder = node.props["placeholder"] as? String ?: ""
    val keyboard = when (node.props["keyboard"] as? String) {
        "number" -> KeyboardType.Number
        "phone" -> KeyboardType.Phone
        "email" -> KeyboardType.Email
        else -> KeyboardType.Text
    }
    OutlinedTextField(
        value = value,
        onValueChange = { typed ->
            // Strip anything that is not an allowed editable char and cap at the
            // number of mask slots so the raw value never exceeds the mask.
            val slots = mask.count { it == '9' || it == 'A' }
            val raw = typed.filter { it.isLetterOrDigit() }.let {
                if (slots > 0) it.take(slots) else it
            }
            handlerToken(node, "on_change")?.let {
                onEvent(it, JSONObject().put("value", raw).toString())
            }
        },
        placeholder = { Text(text = placeholder) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        visualTransformation = if (mask.isNotEmpty()) MaskTransformation(mask) else VisualTransformation.None,
        modifier = baseModifier(style),
    )
}

/**
 * Inserts fixed mask separators (`mask` literals) into the displayed text while
 * keeping the underlying value separator-free, with a bidirectional
 * [OffsetMapping] so the caret stays correct. Mask grammar: `9`/`A` are editable
 * slots, every other char is a literal separator.
 */
private class MaskTransformation(private val mask: String) : VisualTransformation {
    override fun filter(text: AnnotatedString): TransformedText {
        val raw = text.text
        val out = StringBuilder()
        // originalToTransformed[i] = transformed offset just before raw char i.
        val originalToTransformed = IntArray(raw.length + 1)
        var rawIndex = 0
        var maskIndex = 0
        while (maskIndex < mask.length && rawIndex < raw.length) {
            val m = mask[maskIndex]
            if (m == '9' || m == 'A') {
                originalToTransformed[rawIndex] = out.length
                out.append(raw[rawIndex])
                rawIndex++
            } else {
                out.append(m)
            }
            maskIndex++
        }
        originalToTransformed[rawIndex] = out.length
        // Any raw overflow (shouldn't happen — capped upstream) appends verbatim.
        while (rawIndex < raw.length) {
            originalToTransformed[rawIndex] = out.length
            out.append(raw[rawIndex])
            rawIndex++
        }
        originalToTransformed[raw.length] = out.length
        val transformed = out.toString()
        val mapping = object : OffsetMapping {
            override fun originalToTransformed(offset: Int): Int =
                originalToTransformed[offset.coerceIn(0, raw.length)]

            override fun transformedToOriginal(offset: Int): Int {
                // Count editable chars at or before the transformed offset.
                var count = 0
                for (i in 0 until raw.length) {
                    if (originalToTransformed[i] < offset) count++ else break
                }
                return count.coerceIn(0, raw.length)
            }
        }
        return TransformedText(AnnotatedString(transformed), mapping)
    }
}

/**
 * A form field (E5): a [Column] stacking an optional label [Text], the field's
 * single child input (rendered recursively), and an error [Text] in red when
 * `error` is non-empty. The error string is computed in Python by the `Form`'s
 * validators and arrives as the `error` prop — there is zero validation logic
 * here.
 */
@Composable
private fun RenderFormField(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val label = node.props["label"] as? String ?: ""
    val error = node.props["error"] as? String ?: ""
    val child = node.children.firstOrNull()
    Column(modifier = baseModifier(style)) {
        if (label.isNotEmpty()) {
            // Field labels carry no IR color → use the tracked contrast color so
            // they stay legible on a dark app background (see Text/Checkbox above).
            Text(
                text = label,
                fontWeight = FontWeight.Medium,
                color = defaultTextColor(),
            )
        }
        if (child != null) RenderNode(child, onEvent)
        if (error.isNotEmpty()) {
            Text(text = error, color = Color.Red, fontSize = 12f.sp)
        }
    }
}

/**
 * A form container (E5): a [Column] of its field children. The submit button is
 * just a child whose `on_submit` token rides the existing event channel; all
 * validation / blocking already ran in Python (`Form.validate`) before any patch
 * reached the device, so the renderer is a faithful leaf.
 */
@Composable
private fun RenderForm(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    Column(
        modifier = baseModifier(style),
        verticalArrangement = verticalArrangement(style),
        horizontalAlignment = horizontalAlignment(style),
    ) {
        node.children.forEach { RenderNode(it, onEvent) }
    }
}

/** A multi-line text field; each edit sends a `TextChangeEvent` to Python. */
@Composable
private fun RenderTextArea(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val rows = (node.props["rows"] as? Number)?.toInt() ?: 3
    OutlinedTextField(
        value = node.props["value"] as? String ?: "",
        onValueChange = { text ->
            handlerToken(node, "on_change")?.let {
                onEvent(it, JSONObject().put("value", text).toString())
            }
        },
        modifier = baseModifier(style),
        placeholder = { Text(node.props["placeholder"] as? String ?: "") },
        minLines = rows.coerceAtLeast(1),
        singleLine = false,
    )
}

/** A labelled boolean switch; toggling sends a `ToggleEvent`. */
@Composable
private fun RenderSwitch(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    Row(
        modifier = baseModifier(style),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Switch(
            checked = node.props["checked"] as? Boolean ?: false,
            onCheckedChange = { checked ->
                handlerToken(node, "on_change")?.let {
                    onEvent(it, JSONObject().put("checked", checked).toString())
                }
            },
        )
        // No per-label color in the IR → tracked contrast color (see RenderCheckbox).
        Text(
            text = node.props["label"] as? String ?: "",
            color = defaultTextColor(),
        )
    }
}

/** A numeric slider over `[min_value, max_value]`; moving it sends a `SlideEvent`. */
@Composable
private fun RenderSlider(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val min = (node.props["min_value"] as? Number)?.toFloat() ?: 0f
    val max = (node.props["max_value"] as? Number)?.toFloat() ?: 100f
    val value = (node.props["value"] as? Number)?.toFloat() ?: min
    val step = (node.props["step"] as? Number)?.toFloat() ?: 0f
    // Compose `steps` counts the divisions *between* endpoints (0 = continuous).
    val steps =
        if (step > 0f && max > min) (((max - min) / step).toInt() - 1).coerceAtLeast(0)
        else 0
    Slider(
        value = value.coerceIn(min, max),
        onValueChange = { v ->
            handlerToken(node, "on_change")?.let {
                onEvent(it, JSONObject().put("value", v.toDouble()).toString())
            }
        },
        modifier = baseModifier(style),
        valueRange = min..max,
        steps = steps,
    )
}

/** A linear progress bar: indeterminate, or determinate over `value` in `[0, 1]`. */
@Composable
private fun RenderProgressBar(node: TempestNode, style: Map<String, Any?>) {
    val indeterminate = node.props["indeterminate"] as? Boolean ?: false
    if (indeterminate) {
        LinearProgressIndicator(modifier = baseModifier(style))
    } else {
        val value = ((node.props["value"] as? Number)?.toFloat() ?: 0f).coerceIn(0f, 1f)
        LinearProgressIndicator(progress = { value }, modifier = baseModifier(style))
    }
}

/** An indeterminate activity spinner, optionally sized to `size` dp. */
@Composable
private fun RenderSpinner(node: TempestNode, style: Map<String, Any?>) {
    val size = (node.props["size"] as? Number)?.toFloat()
    val modifier =
        if (size != null) baseModifier(style).size(size.dp) else baseModifier(style)
    CircularProgressIndicator(modifier = modifier)
}

/** An image loaded from `src` (URL/asset) via Coil, scaled per `fit`. */
@Composable
private fun RenderImage(node: TempestNode, style: Map<String, Any?>) {
    val scale = when (node.props["fit"] as? String) {
        "cover" -> ContentScale.Crop
        "fill" -> ContentScale.FillBounds
        else -> ContentScale.Fit
    }
    AsyncImage(
        model = node.props["src"] as? String,
        contentDescription = node.props["alt"] as? String,
        modifier = sizeModifier(style),
        contentScale = scale,
    )
}

/**
 * An icon node. Resolution order:
 *  1. the curated SVG `d` path inlined by the Python serializer as `iconPath`
 *     (single source of truth — `tempestroid/icons.py`); stroked into a vector.
 *  2. the curated path looked up by `name` in the generated Kotlin port table
 *     (covers `Update` patches where the serializer cannot inline a path because
 *     it has no node type).
 *  3. a bundled Material vector via [iconFor].
 *  4. the name as text (mirrors the Qt simulator's unknown-name fallback).
 */
@Composable
private fun RenderIcon(node: TempestNode, style: Map<String, Any?>) {
    val name = node.props["name"] as? String ?: ""
    val size = (node.props["size"] as? Number)?.toFloat()
    val d = (node.props["iconPath"] as? String) ?: curatedIconPath(name)
    val modifier =
        if (size != null) baseModifier(style).size(size.dp) else baseModifier(style)
    val tint = colorOf(style, "color")
    if (d != null) {
        CuratedIcon(name = name, d = d, tint = tint, modifier = modifier)
        return
    }
    val vector = iconFor(name)
    if (vector != null) {
        Icon(
            imageVector = vector,
            contentDescription = name,
            tint = tint ?: Color.Unspecified,
            modifier = modifier,
        )
    } else {
        // Unknown name: mirror the Qt simulator, which shows the name as text.
        Text(text = name, modifier = baseModifier(style))
    }
}

/**
 * Draw a curated single-path icon from its SVG `d` string. The path is stroked
 * (width ~2, round cap/join) on a 24x24 viewport in `currentColor`
 * ([LocalContentColor]) unless [tint] overrides it, matching the framework's
 * Lucide-style line-icon look on both renderers.
 */
@Composable
private fun CuratedIcon(
    name: String,
    d: String,
    tint: Color?,
    modifier: Modifier = Modifier,
) {
    val resolved = tint ?: LocalContentColor.current
    val vector = remember(d, resolved) { strokedVector(d, resolved) }
    Icon(
        imageVector = vector,
        contentDescription = name,
        tint = Color.Unspecified, // color baked into the stroke below
        modifier = modifier,
    )
}

/**
 * Build a 24x24 [ImageVector] whose single stroked path is parsed from an SVG
 * `d` string. Stroke width 2, round cap/join, no fill — the framework's curated
 * icons are stroke-based line icons. The [color] is baked into the stroke brush.
 */
private fun strokedVector(d: String, color: Color): ImageVector {
    val nodes = PathParser().parsePathString(d).toNodes()
    return ImageVector.Builder(
        name = "curated",
        defaultWidth = 24.dp,
        defaultHeight = 24.dp,
        viewportWidth = 24f,
        viewportHeight = 24f,
    ).addPath(
        pathData = nodes,
        fill = null,
        stroke = SolidColor(color),
        strokeLineWidth = 2f,
        strokeLineCap = StrokeCap.Round,
        strokeLineJoin = StrokeJoin.Round,
    ).build()
}

/** Map a Material-Icons name to a bundled vector, or `null` to fall back to text. */
private fun iconFor(name: String): ImageVector? = when (name.lowercase()) {
    "add" -> Icons.Filled.Add
    "back", "arrow_back" -> Icons.Filled.ArrowBack
    "check" -> Icons.Filled.Check
    "close" -> Icons.Filled.Close
    "delete" -> Icons.Filled.Delete
    "done" -> Icons.Filled.Done
    "edit" -> Icons.Filled.Edit
    "email" -> Icons.Filled.Email
    "favorite" -> Icons.Filled.Favorite
    "home" -> Icons.Filled.Home
    "info" -> Icons.Filled.Info
    "lock" -> Icons.Filled.Lock
    "menu" -> Icons.Filled.Menu
    "notifications" -> Icons.Filled.Notifications
    "person" -> Icons.Filled.Person
    "play", "play_arrow" -> Icons.Filled.PlayArrow
    "search" -> Icons.Filled.Search
    "settings" -> Icons.Filled.Settings
    "share" -> Icons.Filled.Share
    "cart", "shopping_cart" -> Icons.Filled.ShoppingCart
    "star" -> Icons.Filled.Star
    "warning" -> Icons.Filled.Warning
    else -> null
}

/**
 * The curated icon `name -> SVG d` path table, a port of
 * `tempestroid/icons.py:ICON_PATHS`. The Python serializer normally inlines the
 * resolved path as the node's `iconPath` prop (the single source of truth), so
 * this table is only consulted when no path crosses the bridge — chiefly an
 * `Update` patch that changes an icon name but, lacking the node type, cannot
 * inline a path. Keep it in sync with `icons.py`.
 *
 * Regenerate (paste the output into the `when` body below):
 * ```
 * uv run python -c "
 * from tempestroid.icons import ICON_PATHS
 * for name, d in ICON_PATHS.items():
 *     esc = d.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))
 *     print(f'    \"{name}\" -> \"{esc}\"')
 * "
 * ```
 */
private fun curatedIconPath(name: String): String? = when (name) {
    "eye" -> "M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0 M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z"
    "eye-off" -> "M10.733 5.076 a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49 M14.084 14.158 a3 3 0 0 1-4.242-4.242 M17.479 17.499 a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143 M2 2 l20 20"
    "lock" -> "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 1-2-2 Z M7 11 V7 a5 5 0 0 1 10 0 v4"
    "unlock" -> "M5 11 a2 2 0 0 1 2-2 h10 a2 2 0 0 1 2 2 v8 a2 2 0 0 1-2 2 H7 a2 2 0 0 1-2-2 Z M7 11 V7 a5 5 0 0 1 9.9-1"
    "search" -> "M21 21 l-4.34-4.34 M11 19 a8 8 0 1 0 0-16 8 8 0 0 0 0 16 Z"
    "x" -> "M18 6 6 18 M6 6 l12 12"
    "check" -> "M20 6 9 17 l-5-5"
    "chevron-down" -> "M6 9 l6 6 6-6"
    "chevron-up" -> "M18 15 l-6-6-6 6"
    "chevron-left" -> "M15 18 l-6-6 6-6"
    "chevron-right" -> "M9 18 l6-6-6-6"
    "arrow-left" -> "M19 12 H5 M12 19 l-7-7 7-7"
    "arrow-right" -> "M5 12 h14 M12 5 l7 7-7 7"
    "plus" -> "M5 12 h14 M12 5 v14"
    "minus" -> "M5 12 h14"
    "user" -> "M19 21 v-2 a4 4 0 0 0-4-4 H9 a4 4 0 0 0-4 4 v2 M12 11 a4 4 0 1 0 0-8 4 4 0 0 0 0 8 Z"
    "mail" -> "M22 7 l-8.991 5.727 a2 2 0 0 1-2.018 0 L2 7 M4 4 h16 c1.1 0 2 .9 2 2 v12 c0 1.1-.9 2-2 2 H4 c-1.1 0-2-.9-2-2 V6 c0-1.1.9-2 2-2 Z"
    "phone" -> "M13.832 16.568 a1 1 0 0 0 1.213-.303 l.355-.465 A2 2 0 0 1 17 15 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1-2 2 A18 18 0 0 1 2 4 a2 2 0 0 1 2-2 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1-.8 1.6 l-.468.351 a1 1 0 0 0-.292 1.233 a14 14 0 0 0 6.06 6.0 Z"
    "calendar" -> "M8 2 v4 M16 2 v4 M3 10 h18 M5 4 h14 a2 2 0 0 1 2 2 v14 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 V6 a2 2 0 0 1 2-2 Z"
    "clock" -> "M12 6 v6 l4 2 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z"
    "trash" -> "M3 6 h18 M19 6 v14 c0 1-1 2-2 2 H7 c-1 0-2-1-2-2 V6 M8 6 V4 c0-1 1-2 2-2 h4 c1 0 2 1 2 2 v2 M10 11 v6 M14 11 v6"
    "menu" -> "M4 12 h16 M4 6 h16 M4 18 h16"
    "home" -> "M3 9 l9-7 9 7 v11 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 z M9 22 V12 h6 v10"
    "settings" -> "M12.22 2 h-.44 a2 2 0 0 0-2 2 v.18 a2 2 0 0 1-1 1.73 l-.43.25 a2 2 0 0 1-2 0 l-.15-.08 a2 2 0 0 0-2.73.73 l-.22.38 a2 2 0 0 0 .73 2.73 l.15.1 a2 2 0 0 1 1 1.72 v.51 a2 2 0 0 1-1 1.74 l-.15.09 a2 2 0 0 0-.73 2.73 l.22.38 a2 2 0 0 0 2.73.73 l.15-.08 a2 2 0 0 1 2 0 l.43.25 a2 2 0 0 1 1 1.73 V20 a2 2 0 0 0 2 2 h.44 a2 2 0 0 0 2-2 v-.18 a2 2 0 0 1 1-1.73 l.43-.25 a2 2 0 0 1 2 0 l.15.08 a2 2 0 0 0 2.73-.73 l.22-.39 a2 2 0 0 0-.73-2.73 l-.15-.08 a2 2 0 0 1-1-1.74 v-.5 a2 2 0 0 1 1-1.74 l.15-.09 a2 2 0 0 0 .73-2.73 l-.22-.38 a2 2 0 0 0-2.73-.73 l-.15.08 a2 2 0 0 1-2 0 l-.43-.25 a2 2 0 0 1-1-1.73 V4 a2 2 0 0 0-2-2 Z M15 12 a3 3 0 1 1-6 0 3 3 0 0 1 6 0 Z"
    "star" -> "M11.525 2.295 a.53.53 0 0 1 .95 0 l2.31 4.679 a2.123 2.123 0 0 0 1.595 1.16 l5.166.756 a.53.53 0 0 1 .294.904 l-3.736 3.638 a2.123 2.123 0 0 0-.611 1.878 l.882 5.14 a.53.53 0 0 1-.771.56 l-4.618-2.428 a2.122 2.122 0 0 0-1.973 0 L6.396 21.01 a.53.53 0 0 1-.77-.56 l.881-5.139 a2.122 2.122 0 0 0-.611-1.879 L2.16 9.795 a.53.53 0 0 1 .294-.906 l5.165-.755 a2.122 2.122 0 0 0 1.597-1.16 Z"
    "heart" -> "M2 9.5 a5.5 5.5 0 0 1 9.591-3.676 .56.56 0 0 0 .818 0 A5.49 5.49 0 0 1 22 9.5 c0 2.29-1.5 4-3 5.5 l-5.492 5.313 a2 2 0 0 1-3.016 0 L5 14.5 c-1.5-1.5-3-3.2-3-5 Z"
    "bell" -> "M10.268 21 a2 2 0 0 0 3.464 0 M3.262 15.326 A1 1 0 0 0 4 17 h16 a1 1 0 0 0 .74-1.673 C19.41 13.956 18 12.499 18 8 A6 6 0 0 0 6 8 c0 4.499-1.411 5.956-2.738 7.326 Z"
    "info" -> "M12 16 v-4 M12 8 h.01 M12 2 a10 10 0 1 0 0 20 10 10 0 0 0 0-20 Z"
    else -> null
}

/**
 * Resolve a leading/trailing icon slot for a text field. Reads the inlined
 * `*Path` prop (`leadingIconPath` / `trailingIconPath`), falling back to the
 * curated name table, and returns a composable drawing the stroked icon — or
 * `null` when neither the path nor the name resolves (no slot rendered).
 */
private fun iconSlot(node: TempestNode, nameProp: String, pathProp: String): (@Composable () -> Unit)? {
    val name = node.props[nameProp] as? String ?: return null
    val d = (node.props[pathProp] as? String) ?: curatedIconPath(name) ?: return null
    return { CuratedIcon(name = name, d = d, tint = null) }
}

/** A scrollable column (or row when `horizontal`) of children. */
@Composable
private fun RenderScrollView(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val horizontal = node.props["horizontal"] as? Boolean ?: false
    if (horizontal) {
        Row(modifier = baseModifier(style).horizontalScroll(rememberScrollState())) {
            node.children.forEach { RenderNode(it, onEvent) }
        }
    } else {
        Column(modifier = baseModifier(style).verticalScroll(rememberScrollState())) {
            node.children.forEach { RenderNode(it, onEvent) }
        }
    }
}

/**
 * A virtualized list — the Kotlin counterpart of the Qt `LazyColumn`/`LazyRow`.
 *
 * The serialized node carries `props["item_count"]` (the *full* logical length)
 * but only the materialized window in `node.children` (each keyed by its absolute
 * index). Compose iterates the materialized window natively via [LazyColumn]/
 * [LazyRow]; Python widens/slides the window in response to the events emitted
 * here:
 *  - `on_scroll` → [ScrollEvent] `{offset, direction}` on every scroll-offset tick;
 *  - `on_refresh` → [RefreshEvent] `{}` when the [PullToRefreshBox] gesture fires;
 *  - `on_end_reached` → [EndReachedEvent] `{}` when the last visible item's
 *    absolute index crosses `end_reached_threshold` of `item_count` (NOT of the
 *    partial window).
 *
 * @param horizontal render a [LazyRow] (`direction="horizontal"`) instead of a
 *   vertical [LazyColumn].
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderLazyList(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
    horizontal: Boolean,
) {
    val listState = rememberLazyListState()
    val refreshing = node.props["refreshing"] as? Boolean ?: false
    val direction = if (horizontal) "horizontal" else "vertical"

    ReportScroll(listState, direction) { offset ->
        handlerToken(node, "on_scroll")?.let {
            onEvent(it, JSONObject().put("offset", offset.toDouble()).put("direction", direction).toString())
        }
    }
    ReportEndReached(listState, itemCountOf(node), thresholdOf(node)) {
        handlerToken(node, "on_end_reached")?.let { onEvent(it, "{}") }
    }

    // Snapshot the window once: itemsIndexed reads `children` eagerly, and a
    // window slide that mutates `node.children` re-runs this composable, so the
    // LazyColumn/LazyRow content block rebuilds with the new materialized window.
    val children = node.children.toList()
    val onRefresh = { handlerToken(node, "on_refresh")?.let { onEvent(it, "{}") }; Unit }
    PullToRefreshBox(
        isRefreshing = refreshing,
        onRefresh = onRefresh,
        modifier = baseModifier(style),
    ) {
        if (horizontal) {
            LazyRow(state = listState, modifier = Modifier.fillMaxSize()) {
                itemsIndexed(
                    items = children,
                    key = { i, child -> child.key ?: i.toString() },
                ) { _, child -> RenderNode(child, onEvent) }
            }
        } else {
            LazyColumn(state = listState, modifier = Modifier.fillMaxSize()) {
                itemsIndexed(
                    items = children,
                    key = { i, child -> child.key ?: i.toString() },
                ) { _, child -> RenderNode(child, onEvent) }
            }
        }
    }
}

/**
 * A virtualized grid — the Kotlin counterpart of the Qt `LazyGrid`.
 *
 * `props["columns"]` fixes the column count; the materialized window flows across
 * the rows. Like [RenderLazyList], the full length is `props["item_count"]` and
 * `on_scroll`/`on_end_reached` drive the Python-side window.
 */
@Composable
private fun RenderLazyGrid(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val gridState = rememberLazyGridState()
    val columns = (node.props["columns"] as? Number)?.toInt() ?: 2

    ReportGridScroll(gridState) { offset ->
        handlerToken(node, "on_scroll")?.let {
            onEvent(it, JSONObject().put("offset", offset.toDouble()).put("direction", "vertical").toString())
        }
    }
    ReportGridEndReached(gridState, itemCountOf(node), thresholdOf(node)) {
        handlerToken(node, "on_end_reached")?.let { onEvent(it, "{}") }
    }

    val children = node.children.toList()
    LazyVerticalGrid(
        columns = GridCells.Fixed(columns.coerceAtLeast(1)),
        state = gridState,
        modifier = baseModifier(style),
    ) {
        gridItemsIndexed(
            items = children,
            key = { i, child -> child.key ?: i.toString() },
        ) { _, child -> RenderNode(child, onEvent) }
    }
}

/**
 * A sectioned list with pinned headers — the Kotlin counterpart of the Qt
 * `SectionList`. Compose pins each section header natively via `stickyHeader {}`.
 *
 * The serialized window is a flat, already-materialized child list: each child
 * carries the reconciler `key` the IR core assigned (`sec:<title>:header` for a
 * section header, `sec:<title>:<index>` for a row). A child whose key matches
 * [isSectionHeaderKey] is pinned with `stickyHeader {}`; everything else is a
 * plain `item {}`. `on_scroll`/`on_end_reached` mirror [RenderLazyList], using
 * `props["item_count"]` as the full logical length.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
private fun RenderSectionList(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val listState = rememberLazyListState()

    ReportScroll(listState, "vertical") { offset ->
        handlerToken(node, "on_scroll")?.let {
            onEvent(it, JSONObject().put("offset", offset.toDouble()).put("direction", "vertical").toString())
        }
    }
    ReportEndReached(listState, itemCountOf(node), thresholdOf(node)) {
        handlerToken(node, "on_end_reached")?.let { onEvent(it, "{}") }
    }

    // Snapshot the live child list once per recomposition: each `key`/`item`
    // lambda below captures `i` (not the SnapshotStateList directly) so a window
    // slide that mutates `node.children` recomposes the LazyColumn content block.
    val children = node.children.toList()
    LazyColumn(state = listState, modifier = baseModifier(style)) {
        children.forEachIndexed { i, child ->
            val itemKey = child.key ?: i.toString()
            if (isSectionHeaderKey(child.key)) {
                stickyHeader(key = itemKey) { RenderNode(child, onEvent) }
            } else {
                item(key = itemKey) { RenderNode(child, onEvent) }
            }
        }
    }
}

/**
 * Whether a materialized child is a pinned section header.
 *
 * The IR core keys section children `sec:<title>:header` (header) and
 * `sec:<title>:<index>` (row); only the header form ends in `:header`.
 *
 * @param key the child's reconciler key (may be null for an unkeyed child).
 * @return true when [key] denotes a section header.
 */
private fun isSectionHeaderKey(key: String?): Boolean =
    key != null && key.startsWith("sec:") && key.endsWith(":header")

/**
 * A standalone pull-to-refresh container — the Kotlin counterpart of the Qt
 * `RefreshControl`. `props["refreshing"]` drives the [PullToRefreshBox] spinner;
 * the gesture emits `on_refresh` → [RefreshEvent]. Its child (if any) scrolls
 * inside.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderRefreshControl(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val refreshing = node.props["refreshing"] as? Boolean ?: false
    val onRefresh = { handlerToken(node, "on_refresh")?.let { onEvent(it, "{}") }; Unit }
    PullToRefreshBox(
        isRefreshing = refreshing,
        onRefresh = onRefresh,
        modifier = baseModifier(style),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            node.children.forEach { RenderNode(it, onEvent) }
        }
    }
}

/** The full logical item count of a list node (`item_count`), defaulting to the
 *  materialized window size when absent. */
private fun itemCountOf(node: TempestNode): Int =
    (node.props["item_count"] as? Number)?.toInt() ?: node.children.size

/** The `[0,1]` fraction of the scroll past which `on_end_reached` fires. */
private fun thresholdOf(node: TempestNode): Float =
    (node.props["end_reached_threshold"] as? Number)?.toFloat() ?: 0.8f

/** Emit [report] (with the live scroll offset) on every scroll-offset change. */
@Composable
private fun ReportScroll(
    listState: LazyListState,
    @Suppress("UNUSED_PARAMETER") direction: String,
    report: (Int) -> Unit,
) {
    LaunchedEffect(listState) {
        snapshotFlow { listState.firstVisibleItemScrollOffset }
            .collectLatest { offset -> report(offset) }
    }
}

/** Emit [report] (with the live scroll offset) on every grid scroll-offset change. */
@Composable
private fun ReportGridScroll(gridState: LazyGridState, report: (Int) -> Unit) {
    LaunchedEffect(gridState) {
        snapshotFlow { gridState.firstVisibleItemScrollOffset }
            .collectLatest { offset -> report(offset) }
    }
}

/**
 * Fire [report] once each time the last visible item's *absolute* index crosses
 * [threshold] of [itemCount] — the denominator is the full logical length, not
 * the materialized window, so paging triggers at the true list end.
 */
@Composable
private fun ReportEndReached(
    listState: LazyListState,
    itemCount: Int,
    threshold: Float,
    report: () -> Unit,
) {
    val isEndReached by remember(itemCount, threshold) {
        derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()
            last != null && itemCount > 0 &&
                (last.index + 1).toFloat() / itemCount >= threshold
        }
    }
    LaunchedEffect(isEndReached) { if (isEndReached) report() }
}

/** Grid variant of [ReportEndReached]. */
@Composable
private fun ReportGridEndReached(
    gridState: LazyGridState,
    itemCount: Int,
    threshold: Float,
    report: () -> Unit,
) {
    val isEndReached by remember(itemCount, threshold) {
        derivedStateOf {
            val last = gridState.layoutInfo.visibleItemsInfo.lastOrNull()
            last != null && itemCount > 0 &&
                (last.index + 1).toFloat() / itemCount >= threshold
        }
    }
    LaunchedEffect(isEndReached) { if (isEndReached) report() }
}

/**
 * A transparent box that recognizes gestures over its child and routes them to
 * Python — the Kotlin counterpart of the Qt ``_GestureWidget``.
 *
 * Taps, double-taps and long-presses come from [detectTapGestures]; swipes are
 * the net travel of a [detectDragGestures] sequence, classified by dominant axis
 * on drag end. Each fires the matching handler token with a JSON payload.
 */
@Composable
private fun RenderGestureDetector(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val mod = baseModifier(style)
        .pointerInput(node) {
            detectTapGestures(
                onTap = { offset ->
                    handlerToken(node, "on_tap")?.let { onEvent(it, pointJson(offset)) }
                },
                onDoubleTap = { offset ->
                    handlerToken(node, "on_double_tap")?.let { onEvent(it, pointJson(offset)) }
                },
                onLongPress = { offset ->
                    handlerToken(node, "on_long_press")?.let { onEvent(it, pointJson(offset)) }
                },
            )
        }
        .pointerInput(node) {
            var dx = 0f
            var dy = 0f
            detectDragGestures(
                onDragStart = { dx = 0f; dy = 0f },
                onDrag = { change, amount -> dx += amount.x; dy += amount.y; change.consume() },
                onDragEnd = {
                    if (maxOf(abs(dx), abs(dy)) >= SWIPE_THRESHOLD_PX) {
                        handlerToken(node, "on_swipe")?.let {
                            onEvent(it, swipeJson(dx, dy))
                        }
                    }
                },
            )
        }
    Box(modifier = mod) { node.children.forEach { RenderNode(it, onEvent) } }
}

// ---------------------------------------------------------------------------
// E4 — advanced gestures (PanHandler / ScaleHandler / DoubleTapHandler /
// Draggable / DragTarget / Dismissible / ReorderableList / InteractiveViewer).
//
// Each is the Kotlin leaf of the matching Python gesture widget. Handler props
// are read by the path token (`handlerToken`), and the gesture result is
// reported back over the existing event channel via [onEvent] as a JSON payload
// that `parse_event` validates into the matching frozen Event. No reserved
// bridge token and no JNI change — these are plain widget-handler events.
// ---------------------------------------------------------------------------

/**
 * A pan recognizer over its single child — the Kotlin leaf of the Python
 * `PanHandler`. A [detectDragGestures] sequence accumulates the net delta while a
 * [VelocityTracker] records pointer positions; on drag-end it fires `on_pan` with
 * the [PanEvent]-shaped JSON `{dx, dy, vx, vy}` (vx/vy are px/s at release).
 */
@Composable
private fun RenderPanHandler(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val mod = baseModifier(style).pointerInput(node) {
        var dx = 0f
        var dy = 0f
        val tracker = VelocityTracker()
        detectDragGestures(
            onDragStart = { dx = 0f; dy = 0f; tracker.resetTracking() },
            onDrag = { change, amount ->
                dx += amount.x
                dy += amount.y
                tracker.addPosition(change.uptimeMillis, change.position)
                change.consume()
            },
            onDragEnd = {
                val velocity = tracker.calculateVelocity()
                handlerToken(node, "on_pan")?.let {
                    onEvent(it, panJson(dx, dy, velocity.x, velocity.y))
                }
            },
        )
    }
    Box(modifier = mod) { node.children.forEach { RenderNode(it, onEvent) } }
}

/**
 * A pinch/rotation recognizer over its single child — the Kotlin leaf of the
 * Python `ScaleHandler`. [detectTransformGestures] reports the multitouch pinch
 * (true multitouch, unlike the Qt desktop scroll fallback): each gesture step
 * fires `on_scale` with the [ScaleEvent]-shaped JSON `{scale, focus_x, focus_y,
 * rotation}` (focus is two top-level floats, never a tuple). A separate
 * [detectTapGestures] reports `on_double_tap` as a [TapEvent] `{x, y}`.
 */
@Composable
private fun RenderScaleHandler(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val mod = baseModifier(style)
        .pointerInput(node) {
            // Accumulate scale across the gesture so the reported value is the
            // running pinch factor, not the per-frame delta.
            var scale = 1f
            var rotation = 0f
            detectTransformGestures(
                onGesture = { centroid, _, zoomChange, rotationChange ->
                    scale *= zoomChange
                    rotation += rotationChange
                    handlerToken(node, "on_scale")?.let {
                        onEvent(it, scaleJson(scale, centroid.x, centroid.y, rotation))
                    }
                },
            )
        }
        .pointerInput(node) {
            detectTapGestures(
                onDoubleTap = { offset ->
                    handlerToken(node, "on_double_tap")?.let { onEvent(it, pointJson(offset)) }
                },
            )
        }
    Box(modifier = mod) { node.children.forEach { RenderNode(it, onEvent) } }
}

/**
 * A double-tap recognizer over its single child — the Kotlin leaf of the Python
 * `DoubleTapHandler`. Fires `on_double_tap` with a [TapEvent] `{x, y}`.
 */
@Composable
private fun RenderDoubleTapHandler(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val mod = baseModifier(style).pointerInput(node) {
        detectTapGestures(
            onDoubleTap = { offset ->
                handlerToken(node, "on_double_tap")?.let { onEvent(it, pointJson(offset)) }
            },
        )
    }
    Box(modifier = mod) { node.children.forEach { RenderNode(it, onEvent) } }
}

/**
 * A long-press-then-drag draggable — the Kotlin leaf of the Python `Draggable`.
 *
 * Compose's Material3 has no stable native cross-widget drag-and-drop, so this is
 * the documented divergence from the Qt `QDrag`/`QMimeData` OS drag: a
 * [detectDragGesturesAfterLongPress] tracks a manual `offset` applied via
 * `Modifier.offset` for visual feedback. On release it fires `on_drag` with the
 * [DragEvent]-shaped JSON `{data, x, y}` (data = the `drag_data` prop, x/y = the
 * final drag offset) and snaps the child back. A `DragTarget` hit is resolved by
 * the Python handler from `drag_data`/position (no native drop routing).
 */
@Composable
private fun RenderDraggable(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val dragData = node.props["drag_data"] as? String ?: ""
    var offset by remember(node) { mutableStateOf(Offset.Zero) }
    val mod = baseModifier(style)
        .offset { IntOffset(offset.x.roundToInt(), offset.y.roundToInt()) }
        .pointerInput(node) {
            detectDragGesturesAfterLongPress(
                onDrag = { change, amount ->
                    offset += amount
                    change.consume()
                },
                onDragEnd = {
                    handlerToken(node, "on_drag")?.let {
                        onEvent(it, dragJson(dragData, offset.x, offset.y))
                    }
                    offset = Offset.Zero
                },
                onDragCancel = { offset = Offset.Zero },
            )
        }
    Box(modifier = mod) { node.children.forEach { RenderNode(it, onEvent) } }
}

/**
 * A drop target — the Kotlin leaf of the Python `DragTarget`. Material3 has no
 * stable native cross-widget drop routing, so this renders its child plainly and
 * fires `on_drop` with a [DragEvent] `{data, x, y}` only on a direct
 * [detectDragGesturesAfterLongPress] release inside its own bounds (a self-drop).
 * Cross-widget drop matching is owned by the Python handler via `drag_data` and
 * position — the documented Qt (native QDrop) divergence.
 */
@Composable
private fun RenderDragTarget(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val mod = baseModifier(style).pointerInput(node) {
        detectDragGesturesAfterLongPress(
            onDragEnd = { },
            onDrag = { change, _ ->
                change.consume()
                handlerToken(node, "on_drop")?.let {
                    onEvent(it, dragJson("", change.position.x, change.position.y))
                }
            },
        )
    }
    Box(modifier = mod) { node.children.forEach { RenderNode(it, onEvent) } }
}

/**
 * A swipe-to-dismiss container — the Kotlin leaf of the Python `Dismissible`. Uses
 * the Material3 [SwipeToDismissBox]: when the user swipes the child past the
 * threshold in the allowed direction, `confirmValueChange` fires `on_dismiss` with
 * the [DismissEvent]-shaped JSON `{overlay_id: null}` (reused unchanged from E2),
 * letting the Python handler drop the item from state (the A2 keyed diff then
 * emits the Remove). The `direction` prop (`left`/`right`/`up`/`down`) restricts
 * which swipe directions are enabled (M3 `SwipeToDismissBox` only supports the
 * horizontal start/end directions — vertical falls back to both horizontal, a
 * documented divergence from the Qt `_DismissibleWidget`).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RenderDismissible(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val direction = node.props["direction"] as? String ?: "left"
    val state = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            if (value != SwipeToDismissBoxValue.Settled) {
                handlerToken(node, "on_dismiss")?.let {
                    onEvent(it, JSONObject().put("overlay_id", JSONObject.NULL).toString())
                }
                true
            } else {
                false
            }
        },
    )
    // `direction` left/right map to StartToEnd/EndToStart; up/down have no M3
    // vertical analogue, so they enable both horizontal directions.
    val enableStartToEnd = direction == "right" || direction == "up" || direction == "down"
    val enableEndToStart = direction == "left" || direction == "up" || direction == "down"
    SwipeToDismissBox(
        state = state,
        enableDismissFromStartToEnd = enableStartToEnd,
        enableDismissFromEndToStart = enableEndToStart,
        backgroundContent = {
            Box(modifier = Modifier.fillMaxSize().background(Color(0x33FF0000)))
        },
        modifier = baseModifier(style),
    ) {
        node.children.forEach { RenderNode(it, onEvent) }
    }
}

/**
 * A drag-to-reorder list — the Kotlin leaf of the Python `ReorderableList`.
 *
 * Without a reorder library (the project forbids unjustified deps), this is the
 * DIY divergence from the Qt `QDrag`-based reorder: a [Column] iterating
 * `node.children`, each item wrapped in a [detectDragGesturesAfterLongPress] that
 * tracks the dragged index and a vertical offset; the destination index is
 * `from + round(offset.y / itemHeight)`. On release it fires `on_reorder` with the
 * [ReorderEvent]-shaped JSON `{from_index, to_index}` (the Python handler mutates
 * state; the A2 keyed diff emits the Reorder patch). There is no smooth item
 * animation during the drag — a documented Qt×Compose divergence.
 */
@Composable
private fun RenderReorderableList(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val children = node.children.toList()
    var dragIndex by remember(node) { mutableIntStateOf(-1) }
    var dragOffset by remember(node) { mutableFloatStateOf(0f) }
    var itemHeight by remember(node) { mutableIntStateOf(1) }
    Column(modifier = baseModifier(style)) {
        children.forEachIndexed { index, child ->
            val isDragging = index == dragIndex
            val itemMod = Modifier
                .fillMaxWidth()
                .onSizeChanged { if (it.height > 0) itemHeight = it.height }
                .offset { IntOffset(0, if (isDragging) dragOffset.roundToInt() else 0) }
                .pointerInput(node, index) {
                    detectDragGesturesAfterLongPress(
                        onDragStart = { dragIndex = index; dragOffset = 0f },
                        onDrag = { change, amount -> dragOffset += amount.y; change.consume() },
                        onDragEnd = {
                            val delta = (dragOffset / itemHeight.coerceAtLeast(1)).roundToInt()
                            val to = (index + delta).coerceIn(0, children.size - 1)
                            if (to != index) {
                                handlerToken(node, "on_reorder")?.let {
                                    onEvent(it, reorderJson(index, to))
                                }
                            }
                            dragIndex = -1
                            dragOffset = 0f
                        },
                        onDragCancel = { dragIndex = -1; dragOffset = 0f },
                    )
                }
            Box(modifier = itemMod) { RenderNode(child, onEvent) }
        }
    }
}

/**
 * A pan+zoom viewport — the Kotlin leaf of the Python `InteractiveViewer`. A
 * [detectTransformGestures] drives a `scale` (clamped to `min_scale`/`max_scale`)
 * and a `translation`, both applied via `Modifier.graphicsLayer` (the divergence
 * from the Qt `QGraphicsView`/`QTransform`). At the end of each gesture it fires
 * `on_interaction` with the [ScaleEvent]-shaped JSON `{scale, focus_x, focus_y,
 * rotation}` so the Python handler can persist the zoom level.
 */
@Composable
private fun RenderInteractiveViewer(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val minScale = (node.props["min_scale"] as? Number)?.toFloat() ?: 0.5f
    val maxScale = (node.props["max_scale"] as? Number)?.toFloat() ?: 4.0f
    var scale by remember(node) { mutableFloatStateOf(1f) }
    var translation by remember(node) { mutableStateOf(Offset.Zero) }
    var focus by remember(node) { mutableStateOf(Offset.Zero) }
    val mod = baseModifier(style)
        .graphicsLayer {
            scaleX = scale
            scaleY = scale
            translationX = translation.x
            translationY = translation.y
        }
        .pointerInput(node) {
            detectTransformGestures(
                onGesture = { centroid, pan, zoomChange, _ ->
                    scale = (scale * zoomChange).coerceIn(minScale, maxScale)
                    translation += pan
                    focus = centroid
                },
            )
        }
        .pointerInput(node) {
            // Report the settled transform at the end of each gesture sequence.
            detectDragGestures(
                onDrag = { change, _ -> change.consume() },
                onDragEnd = {
                    handlerToken(node, "on_interaction")?.let {
                        onEvent(it, scaleJson(scale, focus.x, focus.y, 0f))
                    }
                },
            )
        }
    Box(modifier = mod) { node.children.forEach { RenderNode(it, onEvent) } }
}

/** [PanEvent] payload `{dx, dy, vx, vy}` (velocity px/s at release). */
private fun panJson(dx: Float, dy: Float, vx: Float, vy: Float): String =
    JSONObject()
        .put("dx", dx.toDouble())
        .put("dy", dy.toDouble())
        .put("vx", vx.toDouble())
        .put("vy", vy.toDouble())
        .toString()

/** [ScaleEvent] payload `{scale, focus_x, focus_y, rotation}` (focus = two floats). */
private fun scaleJson(scale: Float, fx: Float, fy: Float, rot: Float): String =
    JSONObject()
        .put("scale", scale.toDouble())
        .put("focus_x", fx.toDouble())
        .put("focus_y", fy.toDouble())
        .put("rotation", rot.toDouble())
        .toString()

/** [DragEvent] payload `{data, x, y}` for a Draggable/DragTarget. */
private fun dragJson(data: String, x: Float, y: Float): String =
    JSONObject()
        .put("data", data)
        .put("x", x.toDouble())
        .put("y", y.toDouble())
        .toString()

/** [ReorderEvent] payload `{from_index, to_index}`. */
private fun reorderJson(from: Int, to: Int): String =
    JSONObject()
        .put("from_index", from)
        .put("to_index", to)
        .toString()

/** Logical-pixel travel past which a drag counts as a swipe (mirrors the Qt threshold). */
private const val SWIPE_THRESHOLD_PX = 40f

private fun pointJson(offset: Offset): String =
    JSONObject().put("x", offset.x.toDouble()).put("y", offset.y.toDouble()).toString()

private fun swipeJson(dx: Float, dy: Float): String {
    val direction = if (abs(dx) >= abs(dy)) {
        if (dx > 0) "right" else "left"
    } else {
        if (dy > 0) "down" else "up"
    }
    return JSONObject()
        .put("direction", direction)
        .put("dx", dx.toDouble())
        .put("dy", dy.toDouble())
        .toString()
}

/** Two-axis [Alignment] for a Stack's non-positioned children, from `stackAlign`. */
internal fun stackAlignmentOf(style: Map<String, Any?>): Alignment = when (style["stackAlign"]) {
    "topStart" -> Alignment.TopStart
    "topCenter" -> Alignment.TopCenter
    "topEnd" -> Alignment.TopEnd
    "centerStart" -> Alignment.CenterStart
    "center" -> Alignment.Center
    "centerEnd" -> Alignment.CenterEnd
    "bottomStart" -> Alignment.BottomStart
    "bottomCenter" -> Alignment.BottomCenter
    "bottomEnd" -> Alignment.BottomEnd
    else -> Alignment.TopStart
}

/** Modifier for an absolutely-positioned Stack child: fill the stack, inset by edges. */
private fun BoxScope.absoluteModifier(style: Map<String, Any?>): Modifier {
    fun inset(key: String) = (style[key] as? Number)?.toFloat()?.dp ?: 0.dp
    return Modifier
        .matchParentSize()
        .padding(start = inset("left"), top = inset("top"), end = inset("right"), bottom = inset("bottom"))
}

@Suppress("UNCHECKED_CAST")
internal fun styleOf(node: TempestNode): Map<String, Any?> =
    node.props["style"] as? Map<String, Any?> ?: emptyMap()

internal fun handlerToken(node: TempestNode, prop: String): String? {
    @Suppress("UNCHECKED_CAST")
    val ref = node.props[prop] as? Map<String, Any?> ?: return null
    return ref["\$handler"] as? String
}

/** Size-only Modifier (width/height) — used by widgets that paint their own
 *  background, like [Button], so the Style background is not drawn twice. */
private fun sizeModifier(style: Map<String, Any?>): Modifier {
    var m: Modifier = Modifier
    (style["width"] as? Number)?.let { m = m.width(it.toFloat().dp) }
    (style["height"] as? Number)?.let { m = m.height(it.toFloat().dp) }
    return m
}

/**
 * Size + background (no padding) — used by hosts like [RenderTabView] that must
 * place a flush-to-edge child (the tab strip) before applying the Style padding,
 * which is moved onto the content slot via [paddingModifier].
 */
private fun backgroundSizeModifier(style: Map<String, Any?>): Modifier {
    var m: Modifier = Modifier
    (style["width"] as? Number)?.let { m = m.width(it.toFloat().dp) }
    (style["height"] as? Number)?.let { m = m.height(it.toFloat().dp) }
    colorOf(style, "background")?.let { bg ->
        val radius = (style["radius"] as? Number)?.toFloat() ?: 0f
        m = m.background(bg, RoundedCornerShape(radius.dp))
    }
    return m
}

/** The Style padding alone — the complement of [backgroundSizeModifier]. */
private fun paddingModifier(style: Map<String, Any?>): Modifier {
    var m: Modifier = Modifier
    edgeOf(style, "padding")?.let { m = m.padding(it) }
    return m
}

/**
 * Build the box-model Modifier chain, consuming the full `Style → Compose` spec
 * `to_compose` emits (mirroring the Qt translator + the box-model contract pinned
 * by `tests/conformance/`):
 *
 *  - `margin`  → outer [Modifier.padding] (the box-model's outer spacing),
 *  - `minWidth`/`maxWidth`/`minHeight`/`maxHeight` → [Modifier.widthIn]/[heightIn],
 *  - `width`/`height` → fixed [Modifier.width]/[height],
 *  - `background` → a solid [Modifier.background] for a hex string, OR a
 *    [Brush.linearGradient] when it is a gradient map (`{kind:"gradient",…}`),
 *  - `radius` (uniform or per-corner) → the background/border [RoundedCornerShape],
 *  - `border` (uniform or per-side) → [Modifier.border],
 *  - `padding` → inner [Modifier.padding].
 *
 * Order matters: margin (outer) → sizing → background/border (clipped by radius) →
 * padding (inner), the standard CSS-like box model.
 */
internal fun baseModifier(style: Map<String, Any?>): Modifier {
    var m: Modifier = Modifier
    // Outer spacing first, so it sits OUTSIDE the painted box (mirrors the box model).
    marginOf(style)?.let { m = m.padding(it) }
    // Min/max constraints, then fixed size (a fixed dimension still respects the
    // surrounding chain; both can coexist as the Python style allows).
    sizingConstraints(style)?.let { (minW, maxW, minH, maxH) ->
        m = m.widthIn(min = minW, max = maxW).heightIn(min = minH, max = maxH)
    }
    (style["width"] as? Number)?.let { m = m.width(it.toFloat().dp) }
    (style["height"] as? Number)?.let { m = m.height(it.toFloat().dp) }
    val shape = cornerShapeOf(style)
    val brush = backgroundBrushOf(style)
    if (brush != null) {
        m = m.background(brush = brush, shape = shape)
    } else {
        colorOf(style, "background")?.let { bg -> m = m.background(color = bg, shape = shape) }
    }
    borderStrokeOf(style)?.let { stroke -> m = m.border(border = stroke, shape = shape) }
    edgeOf(style, "padding")?.let { m = m.padding(it) }
    return m
}

/** The Style `margin` (serialized as a four-side edge map) as [PaddingValues], or null. */
internal fun marginOf(style: Map<String, Any?>): PaddingValues? = edgeOf(style, "margin")

/**
 * The `minWidth`/`maxWidth`/`minHeight`/`maxHeight` constraints (serialized px →
 * dp) as a `(minW, maxW, minH, maxH)` tuple, or null when none is present. Absent
 * sides default to the unbounded sentinel ([Dp.Unspecified]) so [Modifier.widthIn]
 * / [Modifier.heightIn] leaves them unconstrained.
 */
internal fun sizingConstraints(style: Map<String, Any?>): SizingConstraints? {
    val minW = (style["minWidth"] as? Number)?.toFloat()
    val maxW = (style["maxWidth"] as? Number)?.toFloat()
    val minH = (style["minHeight"] as? Number)?.toFloat()
    val maxH = (style["maxHeight"] as? Number)?.toFloat()
    if (minW == null && maxW == null && minH == null && maxH == null) return null
    return SizingConstraints(
        minWidth = minW?.dp ?: Dp.Unspecified,
        maxWidth = maxW?.dp ?: Dp.Unspecified,
        minHeight = minH?.dp ?: Dp.Unspecified,
        maxHeight = maxH?.dp ?: Dp.Unspecified,
    )
}

/** Resolved min/max width/height constraints from a Compose style spec. */
internal data class SizingConstraints(
    val minWidth: Dp,
    val maxWidth: Dp,
    val minHeight: Dp,
    val maxHeight: Dp,
)

/**
 * The corner [RoundedCornerShape] from `radius` — either a uniform number or a
 * per-corner map `{topLeft, topRight, bottomRight, bottomLeft}` (the `Corners`
 * shape `to_compose` emits). Defaults to a sharp (zero-radius) shape.
 */
internal fun cornerShapeOf(style: Map<String, Any?>): RoundedCornerShape {
    val radius = style["radius"]
    @Suppress("UNCHECKED_CAST")
    val corners = radius as? Map<String, Any?>
    if (corners != null) {
        fun corner(name: String) = (corners[name] as? Number)?.toFloat()?.dp ?: 0.dp
        return RoundedCornerShape(
            topStart = corner("topLeft"),
            topEnd = corner("topRight"),
            bottomEnd = corner("bottomRight"),
            bottomStart = corner("bottomLeft"),
        )
    }
    val uniform = (radius as? Number)?.toFloat() ?: 0f
    return RoundedCornerShape(uniform.dp)
}

/**
 * The background as a [Brush] when `background` is a gradient map (`to_compose`
 * emits `{kind:"gradient", direction, stops:[{color,position}]}`), else null (a
 * plain hex background is handled by [colorOf]). The `direction` token picks the
 * gradient axis; `stops` carry the colors and `[0,1]` positions.
 */
internal fun backgroundBrushOf(style: Map<String, Any?>): Brush? {
    @Suppress("UNCHECKED_CAST")
    val bg = style["background"] as? Map<String, Any?> ?: return null
    if (bg["kind"] != "gradient") return null
    @Suppress("UNCHECKED_CAST")
    val rawStops = bg["stops"] as? List<*> ?: return null
    val stops = rawStops.mapNotNull { entry ->
        @Suppress("UNCHECKED_CAST")
        val map = entry as? Map<String, Any?> ?: return@mapNotNull null
        val color = (map["color"] as? String)?.let { parseHexColor(it) } ?: return@mapNotNull null
        val position = (map["position"] as? Number)?.toFloat() ?: 0f
        position to color
    }
    if (stops.isEmpty()) return null
    val pairs = stops.toTypedArray()
    return when (bg["direction"] as? String) {
        "topBottom" -> Brush.verticalGradient(colorStops = pairs)
        "bottomTop" -> Brush.verticalGradient(colorStops = pairs, startY = Float.POSITIVE_INFINITY, endY = 0f)
        "rightLeft" -> Brush.horizontalGradient(colorStops = pairs, startX = Float.POSITIVE_INFINITY, endX = 0f)
        else -> Brush.horizontalGradient(colorStops = pairs) // "leftRight" (default)
    }
}

/**
 * A [BorderStroke] from `border` — either a uniform `{width, color}` map, or a
 * per-side `{top,right,bottom,left}` map (the `SideBorder` shape). Compose's
 * [Modifier.border] paints a single uniform stroke, so a per-side border collapses
 * to the first non-null side present (documented divergence: Qt paints each side
 * independently; the device draws the dominant side around the whole box). Null
 * when no border is declared or none of the sides carries a stroke.
 */
internal fun borderStrokeOf(style: Map<String, Any?>): BorderStroke? {
    @Suppress("UNCHECKED_CAST")
    val border = style["border"] as? Map<String, Any?> ?: return null
    fun strokeFrom(spec: Map<String, Any?>?): BorderStroke? {
        if (spec == null) return null
        val width = (spec["width"] as? Number)?.toFloat() ?: return null
        val color = (spec["color"] as? String)?.let { parseHexColor(it) } ?: return null
        if (width <= 0f) return null
        return BorderStroke(width.dp, color)
    }
    // Uniform border: a {width, color} map.
    if (border.containsKey("width")) return strokeFrom(border)
    // Per-side SideBorder: collapse to the first present side (top→right→bottom→left).
    for (side in listOf("top", "right", "bottom", "left")) {
        @Suppress("UNCHECKED_CAST")
        val sideSpec = border[side] as? Map<String, Any?>
        strokeFrom(sideSpec)?.let { return it }
    }
    return null
}

internal fun edgeOf(style: Map<String, Any?>, key: String): PaddingValues? {
    @Suppress("UNCHECKED_CAST")
    val edge = style[key] as? Map<String, Any?> ?: return null
    fun side(name: String) = (edge[name] as? Number)?.toFloat()?.dp ?: 0.dp
    return PaddingValues(
        start = side("left"), top = side("top"),
        end = side("right"), bottom = side("bottom"),
    )
}

internal fun colorOf(style: Map<String, Any?>, key: String): Color? {
    val hex = style[key] as? String ?: return null
    return parseHexColor(hex)
}

/** Parse `#rrggbb` or `#aarrggbb` into a Compose [Color]. */
internal fun parseHexColor(hex: String): Color? {
    val s = hex.removePrefix("#")
    return when (s.length) {
        6 -> Color(("ff$s").toLong(16))
        8 -> Color(s.toLong(16))
        else -> null
    }
}

/**
 * E9 font size with `text_scale` applied. Reads `fontSize` (px → sp) and multiplies
 * it by the serialized `textScale` factor (default 1.0), mirroring the Qt translator
 * which folds the same factor into `font-size`. Returns `Unspecified` when no font
 * size is declared (so the Material default size, itself subject to text scale, wins).
 */
internal fun scaledFontSize(style: Map<String, Any?>): androidx.compose.ui.unit.TextUnit {
    val size = (style["fontSize"] as? Number)?.toFloat() ?: return androidx.compose.ui.unit.TextUnit.Unspecified
    val scale = (style["textScale"] as? Number)?.toFloat() ?: 1f
    return (size * scale).sp
}

/**
 * E9 custom font family. When the serialized style carries a `fontAsset` (a path
 * relative to the app's `assets/`, e.g. `"fonts/Custom.ttf"`), build a
 * [FontFamily] from that bundled font via the [Font] asset overload. `null` (the
 * common case) falls back to the platform default family. Mirrors the Qt path,
 * which registers the same file via `QFontDatabase.addApplicationFont`.
 */
@Composable
private fun fontFamilyOf(style: Map<String, Any?>): FontFamily? {
    val asset = style["fontAsset"] as? String ?: return null
    val context = LocalContext.current
    return remember(asset) {
        runCatching { FontFamily(Font(path = asset, assetManager = context.assets)) }.getOrNull()
    }
}

internal fun textAlignOf(style: Map<String, Any?>): TextAlign? = when (style["textAlign"]) {
    "left" -> TextAlign.Left
    "center" -> TextAlign.Center
    "right" -> TextAlign.Right
    "justify" -> TextAlign.Justify
    else -> null
}

internal fun verticalArrangement(style: Map<String, Any?>): Arrangement.Vertical {
    val gap = (style["gap"] as? Number)?.toFloat()
    return when (style["arrangement"]) {
        "center" -> Arrangement.Center
        "end" -> Arrangement.Bottom
        "spaceBetween" -> Arrangement.SpaceBetween
        "spaceAround" -> Arrangement.SpaceAround
        "spaceEvenly" -> Arrangement.SpaceEvenly
        else -> if (gap != null) Arrangement.spacedBy(gap.dp) else Arrangement.Top
    }
}

internal fun horizontalArrangement(style: Map<String, Any?>): Arrangement.Horizontal {
    val gap = (style["gap"] as? Number)?.toFloat()
    return when (style["arrangement"]) {
        "center" -> Arrangement.Center
        "end" -> Arrangement.End
        "spaceBetween" -> Arrangement.SpaceBetween
        "spaceAround" -> Arrangement.SpaceAround
        "spaceEvenly" -> Arrangement.SpaceEvenly
        else -> if (gap != null) Arrangement.spacedBy(gap.dp) else Arrangement.Start
    }
}

internal fun horizontalAlignment(style: Map<String, Any?>): Alignment.Horizontal = when (style["alignment"]) {
    "center" -> Alignment.CenterHorizontally
    "end" -> Alignment.End
    else -> Alignment.Start
}

internal fun verticalAlignment(style: Map<String, Any?>): Alignment.Vertical = when (style["alignment"]) {
    "center" -> Alignment.CenterVertically
    "end" -> Alignment.Bottom
    else -> Alignment.Top
}
