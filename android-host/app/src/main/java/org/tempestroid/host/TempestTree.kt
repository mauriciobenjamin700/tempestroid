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
     * Apply one serialized message (`mount` or `patch`).
     *
     * @param message the parsed message envelope.
     */
    fun apply(message: JSONObject) {
        when (message.optString("kind")) {
            "mount" -> root = parseNode(message.getJSONObject("root"))
            "patch" -> applyPatches(message.getJSONArray("patches"))
        }
    }

    private fun applyPatches(patches: JSONArray) {
        for (i in 0 until patches.length()) {
            applyPatch(patches.getJSONObject(i))
        }
    }

    private fun applyPatch(patch: JSONObject) {
        val path = toIntList(patch.getJSONArray("path"))
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
                    parentOf(path)?.children?.set(path.last(), node)
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

    /** Resolve the node at [path] (child indices from the root). */
    private fun nodeAt(path: List<Int>): TempestNode? {
        var node = root ?: return null
        for (index in path) node = node.children.getOrNull(index) ?: return null
        return node
    }

    /** Resolve the parent of the node at [path] (path must be non-empty). */
    private fun parentOf(path: List<Int>): TempestNode? = nodeAt(path.dropLast(1))

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

    /** Convert an org.json value into plain Kotlin (Map/List/String/Double/Boolean/null). */
    private fun jsonToKotlin(value: Any?): Any? = when (value) {
        is JSONObject -> buildMap {
            for (k in value.keys()) put(k, jsonToKotlin(value.get(k)))
        }
        is JSONArray -> (0 until value.length()).map { jsonToKotlin(value.get(it)) }
        JSONObject.NULL -> null
        else -> value
    }
}
