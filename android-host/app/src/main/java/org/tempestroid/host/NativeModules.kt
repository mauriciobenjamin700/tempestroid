package org.tempestroid.host

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import org.json.JSONObject

/**
 * Routes `{"kind": "native", ...}` command envelopes from Python to the matching
 * device-capability module (phase B6).
 *
 * The bridge carries these over the same channel as mount/patch; [MainActivity]
 * peels off `native` envelopes (it holds the [Context]) and forwards them here.
 */
object NativeModules {

    /**
     * Dispatch one native command to its module.
     *
     * @param context an Android context (the activity).
     * @param command the parsed `native` envelope.
     */
    fun handle(context: Context, command: JSONObject) {
        val module = command.optString("module")
        val action = command.optString("action")
        val args = command.optJSONObject("args") ?: JSONObject()
        when (module) {
            "notifications" -> NotificationModule.handle(context, action, args)
            else -> Log.w("tempestroid", "unknown native module: $module")
        }
    }
}

/** Native notifications: posts a system notification via NotificationManager. */
private object NotificationModule {

    private const val CHANNEL_ID = "tempestroid"
    private var nextId = 1

    fun handle(context: Context, action: String, args: JSONObject) {
        when (action) {
            "notify" -> notify(context, args.optString("title"), args.optString("body"))
            else -> Log.w("tempestroid", "unknown notifications action: $action")
        }
    }

    private fun notify(context: Context, title: String, body: String) {
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID, "tempestroid", NotificationManager.IMPORTANCE_DEFAULT
            )
            manager.createNotificationChannel(channel)
        }
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .build()
        manager.notify(nextId++, notification)
        Log.i("tempestroid", "posted notification: $title")
    }
}
