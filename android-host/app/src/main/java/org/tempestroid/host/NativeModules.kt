package org.tempestroid.host

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/**
 * Routes `{"kind": "native", ...}` command envelopes from Python to the device
 * capability that fulfils them (phases B6 / native-capabilities).
 *
 * Two envelope shapes (mirroring `tempestroid.native.dispatch`):
 *  - **fire-and-forget** — no `request_id`; the module just acts (notify, share).
 *  - **request/response** — carries `request_id`; the module replies by calling
 *    [PythonRuntime.dispatchEvent] with the reserved token
 *    `"__native_result__:<id>"` and a `{"ok": Bool, "data"/"error": ...}` body,
 *    which the Python side ([resolve_native_result]) matches to a pending future.
 *
 * It is a per-activity object (not a static singleton) because several
 * capabilities need [ActivityResultLauncher]s, which must be registered while the
 * activity is being created.
 *
 * @param activity the host activity, used for permissions, file providers, and
 *   activity-result launchers.
 */
class NativeModules(private val activity: ComponentActivity) {

    /** A native command awaiting an async device result, pinned by request id. */
    private data class Pending(val requestId: String, val command: JSONObject)

    /** The capture currently awaiting [takePicture], or null. */
    private var pendingPhoto: Pending? = null
    private var pendingPhotoFile: File? = null

    /** Native commands gated on a runtime-permission grant, by request code. */
    private val pendingPermission = mutableMapOf<Int, Pending>()
    private var nextPermissionCode = 1000

    private val requestPermissions: ActivityResultLauncher<Array<String>> =
        activity.registerForActivityResult(
            ActivityResultContracts.RequestMultiplePermissions()
        ) { grants -> onPermissionResult(grants) }

    private val takePicture: ActivityResultLauncher<Uri> =
        activity.registerForActivityResult(
            ActivityResultContracts.TakePicture()
        ) { saved -> onPhotoResult(saved) }

    /**
     * Dispatch one native command to its capability module.
     *
     * @param command the parsed `native` envelope.
     */
    fun handle(command: JSONObject) {
        val module = command.optString("module")
        val action = command.optString("action")
        val args = command.optJSONObject("args") ?: JSONObject()
        val requestId = command.optString("request_id").ifEmpty { null }
        when (module) {
            "notifications" -> NotificationModule.handle(activity, action, args)
            "share" -> handleShare(action, args)
            "clipboard" -> handleClipboard(action, args, requestId)
            "storage" -> handleStorage(action, args, requestId)
            "geolocation" -> handleGeolocation(args, requestId)
            "camera" -> handleCamera(command, requestId)
            "bluetooth" -> handleBluetooth(args, requestId)
            else -> {
                Log.w(TAG, "unknown native module: $module")
                reply(requestId, false, error = "unavailable", message = "no module $module")
            }
        }
    }

    // --- reply helper --------------------------------------------------------

    /**
     * Send a request/response result back to Python over the reserved token.
     * No-op for fire-and-forget commands (null [requestId]).
     */
    private fun reply(
        requestId: String?,
        ok: Boolean,
        data: JSONObject? = null,
        error: String? = null,
        message: String? = null,
    ) {
        if (requestId == null) return
        val envelope = JSONObject().put("ok", ok)
        if (data != null) envelope.put("data", data)
        if (error != null) envelope.put("error", error)
        if (message != null) envelope.put("message", message)
        PythonRuntime.dispatchEvent("$NATIVE_RESULT_PREFIX$requestId", envelope.toString())
    }

    // --- permissions ---------------------------------------------------------

    private fun hasPermission(name: String): Boolean =
        activity.checkSelfPermission(name) == PackageManager.PERMISSION_GRANTED

    /**
     * Run [command] now if all [permissions] are granted, else request them and
     * resume once the user responds. The resume re-enters [handle].
     */
    private fun withPermissions(
        permissions: Array<String>,
        requestId: String?,
        command: JSONObject,
        granted: () -> Unit,
    ) {
        val missing = permissions.filterNot { hasPermission(it) }
        if (missing.isEmpty()) {
            granted()
            return
        }
        if (requestId == null) {
            // Fire-and-forget capability cannot wait on a grant: skip silently.
            return
        }
        val code = nextPermissionCode++
        pendingPermission[code] = Pending(requestId, command)
        // Stash the request code on the command so the resume can re-dispatch it.
        command.put("__perm_code", code)
        requestPermissions.launch(missing.toTypedArray())
    }

    private fun onPermissionResult(grants: Map<String, Boolean>) {
        // Resolve the most recent pending permission request (one in flight).
        val entry = pendingPermission.entries.lastOrNull() ?: return
        pendingPermission.remove(entry.key)
        val pending = entry.value
        if (grants.values.all { it }) {
            // Re-dispatch the original command now that permission is granted.
            handle(pending.command)
        } else {
            reply(pending.requestId, false, error = "permission_denied")
        }
    }

    // --- share (fire-and-forget) --------------------------------------------

    private fun handleShare(action: String, args: JSONObject) {
        when (action) {
            "share" -> {
                val text = args.optString("text")
                val url = args.optString("url")
                val title = args.optString("title")
                val body = listOf(text, url).filter { it.isNotEmpty() }.joinToString(" ")
                val send = Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_TEXT, body)
                }
                startActivitySafely(Intent.createChooser(send, title))
            }
            "whatsapp" -> {
                val text = args.optString("text")
                val phone = args.optString("phone")
                val uri = if (phone.isNotEmpty()) {
                    Uri.parse("https://wa.me/$phone?text=" + Uri.encode(text))
                } else {
                    Uri.parse("https://wa.me/?text=" + Uri.encode(text))
                }
                startActivitySafely(Intent(Intent.ACTION_VIEW, uri).setPackage(WHATSAPP_PKG))
            }
            "open_url" -> {
                startActivitySafely(Intent(Intent.ACTION_VIEW, Uri.parse(args.optString("url"))))
            }
            else -> Log.w(TAG, "unknown share action: $action")
        }
    }

    private fun startActivitySafely(intent: Intent) {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            activity.startActivity(intent)
        } catch (e: android.content.ActivityNotFoundException) {
            Log.w(TAG, "no activity for intent: ${e.message}")
        }
    }

    // --- clipboard -----------------------------------------------------------

    private fun handleClipboard(action: String, args: JSONObject, requestId: String?) {
        val clipboard = activity.getSystemService(ClipboardManager::class.java)
        when (action) {
            "set" -> clipboard.setPrimaryClip(
                ClipData.newPlainText("tempestroid", args.optString("text"))
            )
            "get" -> {
                val text = clipboard.primaryClip
                    ?.takeIf { it.itemCount > 0 }
                    ?.getItemAt(0)
                    ?.coerceToText(activity)
                    ?.toString()
                    ?: ""
                reply(requestId, true, data = JSONObject().put("text", text))
            }
            else -> reply(requestId, false, error = "unavailable")
        }
    }

    // --- storage (app-private files) ----------------------------------------

    private fun handleStorage(action: String, args: JSONObject, requestId: String?) {
        val name = args.optString("name")
        val file = File(activity.filesDir, name)
        try {
            when (action) {
                "write" -> {
                    file.parentFile?.mkdirs()
                    file.writeText(args.optString("content"))
                    reply(requestId, true, data = JSONObject())
                }
                "read" -> {
                    if (!file.exists()) {
                        reply(requestId, false, error = "not_found")
                    } else {
                        reply(requestId, true, data = JSONObject().put("content", file.readText()))
                    }
                }
                "delete" -> {
                    if (!file.exists()) {
                        reply(requestId, false, error = "not_found")
                    } else {
                        file.delete()
                        reply(requestId, true, data = JSONObject())
                    }
                }
                "list" -> {
                    val names = activity.filesDir.listFiles()?.map { it.name } ?: emptyList()
                    val files = JSONArray().apply { names.forEach { put(it) } }
                    reply(requestId, true, data = JSONObject().put("files", files))
                }
                else -> reply(requestId, false, error = "unavailable")
            }
        } catch (e: java.io.IOException) {
            reply(requestId, false, error = "io_error", message = e.message ?: "")
        }
    }

    // --- geolocation ---------------------------------------------------------

    private fun handleGeolocation(args: JSONObject, requestId: String?) {
        val command = JSONObject()
            .put("kind", "native").put("module", "geolocation")
            .put("action", "get_position").put("args", args)
        if (requestId != null) command.put("request_id", requestId)
        withPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION), requestId, command) {
            readSingleLocation(args.optBoolean("high_accuracy", true), requestId)
        }
    }

    @Suppress("MissingPermission")
    private fun readSingleLocation(highAccuracy: Boolean, requestId: String?) {
        val manager = activity.getSystemService(LocationManager::class.java)
        val provider = if (highAccuracy) LocationManager.GPS_PROVIDER
        else LocationManager.NETWORK_PROVIDER
        val deliver = { location: Location? ->
            if (location == null) {
                reply(requestId, false, error = "unavailable")
            } else {
                val data = JSONObject()
                    .put("latitude", location.latitude)
                    .put("longitude", location.longitude)
                    .put("accuracy", location.accuracy.toDouble())
                if (location.hasAltitude()) data.put("altitude", location.altitude)
                reply(requestId, true, data = data)
            }
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                manager.getCurrentLocation(
                    provider, null, activity.mainExecutor
                ) { location -> deliver(location) }
            } else {
                @Suppress("DEPRECATION")
                manager.requestSingleUpdate(
                    provider,
                    { location -> deliver(location) },
                    Looper.getMainLooper(),
                )
            }
        } catch (e: IllegalArgumentException) {
            reply(requestId, false, error = "unavailable", message = e.message ?: "")
        }
    }

    // --- camera --------------------------------------------------------------

    private fun handleCamera(command: JSONObject, requestId: String?) {
        withPermissions(arrayOf(Manifest.permission.CAMERA), requestId, command) {
            launchCamera(requestId)
        }
    }

    private fun launchCamera(requestId: String?) {
        if (requestId == null) return
        val dir = File(activity.filesDir, "photos").apply { mkdirs() }
        val file = File(dir, "photo_${pendingPhotoCounter++}.jpg")
        val uri = FileProvider.getUriForFile(
            activity, "${activity.packageName}.fileprovider", file
        )
        pendingPhoto = Pending(requestId, JSONObject())
        pendingPhotoFile = file
        takePicture.launch(uri)
    }

    private fun onPhotoResult(saved: Boolean) {
        val pending = pendingPhoto ?: return
        val file = pendingPhotoFile
        pendingPhoto = null
        pendingPhotoFile = null
        if (saved && file != null && file.exists()) {
            reply(pending.requestId, true, data = JSONObject().put("path", file.absolutePath))
        } else {
            reply(pending.requestId, false, error = "cancelled")
        }
    }

    // --- bluetooth -----------------------------------------------------------

    private fun handleBluetooth(args: JSONObject, requestId: String?) {
        val command = JSONObject()
            .put("kind", "native").put("module", "bluetooth")
            .put("action", "scan").put("args", args)
        if (requestId != null) command.put("request_id", requestId)
        withPermissions(bluetoothPermissions(), requestId, command) {
            startBluetoothScan((args.optDouble("timeout", 8.0) * 1000).toLong(), requestId)
        }
    }

    private fun bluetoothPermissions(): Array<String> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }

    @Suppress("MissingPermission")
    private fun startBluetoothScan(timeoutMs: Long, requestId: String?) {
        val adapter = activity.getSystemService(BluetoothManager::class.java)?.adapter
        if (adapter == null || !adapter.isEnabled) {
            reply(requestId, false, error = "unavailable")
            return
        }
        val found = JSONArray()
        val seen = mutableSetOf<String>()
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (intent.action != BluetoothDevice.ACTION_FOUND) return
                val device: BluetoothDevice? =
                    intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                val address = device?.address ?: return
                if (!seen.add(address)) return
                val entry = JSONObject().put("address", address).put("name", device.name ?: "")
                if (intent.hasExtra(BluetoothDevice.EXTRA_RSSI)) {
                    entry.put("rssi", intent.getShortExtra(BluetoothDevice.EXTRA_RSSI, 0).toInt())
                }
                found.put(entry)
            }
        }
        activity.registerReceiver(receiver, IntentFilter(BluetoothDevice.ACTION_FOUND))
        adapter.startDiscovery()
        Handler(Looper.getMainLooper()).postDelayed({
            adapter.cancelDiscovery()
            try {
                activity.unregisterReceiver(receiver)
            } catch (_: IllegalArgumentException) {
            }
            reply(requestId, true, data = JSONObject().put("devices", found))
        }, timeoutMs)
    }

    companion object {
        private const val TAG = "tempestroid"

        /** Must match `tempestroid.native.dispatch.NATIVE_RESULT_PREFIX`. */
        private const val NATIVE_RESULT_PREFIX = "__native_result__:"
        private const val WHATSAPP_PKG = "com.whatsapp"

        private var pendingPhotoCounter = 1
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
