package org.tempestroid.host

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.runtime.snapshots.SnapshotStateMap
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import org.json.JSONArray
import org.json.JSONObject

/**
 * A renderable node mirroring the serialized IR (`{type, key, props, children}`).
 *
 * `props` and `children` are Compose snapshot state, so mutating them from patch
 * application triggers a granular recomposition of just the affected subtree.
 *
 * @property type the widget tag (`Text` / `Button` / `Column` / `Row` / `Container`).
 * @property key the optional reconciler key.
 * @property props the live prop map (style is a nested spec map; handlers are
 *   `{"$handler": token}` maps).
 * @property children the ordered child nodes.
 */
class TempestNode(
    val type: String,
    val key: String?,
    val props: SnapshotStateMap<String, Any?>,
    val children: SnapshotStateList<TempestNode>,
)

/**
 * Holds the device-side widget tree and applies bridge messages to it.
 *
 * The Python side sends one `mount` (the full tree) followed by `patch` batches
 * (insert/remove/update/reorder/replace). This holder parses them into
 * [TempestNode]s; the Compose renderer observes [root] and recomposes.
 */
class TempestTree {

    /** The current root node, or null before the first mount. */
    var root by mutableStateOf<TempestNode?>(null)
        private set

    /**
     * The current floating overlay layer (E2), in ascending z-order. Each entry's
     * [TempestNode.key] is its stable overlay id (used for `__dismiss__:<id>`).
     * Empty before the first mount or when no overlay is shown.
     */
    var overlays by mutableStateOf<List<TempestNode>>(emptyList())
        private set

    /**
     * Apply one serialized message (`mount` or `patch`).
     *
     * @param message the parsed message envelope.
     */
    fun apply(message: JSONObject) {
        when (message.optString("kind")) {
            "mount" -> {
                root = parseNode(message.getJSONObject("root"))
                // E2: a mount may carry a floating overlay layer. Absent → empty.
                val arr = message.optJSONArray("overlays")
                overlays =
                    if (arr != null) {
                        (0 until arr.length()).map { parseNode(arr.getJSONObject(it)) }
                    } else {
                        emptyList()
                    }
            }
            "patch" -> applyPatches(message.getJSONArray("patches"))
        }
    }

    private fun applyPatches(patches: JSONArray) {
        for (i in 0 until patches.length()) {
            applyPatch(patches.getJSONObject(i))
        }
    }

    private fun applyPatch(patch: JSONObject) {
        val path = toPathList(patch.getJSONArray("path"))
        // E2: the overlay layer is diffed as the children of a virtual parent
        // addressed by the reserved string token "overlay" (paths start with it).
        // A layer-level op (insert/remove/reorder of whole overlays) has path
        // == ["overlay"]; an op inside overlay i has path ["overlay", i, ...].
        if (path.firstOrNull() == OVERLAY_STEP) {
            applyOverlayPatch(patch, path)
            return
        }
        when (patch.getString("op")) {
            "update" -> nodeAt(path)?.let { node ->
                val set = patch.getJSONObject("set")
                for (name in set.keys()) node.props[name] = jsonToKotlin(set.get(name))
                val unset = patch.getJSONArray("unset")
                for (i in 0 until unset.length()) node.props.remove(unset.getString(i))
            }
            "replace" -> {
                val node = parseNode(patch.getJSONObject("node"))
                if (path.isEmpty()) {
                    root = node
                } else {
                    parentOf(path)?.children?.set(path.last() as Int, node)
                }
            }
            "insert" -> nodeAt(path)?.children?.add(
                patch.getInt("index"), parseNode(patch.getJSONObject("node"))
            )
            "remove" -> nodeAt(path)?.children?.removeAt(patch.getInt("index"))
            "reorder" -> nodeAt(path)?.let { node ->
                val order = toIntList(patch.getJSONArray("order"))
                val snapshot = node.children.toList()
                node.children.clear()
                node.children.addAll(order.map { snapshot[it] })
            }
        }
    }

    /**
     * Apply a patch addressed at the overlay layer (path starts with "overlay").
     *
     * The overlay list ([overlays]) is plain snapshot state (not a
     * `SnapshotStateList`), so a layer-level op rebuilds the list immutably; an op
     * targeting inside an overlay mutates that overlay's snapshot props/children
     * in place (granular recomposition of just that overlay subtree).
     */
    private fun applyOverlayPatch(patch: JSONObject, path: List<Any>) {
        val op = patch.getString("op")
        // Layer-level ops have path == ["overlay"] (one element): they add, remove
        // or reorder whole overlays.
        if (path.size == 1) {
            when (op) {
                "insert" -> {
                    val node = parseNode(patch.getJSONObject("node"))
                    val index = patch.getInt("index").coerceIn(0, overlays.size)
                    overlays = overlays.toMutableList().apply { add(index, node) }
                }
                "remove" -> {
                    val index = patch.getInt("index")
                    if (index in overlays.indices) {
                        overlays = overlays.toMutableList().apply { removeAt(index) }
                    }
                }
                "reorder" -> {
                    val order = toIntList(patch.getJSONArray("order"))
                    val snapshot = overlays
                    overlays = order.mapNotNull { snapshot.getOrNull(it) }
                }
                "replace" -> {
                    // A replace addressed at the layer root is unusual but handle
                    // it as a no-op-safe full swap of the layer's single overlay.
                    val node = parseNode(patch.getJSONObject("node"))
                    overlays = listOf(node)
                }
            }
            return
        }
        // In-overlay ops: ["overlay", i, ...rest] addresses inside overlay i. Drop
        // the "overlay" token, then walk the remaining (all-Int) path from that
        // overlay node — reusing the same child-index traversal as the root tree.
        val overlayIndex = path[1] as? Int ?: return
        val overlay = overlays.getOrNull(overlayIndex) ?: return
        val rest = path.drop(2)
        when (op) {
            "update" -> overlayNodeAt(overlay, rest)?.let { node ->
                val set = patch.getJSONObject("set")
                for (name in set.keys()) node.props[name] = jsonToKotlin(set.get(name))
                val unset = patch.getJSONArray("unset")
                for (i in 0 until unset.length()) node.props.remove(unset.getString(i))
            }
            "replace" -> {
                val node = parseNode(patch.getJSONObject("node"))
                if (rest.isEmpty()) {
                    overlays = overlays.toMutableList().apply { set(overlayIndex, node) }
                } else {
                    val parent = overlayNodeAt(overlay, rest.dropLast(1))
                    parent?.children?.set(rest.last() as Int, node)
                }
            }
            "insert" -> overlayNodeAt(overlay, rest)?.children?.add(
                patch.getInt("index"), parseNode(patch.getJSONObject("node"))
            )
            "remove" -> overlayNodeAt(overlay, rest)?.children?.removeAt(patch.getInt("index"))
            "reorder" -> overlayNodeAt(overlay, rest)?.let { node ->
                val order = toIntList(patch.getJSONArray("order"))
                val snapshot = node.children.toList()
                node.children.clear()
                node.children.addAll(order.map { snapshot[it] })
            }
        }
    }

    /** Resolve the node at [path] (child indices, all Int) starting from [from]. */
    private fun overlayNodeAt(from: TempestNode, path: List<Any>): TempestNode? {
        var node = from
        for (step in path) {
            val index = step as? Int ?: return null
            node = node.children.getOrNull(index) ?: return null
        }
        return node
    }

    /** Resolve the node at [path] (child indices from the root). */
    private fun nodeAt(path: List<Any>): TempestNode? {
        var node = root ?: return null
        for (step in path) {
            val index = step as? Int ?: return null
            node = node.children.getOrNull(index) ?: return null
        }
        return node
    }

    /** Resolve the parent of the node at [path] (path must be non-empty). */
    private fun parentOf(path: List<Any>): TempestNode? = nodeAt(path.dropLast(1))

    private fun parseNode(json: JSONObject): TempestNode {
        val props = mutableStateMapOf<String, Any?>()
        val rawProps = json.getJSONObject("props")
        for (name in rawProps.keys()) props[name] = jsonToKotlin(rawProps.get(name))

        val children = mutableStateListOf<TempestNode>()
        val rawChildren = json.getJSONArray("children")
        for (i in 0 until rawChildren.length()) {
            children.add(parseNode(rawChildren.getJSONObject(i)))
        }

        return TempestNode(
            type = json.getString("type"),
            key = if (json.isNull("key")) null else json.getString("key"),
            props = props,
            children = children,
        )
    }

    private fun toIntList(arr: JSONArray): List<Int> =
        (0 until arr.length()).map { arr.getInt(it) }

    /**
     * Parse a patch `path` array into a mixed [Int]/[String] list.
     *
     * Root-tree paths are all child indices ([Int]); an overlay-layer path (E2)
     * starts with the reserved [OVERLAY_STEP] string token, followed by the
     * overlay index and then child indices.
     */
    private fun toPathList(arr: JSONArray): List<Any> =
        (0 until arr.length()).map { i ->
            val v = arr.get(i)
            if (v is String) v else (v as Number).toInt()
        }

    /** Convert an org.json value into plain Kotlin (Map/List/String/Double/Boolean/null). */
    private fun jsonToKotlin(value: Any?): Any? = when (value) {
        is JSONObject -> buildMap {
            for (k in value.keys()) put(k, jsonToKotlin(value.get(k)))
        }
        is JSONArray -> (0 until value.length()).map { jsonToKotlin(value.get(it)) }
        JSONObject.NULL -> null
        else -> value
    }

    companion object {
        /**
         * Reserved path token (E2) marking a patch addressed at the overlay layer
         * rather than the root tree. Must stay in sync with the Python
         * `reconciler.OVERLAY_STEP` ("overlay").
         */
        private const val OVERLAY_STEP = "overlay"
    }
}
