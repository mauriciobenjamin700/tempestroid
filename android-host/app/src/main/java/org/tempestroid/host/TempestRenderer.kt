package org.tempestroid.host

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.pointerInput
import kotlin.math.abs
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import coil.compose.AsyncImage
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

        else -> Box(modifier = baseModifier(style)) {
            node.children.forEach { RenderNode(it, onEvent) }
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
