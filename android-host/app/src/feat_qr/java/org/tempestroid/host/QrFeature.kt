package org.tempestroid.host

import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import org.json.JSONObject

/**
 * REAL `qr` feature renderer (built only when `-Ptempest.features` includes `qr`;
 * `qr` transitively pulls the `camera` deps too). A CameraX [PreviewView] with an
 * [ImageAnalysis] stage feeding ML Kit [BarcodeScanning]. On a decode, `on_scan`
 * fires a `{data, format}` payload over the NORMAL event channel. To avoid a
 * flood, only the first non-blank value per analyzer lifetime is sent. The stub
 * counterpart in `src/stub_qr` has the identical signature.
 *
 * @param node the serialized `QrScanner` node.
 * @param style the resolved Compose style spec.
 * @param onEvent the renderer event sink (token, payload-json).
 */
@androidx.annotation.OptIn(androidx.camera.core.ExperimentalGetImage::class)
@Composable
fun RenderQrScanner(
    node: TempestNode,
    style: Map<String, Any?>,
    onEvent: (String, String) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val emitted = remember { mutableStateOf(false) }
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
                    val scanner = BarcodeScanning.getClient()
                    val analysis = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()
                    analysis.setAnalyzer(ContextCompat.getMainExecutor(ctx)) { proxy ->
                        val mediaImage = proxy.image
                        if (mediaImage == null) { proxy.close(); return@setAnalyzer }
                        val image = InputImage.fromMediaImage(
                            mediaImage, proxy.imageInfo.rotationDegrees,
                        )
                        scanner.process(image)
                            .addOnSuccessListener { codes ->
                                val first = codes.firstOrNull { !it.rawValue.isNullOrEmpty() }
                                if (first != null && !emitted.value) {
                                    emitted.value = true
                                    handlerToken(node, "on_scan")?.let { token ->
                                        val payload = JSONObject()
                                            .put("data", first.rawValue)
                                            .put("format", barcodeFormatName(first.format))
                                        onEvent(token, payload.toString())
                                    }
                                }
                            }
                            .addOnCompleteListener { proxy.close() }
                    }
                    runCatching {
                        provider.unbindAll()
                        provider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            analysis,
                        )
                    }
                }, ContextCompat.getMainExecutor(context))
            }
        },
    )
}

/** Map an ML Kit barcode format constant to the `QrScanEvent` `format` string. */
private fun barcodeFormatName(format: Int): String = when (format) {
    Barcode.FORMAT_QR_CODE -> "QR_CODE"
    Barcode.FORMAT_EAN_13 -> "EAN_13"
    Barcode.FORMAT_EAN_8 -> "EAN_8"
    Barcode.FORMAT_CODE_128 -> "CODE_128"
    Barcode.FORMAT_CODE_39 -> "CODE_39"
    Barcode.FORMAT_UPC_A -> "UPC_A"
    Barcode.FORMAT_UPC_E -> "UPC_E"
    Barcode.FORMAT_DATA_MATRIX -> "DATA_MATRIX"
    Barcode.FORMAT_PDF417 -> "PDF417"
    Barcode.FORMAT_AZTEC -> "AZTEC"
    else -> "QR_CODE"
}
