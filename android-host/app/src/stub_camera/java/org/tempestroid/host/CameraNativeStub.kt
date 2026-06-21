package org.tempestroid.host

import org.json.JSONObject

/**
 * STUB `camera` native handler (built when `camera` is NOT in
 * `-Ptempest.features`). Replies `feature_not_built` so the Python side raises
 * `NativeError("feature_not_built")` for `take_photo`/`record_video`. The lean
 * APK ships without the CAMERA permission + FileProvider, so the real capture
 * path would crash; this short-circuit keeps it honest. Signature matches the
 * real `handleCamera` in `src/feat_camera`.
 *
 * @param modules the host module router.
 * @param command the parsed `camera` envelope.
 * @param requestId the request id for the request/response reply, or null.
 */
internal fun handleCamera(modules: NativeModules, command: JSONObject, requestId: String?) {
    modules.reply(
        requestId,
        ok = false,
        error = "feature_not_built",
        message = "camera feature not built into this APK (rebuild with --feature camera)",
    )
}
