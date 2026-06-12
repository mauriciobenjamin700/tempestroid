package org.tempestroid.host

import org.json.JSONObject

/**
 * STUB `push` native handler (built when `push` is NOT in `-Ptempest.features`).
 * `register` replies `feature_not_built` (the lean APK has no FCM service nor the
 * `firebase-messaging` dependency), so the Python side raises
 * `NativeError("feature_not_built")`. `schedule_notification` still posts a local
 * notification — it needs no Firebase, only the always-present [NotificationModule].
 * Signature matches the real `handlePush` in `src/feat_push`.
 *
 * @param modules the host module router.
 * @param action the push action (`register` / `schedule_notification`).
 * @param args the action arguments.
 * @param requestId the request id for the request/response reply, or null.
 */
internal fun handlePush(
    modules: NativeModules,
    action: String,
    args: JSONObject,
    requestId: String?,
) {
    when (action) {
        "register" -> modules.reply(
            requestId,
            ok = false,
            error = "feature_not_built",
            message = "push feature not built into this APK (rebuild with --feature push)",
        )
        "schedule_notification" -> {
            val notifyArgs = JSONObject()
                .put("title", args.optString("title"))
                .put("body", args.optString("body"))
            NotificationModule.handle(modules.hostActivity, "notify", notifyArgs)
        }
        else -> modules.reply(requestId, false, error = "unavailable", message = "no $action")
    }
}
