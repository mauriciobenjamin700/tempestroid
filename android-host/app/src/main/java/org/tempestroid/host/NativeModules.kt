package org.tempestroid.host

import android.Manifest
import android.app.Activity
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
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.location.Location
import android.location.LocationManager
import android.media.MediaMetadataRetriever
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
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

    /** The capture (photo or video) currently awaiting [captureLauncher], or null. */
    private var pendingCapture: Pending? = null
    private var pendingCaptureFile: File? = null
    private var pendingCaptureIsVideo = false

    /** Microphone recorder + speaker player (created on demand). */
    private var recorder: MediaRecorder? = null
    private var recorderFile: File? = null
    private var pendingAudio: Pending? = null
    private var player: MediaPlayer? = null

    /** Native commands gated on a runtime-permission grant, by request code. */
    private val pendingPermission = mutableMapOf<Int, Pending>()
    private var nextPermissionCode = 1000

    private val requestPermissions: ActivityResultLauncher<Array<String>> =
        activity.registerForActivityResult(
            ActivityResultContracts.RequestMultiplePermissions()
        ) { grants -> onPermissionResult(grants) }

    // A single result launcher backs both photo and video capture, so the camera
    // intent can carry the requested extras (facing / size / duration / quality).
    private val captureLauncher: ActivityResultLauncher<Intent> =
        activity.registerForActivityResult(
            ActivityResultContracts.StartActivityForResult()
        ) { result -> onCaptureResult(result.resultCode == Activity.RESULT_OK) }

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
            "audio" -> handleAudio(command, action, args, requestId)
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
        val action = command.optString("action")
        val args = command.optJSONObject("args") ?: JSONObject()
        // Video also records audio, so it needs the microphone permission too.
        val permissions =
            if (action == "record_video") {
                arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
            } else {
                arrayOf(Manifest.permission.CAMERA)
            }
        withPermissions(permissions, requestId, command) {
            launchCapture(action, args, requestId)
        }
    }

    private fun launchCapture(action: String, args: JSONObject, requestId: String?) {
        if (requestId == null) return
        val video = action == "record_video"
        val dir = File(activity.filesDir, if (video) "videos" else "photos")
        dir.mkdirs()
        val ext = if (video) "mp4" else "jpg"
        val file = File(dir, "capture_${pendingCaptureCounter++}.$ext")
        val uri = FileProvider.getUriForFile(
            activity, "${activity.packageName}.fileprovider", file
        )
        val intent = Intent(
            if (video) MediaStore.ACTION_VIDEO_CAPTURE else MediaStore.ACTION_IMAGE_CAPTURE
        ).apply {
            putExtra(MediaStore.EXTRA_OUTPUT, uri)
            addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            // Camera facing is a non-standard hint honored by some camera apps.
            if (args.optString("camera") == "front") {
                putExtra("android.intent.extras.CAMERA_FACING", 1)
                putExtra("android.intent.extras.LENS_FACING_FRONT", 1)
                putExtra("android.intent.extra.USE_FRONT_CAMERA", true)
            }
            if (video) {
                putExtra(
                    MediaStore.EXTRA_VIDEO_QUALITY,
                    if (args.optString("quality") == "low") 0 else 1,
                )
                if (!args.isNull("max_duration_s")) {
                    putExtra(MediaStore.EXTRA_DURATION_LIMIT, args.optInt("max_duration_s"))
                }
            }
        }
        if (intent.resolveActivity(activity.packageManager) == null) {
            reply(requestId, false, error = "unavailable", message = "no camera app")
            return
        }
        pendingCapture = Pending(requestId, args)
        pendingCaptureFile = file
        pendingCaptureIsVideo = video
        captureLauncher.launch(intent)
    }

    private fun onCaptureResult(saved: Boolean) {
        val pending = pendingCapture ?: return
        val file = pendingCaptureFile
        val video = pendingCaptureIsVideo
        val args = pending.command
        pendingCapture = null
        pendingCaptureFile = null
        if (!saved || file == null || !file.exists() || file.length() == 0L) {
            reply(pending.requestId, false, error = "cancelled")
            return
        }
        val data = if (video) videoData(file) else photoData(file, args)
        reply(pending.requestId, true, data = data)
    }

    /** Describe a captured video (path + duration + frame size) via metadata. */
    private fun videoData(file: File): JSONObject {
        val data = JSONObject().put("path", file.absolutePath)
        val mmr = MediaMetadataRetriever()
        try {
            mmr.setDataSource(file.absolutePath)
            mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                ?.toIntOrNull()?.let { data.put("duration_ms", it) }
            mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)
                ?.toIntOrNull()?.let { data.put("width", it) }
            mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)
                ?.toIntOrNull()?.let { data.put("height", it) }
        } catch (e: RuntimeException) {
            Log.w(TAG, "video metadata read failed: ${e.message}")
        } finally {
            mmr.release()
        }
        return data
    }

    /** Describe a captured photo, downscaling it in place to the size caps. */
    private fun photoData(file: File, args: JSONObject): JSONObject {
        val maxW = if (args.isNull("max_width")) 0 else args.optInt("max_width")
        val maxH = if (args.isNull("max_height")) 0 else args.optInt("max_height")
        var bitmap = BitmapFactory.decodeFile(file.absolutePath)
        if (bitmap != null && (maxW > 0 || maxH > 0)) {
            val scale = minOf(
                if (maxW > 0) maxW.toFloat() / bitmap.width else Float.MAX_VALUE,
                if (maxH > 0) maxH.toFloat() / bitmap.height else Float.MAX_VALUE,
            )
            if (scale < 1f) {
                val scaled = Bitmap.createScaledBitmap(
                    bitmap,
                    (bitmap.width * scale).toInt().coerceAtLeast(1),
                    (bitmap.height * scale).toInt().coerceAtLeast(1),
                    true,
                )
                file.outputStream().use {
                    scaled.compress(Bitmap.CompressFormat.JPEG, 90, it)
                }
                bitmap = scaled
            }
        }
        val data = JSONObject().put("path", file.absolutePath)
        if (bitmap != null) {
            data.put("width", bitmap.width).put("height", bitmap.height)
        }
        return data
    }

    // --- audio: microphone capture + speaker playback -----------------------

    private fun handleAudio(
        command: JSONObject,
        action: String,
        args: JSONObject,
        requestId: String?,
    ) {
        when (action) {
            "record_audio" ->
                withPermissions(
                    arrayOf(Manifest.permission.RECORD_AUDIO), requestId, command
                ) { startRecording(args, requestId) }
            "play_sound" -> playSound(args, requestId)
            "stop_sound" -> stopSound(requestId)
            else -> reply(requestId, false, error = "unavailable", message = "no $action")
        }
    }

    private fun startRecording(args: JSONObject, requestId: String?) {
        if (requestId == null) return
        val dir = File(activity.filesDir, "audio").apply { mkdirs() }
        val file = File(dir, "rec_${pendingCaptureCounter++}.m4a")
        @Suppress("DEPRECATION")
        val rec =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) MediaRecorder(activity)
            else MediaRecorder()
        try {
            rec.setAudioSource(MediaRecorder.AudioSource.MIC)
            rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            rec.setOutputFile(file.absolutePath)
            if (!args.isNull("max_duration_s")) {
                rec.setMaxDuration((args.optDouble("max_duration_s") * 1000).toInt())
                rec.setOnInfoListener { _, what, _ ->
                    if (what == MediaRecorder.MEDIA_RECORDER_INFO_MAX_DURATION_REACHED) {
                        finishRecording()
                    }
                }
            }
            rec.prepare()
            rec.start()
        } catch (e: Exception) {
            rec.release()
            reply(requestId, false, error = "unavailable", message = e.message ?: "")
            return
        }
        recorder = rec
        recorderFile = file
        pendingAudio = Pending(requestId, args)
    }

    /** Stop the active recording and reply with the saved clip. */
    private fun finishRecording() {
        val rec = recorder ?: return
        val file = recorderFile
        val pending = pendingAudio
        recorder = null
        recorderFile = null
        pendingAudio = null
        val durationMs = try {
            rec.stop()
            mediaDurationMs(file)
        } catch (_: RuntimeException) {
            null
        } finally {
            rec.release()
        }
        if (pending == null) return
        if (file != null && file.exists() && file.length() > 0L) {
            val data = JSONObject().put("path", file.absolutePath)
            if (durationMs != null) data.put("duration_ms", durationMs)
            reply(pending.requestId, true, data = data)
        } else {
            reply(pending.requestId, false, error = "unavailable")
        }
    }

    private fun mediaDurationMs(file: File?): Int? {
        if (file == null) return null
        val mmr = MediaMetadataRetriever()
        return try {
            mmr.setDataSource(file.absolutePath)
            mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toIntOrNull()
        } catch (_: RuntimeException) {
            null
        } finally {
            mmr.release()
        }
    }

    private fun playSound(args: JSONObject, requestId: String?) {
        player?.release()
        val volume = args.optDouble("volume", 1.0).toFloat().coerceIn(0f, 1f)
        try {
            val mp = MediaPlayer()
            mp.setDataSource(args.optString("src"))
            mp.setVolume(volume, volume)
            mp.setOnCompletionListener { it.release(); if (player === it) player = null }
            mp.prepare()
            mp.start()
            player = mp
            reply(requestId, true, data = JSONObject())
        } catch (e: Exception) {
            reply(requestId, false, error = "unavailable", message = e.message ?: "")
        }
    }

    private fun stopSound(requestId: String?) {
        player?.let {
            try {
                it.stop()
            } catch (_: IllegalStateException) {
            }
            it.release()
        }
        player = null
        reply(requestId, true, data = JSONObject())
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

        private var pendingCaptureCounter = 1
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
