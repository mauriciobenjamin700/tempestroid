package org.tempestroid.host

import org.json.JSONObject

/**
 * STUB `onnx` native handler (built when `vision` is NOT in
 * `-Ptempest.features`). Every action replies `feature_not_built` — the lean APK
 * has no `onnxruntime-android` AAR — so the Python side raises
 * `NativeError("feature_not_built")`. Signature matches the real [handleOnnx] in
 * `src/feat_vision`.
 *
 * @param modules the host module router.
 * @param action the onnx action (`load` / `infer`).
 * @param args the action arguments.
 * @param requestId the request id for the request/response reply, or null.
 */
internal fun handleOnnx(
    modules: NativeModules,
    action: String,
    args: JSONObject,
    requestId: String?,
) {
    modules.reply(
        requestId,
        ok = false,
        error = "feature_not_built",
        message = "vision feature not built into this APK (rebuild with --feature vision)",
    )
}
