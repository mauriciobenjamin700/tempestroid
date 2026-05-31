package org.tempestroid.host

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.system.Os
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
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

    /** Native capability router; registers its activity-result launchers here. */
    private lateinit var native: NativeModules

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

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
                if (message.optString("kind") == "native") {
                    native.handle(message)
                } else {
                    tree.apply(message)
                }
            }
        }

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    tree.root?.let { root ->
                        RenderNode(root) { token, payload ->
                            PythonRuntime.dispatchEvent(token, payload)
                        }
                    }
                }
            }
        }

        // Pick the Python entry point, in priority order:
        //   1. dev mode (B5): `tempest_dev_url` extra → code-push client.
        //        adb reverse tcp:8765 tcp:8765
        //        adb shell am start -n org.tempestroid.host/.MainActivity \
        //          --es tempest_dev_url http://localhost:8765
        //   2. packaged app (C): a `tempest_app.py` asset embedded by
        //      `tempest build` → load + run it.
        //   3. otherwise: the bundled demo.
        val devUrl = intent?.getStringExtra("tempest_dev_url")
        val entry = when {
            // Dev mode wins: poll the dev server and hot-reload over LAN.
            devUrl != null ->
                "from tempestroid.devserver.client import serve_device; " +
                    "serve_device('$devUrl')"
            // A `tempest build` APK bundles the user's app as this asset; extract
            // it and run it via the file loader (make_state + view contract).
            hasAsset(BUNDLED_APP_ASSET) -> {
                val appFile = File(filesDir, BUNDLED_APP_ASSET)
                extractAssets(BUNDLED_APP_ASSET, appFile)
                "from tempestroid.bridge.jni import run_device_file; " +
                    "run_device_file('${appFile.absolutePath}')"
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

        /** Asset slot a `tempest build` APK stages the user's app source into. */
        private const val BUNDLED_APP_ASSET = "tempest_app.py"

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
