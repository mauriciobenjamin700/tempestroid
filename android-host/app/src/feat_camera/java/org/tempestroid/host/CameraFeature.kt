package org.tempestroid.host

import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner

/**
 * REAL `camera` feature renderer (built only when `-Ptempest.features` includes
 * `camera`). A CameraX [PreviewView] hosted in [AndroidView] showing the live
 * `facing` camera feed. The stub counterpart in `src/stub_camera` has the
 * identical signature so `src/main`'s `when` compiles against either source set.
 *
 * @param node the serialized `CameraPreview` node.
 * @param style the resolved Compose style spec.
 */
@Composable
fun RenderCameraPreview(node: TempestNode, style: Map<String, Any?>) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val facing = node.props["facing"] as? String ?: "back"
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
                    runCatching {
                        provider.unbindAll()
                        provider.bindToLifecycle(lifecycleOwner, selector, preview)
                    }
                }, ContextCompat.getMainExecutor(context))
            }
        },
    )
}
