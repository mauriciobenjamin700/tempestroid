package org.tempestroid.host

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

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

        else -> Box(modifier = baseModifier(style)) {
            node.children.forEach { RenderNode(it, onEvent) }
        }
    }
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
