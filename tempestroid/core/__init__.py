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
    Update,
)
from tempestroid.core.reconciler import build, diff
from tempestroid.core.state import App

__all__ = [
    "Path",
    "Node",
    "Replace",
    "Update",
    "Insert",
    "Remove",
    "Reorder",
    "Patch",
    "build",
    "diff",
    "App",
    "introspect",
    "widget_catalog",
    "event_catalog",
]
