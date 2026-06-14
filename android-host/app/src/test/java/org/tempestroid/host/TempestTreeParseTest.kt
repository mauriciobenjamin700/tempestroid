package org.tempestroid.host

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * F7 camada B — pins the mount/patch envelope parse in [TempestTree].
 *
 * The Python bridge (`bridge/serialize.py`) lowers the IR to `{type, key, props,
 * children}` nodes and emits a `mount` envelope followed by `patch` batches
 * (insert/remove/update/reorder/replace). This pins the Kotlin side of THAT
 * contract: that [TempestTree.apply] parses those envelopes into the snapshot
 * node tree the Compose renderer observes — the structure that, on a real device,
 * only the bridge round-trip exercises.
 *
 * Runs on the plain JVM (org.json ships in the Android test classpath; Compose
 * snapshot state reads/writes work without a composition).
 */
class TempestTreeParseTest {

    /** Build a serialized node envelope `{type, key, props, children}`. */
    private fun node(
        type: String,
        key: String? = null,
        props: Map<String, Any?> = emptyMap(),
        children: List<JSONObject> = emptyList(),
    ): JSONObject {
        val p = JSONObject()
        for ((k, v) in props) p.put(k, v)
        val c = org.json.JSONArray()
        for (child in children) c.put(child)
        return JSONObject()
            .put("type", type)
            .put("key", key ?: JSONObject.NULL)
            .put("props", p)
            .put("children", c)
    }

    private fun mount(root: JSONObject): JSONObject =
        JSONObject().put("kind", "mount").put("root", root)

    private fun patch(vararg ops: JSONObject): JSONObject {
        val arr = org.json.JSONArray()
        for (op in ops) arr.put(op)
        return JSONObject().put("kind", "patch").put("patches", arr)
    }

    @Test
    fun mountsRootNodeWithTypeAndProps() {
        val tree = TempestTree()
        tree.apply(
            mount(
                node(
                    "Column",
                    props = mapOf("style" to JSONObject().put("gap", 8.0)),
                    children = listOf(node("Text", props = mapOf("content" to "hi"))),
                ),
            ),
        )
        val root = tree.root
        assertNotNull(root)
        assertEquals("Column", root!!.type)
        assertEquals(1, root.children.size)
        assertEquals("Text", root.children[0].type)
        assertEquals("hi", root.children[0].props["content"])
    }

    @Test
    fun parsesNullKeyAsNull() {
        val tree = TempestTree()
        tree.apply(mount(node("Text")))
        assertNull(tree.root!!.key)
    }

    @Test
    fun parsesNonNullKey() {
        val tree = TempestTree()
        tree.apply(mount(node("Text", key = "item-3")))
        assertEquals("item-3", tree.root!!.key)
    }

    @Test
    fun parsesNestedStyleMap() {
        // The style is a nested JSON object → must become a Kotlin Map so styleOf
        // and the mapping functions can read it.
        val style = JSONObject()
            .put("background", "#ff0000")
            .put("padding", JSONObject().put("left", 8.0).put("top", 8.0))
        val tree = TempestTree()
        tree.apply(mount(node("Stack", props = mapOf("style" to style))))
        val styleMap = styleOf(tree.root!!)
        assertEquals("#ff0000", styleMap["background"])
        @Suppress("UNCHECKED_CAST")
        val padding = styleMap["padding"] as Map<String, Any?>
        assertEquals(8.0, padding["left"])
    }

    @Test
    fun handlerRefIsParsedSoTokenResolves() {
        // A handler prop serializes as {"$handler": "<token>"}. handlerToken reads
        // it back — the path a tap takes to fire dispatchEvent.
        val handler = JSONObject().put("\$handler", "1:on_click")
        val tree = TempestTree()
        tree.apply(mount(node("Button", props = mapOf("on_click" to handler, "label" to "Tap"))))
        assertEquals("1:on_click", handlerToken(tree.root!!, "on_click"))
        assertNull(handlerToken(tree.root!!, "on_press"))
    }

    @Test
    fun updatePatchSetsAndUnsetsProps() {
        val tree = TempestTree()
        tree.apply(mount(node("Text", props = mapOf("content" to "0", "stale" to "x"))))
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "update")
                    .put("path", org.json.JSONArray())
                    .put("set", JSONObject().put("content", "1"))
                    .put("unset", org.json.JSONArray().put("stale")),
            ),
        )
        assertEquals("1", tree.root!!.props["content"])
        assertTrue(!tree.root!!.props.containsKey("stale"))
    }

    @Test
    fun insertPatchAddsChildAtIndex() {
        val tree = TempestTree()
        tree.apply(
            mount(
                node(
                    "Column",
                    children = listOf(node("Text", props = mapOf("content" to "a"))),
                ),
            ),
        )
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "insert")
                    .put("path", org.json.JSONArray())
                    .put("index", 0)
                    .put("node", node("Text", props = mapOf("content" to "z"))),
            ),
        )
        assertEquals(2, tree.root!!.children.size)
        assertEquals("z", tree.root!!.children[0].props["content"])
        assertEquals("a", tree.root!!.children[1].props["content"])
    }

    @Test
    fun removePatchDropsChildAtIndex() {
        val tree = TempestTree()
        tree.apply(
            mount(
                node(
                    "Column",
                    children = listOf(
                        node("Text", props = mapOf("content" to "a")),
                        node("Text", props = mapOf("content" to "b")),
                    ),
                ),
            ),
        )
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "remove")
                    .put("path", org.json.JSONArray())
                    .put("index", 0),
            ),
        )
        assertEquals(1, tree.root!!.children.size)
        assertEquals("b", tree.root!!.children[0].props["content"])
    }

    @Test
    fun reorderPatchPermutesChildren() {
        val tree = TempestTree()
        tree.apply(
            mount(
                node(
                    "Column",
                    children = listOf(
                        node("Text", props = mapOf("content" to "a")),
                        node("Text", props = mapOf("content" to "b")),
                        node("Text", props = mapOf("content" to "c")),
                    ),
                ),
            ),
        )
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "reorder")
                    .put("path", org.json.JSONArray())
                    .put("order", org.json.JSONArray().put(2).put(0).put(1)),
            ),
        )
        val contents = tree.root!!.children.map { it.props["content"] }
        assertEquals(listOf("c", "a", "b"), contents)
    }

    @Test
    fun replacePatchSwapsRoot() {
        val tree = TempestTree()
        tree.apply(mount(node("Text", props = mapOf("content" to "old"))))
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "replace")
                    .put("path", org.json.JSONArray())
                    .put("node", node("Button", props = mapOf("label" to "new"))),
            ),
        )
        assertEquals("Button", tree.root!!.type)
        assertEquals("new", tree.root!!.props["label"])
    }

    @Test
    fun updatePatchAtNestedPathTargetsChild() {
        val tree = TempestTree()
        tree.apply(
            mount(
                node(
                    "Column",
                    children = listOf(
                        node("Text", props = mapOf("content" to "a")),
                        node("Text", props = mapOf("content" to "b")),
                    ),
                ),
            ),
        )
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "update")
                    .put("path", org.json.JSONArray().put(1))
                    .put("set", JSONObject().put("content", "B!"))
                    .put("unset", org.json.JSONArray()),
            ),
        )
        assertEquals("a", tree.root!!.children[0].props["content"])
        assertEquals("B!", tree.root!!.children[1].props["content"])
    }

    @Test
    fun mountWithOverlayLayerPopulatesOverlays() {
        // E2: a mount may carry a floating overlay layer (z-ordered). Each overlay
        // node's key is its stable dismiss id.
        val tree = TempestTree()
        val envelope = JSONObject()
            .put("kind", "mount")
            .put("root", node("Column"))
            .put(
                "overlays",
                org.json.JSONArray().put(node("Dialog", key = "d1", props = mapOf("title" to "Hi"))),
            )
        tree.apply(envelope)
        assertEquals(1, tree.overlays.size)
        assertEquals("Dialog", tree.overlays[0].type)
        assertEquals("d1", tree.overlays[0].key)
    }

    @Test
    fun overlayLayerInsertPatchAddsOverlay() {
        // An overlay-layer op is addressed by the reserved "overlay" path token.
        val tree = TempestTree()
        tree.apply(mount(node("Column")))
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "insert")
                    .put("path", org.json.JSONArray().put("overlay"))
                    .put("index", 0)
                    .put("node", node("Toast", key = "t1", props = mapOf("message" to "saved"))),
            ),
        )
        assertEquals(1, tree.overlays.size)
        assertEquals("Toast", tree.overlays[0].type)
        assertEquals("saved", tree.overlays[0].props["message"])
    }

    @Test
    fun overlayInnerUpdatePatchTargetsOverlayChild() {
        // ["overlay", i, ...] addresses inside overlay i.
        val tree = TempestTree()
        val envelope = JSONObject()
            .put("kind", "mount")
            .put("root", node("Column"))
            .put(
                "overlays",
                org.json.JSONArray().put(
                    node(
                        "Dialog",
                        key = "d1",
                        children = listOf(node("Text", props = mapOf("content" to "before"))),
                    ),
                ),
            )
        tree.apply(envelope)
        tree.apply(
            patch(
                JSONObject()
                    .put("op", "update")
                    .put("path", org.json.JSONArray().put("overlay").put(0).put(0))
                    .put("set", JSONObject().put("content", "after"))
                    .put("unset", org.json.JSONArray()),
            ),
        )
        assertEquals("after", tree.overlays[0].children[0].props["content"])
    }
}
