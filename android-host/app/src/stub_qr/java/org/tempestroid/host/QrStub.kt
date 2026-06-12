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
 * STUB `qr` feature renderer (built when `qr` is NOT in `-Ptempest.features`).
 * Renders a labelled placeholder instead of the CameraX + ML Kit scanner, so the
 * lean APK ships without `com.google.mlkit:barcode-scanning`. Signature matches
 * the real `RenderQrScanner` in `src/feat_qr`.
 *
 * @param node the serialized `QrScanner` node.
 * @param style the resolved Compose style spec.
 * @param onEvent the renderer event sink (unused in the stub).
 */
@Composable
fun RenderQrScanner(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    Box(
        modifier = baseModifier(style)
            .background(Color(0xFFE0E0E0), RoundedCornerShape(8.dp))
            .padding(16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = "QrScanner — qr feature not built")
    }
}
