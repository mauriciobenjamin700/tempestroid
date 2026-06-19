package org.tempestroid.host

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import android.util.Log
import java.util.concurrent.Executors
import org.json.JSONObject

/**
 * REAL `image` native handler (always present in `src/main`).
 *
 * Decodes an image file/byte buffer to raw **HWC uint8 RGB** pixels via Android's
 * [BitmapFactory] — `android.graphics`, zero heavy dependencies, unlike the
 * onnxruntime AAR — so it ships in every APK regardless of `-Ptempest.features`.
 *
 * This is the Trilho G2 decode bridge: there is no cross-compiled Pillow/OpenCV
 * wheel for Android (libjpeg/zlib native deps), so the Python
 * [tempestroid.native.image.decode_image] cannot decode on device. Instead it
 * routes a `decode` command here; the result reassembles into a canonical
 * `(H, W, 3)` uint8 RGB `ndarray` — exactly the array `ort-vision-sdk` accepts.
 *
 * One action, matching the Python contract exactly:
 *  - `decode` — decode `path` (filesystem) or `bytes` (base64 of encoded image),
 *    optionally downsampling so the longest side is at most `max_size`, then reply
 *    `{"width", "height", "data"}` where `data` is base64 of a `width*height*3`
 *    raw RGB buffer (R,G,B order, row-major, **no alpha, no padding**).
 *
 * Errors mirror the Python contract: `not_found` (missing path), `decode_failed`
 * (BitmapFactory returns null / unsupported format).
 *
 * The decode runs on a dedicated background executor (off the UI thread, like the
 * vision module) and replies over the existing request/response native channel.
 */
internal object ImageModule {

    private const val TAG = "tempestroid.image"

    /**
     * Decode executor — a single background thread so a large photo decode never
     * touches the UI thread (where [NativeModules.handle] dispatches us).
     */
    private val executor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "tempest-image").apply { isDaemon = true }
    }

    /**
     * Dispatch one `image` command (`decode`) to this module.
     *
     * @param modules the host module router (used for the reply channel).
     * @param action the image action.
     * @param args the action arguments.
     * @param requestId the request id for the request/response reply, or null.
     */
    fun handle(
        modules: NativeModules,
        action: String,
        args: JSONObject,
        requestId: String?,
    ) {
        executor.execute {
            try {
                when (action) {
                    "decode" -> doDecode(modules, args, requestId)
                    else -> modules.reply(
                        requestId, false, error = "unavailable", message = "no $action",
                    )
                }
            } catch (e: Throwable) {
                Log.e(TAG, "image $action failed", e)
                modules.reply(
                    requestId, false,
                    error = "decode_failed",
                    message = "${e.javaClass.simpleName}: ${e.message}",
                )
            }
        }
    }

    /**
     * Decode an image to raw RGB pixels and reply `{width, height, data}`.
     *
     * Resolves the source (filesystem [path] or base64 [bytes]), optionally
     * downsamples via [BitmapFactory.Options.inSampleSize] (power-of-two, computed
     * from a bounds-only first pass so a large photo never OOMs), forces
     * `ARGB_8888`, then packs the pixels into a `width*height*3` RGB byte array.
     *
     * @param modules the host module router.
     * @param args carries `path` OR `bytes` (base64), plus an optional `max_size`.
     * @param requestId the reply id.
     */
    private fun doDecode(modules: NativeModules, args: JSONObject, requestId: String?) {
        val path = args.optString("path").ifEmpty { null }
        val encoded = args.optString("bytes").ifEmpty { null }
        val maxSize = if (args.isNull("max_size")) 0 else args.optInt("max_size")

        if (path != null && !java.io.File(path).isFile) {
            modules.reply(requestId, false, error = "not_found", message = path)
            return
        }

        // First pass: bounds only (no pixels allocated) to size the subsample.
        val bytes: ByteArray? = encoded?.let { Base64.decode(it, Base64.DEFAULT) }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        decodeWith(path, bytes, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
            modules.reply(requestId, false, error = "decode_failed", message = "unsupported image")
            return
        }

        // Second pass: decode the actual pixels, subsampled if a cap is requested.
        val options = BitmapFactory.Options().apply {
            inPreferredConfig = Bitmap.Config.ARGB_8888
            inSampleSize = sampleSizeFor(bounds.outWidth, bounds.outHeight, maxSize)
        }
        val bitmap = decodeWith(path, bytes, options)
        if (bitmap == null) {
            modules.reply(requestId, false, error = "decode_failed", message = "decode returned null")
            return
        }
        try {
            val data = packRgb(bitmap)
            modules.reply(
                requestId, true,
                data = JSONObject()
                    .put("width", bitmap.width)
                    .put("height", bitmap.height)
                    .put("data", data),
            )
        } finally {
            bitmap.recycle()
        }
    }

    /**
     * Run a [BitmapFactory] decode against whichever source is present.
     *
     * @param path a filesystem path, or null when decoding [bytes].
     * @param bytes an encoded-image byte buffer, or null when decoding [path].
     * @param options the decode options (bounds-only or full).
     * @return the decoded bitmap, or null (also null for bounds-only passes).
     */
    private fun decodeWith(
        path: String?,
        bytes: ByteArray?,
        options: BitmapFactory.Options,
    ): Bitmap? = when {
        path != null -> BitmapFactory.decodeFile(path, options)
        bytes != null -> BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
        else -> null
    }

    /**
     * Compute the largest power-of-two subsample factor that keeps the longest
     * side at least [maxSize] (so the result may exceed `max_size` but never falls
     * below it). `maxSize <= 0` means no downsampling (factor 1).
     *
     * @param width the source width.
     * @param height the source height.
     * @param maxSize the requested cap on the longest side, or 0 for none.
     * @return the [BitmapFactory.Options.inSampleSize] factor (a power of two).
     */
    private fun sampleSizeFor(width: Int, height: Int, maxSize: Int): Int {
        if (maxSize <= 0) return 1
        val longest = maxOf(width, height)
        var sample = 1
        // Double the factor while halving again would still exceed the cap.
        while (longest / (sample * 2) >= maxSize) {
            sample *= 2
        }
        return sample
    }

    /**
     * Pack an [ARGB_8888][Bitmap.Config.ARGB_8888] bitmap into a base64 string of
     * its raw RGB bytes: exactly `width * height * 3` bytes, R,G,B per pixel,
     * row-major, **dropping the alpha channel and with no row padding** (the
     * Python side reshapes to `(H, W, 3)` and hard-asserts the byte count).
     *
     * @param bitmap the decoded bitmap (any config; pixels are read as ARGB ints).
     * @return base64 (NO_WRAP) of the `width*height*3` RGB buffer.
     */
    private fun packRgb(bitmap: Bitmap): String {
        val width = bitmap.width
        val height = bitmap.height
        val pixels = IntArray(width * height)
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
        val rgb = ByteArray(width * height * 3)
        var dst = 0
        for (p in pixels) {
            rgb[dst++] = ((p shr 16) and 0xFF).toByte() // R
            rgb[dst++] = ((p shr 8) and 0xFF).toByte() // G
            rgb[dst++] = (p and 0xFF).toByte() // B
        }
        return Base64.encodeToString(rgb, Base64.NO_WRAP)
    }
}
