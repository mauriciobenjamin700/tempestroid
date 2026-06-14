package org.tempestroid.host

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.Role
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * F7 camada B — pins the KOTLIN consumption of the `Style → Compose` spec.
 *
 * The phase-D conformance suite (`tests/conformance/`) pins the Python side: it
 * snapshots what `to_compose(style)` emits for each canonical style. This JVM
 * unit test pins the OTHER side of the same contract — the pure mapping functions
 * in [TempestRenderer] that turn those serialized maps into Compose
 * `Color` / `Arrangement` / `Alignment` / `PaddingValues` / `TextAlign` values.
 *
 * Each test reconstructs the EXACT `compose` block a golden file records (see the
 * `// golden:` reference on each), so a drift on either side of the bridge is
 * caught: Python by the conformance golden, Kotlin by this assert.
 *
 * Runs on the plain JVM in milliseconds (no device, no emulator, no Robolectric):
 * the asserted functions touch only Compose value types, never the Android
 * framework.
 */
class StyleComposeMappingTest {

    // --- colors (background / color → Compose Color) ------------------------

    @Test
    fun parsesSixDigitHexAsOpaqueColor() {
        // to_compose serializes a Color as "#rrggbb"; the renderer reads it back
        // as an opaque ARGB Color (alpha forced to 0xFF).
        assertEquals(Color(0xFFFF0000), parseHexColor("#ff0000"))
        assertEquals(Color(0xFF0000FF), parseHexColor("#0000ff"))
        assertEquals(Color(0xFF000000), parseHexColor("#000000"))
        assertEquals(Color(0xFFC8C8C8), parseHexColor("#c8c8c8"))
    }

    @Test
    fun parsesEightDigitHexWithAlpha() {
        assertEquals(Color(0x80FF0000), parseHexColor("#80ff0000"))
    }

    @Test
    fun rejectsMalformedHex() {
        assertNull(parseHexColor("#fff"))
        assertNull(parseHexColor("nope"))
    }

    @Test
    fun colorOfReadsNamedStyleKeys() {
        // golden: typography.json has no color; box.json border color etc. Here we
        // assert the generic background/color extraction the renderer uses.
        val style = mapOf("background" to "#ff0000", "color" to "#0000ff")
        assertEquals(Color(0xFFFF0000), colorOf(style, "background"))
        assertEquals(Color(0xFF0000FF), colorOf(style, "color"))
        assertNull(colorOf(style, "missing"))
    }

    @Test
    fun colorOfIgnoresNonStringBackground() {
        // gradient.json emits `background` as a MAP, not a hex string. The current
        // renderer's box-model path only consumes the hex form, so a gradient
        // background is read as null here (documented Kotlin gap — see report).
        val style = mapOf("background" to mapOf("kind" to "gradient"))
        assertNull(colorOf(style, "background"))
    }

    // --- arrangement (Column.verticalArrangement / Row.horizontalArrangement)

    @Test
    fun verticalArrangementMapsEachToken() {
        // golden: flex_col_end.json → arrangement "end"; flex_row_center → "center".
        assertEquals(Arrangement.Top, verticalArrangement(emptyMap()))
        assertEquals(Arrangement.Center, verticalArrangement(mapOf("arrangement" to "center")))
        assertEquals(Arrangement.Bottom, verticalArrangement(mapOf("arrangement" to "end")))
        assertEquals(
            Arrangement.SpaceBetween,
            verticalArrangement(mapOf("arrangement" to "spaceBetween")),
        )
        assertEquals(
            Arrangement.SpaceAround,
            verticalArrangement(mapOf("arrangement" to "spaceAround")),
        )
        assertEquals(
            Arrangement.SpaceEvenly,
            verticalArrangement(mapOf("arrangement" to "spaceEvenly")),
        )
    }

    @Test
    fun horizontalArrangementMapsEachToken() {
        assertEquals(Arrangement.Start, horizontalArrangement(emptyMap()))
        assertEquals(Arrangement.Center, horizontalArrangement(mapOf("arrangement" to "center")))
        assertEquals(Arrangement.End, horizontalArrangement(mapOf("arrangement" to "end")))
        assertEquals(
            Arrangement.SpaceBetween,
            horizontalArrangement(mapOf("arrangement" to "spaceBetween")),
        )
    }

    @Test
    fun arrangementGapBecomesSpacedBy() {
        // golden: flex_row_center.json → gap 12.0. With no arrangement token but a
        // gap, the renderer uses Arrangement.spacedBy(gap.dp).
        assertEquals(
            Arrangement.spacedBy(12.0f.dp),
            horizontalArrangement(mapOf("gap" to 12.0)),
        )
        assertEquals(
            Arrangement.spacedBy(12.0f.dp),
            verticalArrangement(mapOf("gap" to 12.0)),
        )
    }

    @Test
    fun explicitArrangementWinsOverGap() {
        // An explicit arrangement token takes precedence over gap (matches the
        // renderer's `when` ordering).
        assertEquals(
            Arrangement.Center,
            horizontalArrangement(mapOf("arrangement" to "center", "gap" to 12.0)),
        )
    }

    // --- alignment (Column.horizontalAlignment / Row.verticalAlignment) -----

    @Test
    fun horizontalAlignmentMapsEachToken() {
        // golden: flex_col_end.json → alignment "end"; flex_row_center → "center".
        assertEquals(Alignment.Start, horizontalAlignment(emptyMap()))
        assertEquals(Alignment.CenterHorizontally, horizontalAlignment(mapOf("alignment" to "center")))
        assertEquals(Alignment.End, horizontalAlignment(mapOf("alignment" to "end")))
    }

    @Test
    fun verticalAlignmentMapsEachToken() {
        assertEquals(Alignment.Top, verticalAlignment(emptyMap()))
        assertEquals(Alignment.CenterVertically, verticalAlignment(mapOf("alignment" to "center")))
        assertEquals(Alignment.Bottom, verticalAlignment(mapOf("alignment" to "end")))
    }

    // --- stack alignment (Box.contentAlignment) -----------------------------

    @Test
    fun stackAlignmentMapsEachToken() {
        // golden: stack_align.json → stackAlign "bottomEnd".
        assertEquals(Alignment.TopStart, stackAlignmentOf(emptyMap()))
        assertEquals(Alignment.BottomEnd, stackAlignmentOf(mapOf("stackAlign" to "bottomEnd")))
        assertEquals(Alignment.Center, stackAlignmentOf(mapOf("stackAlign" to "center")))
        assertEquals(Alignment.TopCenter, stackAlignmentOf(mapOf("stackAlign" to "topCenter")))
        assertEquals(Alignment.CenterStart, stackAlignmentOf(mapOf("stackAlign" to "centerStart")))
    }

    // --- padding edge (Style.padding → PaddingValues) -----------------------

    @Test
    fun edgeOfBuildsPaddingValues() {
        // golden: box.json → padding {left,top,right,bottom = 8}. The renderer maps
        // the four sides to a PaddingValues; absent key → null.
        val style = mapOf(
            "padding" to mapOf("left" to 8.0, "top" to 8.0, "right" to 8.0, "bottom" to 8.0),
        )
        val pv = edgeOf(style, "padding")
        assertEquals(8.0f.dp, pv?.calculateTopPadding())
        assertEquals(8.0f.dp, pv?.calculateBottomPadding())
        assertNull(edgeOf(style, "margin"))
    }

    @Test
    fun edgeOfDefaultsMissingSidesToZero() {
        // rtl_layout.json LTR → padding {left 8, right 16, top 0, bottom 0}.
        val style = mapOf("padding" to mapOf("left" to 8.0, "right" to 16.0))
        val pv = edgeOf(style, "padding")
        assertEquals(0.0f.dp, pv?.calculateTopPadding())
        assertEquals(0.0f.dp, pv?.calculateBottomPadding())
    }

    // --- text align + scaled font (typography / text_scale_font_asset) ------

    @Test
    fun textAlignMapsEachToken() {
        // golden: typography.json → textAlign "center"; rtl_layout LTR → "left",
        // RTL → "right".
        assertNull(textAlignOf(emptyMap()))
        assertEquals(TextAlign.Left, textAlignOf(mapOf("textAlign" to "left")))
        assertEquals(TextAlign.Center, textAlignOf(mapOf("textAlign" to "center")))
        assertEquals(TextAlign.Right, textAlignOf(mapOf("textAlign" to "right")))
        assertEquals(TextAlign.Justify, textAlignOf(mapOf("textAlign" to "justify")))
    }

    @Test
    fun scaledFontSizeAppliesTextScale() {
        // golden: text_scale_font_asset.json → fontSize 16.0, textScale 1.4 ⇒ 22.4sp
        // (the Qt translator folds the same factor into font-size: 22.4px).
        val unit = scaledFontSize(mapOf("fontSize" to 16.0, "textScale" to 1.4))
        assertEquals(22.4f, unit.value, 0.001f)
    }

    @Test
    fun scaledFontSizeDefaultsScaleToOne() {
        // golden: typography.json → fontSize 18.0, no textScale ⇒ 18.0sp.
        val unit = scaledFontSize(mapOf("fontSize" to 18.0))
        assertEquals(18.0f, unit.value, 0.001f)
    }

    @Test
    fun scaledFontSizeUnspecifiedWhenNoFontSize() {
        assertEquals(TextUnit.Unspecified, scaledFontSize(emptyMap()))
    }

    // --- color-from-prop (shimmer / skeleton base/highlight) ----------------

    @Test
    fun colorFromPropReadsHexStringOrNull() {
        assertEquals(Color(0xFFE0E0E0), colorFromProp("#e0e0e0"))
        assertNull(colorFromProp(42))
        assertNull(colorFromProp(null))
    }

    // --- semantics role mapping (E9 accessibility) --------------------------

    @Test
    fun roleForMapsKnownRoles() {
        assertEquals(Role.Button, roleFor("button"))
        assertEquals(Role.Checkbox, roleFor("checkbox"))
        assertEquals(Role.Switch, roleFor("switch"))
        assertEquals(Role.RadioButton, roleFor("radio"))
        assertEquals(Role.Tab, roleFor("tab"))
        assertEquals(Role.Image, roleFor("image"))
        assertEquals(Role.DropdownList, roleFor("dropdown"))
        // "heading" is handled separately (Modifier.heading), so roleFor → null.
        assertNull(roleFor("heading"))
        assertNull(roleFor(null))
        assertNull(roleFor("unknown"))
    }
}
