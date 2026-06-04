package org.tempestroid.host

import android.Manifest
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.system.Os
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawingPadding
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import java.io.File
import org.json.JSONObject

/**
 * Host activity: extracts the bundled Python tree, boots the interpreter on a
 * background thread (never the UI thread → no ANR), and renders the widget tree
 * Python pushes over the bridge with Jetpack Compose (phase B4).
 *
 * Modelled on the CPython `Platforms/Android/testbed` MainActivity, with the
 * interpreter off the UI thread and a Compose renderer wired to the bridge.
 */
class MainActivity : ComponentActivity() {

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

        // Android only sets TMPDIR on API 33+; CPython expects it.
        Os.setenv("TMPDIR", cacheDir.absolutePath, false)

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
            // E9 dark mode: the active palette follows the OS theme. Python tracks
            // `Theme.mode = SYSTEM` by default, so the host reflects the system
            // setting into the Material color scheme — a `darkColorScheme` /
            // `lightColorScheme` swap that recomposes the whole tree when the user
            // toggles dark mode. Material primitives (Button container/content,
            // Surface, TextField) pick up these colors automatically; widgets that
            // declare an explicit Style.background/color still override per-node.
            //
            // Divergence: theme cadence is OS-driven here (isSystemInDarkTheme),
            // NOT pushed from Python — the serializer emits no `theme_mode` envelope
            // field (Option B context, currently un-emitted; see gaps). When the
            // system flips, we additionally notify Python over the existing event
            // channel under THEME_TOKEN ({"mode":"system"}), which routes to
            // App.set_theme and rebuilds — so theme-conditional Python views react.
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
            val colorScheme = if (systemDark) darkColorScheme() else lightColorScheme()
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
        Thread({
            val rc = PythonRuntime.startPython(
                pythonHome.absolutePath,
                entryArgs = arrayOf("-c", entry),
            )
            Log.i(TAG, "python exited rc=$rc")
        }, "tempest-python").start()
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
