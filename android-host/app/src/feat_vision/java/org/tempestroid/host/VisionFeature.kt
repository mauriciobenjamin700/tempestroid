package org.tempestroid.host

import ai.onnxruntime.OnnxJavaType
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import android.util.Base64
import android.util.Log
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors
import org.json.JSONArray
import org.json.JSONObject

/**
 * REAL `onnx` native handler (built only when `-Ptempest.features` includes
 * `vision`). It runs the native `onnxruntime-android` AAR on the device, driven
 * by the Python [tempestroid.native.inference.AarBackend] over the existing
 * request/response native channel. This is the Trilho G bridge: ONNX Runtime
 * ships for Android only as a native AAR (no Python wheel), so the inference runs
 * in Kotlin/C++ here while the SDK's NumPy preprocessing/postprocessing stay in
 * Python.
 *
 * Two actions, matching the Python contract exactly:
 *  - `load` — open a model and reply with its input/output names + shapes so the
 *    SDK can read metadata (e.g. ``num_classes``) synchronously.
 *  - `infer` — run one inference and reply with the output tensors.
 *
 * Tensors cross the bridge as ``{"dtype", "shape", "data"}`` where ``data`` is
 * base64 of the raw little-endian contiguous buffer (see ``encode_tensor`` /
 * ``decode_tensor`` in ``inference.py``).
 *
 * The execution-provider chain tries **NNAPI** then **XNNPACK** then falls back
 * to plain CPU, catching each so it still runs on the emulator (where NNAPI is a
 * sample HAL that may reject the model). Inference runs on a dedicated background
 * executor so the bridge round-trip never blocks the UI thread.
 *
 * The stub counterpart in `src/stub_vision` has the identical [handleOnnx]
 * signature and replies `feature_not_built`.
 */
internal object OnnxModule {

    private const val TAG = "tempestroid.onnx"

    /** The shared ORT environment (one per process). Created lazily. */
    private val environment: OrtEnvironment by lazy { OrtEnvironment.getEnvironment() }

    /** Loaded sessions, keyed by the session id handed back to Python. */
    private val sessions = mutableMapOf<String, OrtSession>()

    /** The provider chain that successfully opened each session (for diagnostics). */
    private val sessionProvider = mutableMapOf<String, String>()

    private var nextSessionId = 1

    /**
     * Inference executor — a single background thread so heavy model runs never
     * touch the UI thread (where [NativeModules.handle] dispatches us).
     */
    private val executor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "tempest-onnx").apply { isDaemon = true }
    }

    /**
     * Dispatch one `onnx` command (`load` / `infer`) to this module.
     *
     * @param modules the host module router (used for the reply channel).
     * @param action the onnx action.
     * @param args the action arguments.
     * @param requestId the request id for the request/response reply, or null.
     */
    fun handle(
        modules: NativeModules,
        action: String,
        args: JSONObject,
        requestId: String?,
    ) {
        // Run off the UI thread: model load + inference are both heavy.
        executor.execute {
            try {
                when (action) {
                    "load" -> doLoad(modules, args, requestId)
                    "infer" -> doInfer(modules, args, requestId)
                    else -> modules.reply(
                        requestId, false, error = "unavailable", message = "no $action",
                    )
                }
            } catch (e: Throwable) {
                Log.e(TAG, "onnx $action failed", e)
                modules.reply(
                    requestId, false,
                    error = "inference_failed",
                    message = "${e.javaClass.simpleName}: ${e.message}",
                )
            }
        }
    }

    /**
     * Open a model and reply with its input/output metadata.
     *
     * @param modules the host module router.
     * @param args carries `path` and an optional `providers` hint.
     * @param requestId the reply id.
     */
    private fun doLoad(modules: NativeModules, args: JSONObject, requestId: String?) {
        val path = args.optString("path")
        if (path.isEmpty()) {
            modules.reply(requestId, false, error = "unavailable", message = "no model path")
            return
        }
        val (session, provider) = openWithProviderChain(path)
        val id = "onnx-${nextSessionId++}"
        sessions[id] = session
        sessionProvider[id] = provider
        Log.i(TAG, "loaded $path as $id via $provider")

        val data = JSONObject()
            .put("session_id", id)
            .put("provider", provider)
            .put("input_names", JSONArray(session.inputNames.toList()))
            .put("input_shapes", shapesOf(session.inputInfo.values))
            .put("output_names", JSONArray(session.outputNames.toList()))
            .put("output_shapes", shapesOf(session.outputInfo.values))
        modules.reply(requestId, true, data = data)
    }

    /**
     * Open [path] trying NNAPI, then XNNPACK, then plain CPU, returning the first
     * session that opens together with the provider name that worked.
     *
     * On the emulator NNAPI is a sample HAL that may reject the model, and the
     * XNNPACK EP is only present in some AAR builds — so each attempt is wrapped
     * and we fall through to the always-present CPU provider.
     *
     * @param path the `.onnx` model path on the device filesystem.
     * @return the open session paired with the provider name used.
     */
    private fun openWithProviderChain(path: String): Pair<OrtSession, String> {
        val attempts: List<Pair<String, () -> OrtSession.SessionOptions>> = listOf(
            "NNAPI" to {
                OrtSession.SessionOptions().apply { addNnapi() }
            },
            "XNNPACK" to {
                OrtSession.SessionOptions().apply {
                    addXnnpack(mapOf("intra_op_num_threads" to "2"))
                }
            },
            "CPU" to { OrtSession.SessionOptions() },
        )
        var lastError: Throwable? = null
        for ((name, makeOptions) in attempts) {
            try {
                val options = makeOptions()
                return environment.createSession(path, options) to name
            } catch (e: Throwable) {
                Log.w(TAG, "EP $name unavailable, trying next: ${e.message}")
                lastError = e
            }
        }
        throw IllegalStateException(
            "no execution provider could open the model", lastError,
        )
    }

    /**
     * Run one inference and reply with the output tensors.
     *
     * @param modules the host module router.
     * @param args carries `session_id`, `inputs` (name -> tensor envelope) and an
     *   optional `output_names` list (empty = all outputs in order).
     * @param requestId the reply id.
     */
    private fun doInfer(modules: NativeModules, args: JSONObject, requestId: String?) {
        val id = args.optString("session_id")
        val session = sessions[id]
        if (session == null) {
            modules.reply(requestId, false, error = "unavailable", message = "no session $id")
            return
        }
        val inputsJson = args.optJSONObject("inputs") ?: JSONObject()
        val tensors = mutableMapOf<String, OnnxTensor>()
        try {
            val keys = inputsJson.keys()
            while (keys.hasNext()) {
                val name = keys.next()
                tensors[name] = decodeTensor(inputsJson.getJSONObject(name))
            }
            val requested = args.optJSONArray("output_names")
            val outputNames: Set<String>? =
                if (requested == null || requested.length() == 0) {
                    null
                } else {
                    (0 until requested.length()).map { requested.getString(it) }.toSet()
                }
            val orderedOutputs =
                if (outputNames == null) session.outputNames.toList()
                else session.outputNames.filter { it in outputNames }

            session.run(tensors, orderedOutputs.toSet()).use { result ->
                val outArray = JSONArray()
                for (name in orderedOutputs) {
                    val value = result.get(name).orElseThrow {
                        IllegalStateException("output $name missing from run result")
                    }
                    val tensor = value as OnnxTensor
                    outArray.put(encodeTensor(tensor))
                }
                modules.reply(
                    requestId, true,
                    data = JSONObject().put("outputs", outArray),
                )
            }
        } finally {
            tensors.values.forEach { it.close() }
        }
    }

    // --- tensor (de)serialization ------------------------------------------

    /**
     * Decode a tensor envelope into an [OnnxTensor].
     *
     * @param envelope `{"dtype", "shape", "data"}`; `data` is base64 of the raw
     *   little-endian contiguous buffer.
     * @return a newly allocated [OnnxTensor] (the caller must close it).
     */
    private fun decodeTensor(envelope: JSONObject): OnnxTensor {
        val dtype = envelope.getString("dtype")
        val shapeJson = envelope.getJSONArray("shape")
        val shape = LongArray(shapeJson.length()) { shapeJson.getLong(it) }
        val raw = Base64.decode(envelope.getString("data"), Base64.DEFAULT)
        val buffer = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        return when (dtype) {
            "float32" -> OnnxTensor.createTensor(environment, buffer.asFloatBuffer(), shape)
            "float64" -> OnnxTensor.createTensor(environment, buffer.asDoubleBuffer(), shape)
            "int64" -> OnnxTensor.createTensor(environment, buffer.asLongBuffer(), shape)
            "int32" -> OnnxTensor.createTensor(environment, buffer.asIntBuffer(), shape)
            "int16" -> OnnxTensor.createTensor(environment, buffer.asShortBuffer(), shape)
            "uint8" -> OnnxTensor.createTensor(
                environment, buffer, shape, OnnxJavaType.UINT8,
            )
            "int8" -> OnnxTensor.createTensor(
                environment, buffer, shape, OnnxJavaType.INT8,
            )
            "bool" -> OnnxTensor.createTensor(
                environment, buffer, shape, OnnxJavaType.BOOL,
            )
            else -> throw IllegalArgumentException("unsupported input dtype: $dtype")
        }
    }

    /**
     * Encode an [OnnxTensor] result into a tensor envelope.
     *
     * @param tensor the ORT output tensor.
     * @return `{"dtype", "shape", "data"}` matching the Python envelope shape.
     */
    private fun encodeTensor(tensor: OnnxTensor): JSONObject {
        val info = tensor.info
        val shape = info.shape
        // The raw ByteBuffer is the contiguous little-endian buffer; ORT exposes
        // the underlying bytes via getByteBuffer(), already in native (LE) order.
        val byteBuffer = tensor.byteBuffer.order(ByteOrder.LITTLE_ENDIAN)
        val bytes = ByteArray(byteBuffer.remaining())
        byteBuffer.get(bytes)
        val dtype = dtypeName(info.type)
        val shapeArray = JSONArray()
        shape.forEach { shapeArray.put(it) }
        return JSONObject()
            .put("dtype", dtype)
            .put("shape", shapeArray)
            .put("data", Base64.encodeToString(bytes, Base64.NO_WRAP))
    }

    /**
     * Map an ORT element type to the NumPy dtype string the Python side expects.
     *
     * @param type the ORT [OnnxJavaType] of a tensor's elements.
     * @return the NumPy dtype string (e.g. ``"float32"``).
     */
    private fun dtypeName(type: OnnxJavaType): String = when (type) {
        OnnxJavaType.FLOAT -> "float32"
        OnnxJavaType.DOUBLE -> "float64"
        OnnxJavaType.INT64 -> "int64"
        OnnxJavaType.INT32 -> "int32"
        OnnxJavaType.INT16 -> "int16"
        OnnxJavaType.INT8 -> "int8"
        OnnxJavaType.UINT8 -> "uint8"
        OnnxJavaType.BOOL -> "bool"
        else -> throw IllegalArgumentException("unsupported output dtype: $type")
    }

    /**
     * Build a JSON array of shape arrays from a collection of ORT node infos.
     * Dynamic dims (negative in ORT) are emitted as their name placeholder
     * string so the Python side keeps them as strings.
     *
     * @param infos the input or output node infos.
     * @return a JSON array of per-node shape arrays.
     */
    private fun shapesOf(infos: Collection<ai.onnxruntime.NodeInfo>): JSONArray {
        val result = JSONArray()
        for (node in infos) {
            val shapeArray = JSONArray()
            val info = node.info
            if (info is TensorInfo) {
                for (dim in info.shape) {
                    if (dim < 0) shapeArray.put("dynamic") else shapeArray.put(dim)
                }
            }
            result.put(shapeArray)
        }
        return result
    }
}

/**
 * Feature-gated dispatch entry for the `onnx` module — delegates to
 * [OnnxModule]. The stub counterpart in `src/stub_vision` has the identical
 * signature and replies `feature_not_built`.
 *
 * @param modules the host module router.
 * @param action the onnx action (`load` / `infer`).
 * @param args the action arguments.
 * @param requestId the request id for the request/response reply, or null.
 */
internal fun handleOnnx(
    modules: NativeModules,
    action: String,
    args: JSONObject,
    requestId: String?,
) {
    OnnxModule.handle(modules, action, args, requestId)
}
