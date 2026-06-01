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
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
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
    val style = styleOf(node)
    when (node.type) {
        "Text" -> Text(
            text = node.props["content"] as? String ?: "",
            color = colorOf(style, "color") ?: Color.Unspecified,
            fontSize = (style["fontSize"] as? Number)?.toFloat()?.sp ?: androidx.compose.ui.unit.TextUnit.Unspecified,
            fontWeight = (style["fontWeight"] as? Number)?.let { FontWeight(it.toInt()) },
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
                    fontSize = (style["fontSize"] as? Number)?.toFloat()?.sp
                        ?: androidx.compose.ui.unit.TextUnit.Unspecified,
                    fontWeight = (style["fontWeight"] as? Number)?.let { FontWeight(it.toInt()) },
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

/** Parse a serialized color prop (a `#rrggbb`/`#aarrggbb` hex string) to a [Color]. */
private fun colorFromProp(value: Any?): Color? =
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
    Column(modifier = baseModifier(style)) {
        TabStrip(node, active, onEvent)
        AnimatedContent(
            targetState = active,
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            label = "tabview",
        ) { selected ->
            // The content is built by Python for the active tab; key the slot by
            // the selected index so a tab swap cross-fades the new content.
            if (child != null && selected == active) {
                RenderNode(child, onEvent)
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

/** A controlled text field: the value lives in Python; each edit sends a `TextChangeEvent`. */
@Composable
private fun RenderInput(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    OutlinedTextField(
        value = node.props["value"] as? String ?: "",
        onValueChange = { text ->
            handlerToken(node, "on_change")?.let {
                onEvent(it, JSONObject().put("value", text).toString())
            }
        },
        placeholder = { Text(text = node.props["placeholder"] as? String ?: "") },
        singleLine = true,
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
        Text(text = node.props["label"] as? String ?: "")
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
    Button(onClick = { open = true }, modifier = baseModifier(style)) {
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
    Button(onClick = { launcher.launch("*/*") }, modifier = baseModifier(style)) {
        Text(text = if (value.isNotEmpty()) "$label: $value" else label)
    }
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
        Text(text = node.props["label"] as? String ?: "")
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

/** A named Material icon (`name`), falling back to the name as text if unknown. */
@Composable
private fun RenderIcon(node: TempestNode, style: Map<String, Any?>) {
    val name = node.props["name"] as? String ?: ""
    val size = (node.props["size"] as? Number)?.toFloat()
    val vector = iconFor(name)
    if (vector != null) {
        val modifier =
            if (size != null) baseModifier(style).size(size.dp) else baseModifier(style)
        Icon(
            imageVector = vector,
            contentDescription = name,
            tint = colorOf(style, "color") ?: Color.Unspecified,
            modifier = modifier,
        )
    } else {
        // Unknown name: mirror the Qt simulator, which shows the name as text.
        Text(text = name, modifier = baseModifier(style))
    }
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
private fun stackAlignmentOf(style: Map<String, Any?>): Alignment = when (style["stackAlign"]) {
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
private fun styleOf(node: TempestNode): Map<String, Any?> =
    node.props["style"] as? Map<String, Any?> ?: emptyMap()

private fun handlerToken(node: TempestNode, prop: String): String? {
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

/** Build the box-model Modifier chain (size → background+radius → padding). */
private fun baseModifier(style: Map<String, Any?>): Modifier {
    var m: Modifier = Modifier
    (style["width"] as? Number)?.let { m = m.width(it.toFloat().dp) }
    (style["height"] as? Number)?.let { m = m.height(it.toFloat().dp) }
    colorOf(style, "background")?.let { bg ->
        val radius = (style["radius"] as? Number)?.toFloat() ?: 0f
        m = m.background(bg, RoundedCornerShape(radius.dp))
    }
    edgeOf(style, "padding")?.let { m = m.padding(it) }
    return m
}

private fun edgeOf(style: Map<String, Any?>, key: String): PaddingValues? {
    @Suppress("UNCHECKED_CAST")
    val edge = style[key] as? Map<String, Any?> ?: return null
    fun side(name: String) = (edge[name] as? Number)?.toFloat()?.dp ?: 0.dp
    return PaddingValues(
        start = side("left"), top = side("top"),
        end = side("right"), bottom = side("bottom"),
    )
}

private fun colorOf(style: Map<String, Any?>, key: String): Color? {
    val hex = style[key] as? String ?: return null
    return parseHexColor(hex)
}

/** Parse `#rrggbb` or `#aarrggbb` into a Compose [Color]. */
private fun parseHexColor(hex: String): Color? {
    val s = hex.removePrefix("#")
    return when (s.length) {
        6 -> Color(("ff$s").toLong(16))
        8 -> Color(s.toLong(16))
        else -> null
    }
}

private fun textAlignOf(style: Map<String, Any?>): TextAlign? = when (style["textAlign"]) {
    "left" -> TextAlign.Left
    "center" -> TextAlign.Center
    "right" -> TextAlign.Right
    "justify" -> TextAlign.Justify
    else -> null
}

private fun verticalArrangement(style: Map<String, Any?>): Arrangement.Vertical {
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

private fun horizontalArrangement(style: Map<String, Any?>): Arrangement.Horizontal {
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

private fun horizontalAlignment(style: Map<String, Any?>): Alignment.Horizontal = when (style["alignment"]) {
    "center" -> Alignment.CenterHorizontally
    "end" -> Alignment.End
    else -> Alignment.Start
}

private fun verticalAlignment(style: Map<String, Any?>): Alignment.Vertical = when (style["alignment"]) {
    "center" -> Alignment.CenterVertically
    "end" -> Alignment.Bottom
    else -> Alignment.Top
}
