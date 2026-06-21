package org.tempestroid.host

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.runtime.snapshots.SnapshotStateMap
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * F7 camada B (opt-in) — Roborazzi golden screenshots of the Compose renderer
 * rendered off-device via Robolectric.
 *
 * These pin the PIXELS of `RenderNode` for the canonical styles (the same ones
 * the phase-D conformance suite pins on the Python `to_compose` side). Run/record
 * with:
 *
 * ```
 * cd android-host && ./gradlew :app:recordRoborazziDebug -Ptempest.roborazzi=true
 * ```
 *
 * Verify (compare against committed goldens) with:
 *
 * ```
 * cd android-host && ./gradlew :app:verifyRoborazziDebug -Ptempest.roborazzi=true
 * ```
 *
 * Golden PNGs land in `app/src/test/screenshots/` (versioned). This path is
 * opt-in (Robolectric downloads its android-all runtime on first run), so the
 * default JVM gate runs the lean deterministic-assert tests instead.
 *
 * It uses the `captureRoboImage(content = { … })` overload (roborazzi-compose),
 * which renders the composable into an offscreen surface directly — no
 * `ComponentActivity` / `createComposeRule`, so it needs no test manifest entry.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class RenderNodeScreenshotTest {

    /** Build a snapshot-state [TempestNode] directly (bypassing the JSON parse). */
    private fun node(
        type: String,
        props: Map<String, Any?> = emptyMap(),
        children: List<TempestNode> = emptyList(),
    ): TempestNode {
        val p: SnapshotStateMap<String, Any?> = mutableStateMapOf()
        p.putAll(props)
        val c: SnapshotStateList<TempestNode> = mutableStateListOf()
        c.addAll(children)
        return TempestNode(type = type, key = null, props = p, children = c)
    }

    private fun capture(path: String, content: @Composable () -> Unit) {
        captureRoboImage(filePath = path) {
            MaterialTheme {
                Surface(modifier = Modifier.size(220.dp)) { content() }
            }
        }
    }

    @Test
    fun columnEndAlignment() {
        // golden parity: flex_col_end.json (alignment/arrangement "end").
        capture("src/test/screenshots/column_end.png") {
            RenderNode(
                node(
                    "Column",
                    props = mapOf(
                        "style" to mapOf("alignment" to "end", "arrangement" to "end"),
                    ),
                    children = listOf(
                        node("Text", props = mapOf("content" to "one")),
                        node("Text", props = mapOf("content" to "two")),
                    ),
                ),
            ) { _, _ -> }
        }
    }

    @Test
    fun rowCenterWithGap() {
        // golden parity: flex_row_center.json (center, gap 12).
        capture("src/test/screenshots/row_center_gap.png") {
            RenderNode(
                node(
                    "Row",
                    props = mapOf(
                        "style" to mapOf(
                            "alignment" to "center",
                            "arrangement" to "center",
                            "gap" to 12.0,
                        ),
                    ),
                    children = listOf(
                        node("Text", props = mapOf("content" to "A")),
                        node("Text", props = mapOf("content" to "B")),
                    ),
                ),
            ) { _, _ -> }
        }
    }

    @Test
    fun boxWithBackgroundRadiusPadding() {
        // golden parity: box.json (radius 6, padding 8) + a hex background the
        // Kotlin renderer DOES consume (gradient maps are a documented gap).
        capture("src/test/screenshots/box_bg_radius.png") {
            RenderNode(
                node(
                    "Stack",
                    props = mapOf(
                        "style" to mapOf(
                            "background" to "#3366cc",
                            "radius" to 6.0,
                            "width" to 120.0,
                            "height" to 80.0,
                            "padding" to mapOf(
                                "left" to 8.0, "top" to 8.0, "right" to 8.0, "bottom" to 8.0,
                            ),
                        ),
                    ),
                    children = listOf(node("Text", props = mapOf("content" to "box"))),
                ),
            ) { _, _ -> }
        }
    }

    @Test
    fun styledTextColorAndAlign() {
        // golden parity: typography.json (fontSize 18, weight 700, align center).
        capture("src/test/screenshots/styled_text.png") {
            Box(modifier = Modifier.fillMaxSize()) {
                RenderNode(
                    node(
                        "Text",
                        props = mapOf(
                            "content" to "Hello",
                            "style" to mapOf(
                                "color" to "#cc0000",
                                "fontSize" to 18.0,
                                "fontWeight" to 700,
                                "textAlign" to "center",
                            ),
                        ),
                    ),
                ) { _, _ -> }
            }
        }
    }
}
