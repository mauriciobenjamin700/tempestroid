package org.tempestroid.host

import android.util.Log

/**
 * JNI surface to the embedded CPython interpreter.
 *
 * Loading `tempest_host` transitively loads `libpython3.14.so` (the native lib
 * is linked against it; see `c/CMakeLists.txt`). The native side initializes the
 * interpreter with `PyConfig` / `Py_InitializeFromConfig` and runs it with
 * `Py_RunMain` — the official-CPython embedding contract (PEP 738), no third-party
 * bridge.
 */
object PythonRuntime {

    init {
        System.loadLibrary("tempest_host")
    }

    /**
     * Sink for messages coming up from Python (`mount` / `patch`). The Compose
     * renderer (phase B4) sets this; until then messages are just logged.
     */
    @Volatile
    @JvmStatic
    var messageSink: ((String) -> Unit)? = null

    /**
     * Whether the device should drive the Python frame clock (E3 animations).
     *
     * Set from the `has_animations` flag every mount/patch envelope carries
     * (defaulting `false`): when `true`, [MainActivity]'s `withFrameNanos` loop
     * fires the reserved [FRAME_TOKEN] event each frame so Python's
     * `App._tick_from_device` advances its [AnimationController]s at the device's
     * native refresh rate; when it flips back to `false` (the last animation
     * finished, signalled by the next envelope), the loop stops.
     *
     * This is OPTIONAL: today the Python core also drives a `loop.call_later`
     * 60fps clock on its own, so animations run even if the flag is never set —
     * the device clock just makes them track the panel's true refresh rate. A
     * Python build that never emits `has_animations` leaves this `false` and the
     * device never sends [FRAME_TOKEN] (no spurious bridge traffic).
     */
    @Volatile
    @JvmStatic
    var needsFrames: Boolean = false

    /**
     * Called from native code (`_tempest_host.send_to_host`) with one serialized
     * message from Python. Forwards to [messageSink] or logs it.
     *
     * @param json the serialized message (a `mount` or `patch` envelope).
     */
    @JvmStatic
    fun onMessageFromPython(json: String) {
        val sink = messageSink
        if (sink != null) {
            sink(json)
        } else {
            Log.i(TAG, "py->host: $json")
        }
    }

    /**
     * Initialize and run the interpreter. Blocks until Python exits, so callers
     * MUST invoke this from a background thread.
     *
     * @param pythonHome absolute path to the extracted Python tree (PYTHONHOME).
     * @param entryArgs argv to hand to Py_RunMain (e.g. ["-m", "tempest_bootstrap"]).
     * @return the interpreter exit code.
     */
    external fun startPython(pythonHome: String, entryArgs: Array<String>): Int

    /**
     * Kotlin -> Python: deliver one device event, addressed by handler token.
     *
     * Safe to call from any thread (e.g. the UI thread on a tap): the native
     * side acquires the GIL, invokes the registered Python sink, which marshals
     * the event onto the asyncio loop via `call_soon_threadsafe`. The payload is
     * validated by `parse_event` (A6) inside the handler registry before dispatch.
     *
     * @param token the handler token, e.g. `"1:on_click"`.
     * @param payloadJson the raw event payload as JSON (`"{}"` for none).
     */
    external fun dispatchEvent(token: String, payloadJson: String)

    private const val TAG = "tempestroid"

    /**
     * Reserved event token (E3) the host sends once per frame, via
     * [dispatchEvent], while [needsFrames] is `true`. The bridge routes it to
     * `App._tick_from_device` (advance the animation clock one frame, no rebuild
     * timer of its own). Must stay in sync with
     * `tempestroid.bridge.protocol.FRAME_TOKEN`. Like the back/dismiss tokens it
     * rides the existing event channel — no new JNI/C entry point.
     *
     * Exact match (no `<id>` suffix, unlike the dismiss/native-result tokens),
     * so it carries no trailing `:` — it must equal the Python `FRAME_TOKEN`
     * string verbatim for the bridge's `token == FRAME_TOKEN` route to fire.
     */
    const val FRAME_TOKEN = "__frame__"

    // TODO(B4): patch application for the Compose renderer — parse the `patch`
    //   envelopes arriving via [messageSink] and apply insert/remove/update/
    //   reorder/replace to the Compose tree state.
}
