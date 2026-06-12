package org.tempestroid.host

import android.util.Log
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import org.json.JSONObject

/**
 * REAL `push` native handler (built only when `-Ptempest.features` includes
 * `push`). `register` reads the FCM registration token (request/response);
 * `schedule_notification` posts a local notification (fire-and-forget, via the
 * shared [NotificationModule]).
 *
 * FCM is additionally device-configuration-gated: without a
 * `google-services.json` + FirebaseApp init the token read throws, and we reply
 * `error="not_configured"` (documented pendency). The stub counterpart in
 * `src/stub_push` has the identical signature.
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
        "register" -> {
            try {
                FirebaseMessaging.getInstance().token
                    .addOnSuccessListener { token ->
                        modules.reply(requestId, true, data = JSONObject().put("token", token))
                    }
                    .addOnFailureListener { e ->
                        modules.reply(
                            requestId, false,
                            error = "not_configured", message = e.message ?: "",
                        )
                    }
            } catch (e: Exception) {
                // FirebaseApp not initialised (no google-services.json).
                modules.reply(
                    requestId, false, error = "not_configured", message = e.message ?: "",
                )
            }
        }
        "schedule_notification" -> {
            // v1: post immediately (no exact-alarm scheduling); the title/body
            // route through the existing notification channel.
            val notifyArgs = JSONObject()
                .put("title", args.optString("title"))
                .put("body", args.optString("body"))
            NotificationModule.handle(modules.hostActivity, "notify", notifyArgs)
        }
        else -> modules.reply(requestId, false, error = "unavailable", message = "no $action")
    }
}

/**
 * FCM receiver service (E8 PushModule), declared in the `src/feat_push` manifest
 * overlay so it is only merged when the `push` feature is built. Device-gated:
 * without a `google-services.json` FirebaseApp never initialises and this service
 * is never instantiated. A delivered message is logged; routing it into Python is
 * a documented pendency tied to the same Firebase config.
 */
class TempestMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        Log.i("tempestroid", "FCM new token: $token")
    }

    override fun onMessageReceived(message: RemoteMessage) {
        Log.i("tempestroid", "FCM message: ${message.data}")
    }
}
