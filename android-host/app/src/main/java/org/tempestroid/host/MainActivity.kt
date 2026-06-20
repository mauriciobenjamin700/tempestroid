package org.tempestroid.host

import android.Manifest
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Bundle
import android.system.Os
import android.util.Log
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.fragment.app.FragmentActivity
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalConfiguration
import kotlinx.coroutines.delay
import java.io.File
import org.json.JSONObject

/**
 * Map an app `theme_mode` (E9 Option B) to a Material [ColorScheme].
 *
 * The `theme_mode` rides every mount/patch envelope ([TempestTree.themeMode]):
 *  - `"dark"`  → [darkColorScheme] (forced, ignoring the OS),
 *  - `"light"` → [lightColorScheme] (forced, ignoring the OS),
 *  - `"system"` (the default, and any unknown value) → defer to [systemDark]
 *    (the OS dark-mode reading from `isSystemInDarkTheme()`).
 *
 * So a dark app under a light OS renders Material primitives (TextField, dropdown,
 * slider, surfaces) dark — matching the app — instead of the prior OS-only mismatch.
 *
 * Pure (no Android framework, no composition) so the JVM unit test pins it.
 *
 * @param themeMode the app's theme mode (`"light"` / `"dark"` / `"system"`).
 * @param systemDark whether the OS is in dark mode (the `"system"` fallback).
 * @return the Material color scheme to install.
 */
internal fun colorSchemeFor(themeMode: String, systemDark: Boolean): ColorScheme =
    when (themeMode) {
        "dark" -> darkColorScheme()
        "light" -> lightColorScheme()
        else -> if (systemDark) darkColorScheme() else lightColorScheme()
    }

/**
 * Host activity: extracts the bundled Python tree, boots the interpreter on a
 * background thread (never the UI thread → no ANR), and renders the widget tree
 * Python pushes over the bridge with Jetpack Compose (phase B4).
 *
 * Modelled on the CPython `Platforms/Android/testbed` MainActivity, with the
 * interpreter off the UI thread and a Compose renderer wired to the bridge.
 */
// FragmentActivity (not bare ComponentActivity) so androidx BiometricPrompt can
// host its dialog — it requires a FragmentActivity. FragmentActivity IS a
// ComponentActivity, so setContent/edge-to-edge/onBackPressedDispatcher are
// unaffected.
class MainActivity : FragmentActivity() {

    private val tree = TempestTree()

    /**
     * E3 device frame clock gate, as Compose snapshot state.
     *
     * Set from the `has_animations` flag every mount/patch envelope carries
     * (defaulting `false`). Because it is `mutableStateOf`, the `LaunchedEffect`
     * keyed on it restarts when the flag flips: `true` spins up a per-frame
     * `withFrameNanos` loop that fires the reserved [PythonRuntime.FRAME_TOKEN]
     * each frame; flipping back to `false` cancels that effect entirely, so the
     * host parks no coroutine and sends no frame traffic while idle (no
     * busy-loop). `PythonRuntime.needsFrames` is kept in sync for any non-Compose
     * reader, but this state is the one the renderer observes.
     */
    private var needsFrames by mutableStateOf(false)

    /**
     * Branded boot splash gate (assets-drawn, NOT the res SplashScreen API).
     *
     * Shown full-screen on the UI thread the instant the activity composes —
     * BEFORE/while CPython boots off-thread (~seconds of otherwise-blank screen) —
     * and kept up until the FIRST render arrives. "First render" is the first
     * message through [PythonRuntime.messageSink] (a `mount`, including the
     * on-device error screen from `run_device_error`, a `patch`, or a `native`
     * envelope): any of these means Python is alive and content is on its way, so
     * the splash dismisses. A timeout (see the splash composable) also dismisses
     * it so a failed boot never leaves the splash stuck.
     *
     * The splash image is `assets/tempest/splash.png` centered over the color in
     * `assets/tempest/splash_bg.txt` — stable zip paths the CLI `--fast` repackage
     * path swaps per app. Reading happens at runtime in [loadSplashBgColor] /
     * [setContent], so an app's custom splash needs no recompile.
     */
    private var splashVisible by mutableStateOf(true)

    /** Native capability router; registers its activity-result launchers here. */
    private lateinit var native: NativeModules

    /**
     * System-back handler (E0d). Disabled by default so the platform's default
     * back action (closing the activity) runs at the navigation root. It is
     * enabled/disabled from the `can_pop` flag Python reflects on every
     * mount/patch envelope; when enabled, a back press is forwarded to Python as
     * the reserved [BACK_TOKEN] event, which pops one navigation screen.
     */
    private val backCallback = object : OnBackPressedCallback(false) {
        override fun handleOnBackPressed() {
            PythonRuntime.dispatchEvent(BACK_TOKEN, "{}")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Register the system-back handler. It stays disabled until Python
        // reports a poppable stack (`can_pop`), so at the root the default
        // close-the-app behaviour runs (mirrors App.pop's root no-op).
        onBackPressedDispatcher.addCallback(this, backCallback)

        // Draw under the system bars so a `SafeArea` widget can inset against the
        // real `WindowInsets.safeDrawing`. Without this the system consumes those
        // insets and safeDrawing reports empty — content that opts out of SafeArea
        // therefore must place its own padding.
        enableEdgeToEdge()

        // Must be built during onCreate: it registers ActivityResultLaunchers,
        // which the framework forbids once the activity is STARTED.
        native = NativeModules(this)

        // Android only sets TMPDIR on API 33+; CPython expects it. Force the
        // overwrite (was `false`): a stale/empty inherited TMPDIR otherwise
        // sticks and `tempfile.gettempdir()` falls through to its non-writable
        // fallback list (/tmp, /var/tmp, …) and raises FileNotFoundError on the
        // app's first temp-dir use (serve bundle sweep, G4 model cache).
        Os.setenv("TMPDIR", cacheDir.absolutePath, true)

        val pythonHome = File(filesDir, "python")
        extractAssets("python", pythonHome)

        // Notifications need a runtime grant on API 33+ (phase B6).
        requestNotificationPermission()

        // Bridge -> host: route messages on the UI thread. `native` command
        // envelopes (B6) go to the capability modules; everything else
        // (mount/patch) updates the Compose tree. The sink fires from the
        // interpreter thread, so hop to the main thread first.
        PythonRuntime.messageSink = { json ->
            runOnUiThread {
                // First message from Python = the interpreter is alive and content
                // is rendering (mount/patch, the run_device_error screen, or a
                // native reply). Dismiss the boot splash to reveal the tree. Cheap
                // and idempotent — a no-op once already false.
                splashVisible = false
                val message = JSONObject(json)
                when (message.optString("kind")) {
                    "native" -> native.handle(message)
                    else -> {
                        // mount/patch envelopes carry `can_pop` (E0d): gate the
                        // system-back handler off the live navigation depth so a
                        // back press pops a screen only when one exists, else the
                        // default close-the-app action runs.
                        if (message.has("can_pop")) {
                            backCallback.isEnabled = message.optBoolean("can_pop", false)
                        }
                        // E3: gate the device frame clock off `has_animations`
                        // (default false). When true, the withFrameNanos loop below
                        // sends FRAME_TOKEN each frame so Python advances its
                        // animation controllers at the panel's refresh rate. The
                        // Python core also runs its own loop.call_later clock, so
                        // this is purely additive — absent flag → no frame traffic.
                        // Drive the Compose snapshot state (which keys the
                        // LaunchedEffect) and mirror it onto PythonRuntime for any
                        // non-Compose reader. This runs on the UI thread, so it is
                        // a safe snapshot write.
                        val animating = message.optBoolean("has_animations", false)
                        needsFrames = animating
                        PythonRuntime.needsFrames = animating
                        tree.apply(message)
                    }
                }
            }
        }

        setContent {
            // E9 dark mode (Option B): the active palette follows the APP's
            // `Theme.mode`, which Python re-sends as the `theme_mode` field on every
            // mount/patch envelope (TempestTree.themeMode, default "system"). The
            // host maps it to the Material color scheme via colorSchemeFor():
            // "dark"/"light" FORCE the scheme so Material primitives (TextField,
            // dropdown, slider, surfaces) match a dark/light app even under the
            // opposite OS theme; "system" (the default) defers to
            // isSystemInDarkTheme() — the prior OS-driven behaviour, now only the
            // fallback. A runtime App.set_theme pushes a patch with the new
            // theme_mode, flips this snapshot read, and recomposes the whole tree.
            // Material primitives pick up the scheme colors automatically; widgets
            // that declare an explicit Style.background/color still override per-node.
            //
            // The SYSTEM-mirror flow is preserved: when the OS dark mode flips, the
            // LaunchedEffect below notifies Python over THEME_TOKEN ({"mode":"system"})
            // so a `Theme.mode = SYSTEM` app rebuilds its theme-conditional tree.
            val systemDark = isSystemInDarkTheme()
            // RTL layout direction: Python mirrors padding/margin/text-align in the
            // serialized Style (to_compose(rtl=...)), so the box-model arrives already
            // flipped. The host still flips LocalLayoutDirection (in RenderNode) so
            // Compose orders children and aligns text RTL; the flag rides each node's
            // serialized props (`locale_rtl`) — absent → LTR (see gaps: not yet
            // emitted by the Python serializer).
            LaunchedEffect(systemDark) {
                // Mirror the OS dark-mode state to Python so a `Theme.mode = SYSTEM`
                // app rebuilds its theme-conditional tree on a system toggle. Rides
                // the existing event channel (no C/JNI change) under THEME_TOKEN.
                PythonRuntime.dispatchEvent(
                    THEME_TOKEN,
                    JSONObject().put("mode", "system").toString(),
                )
            }
            // E9 locale / RTL + MediaQuery: read the live device Configuration. Its
            // locale drives language/region, its layoutDirection drives RTL, and its
            // fontScale/screen dims feed the MediaQuery context. A config change
            // (system locale switch, font-size accessibility setting, rotation)
            // recomposes this, and the LaunchedEffect re-notifies Python under the
            // existing LOCALE_TOKEN channel so `App.set_locale` rebuilds RTL-aware
            // views. (MediaQuery push to Python has no routed `__media__` token yet —
            // see gaps; the host applies fontScale/RTL locally via Compose.)
            val configuration = LocalConfiguration.current
            val isRtl = configuration.layoutDirection == android.view.View.LAYOUT_DIRECTION_RTL
            val locale = remember(configuration) {
                @Suppress("DEPRECATION")
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                    configuration.locales[0]
                } else {
                    configuration.locale
                }
            }
            LaunchedEffect(locale, isRtl) {
                PythonRuntime.dispatchEvent(
                    LOCALE_TOKEN,
                    JSONObject()
                        .put("language", locale.language.ifEmpty { "und" })
                        .put("region", locale.country.takeIf { it.isNotEmpty() })
                        .put("rtl", isRtl)
                        .toString(),
                )
            }
            // Option B: derive the scheme from the app's theme_mode (snapshot
            // state, recomposes on a runtime App.set_theme patch), with the OS
            // dark-mode reading as the fallback only for the "system" mode.
            val colorScheme = colorSchemeFor(tree.themeMode, systemDark)
            MaterialTheme(colorScheme = colorScheme) {
                // The host draws edge-to-edge (enableEdgeToEdge above), so the
                // root content must inset itself off the system bars (status bar
                // top, navigation bar bottom, display cutout/notch) or it would
                // render under them — the SafeArea-by-default contract. We apply
                // safeDrawing on the Surface that wraps the whole tempestroid tree.
                //
                // This composes correctly with the explicit `SafeArea` widget:
                // Compose's windowInsetsPadding tracks *consumed* insets down the
                // tree, so a nested SafeArea (also using safeDrawing) sees the
                // insets already consumed here and adds zero — no double inset.
                // Likewise, overlays (E2) that escape this Surface via a separate
                // window (Dialog/ModalBottomSheet) get the full, un-consumed insets
                // and inset themselves independently — so they render OUTSIDE the
                // safeDrawing Surface, in the covering Box below, to avoid a double
                // inset (the M3 Dialog/Sheet manage their own WindowInsets).
                val onEvent: (String, String) -> Unit = { token, payload ->
                    PythonRuntime.dispatchEvent(token, payload)
                }
                // E3 device frame clock: while Python reports active animations
                // (`needsFrames`, set from `has_animations`), send the reserved
                // FRAME_TOKEN once per real display frame so Python's
                // `App._tick_from_device` advances its controllers at the panel's
                // native refresh rate. Keying the effect on `needsFrames` means the
                // loop only EXISTS while animations are active: flipping the flag
                // false cancels this coroutine (no parked frame callback, no bridge
                // traffic) — not a busy-loop. withFrameNanos parks until the next
                // display frame, so while active this paces exactly to vsync.
                LaunchedEffect(needsFrames) {
                    if (needsFrames) {
                        while (true) {
                            withFrameNanos { /* park until the next display frame */ }
                            PythonRuntime.dispatchEvent(PythonRuntime.FRAME_TOKEN, "{}")
                        }
                    }
                }
                Box(modifier = Modifier.fillMaxSize()) {
                    Surface(modifier = Modifier.fillMaxSize().safeDrawingPadding()) {
                        tree.root?.let { root -> RenderNode(root, onEvent) }
                    }
                    // The floating overlay layer, in ascending z-order. Each overlay
                    // node decides its own Compose surface (RenderOverlay) and owns
                    // its inset; do NOT wrap these in safeDrawingPadding.
                    tree.overlays.forEach { overlay -> RenderOverlay(overlay, onEvent) }

                    // Boot splash, top-most. Covers the whole window (edge-to-edge,
                    // no safe-area inset — a splash bleeds under the bars by design)
                    // while CPython boots, then fades out once the first render
                    // arrives (splashVisible -> false) or the timeout fires.
                    BootSplash(visible = splashVisible)
                }
            }
        }

        // Pick the Python entry point, in priority order:
        //   1. dev mode (B5): `tempest_dev_url` extra → code-push client.
        //        adb reverse tcp:8765 tcp:8765
        //        adb shell am start -n org.tempestroid.host/.MainActivity \
        //          --es tempest_dev_url http://127.0.0.1:8765
        //      (use 127.0.0.1, NOT localhost — MIUI does not resolve "localhost").
        //   2. packaged project (C): a `tempest_app_bundle.zip` asset embedded
        //      by `tempest build` (the whole multi-file tree) → extract + run.
        //   3. packaged app (legacy): a single `tempest_app.py` asset → run it.
        //   4. otherwise: the bundled demo.
        val devUrl = intent?.getStringExtra("tempest_dev_url")
        // Deep link (E0d): a `tempest_route` extra resolves to the initial
        // navigation stack via `routes_from_path`, so the app opens on the
        // linked screen with its back stack built. Pass it through to the file
        // loader as the `route` argument (App.reset under the hood).
        //   adb shell am start -n org.tempestroid.host/.MainActivity \
        //     --es tempest_route /details
        val route = intent?.getStringExtra("tempest_route")
        val routeArg = if (route != null) ", route='$route'" else ""

        // Env passthrough (G4 + general): a `tempest_env` extra carries
        // `KEY=VALUE` pairs (newline- or comma-separated) that are set in the
        // interpreter's `os.environ` BEFORE the app module imports — so an app
        // can read a launch-time config (e.g. VISIONSPIKE_MODEL_URL to switch the
        // G4 model-store from the embedded asset to a download) without a rebuild.
        //   adb shell am start -n org.tempestroid.host/.MainActivity \
        //     --es tempest_dev_url http://127.0.0.1:8765 \
        //     --es tempest_env 'VISIONSPIKE_MODEL_URL=http://127.0.0.1:8000/squeezenet1.1.onnx'
        // Only the reserved VISIONSPIKE_*/TEMPEST_* prefixes are honoured so an
        // intent cannot set arbitrary process env. Values are passed through a
        // single-quote-safe escape before being embedded in the `-c` source.
        val envPrelude = buildEnvPrelude(intent?.getStringExtra("tempest_env"), cacheDir.absolutePath)
        val entry = when {
            // Dev mode wins: poll the dev server and hot-reload over LAN.
            devUrl != null ->
                "from tempestroid.devserver.client import serve_device; " +
                    "serve_device('$devUrl')"
            // A `tempest build` APK bundles the user's whole project as this
            // zip asset; copy it out and run it via the bundle loader, which
            // extracts the tree onto sys.path (multi-file imports resolve).
            hasAsset(BUNDLED_APP_BUNDLE) -> {
                val bundleFile = File(filesDir, BUNDLED_APP_BUNDLE)
                extractAssets(BUNDLED_APP_BUNDLE, bundleFile)
                "from tempestroid.bridge.jni import run_device_bundle; " +
                    "run_device_bundle('${bundleFile.absolutePath}'$routeArg)"
            }
            // Legacy single-file `tempest build` APK: run the one `.py` asset.
            hasAsset(BUNDLED_APP_ASSET) -> {
                val appFile = File(filesDir, BUNDLED_APP_ASSET)
                extractAssets(BUNDLED_APP_ASSET, appFile)
                "from tempestroid.bridge.jni import run_device_file; " +
                    "run_device_file('${appFile.absolutePath}'$routeArg)"
            }
            // No bundled app and no dev URL: the built-in demo (B4/B6).
            else -> DEVICE_DEMO
        }

        // Boot Python off the UI thread (plan §3.4 "regra de ouro"). The entry
        // blocks in the asyncio loop, so the interpreter stays alive for events.
        // The env prelude (if any) runs first so launch-time config is visible to
        // the app module's import-time `os.environ` reads.
        val source = envPrelude + entry
        Thread({
            val rc = PythonRuntime.startPython(
                pythonHome.absolutePath,
                entryArgs = arrayOf("-c", source),
            )
            Log.i(TAG, "python exited rc=$rc")
        }, "tempest-python").start()
    }

    /**
     * Full-screen boot splash: `assets/tempest/splash.png` centered over the
     * `assets/tempest/splash_bg.txt` color. Fades out when [visible] flips false.
     *
     * Robustness: a [SPLASH_TIMEOUT_MS] watchdog flips [splashVisible] false so a
     * failed/slow boot never strands the splash. The bitmap + bg color are read
     * from assets at runtime (remembered once) — an app's custom splash needs no
     * recompile, only an asset swap.
     *
     * @param visible whether the splash should currently be shown.
     */
    @androidx.compose.runtime.Composable
    private fun BootSplash(visible: Boolean) {
        val bgColor = remember { loadSplashBgColor() }
        val splashBitmap = remember {
            try {
                assets.open(SPLASH_IMAGE_ASSET).use { BitmapFactory.decodeStream(it) }
            } catch (_: java.io.IOException) {
                null
            }
        }
        // Watchdog: dismiss after the timeout even if no render ever arrives.
        LaunchedEffect(Unit) {
            delay(SPLASH_TIMEOUT_MS)
            splashVisible = false
        }
        AnimatedVisibility(visible = visible, exit = fadeOut()) {
            Box(
                modifier = Modifier.fillMaxSize().background(bgColor),
                contentAlignment = Alignment.Center,
            ) {
                val bmp = splashBitmap
                if (bmp != null) {
                    Image(
                        bitmap = bmp.asImageBitmap(),
                        contentDescription = "tempestroid",
                        modifier = Modifier.fillMaxWidth(0.6f),
                    )
                }
            }
        }
    }

    /**
     * Read and parse the splash background color from
     * `assets/tempest/splash_bg.txt` (a single hex line like `#0b0f14`). Falls
     * back to [DEFAULT_SPLASH_BG] when the asset is missing or unparseable.
     */
    private fun loadSplashBgColor(): Color {
        val hex = try {
            assets.open(SPLASH_BG_ASSET).use { input ->
                input.readBytes().toString(Charsets.UTF_8).trim()
            }
        } catch (_: java.io.IOException) {
            ""
        }
        return parseHexColor(hex) ?: DEFAULT_SPLASH_BG
    }

    /**
     * Build a Python `os.environ` prelude from a `tempest_env` intent extra.
     *
     * The extra is a list of `KEY=VALUE` assignments separated by newlines or
     * commas (e.g. `VISIONSPIKE_MODEL_URL=http://127.0.0.1:8000/m.onnx`). Only
     * keys with the reserved `VISIONSPIKE_`/`TEMPEST_` prefixes are honoured, so a
     * launch intent cannot inject arbitrary process environment. Each value is
     * passed through Python's own `os.environ` assignment with a single-quote-safe
     * escape, then a trailing `;` so it prepends cleanly to the entry source.
     *
     * Always sets `TMPDIR` to [cacheDir] first: `android.system.Os.setenv` in
     * `onCreate` does not reliably reach the embedded interpreter's `os.environ`
     * (Python snapshots `environ` at init), so `tempfile.gettempdir()` would fall
     * through to its non-writable fallback list (`/tmp`, …) and raise
     * `FileNotFoundError` on the first temp-dir use (serve bundle extraction, the
     * G4 model cache). Setting it from inside the live interpreter is authoritative.
     *
     * @param raw the `tempest_env` extra (may be null/empty).
     * @param cacheDir the app cache dir to use as `TMPDIR` (always writable).
     * @return Python source that sets `TMPDIR` + the honoured vars.
     */
    private fun buildEnvPrelude(raw: String?, cacheDir: String): String {
        // Always pin TMPDIR to the writable app cache dir (see KDoc).
        val safeCache = cacheDir.replace("\\", "\\\\").replace("'", "\\'")
        val builder = StringBuilder("import os; os.environ['TMPDIR'] = '$safeCache'; ")
        if (raw.isNullOrBlank()) return builder.toString()
        for (pair in raw.split('\n', ',')) {
            val trimmed = pair.trim()
            if (trimmed.isEmpty()) continue
            val eq = trimmed.indexOf('=')
            if (eq <= 0) continue
            val key = trimmed.substring(0, eq).trim()
            if (!key.startsWith("VISIONSPIKE_") && !key.startsWith("TEMPEST_")) {
                Log.w(TAG, "tempest_env: ignoring non-reserved key '$key'")
                continue
            }
            val value = trimmed.substring(eq + 1).trim()
            // Embed as a Python single-quoted literal; escape backslash + quote.
            val safeKey = key.replace("\\", "\\\\").replace("'", "\\'")
            val safeValue = value.replace("\\", "\\\\").replace("'", "\\'")
            builder.append("os.environ['$safeKey'] = '$safeValue'; ")
        }
        return builder.toString()
    }

    /** Request POST_NOTIFICATIONS on API 33+ so the B6 demo can post. */
    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return
        }
        val granted = checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        if (!granted) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }

    /**
     * Copy an assets subtree to [dest], recreating empty dirs (asset packing
     * drops them) and reversing the build's ".gz" -> ".gz-" rename so stdlib
     * data files survive AAPT's auto-decompression.
     */
    private fun extractAssets(assetPath: String, dest: File) {
        val entries = assets.list(assetPath) ?: emptyArray()
        if (entries.isEmpty()) {
            // Leaf file: copy it, undoing the trailing "-" guard if present.
            val outName = if (assetPath.endsWith(".gz-")) assetPath.dropLast(1) else assetPath
            val outFile = File(dest.parentFile, File(outName).name)
            outFile.parentFile?.mkdirs()
            assets.open(assetPath).use { input ->
                outFile.outputStream().use { input.copyTo(it) }
            }
            return
        }
        dest.mkdirs()
        for (entry in entries) extractAssets("$assetPath/$entry", File(dest, stripGuard(entry)))
    }

    private fun stripGuard(name: String): String =
        if (name.endsWith(".gz-")) name.dropLast(1) else name

    /** True if [assetPath] exists as a packaged asset (file or non-empty dir). */
    private fun hasAsset(assetPath: String): Boolean = try {
        assets.open(assetPath).close()
        true
    } catch (_: java.io.IOException) {
        (assets.list(assetPath)?.isNotEmpty()) == true
    }

    companion object {
        private const val TAG = "tempestroid"

        /** Splash image asset (stable zip path the CLI `--fast` path swaps). */
        private const val SPLASH_IMAGE_ASSET = "tempest/splash.png"

        /** Splash background color asset: one hex line, e.g. `#0b0f14`. */
        private const val SPLASH_BG_ASSET = "tempest/splash_bg.txt"

        /** Fallback splash background when the asset is missing/unparseable. */
        private val DEFAULT_SPLASH_BG = Color(0xFF0B0F14)

        /**
         * Watchdog dismiss for the boot splash. A normal boot dismisses it far
         * sooner (on the first render); this only guards a failed/hung boot from
         * stranding the splash forever.
         */
        private const val SPLASH_TIMEOUT_MS = 20_000L

        /**
         * Parse `#RRGGBB` / `#AARRGGBB` (with or without the leading `#`) into a
         * Compose [Color]. Returns null on any malformed input so the caller can
         * fall back to a default.
         */
        private fun parseHexColor(raw: String): Color? {
            val hex = raw.trim().removePrefix("#")
            if (hex.length != 6 && hex.length != 8) return null
            return try {
                val parsed = hex.toLong(16)
                val argb = if (hex.length == 6) 0xFF000000L or parsed else parsed
                Color(argb.toInt())
            } catch (_: NumberFormatException) {
                null
            }
        }

        /**
         * Reserved event token Python routes straight to `App.pop` (E0d). Must
         * stay in sync with `tempestroid.bridge.protocol.BACK_TOKEN`. Forwarding
         * the system back press as this event needs no new JNI entry — it reuses
         * [PythonRuntime.dispatchEvent], the same channel widget taps use.
         */
        const val BACK_TOKEN = "__back__"

        /**
         * Reserved event token Python routes to `App.set_theme` (E9). The host
         * sends it (payload `{"mode": "light"|"dark"|"system"}`) when the OS dark
         * mode changes so a `Theme.mode = SYSTEM` app rebuilds its theme-conditional
         * tree. Rides the existing event channel — no new JNI entry. Must stay in
         * sync with `tempestroid.bridge.protocol.THEME_TOKEN`.
         */
        const val THEME_TOKEN = "__theme__"

        /**
         * Reserved event token Python routes to `App.set_locale` (E9). The host
         * sends it (payload `{"language", "region", "rtl"}`) when the device locale
         * / layout direction changes. Rides the existing event channel — no new JNI
         * entry. Must stay in sync with `tempestroid.bridge.protocol.LOCALE_TOKEN`.
         */
        const val LOCALE_TOKEN = "__locale__"

        /** Asset slot a legacy single-file `tempest build` APK stages into. */
        private const val BUNDLED_APP_ASSET = "tempest_app.py"

        /**
         * Asset slot a `tempest build` APK stages the user's whole project tree
         * into (a zip). The host copies it out and `run_device_bundle` extracts
         * it onto `sys.path`, so multi-file imports resolve. Takes priority over
         * the legacy single-file asset above.
         */
        private const val BUNDLED_APP_BUNDLE = "tempest_app_bundle.zip"

        /**
         * Device demo: a styled counter (B4) plus a "notify" button exercising
         * the native notifications capability (B6). Tapping runs the handler in
         * Python; "+" sends a patch back, "notify" sends a native command.
         */
        private val DEVICE_DEMO = """
            from dataclasses import dataclass
            from tempestroid import (
                App, Button, Color, Column, Edge, SafeArea, Style, Text, Widget,
                notify,
            )
            from tempestroid.bridge.jni import run_device

            @dataclass
            class State:
                n: int = 0

            def _inc(s: State) -> None:
                s.n += 1

            def _ping() -> None:
                notify("tempestroid", "native notification from Python")

            def view(app: App[State]) -> Widget:
                return SafeArea(
                    child=Column(
                        style=Style(
                            padding=Edge.all(24),
                            gap=16,
                            background=Color(r=245, g=245, b=250),
                        ),
                        children=[
                            Text(
                                content="count = " + str(app.state.n),
                                style=Style(font_size=28, color=Color(r=20, g=20, b=40)),
                            ),
                            Button(
                                label="increment",
                                on_click=lambda: app.set_state(_inc),
                            ),
                            Button(label="notify", on_click=_ping),
                        ],
                    ),
                )

            run_device(State(), view)
        """.trimIndent()
    }
}
