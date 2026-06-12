package org.tempestroid.host

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * STUB `video` feature renderer (built when `video` is NOT in
 * `-Ptempest.features`). Renders a labelled placeholder instead of the Media3
 * `PlayerView`, so the lean APK ships without `androidx.media3:*`. Signature
 * matches the real `RenderVideoPlayer` in `src/feat_video`.
 *
 * @param node the serialized `VideoPlayer` node.
 * @param style the resolved Compose style spec.
 */
@Composable
fun RenderVideoPlayer(node: TempestNode, style: Map<String, Any?>) {
    Box(
        modifier = baseModifier(style)
            .background(Color(0xFFE0E0E0), RoundedCornerShape(8.dp))
            .padding(16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = "VideoPlayer — video feature not built")
    }
}
