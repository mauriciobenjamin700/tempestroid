package org.tempestroid.host

import android.Manifest
import org.json.JSONObject

/**
 * REAL `camera` native handler (built only when `-Ptempest.features` includes
 * `camera`). Mirrors the previous in-class `handleCamera`: checks the CAMERA
 * (and, for video, RECORD_AUDIO) permission, then launches the system capture
 * intent through [NativeModules.launchCapture]. The capture-result plumbing lives
 * in [NativeModules] (it references no heavy dependency). The stub counterpart in
 * `src/stub_camera` has the identical signature and replies `feature_not_built`.
 *
 * @param modules the host module router.
 * @param command the parsed `camera` envelope.
 * @param requestId the request id for the request/response reply, or null.
 */
internal fun handleCamera(modules: NativeModules, command: JSONObject, requestId: String?) {
    val action = command.optString("action")
    val args = command.optJSONObject("args") ?: JSONObject()
    // Video also records audio, so it needs the microphone permission too.
    val permissions =
        if (action == "record_video") {
            arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        } else {
            arrayOf(Manifest.permission.CAMERA)
        }
    modules.withPermissions(permissions, requestId, command) {
        modules.launchCapture(action, args, requestId)
    }
}
