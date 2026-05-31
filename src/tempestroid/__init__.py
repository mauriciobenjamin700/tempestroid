"""tempestroid — build native Android apps in typed Python.

Public surface: the typed style model, declarative widget primitives, typed
events, the reconciler (IR + diff), the app/state loop, and introspection. The
Qt simulator runner lives under ``tempestroid.renderers.qt`` (needs the ``qt``
extra) and is imported on demand.
"""

from tempestroid.bridge import (
    Bridge,
    DeviceApp,
    EventMessage,
    JniBridge,
    LoopbackBridge,
    MountMessage,
    PatchMessage,
    run_device,
    serialize_node,
    serialize_patch,
)
from tempestroid.core import (
    App,
    Insert,
    Node,
    Patch,
    Path,
    Remove,
    Reorder,
    Replace,
    Update,
    build,
    diff,
    event_catalog,
    introspect,
    widget_catalog,
)
from tempestroid.devserver import (
    DevServer,
    render_qr,
    run_dev_client,
    serve_device,
)
from tempestroid.native import notify
from tempestroid.renderers.compose import to_compose
from tempestroid.style import (
    AlignItems,
    Border,
    Color,
    Edge,
    FlexDirection,
    FontWeight,
    JustifyContent,
    Style,
    TextAlign,
)
from tempestroid.widgets import (
    Button,
    Checkbox,
    Column,
    Container,
    DateChangeEvent,
    DatePicker,
    Event,
    EventHandler,
    EventValidationError,
    FilePicker,
    FileSelectEvent,
    Input,
    Row,
    TapEvent,
    Text,
    TextChangeEvent,
    ToggleEvent,
    Widget,
    parse_event,
)

__version__ = "0.0.1"

__all__ = [
    "__version__",
    # Style
    "Style",
    "Color",
    "Edge",
    "Border",
    "FlexDirection",
    "JustifyContent",
    "AlignItems",
    "TextAlign",
    "FontWeight",
    # Widgets
    "Widget",
    "Text",
    "Button",
    "Column",
    "Row",
    "Container",
    "Input",
    "Checkbox",
    "DatePicker",
    "FilePicker",
    "EventHandler",
    # Events (typed boundary contract)
    "Event",
    "TapEvent",
    "TextChangeEvent",
    "ToggleEvent",
    "DateChangeEvent",
    "FileSelectEvent",
    "EventValidationError",
    "parse_event",
    # Core (IR + reconciler)
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
    # Introspection
    "introspect",
    "widget_catalog",
    "event_catalog",
    # Compose renderer (Python side, phase B4)
    "to_compose",
    # Bridge (Python↔Kotlin boundary, phase B3)
    "Bridge",
    "LoopbackBridge",
    "JniBridge",
    "run_device",
    "DeviceApp",
    "MountMessage",
    "PatchMessage",
    "EventMessage",
    "serialize_node",
    "serialize_patch",
    # Dev server (LAN code-push, phase B5)
    "DevServer",
    "run_dev_client",
    "serve_device",
    "render_qr",
    # Native capabilities (phase B6)
    "notify",
]
