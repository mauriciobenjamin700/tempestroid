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
 * STUB `camera` feature renderer (built when `camera` is NOT in
 * `-Ptempest.features`). Renders a labelled placeholder instead of the CameraX
 * preview, so the lean APK ships without the `androidx.camera:*` dependencies.
 * Signature matches the real `RenderCameraPreview` in `src/feat_camera`.
 *
 * @param node the serialized `CameraPreview` node.
 * @param style the resolved Compose style spec.
 */
@Composable
fun RenderCameraPreview(node: TempestNode, style: Map<String, Any?>) {
    Box(
        modifier = baseModifier(style)
            .background(Color(0xFFE0E0E0), RoundedCornerShape(8.dp))
            .padding(16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = "CameraPreview — camera feature not built")
    }
}
