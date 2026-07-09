package org.tempestroid.host

import android.graphics.Bitmap
import android.util.Base64
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.util.concurrent.Executors
import org.json.JSONObject

/**
 * REAL `camera` feature renderer (built only when `-Ptempest.features` includes
 * `camera`). A CameraX [PreviewView] hosted in [AndroidView] showing the live
 * `facing` camera feed. When the node wires `on_frame`, an [ImageAnalysis] stage
 * (keeping only the latest frame) is bound too: at most every `frame_interval_ms`
 * a frame is decoded to raw RGB, base64-encoded, and emitted as a
 * `CameraFrameEvent` to the handler token — so the app runs on-device inference
 * on the live feed. The stub counterpart in `src/stub_camera` has the identical
 * signature so `src/main`'s `when` compiles against either source set.
 *
 * @param node the serialized `CameraPreview` node.
 * @param style the resolved Compose style spec.
 * @param onEvent the host event sink (`token`, `payloadJson`).
 */
@Composable
fun RenderCameraPreview(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val facing = node.props["facing"] as? String ?: "back"
    val frameToken = handlerToken(node, "on_frame")
    val intervalMs = (node.props["frame_interval_ms"] as? Number)?.toLong() ?: 300L
    AndroidView(
        modifier = baseModifier(style),
        factory = { ctx ->
            PreviewView(ctx).also { previewView ->
                val providerFuture = ProcessCameraProvider.getInstance(ctx)
                providerFuture.addListener({
                    val provider = providerFuture.get()
                    val preview = Preview.Builder().build().also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }
                    val selector = if (facing == "front") {
                        CameraSelector.DEFAULT_FRONT_CAMERA
                    } else {
                        CameraSelector.DEFAULT_BACK_CAMERA
                    }
                    val analysis = frameToken?.let { token ->
                        buildFrameAnalysis(token, intervalMs, onEvent)
                    }
                    runCatching {
                        provider.unbindAll()
                        if (analysis != null) {
                            provider.bindToLifecycle(
                                lifecycleOwner, selector, preview, analysis,
                            )
                        } else {
                            provider.bindToLifecycle(lifecycleOwner, selector, preview)
                        }
                    }
                }, ContextCompat.getMainExecutor(context))
            }
        },
    )
}

/**
 * An [ImageAnalysis] that emits a throttled `CameraFrameEvent` to [token].
 *
 * Keeps only the latest frame (inference is far slower than the frame rate) and,
 * at most every [intervalMs], decodes the frame to a right-side-up raw RGB buffer
 * and sends `{width,height,data(base64),rotation:0}`. Analysis runs on a single
 * background thread so the decode never blocks the UI.
 */
private fun buildFrameAnalysis(
    token: String,
    intervalMs: Long,
    onEvent: (String, String) -> Unit,
): ImageAnalysis {
    val analysis = ImageAnalysis.Builder()
        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
        .build()
    val executor = Executors.newSingleThreadExecutor()
    var lastEmit = 0L
    analysis.setAnalyzer(executor) { proxy ->
        val now = System.currentTimeMillis()
        if (now - lastEmit < intervalMs) {
            proxy.close()
            return@setAnalyzer
        }
        lastEmit = now
        runCatching {
            val payload = frameEventPayload(proxy)
            onEvent(token, payload)
        }
        proxy.close()
    }
    return analysis
}

/**
 * Build the `CameraFrameEvent` JSON for one frame: the sensor rotation is baked
 * in (the emitted buffer is upright, so `rotation` is 0), and the pixels are the
 * raw row-major RGB bytes, base64-encoded.
 */
private fun frameEventPayload(proxy: ImageProxy): String {
    val rotation = proxy.imageInfo.rotationDegrees
    var bitmap = proxy.toBitmap()
    if (rotation != 0) {
        val matrix = android.graphics.Matrix().apply { postRotate(rotation.toFloat()) }
        bitmap = Bitmap.createBitmap(
            bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true,
        )
    }
    val width = bitmap.width
    val height = bitmap.height
    val pixels = IntArray(width * height)
    bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
    val rgb = ByteArray(width * height * 3)
    var j = 0
    for (pixel in pixels) {
        rgb[j++] = ((pixel shr 16) and 0xFF).toByte()
        rgb[j++] = ((pixel shr 8) and 0xFF).toByte()
        rgb[j++] = (pixel and 0xFF).toByte()
    }
    return JSONObject()
        .put("width", width)
        .put("height", height)
        .put("data", Base64.encodeToString(rgb, Base64.NO_WRAP))
        .put("rotation", 0)
        .toString()
}
