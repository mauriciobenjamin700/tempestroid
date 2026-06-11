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
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.database.sqlite.SQLiteDatabase
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color as AndroidColor
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationManager
import android.media.MediaMetadataRetriever
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.MediaStore
import android.provider.Settings
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.Worker
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import java.util.concurrent.TimeUnit
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

    /** The host activity, exposed for feature source sets (camera/push). */
    internal val hostActivity: ComponentActivity get() = activity

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
            // Gated by the `camera` feature: real impl in src/feat_camera, stub
            // (replies feature_not_built) in src/stub_camera. Same signature.
            "camera" -> handleCamera(this, command, requestId)
            "audio" -> handleAudio(command, action, args, requestId)
            "bluetooth" -> handleBluetooth(args, requestId)
            "haptics" -> handleHaptics(action, args)
            "sensors" -> handleSensors(action, args)
            "system" -> handleSystem(action, args, requestId)
            "lifecycle" -> handleLifecycle(action, args)
            "permissions" -> handlePermissionsModule(action, args, requestId)
            "biometrics" -> handleBiometrics(action, args, requestId)
            "secure_storage" -> handleSecureStorage(action, args, requestId)
            "prefs" -> handlePrefs(action, args, requestId)
            "database" -> handleDatabase(action, args, requestId)
            "connectivity" -> handleConnectivity(action, args, requestId)
            // Gated by the `push` feature: real impl (FirebaseMessaging) in
            // src/feat_push, stub (replies feature_not_built) in src/stub_push.
            "push" -> handlePush(this, action, args, requestId)
            "background" -> handleBackground(action, args)
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
    internal fun reply(
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
    internal fun withPermissions(
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

    // --- camera capture plumbing ---------------------------------------------
    // The dispatch entry `handleCamera` is feature-gated (src/feat_camera vs
    // src/stub_camera); the capture plumbing below stays in src/main since it
    // references no heavy dependency (system camera intent + FileProvider from
    // androidx.core), and is only ever reached via the real feat_camera path.

    internal fun launchCapture(action: String, args: JSONObject, requestId: String?) {
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
        val data = JSONObject().put("path", file.absolutePath)
        val maxW = if (args.isNull("max_width")) 0 else args.optInt("max_width")
        val maxH = if (args.isNull("max_height")) 0 else args.optInt("max_height")
        if (maxW <= 0 && maxH <= 0) {
            // No size caps: read just the JPEG header bounds (no full bitmap in
            // memory) to report width/height.
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(file.absolutePath, bounds)
            if (bounds.outWidth > 0 && bounds.outHeight > 0) {
                data.put("width", bounds.outWidth).put("height", bounds.outHeight)
            }
            return data
        }
        val bitmap = BitmapFactory.decodeFile(file.absolutePath) ?: return data
        val scale = minOf(
            if (maxW > 0) maxW.toFloat() / bitmap.width else Float.MAX_VALUE,
            if (maxH > 0) maxH.toFloat() / bitmap.height else Float.MAX_VALUE,
        )
        val out =
            if (scale < 1f) {
                Bitmap.createScaledBitmap(
                    bitmap,
                    (bitmap.width * scale).toInt().coerceAtLeast(1),
                    (bitmap.height * scale).toInt().coerceAtLeast(1),
                    true,
                ).also { scaled ->
                    file.outputStream().use {
                        scaled.compress(Bitmap.CompressFormat.JPEG, 90, it)
                    }
                }
            } else {
                bitmap
            }
        return data.put("width", out.width).put("height", out.height)
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

    // === E8: platform + system native =======================================

    // --- haptics (fire-and-forget) ------------------------------------------

    /**
     * Vibrate via the [Vibrator]. `vibrate` carries an explicit `duration_ms`;
     * `impact` maps a Haptics impact style to a short canned duration. API 26+
     * uses [VibrationEffect.createOneShot]; older devices fall back to the
     * deprecated `vibrate(ms)`.
     */
    private fun handleHaptics(action: String, args: JSONObject) {
        val durationMs = when (action) {
            "vibrate" -> args.optInt("duration_ms", 50).toLong()
            "impact" -> when (args.optString("style")) {
                "light" -> 20L
                "heavy" -> 80L
                else -> 40L // medium
            }
            else -> {
                Log.w(TAG, "unknown haptics action: $action")
                return
            }
        }
        val vibrator = vibrator() ?: return
        if (!vibrator.hasVibrator()) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(
                VibrationEffect.createOneShot(durationMs, VibrationEffect.DEFAULT_AMPLITUDE)
            )
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(durationMs)
        }
    }

    private fun vibrator(): Vibrator? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            activity.getSystemService(VibratorManager::class.java)?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            activity.getSystemService(Vibrator::class.java)
        }

    // --- system (statusbar / brightness / wakelock / orientation) -----------

    /**
     * System surface controls. Setters are fire-and-forget; `get_brightness` is
     * request/response. Status-bar visibility uses the window insets controller;
     * brightness reads `Settings.System.SCREEN_BRIGHTNESS` (normalised to
     * `[0,1]`); keep-awake toggles `FLAG_KEEP_SCREEN_ON`; orientation sets
     * `requestedOrientation`.
     */
    private fun handleSystem(action: String, args: JSONObject, requestId: String?) {
        when (action) {
            "set_status_bar" -> setStatusBar(args)
            "get_brightness" -> reply(
                requestId, true,
                data = JSONObject().put("value", currentBrightness().toDouble()),
            )
            "set_brightness" -> activity.runOnUiThread {
                val value = args.optDouble("value", 1.0).toFloat().coerceIn(0f, 1f)
                val params = activity.window.attributes
                params.screenBrightness = value
                activity.window.attributes = params
            }
            "keep_awake" -> activity.runOnUiThread {
                if (args.optBoolean("enabled", false)) {
                    activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                } else {
                    activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                }
            }
            "set_orientation" -> activity.runOnUiThread {
                activity.requestedOrientation = when (args.optString("orientation")) {
                    "portrait" -> ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
                    "landscape" -> ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
                    else -> ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
                }
            }
            else -> reply(requestId, false, error = "unavailable", message = "no $action")
        }
    }

    private fun setStatusBar(args: JSONObject) = activity.runOnUiThread {
        val window = activity.window
        if (!args.isNull("hidden")) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                val controller = window.insetsController
                if (args.optBoolean("hidden")) {
                    controller?.hide(android.view.WindowInsets.Type.statusBars())
                } else {
                    controller?.show(android.view.WindowInsets.Type.statusBars())
                }
            } else {
                @Suppress("DEPRECATION")
                if (args.optBoolean("hidden")) {
                    window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
                } else {
                    window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
                }
            }
        }
        if (!args.isNull("color")) {
            runCatching {
                @Suppress("DEPRECATION")
                window.statusBarColor = AndroidColor.parseColor(args.optString("color"))
            }
        }
    }

    private fun currentBrightness(): Float {
        // Prefer the window-level override; fall back to the system setting.
        val windowValue = activity.window.attributes.screenBrightness
        if (windowValue in 0f..1f) return windowValue
        val raw = Settings.System.getInt(
            activity.contentResolver, Settings.System.SCREEN_BRIGHTNESS, 128
        )
        return (raw / 255f).coerceIn(0f, 1f)
    }

    // --- sensors (stream via reserved __sensor__:<type> token) --------------

    /**
     * Start/stop a sensor stream. `start` registers a [SensorEventListener] for
     * the named sensor; each `onSensorChanged` forwards a `{sensor, values,
     * timestamp_ms}` payload to Python over the reserved
     * `"__sensor__:<type>"` event token (no new JNI/C entry). `stop` unregisters.
     */
    private fun handleSensors(action: String, args: JSONObject) {
        val sensorName = args.optString("sensor")
        val manager = activity.getSystemService(SensorManager::class.java) ?: return
        val type = sensorTypeOf(sensorName)
        if (type == null) {
            Log.w(TAG, "unknown sensor type: $sensorName")
            return
        }
        when (action) {
            "start" -> {
                if (sensorListeners.containsKey(sensorName)) return
                val sensor = manager.getDefaultSensor(type) ?: run {
                    Log.w(TAG, "no sensor for $sensorName")
                    return
                }
                val rateMs = args.optInt("rate_ms", 100)
                val listener = object : SensorEventListener {
                    override fun onSensorChanged(event: SensorEvent) {
                        val values = JSONArray()
                        event.values.forEach { values.put(it.toDouble()) }
                        val payload = JSONObject()
                            .put("sensor", sensorName)
                            .put("values", values)
                            .put("timestamp_ms", event.timestamp / 1_000_000L)
                        PythonRuntime.dispatchEvent(
                            "$SENSOR_TOKEN_PREFIX:$sensorName", payload.toString()
                        )
                    }

                    override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) {}
                }
                sensorListeners[sensorName] = listener
                manager.registerListener(listener, sensor, rateMs * 1000)
            }
            "stop" -> {
                sensorListeners.remove(sensorName)?.let { manager.unregisterListener(it) }
            }
            else -> Log.w(TAG, "unknown sensors action: $action")
        }
    }

    private fun sensorTypeOf(name: String): Int? = when (name) {
        "accelerometer" -> Sensor.TYPE_ACCELEROMETER
        "gyroscope" -> Sensor.TYPE_GYROSCOPE
        "magnetometer" -> Sensor.TYPE_MAGNETIC_FIELD
        "pressure" -> Sensor.TYPE_PRESSURE
        "light" -> Sensor.TYPE_LIGHT
        "proximity" -> Sensor.TYPE_PROXIMITY
        "step_counter" -> Sensor.TYPE_STEP_COUNTER
        else -> null
    }

    // --- lifecycle (stream via reserved __lifecycle__ token) ----------------

    /**
     * Start/stop the app-wide lifecycle stream. `start` attaches a
     * [DefaultLifecycleObserver] to [ProcessLifecycleOwner]; `onResume` →
     * `"foreground"`, `onPause` → `"background"`. Each transition forwards a
     * `{state}` payload to Python over the reserved [LIFECYCLE_TOKEN].
     */
    private fun handleLifecycle(action: String, @Suppress("UNUSED_PARAMETER") args: JSONObject) {
        when (action) {
            "start" -> activity.runOnUiThread {
                if (lifecycleObserver != null) return@runOnUiThread
                val observer = object : DefaultLifecycleObserver {
                    override fun onResume(owner: LifecycleOwner) = emitLifecycle("foreground")
                    override fun onPause(owner: LifecycleOwner) = emitLifecycle("background")
                }
                lifecycleObserver = observer
                ProcessLifecycleOwner.get().lifecycle.addObserver(observer)
            }
            "stop" -> activity.runOnUiThread {
                lifecycleObserver?.let {
                    ProcessLifecycleOwner.get().lifecycle.removeObserver(it)
                }
                lifecycleObserver = null
            }
            else -> Log.w(TAG, "unknown lifecycle action: $action")
        }
    }

    private fun emitLifecycle(state: String) {
        PythonRuntime.dispatchEvent(
            LIFECYCLE_TOKEN, JSONObject().put("state", state).toString()
        )
    }

    // --- permissions (request/response) -------------------------------------

    /**
     * Request or check a single runtime permission. `check` replies the current
     * grant; `request` either replies immediately (already granted) or launches
     * the system prompt via the shared [withPermissions] flow and replies once
     * the user responds.
     */
    private fun handlePermissionsModule(
        action: String,
        args: JSONObject,
        requestId: String?,
    ) {
        val permission = args.optString("permission")
        when (action) {
            "check" -> reply(
                requestId, true,
                data = JSONObject().put("status", statusOf(permission)),
            )
            "request" -> {
                if (hasPermission(permission)) {
                    reply(requestId, true, data = JSONObject().put("status", "granted"))
                    return
                }
                val command = JSONObject()
                    .put("kind", "native").put("module", "permissions")
                    .put("action", "check").put("args", args)
                if (requestId != null) command.put("request_id", requestId)
                withPermissions(arrayOf(permission), requestId, command) {
                    reply(requestId, true, data = JSONObject().put("status", "granted"))
                }
            }
            else -> reply(requestId, false, error = "unavailable", message = "no $action")
        }
    }

    private fun statusOf(permission: String): String =
        if (hasPermission(permission)) "granted" else "denied"

    // --- biometrics (request/response) --------------------------------------

    /**
     * Prompt for biometric authentication ([BiometricPrompt]). Replies
     * `{authenticated: true}` on success, `{authenticated: false, error: ...}`
     * on a non-fatal failure/cancel, or `error="unavailable"` when no biometric
     * hardware/enrolment exists.
     */
    private fun handleBiometrics(action: String, args: JSONObject, requestId: String?) {
        if (action != "authenticate") {
            reply(requestId, false, error = "unavailable", message = "no $action")
            return
        }
        // BiometricPrompt requires a FragmentActivity host. The tempestroid host
        // activity is a ComponentActivity; if it is not (also) a FragmentActivity,
        // report unavailable rather than crash. Hosting the prompt is a documented
        // device pendency (would need MainActivity to extend FragmentActivity).
        val fragmentActivity = activity as? androidx.fragment.app.FragmentActivity
        if (fragmentActivity == null) {
            reply(
                requestId, true,
                data = JSONObject().put("authenticated", false).put("error", "unavailable"),
            )
            return
        }
        activity.runOnUiThread {
            val manager = BiometricManager.from(activity)
            val authenticators = BiometricManager.Authenticators.BIOMETRIC_WEAK
            if (manager.canAuthenticate(authenticators) != BiometricManager.BIOMETRIC_SUCCESS) {
                reply(
                    requestId, true,
                    data = JSONObject().put("authenticated", false).put("error", "unavailable"),
                )
                return@runOnUiThread
            }
            val prompt = BiometricPrompt(
                fragmentActivity,
                activity.mainExecutor,
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(
                        result: BiometricPrompt.AuthenticationResult,
                    ) {
                        reply(requestId, true, data = JSONObject().put("authenticated", true))
                    }

                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                        reply(
                            requestId, true,
                            data = JSONObject()
                                .put("authenticated", false)
                                .put("error", errString.toString()),
                        )
                    }

                    override fun onAuthenticationFailed() {
                        // A single non-matching attempt; the prompt stays open, so
                        // do not reply here (wait for success or error/cancel).
                    }
                },
            )
            val reason = args.optString("reason").ifEmpty { "Authenticate" }
            val info = BiometricPrompt.PromptInfo.Builder()
                .setTitle(reason)
                .setNegativeButtonText("Cancel")
                .setAllowedAuthenticators(authenticators)
                .build()
            prompt.authenticate(info)
        }
    }

    // --- secure storage (EncryptedSharedPreferences) ------------------------

    /** `get` is request/response; `set`/`delete` are fire-and-forget. */
    private fun handleSecureStorage(action: String, args: JSONObject, requestId: String?) {
        val prefs = try {
            securePrefs()
        } catch (e: Exception) {
            reply(requestId, false, error = "unavailable", message = e.message ?: "")
            return
        }
        when (action) {
            "get" -> {
                val value = prefs.getString(args.optString("key"), null)
                val data = JSONObject()
                if (value != null) data.put("value", value)
                reply(requestId, true, data = data)
            }
            "set" -> prefs.edit().putString(args.optString("key"), args.optString("value")).apply()
            "delete" -> prefs.edit().remove(args.optString("key")).apply()
            else -> reply(requestId, false, error = "unavailable", message = "no $action")
        }
    }

    private fun securePrefs(): android.content.SharedPreferences {
        val masterKey = MasterKey.Builder(activity)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            activity,
            "tempestroid_secure",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    // --- prefs (plain SharedPreferences) ------------------------------------

    /**
     * Key-value preferences. Values cross the bridge as JSON, so a `set` stashes
     * the raw JSON text and `get`/`get_all` parse it back — preserving non-string
     * types (numbers, bools, lists) round-trip.
     */
    private fun handlePrefs(action: String, args: JSONObject, requestId: String?) {
        val prefs = activity.getSharedPreferences("tempestroid_prefs", Context.MODE_PRIVATE)
        when (action) {
            "get" -> {
                val key = args.optString("key")
                val data = JSONObject()
                if (prefs.contains(key)) {
                    data.put("value", decodePref(prefs.getString(key, null)))
                }
                reply(requestId, true, data = data)
            }
            "get_all" -> {
                val values = JSONObject()
                prefs.all.forEach { (key, raw) ->
                    values.put(key, decodePref(raw as? String))
                }
                reply(requestId, true, data = JSONObject().put("values", values))
            }
            "set" -> {
                // The value rides as JSON under `value`; store its JSON text so the
                // type survives the round-trip.
                val encoded = JSONObject().put("v", args.opt("value")).toString()
                prefs.edit().putString(args.optString("key"), encoded).apply()
            }
            "delete" -> prefs.edit().remove(args.optString("key")).apply()
            else -> reply(requestId, false, error = "unavailable", message = "no $action")
        }
    }

    /** Reverse [handlePrefs]'s JSON-text encoding back to the stored value. */
    private fun decodePref(raw: String?): Any? {
        if (raw == null) return JSONObject.NULL
        return runCatching { JSONObject(raw).opt("v") }.getOrNull() ?: JSONObject.NULL
    }

    // --- database (SQLite) --------------------------------------------------

    /**
     * Run SQL against the app-private SQLite database. `execute` runs one
     * statement and replies `{columns, rows}` (rows as a list of value lists);
     * `execute_many` batches a statement over a list of parameter tuples in a
     * transaction. Parameters arrive as JSON arrays and bind positionally.
     */
    private fun handleDatabase(action: String, args: JSONObject, requestId: String?) {
        val db = try {
            openDatabase()
        } catch (e: Exception) {
            reply(requestId, false, error = "io_error", message = e.message ?: "")
            return
        }
        try {
            when (action) {
                "execute" -> reply(
                    requestId, true,
                    data = runQuery(db, args.optString("sql"), args.optJSONArray("params")),
                )
                "execute_many" -> {
                    val sql = args.optString("sql")
                    val batch = args.optJSONArray("params_list") ?: JSONArray()
                    db.beginTransaction()
                    try {
                        for (i in 0 until batch.length()) {
                            db.execSQL(sql, bindArgs(batch.optJSONArray(i)))
                        }
                        db.setTransactionSuccessful()
                    } finally {
                        db.endTransaction()
                    }
                    reply(requestId, true, data = JSONObject())
                }
                else -> reply(requestId, false, error = "unavailable", message = "no $action")
            }
        } catch (e: Exception) {
            reply(requestId, false, error = "sql_error", message = e.message ?: "")
        } finally {
            db.close()
        }
    }

    private fun openDatabase(): SQLiteDatabase {
        val file = File(activity.filesDir, "app.db")
        return SQLiteDatabase.openOrCreateDatabase(file, null)
    }

    /** Run one SQL statement, returning a `{columns, rows}` result object. */
    private fun runQuery(db: SQLiteDatabase, sql: String, params: JSONArray?): JSONObject {
        val trimmed = sql.trimStart().lowercase()
        val isSelect = trimmed.startsWith("select") || trimmed.startsWith("pragma") ||
            trimmed.startsWith("with")
        if (!isSelect) {
            db.execSQL(sql, bindArgs(params))
            return JSONObject().put("columns", JSONArray()).put("rows", JSONArray())
        }
        val selectionArgs = (params ?: JSONArray()).let { arr ->
            Array(arr.length()) { arr.opt(it)?.toString() ?: "" }
        }
        val cursor = db.rawQuery(sql, selectionArgs)
        val columns = JSONArray()
        cursor.columnNames.forEach { columns.put(it) }
        val rows = JSONArray()
        cursor.use {
            while (it.moveToNext()) {
                val row = JSONArray()
                for (c in 0 until it.columnCount) {
                    when (it.getType(c)) {
                        android.database.Cursor.FIELD_TYPE_NULL -> row.put(JSONObject.NULL)
                        android.database.Cursor.FIELD_TYPE_INTEGER -> row.put(it.getLong(c))
                        android.database.Cursor.FIELD_TYPE_FLOAT -> row.put(it.getDouble(c))
                        else -> row.put(it.getString(c))
                    }
                }
                rows.put(row)
            }
        }
        return JSONObject().put("columns", columns).put("rows", rows)
    }

    /** Bind a JSON params array to the positional-arg `Array<Any?>` execSQL wants. */
    private fun bindArgs(params: JSONArray?): Array<Any?> {
        if (params == null) return emptyArray()
        return Array(params.length()) { params.opt(it).takeIf { v -> v != JSONObject.NULL } }
    }

    // --- connectivity (request/response + stream) ---------------------------

    /**
     * `get` replies the current network state once; `start`/`stop` open/close a
     * default-network callback that forwards each change to Python over the
     * reserved `"__connectivity__:<state>"` event token.
     */
    private fun handleConnectivity(action: String, args: JSONObject, requestId: String?) {
        val manager = activity.getSystemService(ConnectivityManager::class.java)
        if (manager == null) {
            reply(requestId, false, error = "unavailable")
            return
        }
        when (action) {
            "get" -> reply(
                requestId, true,
                data = JSONObject().put("state", connectivityState(manager)),
            )
            "start" -> {
                if (networkCallback != null) return
                val callback = object : ConnectivityManager.NetworkCallback() {
                    override fun onAvailable(network: Network) = emitConnectivity(manager)
                    override fun onLost(network: Network) {
                        PythonRuntime.dispatchEvent(
                            "$CONNECTIVITY_TOKEN_PREFIX:disconnected",
                            JSONObject().put("state", "disconnected").toString(),
                        )
                    }

                    override fun onCapabilitiesChanged(
                        network: Network,
                        caps: NetworkCapabilities,
                    ) = emitConnectivity(manager)
                }
                networkCallback = callback
                manager.registerDefaultNetworkCallback(callback)
            }
            "stop" -> {
                networkCallback?.let { manager.unregisterNetworkCallback(it) }
                networkCallback = null
            }
            else -> reply(requestId, false, error = "unavailable", message = "no $action")
        }
    }

    private fun emitConnectivity(manager: ConnectivityManager) {
        val state = connectivityState(manager)
        PythonRuntime.dispatchEvent(
            "$CONNECTIVITY_TOKEN_PREFIX:$state",
            JSONObject().put("state", state).toString(),
        )
    }

    /** Resolve the active default network to a tempestroid connectivity state. */
    private fun connectivityState(manager: ConnectivityManager): String {
        val network = manager.activeNetwork ?: return "disconnected"
        val caps = manager.getNetworkCapabilities(network) ?: return "disconnected"
        if (!caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) {
            return "disconnected"
        }
        return when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "mobile"
            else -> "connected"
        }
    }

    // The `push` dispatch entry `handlePush` is feature-gated (src/feat_push vs
    // src/stub_push). Both call back into the shared NotificationModule for the
    // fire-and-forget `schedule_notification` action.

    // --- background (WorkManager) -------------------------------------------

    /**
     * Schedule/cancel a unique periodic background task via [WorkManager].
     * Fire-and-forget. The work is a stub [PeriodicWorkRequestBuilder] over a
     * no-op worker — wiring a real worker that re-enters Python is a documented
     * device pendency. Periodic work clamps to a 15-minute minimum interval.
     */
    private fun handleBackground(action: String, args: JSONObject) {
        val workManager = WorkManager.getInstance(activity)
        val name = args.optString("name")
        when (action) {
            "schedule" -> {
                // The task name rides as input data so the worker knows which
                // handler to dispatch when it fires.
                val data = workDataOf("name" to name)
                if (args.isNull("interval_s")) {
                    // One-shot: runs as soon as constraints allow (≈ immediately).
                    val request = OneTimeWorkRequestBuilder<TempestBackgroundWorker>()
                        .setInputData(data)
                        .build()
                    workManager.enqueueUniqueWork(
                        name,
                        androidx.work.ExistingWorkPolicy.REPLACE,
                        request,
                    )
                } else {
                    // Periodic: WorkManager clamps the interval to a 15-min minimum.
                    val intervalMin =
                        (args.optDouble("interval_s", 15.0 * 60) / 60).toLong()
                            .coerceAtLeast(15)
                    val request = PeriodicWorkRequestBuilder<TempestBackgroundWorker>(
                        intervalMin, TimeUnit.MINUTES
                    ).setInputData(data).build()
                    workManager.enqueueUniquePeriodicWork(
                        name,
                        androidx.work.ExistingPeriodicWorkPolicy.UPDATE,
                        request,
                    )
                }
            }
            "cancel" -> workManager.cancelUniqueWork(name)
            else -> Log.w(TAG, "unknown background action: $action")
        }
    }

    // --- E8 stream state ----------------------------------------------------

    /** Open sensor listeners, keyed by sensor name (for `stop`/teardown). */
    private val sensorListeners = mutableMapOf<String, SensorEventListener>()

    /** The active process-lifecycle observer, or null when the stream is off. */
    private var lifecycleObserver: DefaultLifecycleObserver? = null

    /** The active default-network callback, or null when the stream is off. */
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    companion object {
        private const val TAG = "tempestroid"

        /** Must match `tempestroid.native.dispatch.NATIVE_RESULT_PREFIX`. */
        private const val NATIVE_RESULT_PREFIX = "__native_result__:"
        private const val WHATSAPP_PKG = "com.whatsapp"

        /** Reserved stream tokens — must match `tempestroid.bridge.protocol`. */
        private const val SENSOR_TOKEN_PREFIX = "__sensor__"
        private const val LIFECYCLE_TOKEN = "__lifecycle__"
        private const val CONNECTIVITY_TOKEN_PREFIX = "__connectivity__"

        private var pendingCaptureCounter = 1
    }
}

/** Native notifications: posts a system notification via NotificationManager. */
internal object NotificationModule {

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

/**
 * Worker for the E8 BackgroundModule that re-enters Python when a scheduled task
 * fires. Two paths, chosen by interpreter liveness:
 *
 * * **App alive** (`PythonRuntime.isPythonInitialized()`): dispatch the reserved
 *   `__background__:<name>` token into the live interpreter, which runs the
 *   handler registered with `on_background_task` on its asyncio loop.
 * * **Process woken from dead**: boot a fresh short-lived interpreter and call
 *   `run_device_background(<bundle>, <name>)`, which extracts the already-staged
 *   project bundle, registers the app's handlers, runs the named task to
 *   completion, then finalizes. Uses `filesDir/python` + the bundle that the
 *   first app launch already extracted (scheduling requires a prior launch).
 */
class TempestBackgroundWorker(context: Context, params: WorkerParameters) :
    Worker(context, params) {
    override fun doWork(): Result {
        val name = inputData.getString("name").orEmpty()
        if (name.isEmpty()) {
            return Result.success()
        }
        if (PythonRuntime.isPythonInitialized()) {
            // App alive: hand the fired task to the running interpreter.
            PythonRuntime.dispatchEvent("__background__:$name", "{}")
            return Result.success()
        }
        // Dead process: boot a fresh interpreter to run the task. Both the
        // CPython home and the app bundle were extracted by the launch that
        // scheduled the task, so they persist in filesDir.
        val home = File(applicationContext.filesDir, "python")
        val bundle = File(applicationContext.filesDir, "tempest_app_bundle.zip")
        if (!home.isDirectory || !bundle.isFile) {
            Log.w("tempestroid", "background '$name': runtime/bundle not extracted yet")
            return Result.success()
        }
        val code = "from tempestroid.native.background import run_device_background; " +
            "run_device_background('${bundle.absolutePath}', '$name')"
        val rc = PythonRuntime.startPython(home.absolutePath, arrayOf("-c", code))
        Log.i("tempestroid", "background '$name' fresh-boot exited rc=$rc")
        return Result.success()
    }
}

