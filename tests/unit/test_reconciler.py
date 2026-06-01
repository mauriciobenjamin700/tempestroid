from tempestroid import (
    Button,
    Color,
    Column,
    Insert,
    Remove,
    Reorder,
    Replace,
    Row,
    Style,
    Text,
    Update,
    build,
    diff,
)

# --- build (widget -> IR node) ---------------------------------------------


def test_build_leaf_props_exclude_children_and_key():
    node = build(Text(content="hi", key="t", style=Style(gap=2.0)))
    assert node.type == "Text"
    assert node.key == "t"
    assert node.children == []
    assert node.props["content"] == "hi"
    assert node.props["style"] == Style(gap=2.0)
    assert "key" not in node.props


def test_build_recurses_children_and_drops_child_slot_from_props():
    node = build(Column(children=[Text(content="a"), Text(content="b")]))
    assert node.type == "Column"
    assert "children" not in node.props
    assert [c.props["content"] for c in node.children] == ["a", "b"]


def test_build_container_child_slot_excluded():
    from tempestroid import Container

    node = build(Container(child=Text(content="x")))
    assert "child" not in node.props
    assert len(node.children) == 1
    assert node.children[0].props["content"] == "x"


def test_build_button_keeps_handler_prop():
    handler = lambda: None  # noqa: E731
    node = build(Button(label="go", on_click=handler))
    assert node.props["label"] == "go"
    assert node.props["on_click"] is handler


# --- diff: no change --------------------------------------------------------


def test_identical_trees_produce_no_patches():
    tree = Column(children=[Text(content="a"), Button(label="b")])
    assert diff(build(tree), build(tree)) == []


# --- diff: prop update ------------------------------------------------------


def test_text_content_change_is_update_at_root():
    patches = diff(build(Text(content="a")), build(Text(content="b")))
    assert len(patches) == 1
    patch = patches[0]
    assert isinstance(patch, Update)
    assert patch.path == ()
    assert patch.set_props == {"content": "b"}
    assert patch.unset_props == []


def test_style_change_is_update():
    old = build(Text(content="x", style=Style(gap=1.0)))
    new = build(Text(content="x", style=Style(gap=2.0)))
    patches = diff(old, new)
    assert len(patches) == 1
    assert isinstance(patches[0], Update)
    assert patches[0].set_props == {"style": Style(gap=2.0)}


def test_unset_prop_reported():
    old = build(Text(content="x", style=Style(gap=1.0)))
    new = build(Text(content="x"))
    patches = diff(old, new)
    assert len(patches) == 1
    update = patches[0]
    assert isinstance(update, Update)
    # style went from a Style to None — value changed, so it is a set, not unset.
    assert update.set_props == {"style": None}


def test_equal_styles_do_not_diff():
    old = build(Text(content="x", style=Style(background=Color.from_hex("#fff"))))
    new = build(Text(content="x", style=Style(background=Color.from_hex("#ffffff"))))
    assert diff(old, new) == []


# --- diff: replace ----------------------------------------------------------


def test_type_change_is_replace():
    patches = diff(build(Text(content="a")), build(Button(label="a")))
    assert len(patches) == 1
    patch = patches[0]
    assert isinstance(patch, Replace)
    assert patch.path == ()
    assert patch.node.type == "Button"


def test_key_change_is_replace():
    patches = diff(
        build(Text(content="a", key="x")),
        build(Text(content="a", key="y")),
    )
    assert len(patches) == 1
    assert isinstance(patches[0], Replace)


# --- diff: insert / remove (positional) ------------------------------------


def test_append_child_is_insert():
    old = build(Column(children=[Text(content="a")]))
    new = build(Column(children=[Text(content="a"), Text(content="b")]))
    patches = diff(old, new)
    assert len(patches) == 1
    patch = patches[0]
    assert isinstance(patch, Insert)
    assert patch.path == ()
    assert patch.index == 1
    assert patch.node.props["content"] == "b"


def test_remove_trailing_child_is_remove():
    old = build(Column(children=[Text(content="a"), Text(content="b")]))
    new = build(Column(children=[Text(content="a")]))
    patches = diff(old, new)
    assert len(patches) == 1
    patch = patches[0]
    assert isinstance(patch, Remove)
    assert patch.index == 1


def test_multiple_removes_emitted_tail_first():
    old = build(Column(children=[Text(content=str(i)) for i in range(3)]))
    new = build(Column(children=[Text(content="0")]))
    patches = diff(old, new)
    removes = [p for p in patches if isinstance(p, Remove)]
    assert [p.index for p in removes] == [2, 1]


# --- diff: nested recursion paths ------------------------------------------


def test_nested_update_carries_correct_path():
    old = build(Column(children=[Row(children=[Text(content="a")])]))
    new = build(Column(children=[Row(children=[Text(content="z")])]))
    patches = diff(old, new)
    assert len(patches) == 1
    patch = patches[0]
    assert isinstance(patch, Update)
    assert patch.path == (0, 0)
    assert patch.set_props == {"content": "z"}


# --- diff: keyed reorder ----------------------------------------------------


def test_pure_reorder_emits_single_reorder():
    old = build(
        Column(children=[Text(content="a", key="a"), Text(content="b", key="b")])
    )
    new = build(
        Column(children=[Text(content="b", key="b"), Text(content="a", key="a")])
    )
    patches = diff(old, new)
    reorders = [p for p in patches if isinstance(p, Reorder)]
    assert len(reorders) == 1
    assert reorders[0].order == [1, 0]
    # no content changed, so no updates accompany the reorder
    assert all(isinstance(p, Reorder) for p in patches)


def test_reorder_then_update_uses_new_index_path():
    old = build(
        Column(children=[Text(content="a", key="a"), Text(content="b", key="b")])
    )
    new = build(
        Column(children=[Text(content="B", key="b"), Text(content="a", key="a")])
    )
    patches = diff(old, new)
    assert isinstance(patches[0], Reorder)
    assert patches[0].order == [1, 0]
    updates = [p for p in patches if isinstance(p, Update)]
    assert len(updates) == 1
    # "b" now sits at new index 0
    assert updates[0].path == (0,)
    assert updates[0].set_props == {"content": "B"}


def test_unchanged_keyed_order_emits_nothing():
    old = build(Column(children=[Text(content="a", key="a")]))
    new = build(Column(children=[Text(content="a", key="a")]))
    assert diff(old, new) == []


def test_keyed_append_emits_single_insert():
    old = build(Column(children=[Text(content="a", key="a")]))
    new = build(
        Column(children=[Text(content="a", key="a"), Text(content="c", key="c")])
    )
    patches = diff(old, new)
    assert len(patches) == 1
    assert isinstance(patches[0], Insert)
    assert patches[0].index == 1


def test_keyed_middle_insert_emits_only_insert():
    # A keyed insert in the middle must NOT cascade into Replaces/Updates of the
    # positionally-shifted children — just one Insert at the target index.
    old = build(
        Column(children=[Text(content="a", key="a"), Text(content="c", key="c")])
    )
    new = build(
        Column(
            children=[
                Text(content="a", key="a"),
                Text(content="b", key="b"),
                Text(content="c", key="c"),
            ]
        )
    )
    patches = diff(old, new)
    assert len(patches) == 1
    assert isinstance(patches[0], Insert)
    assert patches[0].index == 1
    assert patches[0].node.key == "b"


def test_keyed_middle_remove_emits_only_remove():
    old = build(
        Column(
            children=[
                Text(content="a", key="a"),
                Text(content="b", key="b"),
                Text(content="c", key="c"),
            ]
        )
    )
    new = build(
        Column(children=[Text(content="a", key="a"), Text(content="c", key="c")])
    )
    patches = diff(old, new)
    assert len(patches) == 1
    assert isinstance(patches[0], Remove)
    assert patches[0].index == 1


def test_keyed_mixed_insert_remove_reorder():
    # b removed, d added, a/c swapped — one Remove + one Reorder + one Insert.
    old = build(
        Column(
            children=[
                Text(content="a", key="a"),
                Text(content="b", key="b"),
                Text(content="c", key="c"),
            ]
        )
    )
    new = build(
        Column(
            children=[
                Text(content="c", key="c"),
                Text(content="a", key="a"),
                Text(content="d", key="d"),
            ]
        )
    )
    patches = diff(old, new)
    removes = [p for p in patches if isinstance(p, Remove)]
    reorders = [p for p in patches if isinstance(p, Reorder)]
    inserts = [p for p in patches if isinstance(p, Insert)]
    assert [p.index for p in removes] == [1]  # drop "b"
    assert reorders[0].order == [1, 0]  # survivors [a, c] -> [c, a]
    assert inserts[0].index == 2 and inserts[0].node.key == "d"


def test_keyed_diff_recurses_matched_keys():
    # A moved keyed child whose props changed updates at its NEW index.
    old = build(
        Column(children=[Text(content="a", key="a"), Text(content="b", key="b")])
    )
    new = build(
        Column(children=[Text(content="B!", key="b"), Text(content="a", key="a")])
    )
    patches = diff(old, new)
    updates = [p for p in patches if isinstance(p, Update)]
    assert len(updates) == 1
    assert updates[0].path == (0,)  # "b" now at index 0
    assert updates[0].set_props == {"content": "B!"}


# --- diff: virtualized-list sliding window ----------------------------------


def _windowed_column(start: int, end: int) -> Column:
    """Build a Column standing in for a materialized list window.

    Each child is keyed by its absolute index, exactly as a virtualized list
    materializes its visible ``[start, end)`` window.

    Args:
        start: The first visible index (inclusive).
        end: The one-past-last visible index (exclusive).

    Returns:
        The column with the windowed, keyed children.
    """
    return Column(
        children=[Text(content=str(i), key=str(i)) for i in range(start, end)]
    )


def test_sliding_window_keyed_diff_is_remove_plus_insert():
    # Window [0,10] -> [5,15]: keys 0..4 leave (descending Remove), keys 10..14
    # enter (ascending Insert at their final slots); survivors stay in order.
    old = build(_windowed_column(0, 10))
    new = build(_windowed_column(5, 15))
    patches = diff(old, new)

    removes = [p for p in patches if isinstance(p, Remove)]
    inserts = [p for p in patches if isinstance(p, Insert)]
    reorders = [p for p in patches if isinstance(p, Reorder)]

    assert [p.index for p in removes] == [4, 3, 2, 1, 0]
    assert [p.index for p in inserts] == [5, 6, 7, 8, 9]
    assert [p.node.key for p in inserts] == ["10", "11", "12", "13", "14"]
    # Survivors 5..9 keep their relative order -> no Reorder needed.
    assert reorders == []


def test_window_shrink_removes_only_tail_items():
    # Window [0,10] -> [0,5]: keys 5..9 leave (descending Remove); no inserts.
    old = build(_windowed_column(0, 10))
    new = build(_windowed_column(0, 5))
    patches = diff(old, new)

    removes = [p for p in patches if isinstance(p, Remove)]
    inserts = [p for p in patches if isinstance(p, Insert)]
    reorders = [p for p in patches if isinstance(p, Reorder)]

    assert [p.index for p in removes] == [9, 8, 7, 6, 5]
    assert inserts == []
    assert reorders == []


def test_window_grow_adds_only_tail_items():
    # Window [0,5] -> [0,10]: keys 5..9 enter (ascending Insert); no removes.
    old = build(_windowed_column(0, 5))
    new = build(_windowed_column(0, 10))
    patches = diff(old, new)

    removes = [p for p in patches if isinstance(p, Remove)]
    inserts = [p for p in patches if isinstance(p, Insert)]
    reorders = [p for p in patches if isinstance(p, Reorder)]

    assert removes == []
    assert [p.index for p in inserts] == [5, 6, 7, 8, 9]
    assert [p.node.key for p in inserts] == ["5", "6", "7", "8", "9"]
    assert reorders == []


# --- diff_scene (overlay layer) --------------------------------------------


def test_diff_scene_overlay_add_remove_reorder_mix():
    from tempestroid import Dialog, build_scene, diff_scene

    # Old layer: [a, b, c]; new layer: [c, a, d] -> remove b, reorder, insert d.
    old = build_scene(
        Text(content="root"),
        [
            ("a", Dialog(title="A"), True),
            ("b", Dialog(title="B"), True),
            ("c", Dialog(title="C"), True),
        ],
    )
    new = build_scene(
        Text(content="root"),
        [
            ("c", Dialog(title="C"), True),
            ("a", Dialog(title="A"), True),
            ("d", Dialog(title="D"), True),
        ],
    )
    patches = diff_scene(old, new)
    # Every overlay-layer patch is addressed under the reserved prefix.
    overlay_patches = [
        p for p in patches if p.path and p.path[0] == "overlay"
    ]
    assert overlay_patches  # the overlay layer changed
    removes = [p for p in overlay_patches if isinstance(p, Remove)]
    reorders = [p for p in overlay_patches if isinstance(p, Reorder)]
    inserts = [p for p in overlay_patches if isinstance(p, Insert)]
    assert len(removes) == 1
    assert len(reorders) == 1
    assert {p.node.key for p in inserts} == {"d"}


def test_diff_scene_matched_overlay_update_path_is_indexed():
    from tempestroid import Dialog, build_scene, diff_scene

    old = build_scene(
        Text(content="root"), [("dlg", Dialog(title="old"), True)]
    )
    new = build_scene(
        Text(content="root"), [("dlg", Dialog(title="new"), True)]
    )
    patches = diff_scene(old, new)
    updates = [p for p in patches if isinstance(p, Update) and p.path]
    assert len(updates) == 1
    assert updates[0].path == ("overlay", 0)
