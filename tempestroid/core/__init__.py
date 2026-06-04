"""Core engine: intermediate representation and the reconciler.

The reconciler is renderer-agnostic — it turns widget trees into IR nodes and
diffs them into patches that any leaf renderer can apply.
"""

from tempestroid.core.introspection import (
    event_catalog,
    introspect,
    widget_catalog,
)
from tempestroid.core.ir import (
    Insert,
    Node,
    Patch,
    Path,
    Remove,
    Reorder,
    Replace,
    Scene,
    Update,
)
from tempestroid.core.reconciler import build, build_scene, diff, diff_scene
from tempestroid.core.state import App, OverlayEntry

__all__ = [
    "Path",
    "Node",
    "Scene",
    "Replace",
    "Update",
    "Insert",
    "Remove",
    "Reorder",
    "Patch",
    "build",
    "diff",
    "build_scene",
    "diff_scene",
    "App",
    "OverlayEntry",
    "introspect",
    "widget_catalog",
    "event_catalog",
]
