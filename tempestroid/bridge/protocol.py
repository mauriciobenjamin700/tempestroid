"""Wire protocol for the Python↔Kotlin boundary.

Messages cross a single marshalling boundary (the JNI bridge on the device, an
in-memory channel in tests). Outgoing messages (``mount``/``patch``) tell the
device what to render; the incoming ``event`` message carries a tap/text payload
back, addressed by a **handler token**.

A handler token identifies a handler by its node's **path** in the tree plus the
prop name (e.g. ``"0/1:on_click"``). Path-based (not key-based) so the emit side
(serializer) and the dispatch side (registry) compute identical tokens from the
same tree — they only need to agree within one rebuild, and every rebuild
re-sends. Tokens are stable for the lifetime of a tree shape; a reorder reshuffles
them and the accompanying patches carry the new wiring.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from tempestroid.core.ir import Path
from tempestroid.widgets import (
    ActionSheet,
    Animated,
    AnimatedList,
    BottomSheet,
    Button,
    Checkbox,
    Column,
    Container,
    DatePicker,
    Dialog,
    Event,
    FilePicker,
    GestureDetector,
    Hero,
    Icon,
    Image,
    Input,
    LazyColumn,
    LazyGrid,
    LazyRow,
    Menu,
    Navigator,
    Popover,
    ProgressBar,
    RefreshControl,
    RouteDrawer,
    Row,
    ScrollView,
    SectionList,
    Shimmer,
    Skeleton,
    Slider,
    Spinner,
    Stack,
    Switch,
    TabBar,
    TabView,
    Text,
    TextArea,
    Toast,
    Tooltip,
)

__all__ = [
    "BACK_TOKEN",
    "DISMISS_TOKEN_PREFIX",
    "FRAME_TOKEN",
    "handler_token",
    "event_type_for",
    "EVENT_SCHEMAS",
    "MountMessage",
    "PatchMessage",
    "EventMessage",
]

#: Reserved event token the host sends when the user triggers a system back
#: action (e.g. the Android back gesture). It carries no payload and addresses no
#: widget handler: the bridge routes it straight to ``App.pop``. Mirrors
#: :data:`~tempestroid.native.dispatch.NATIVE_RESULT_PREFIX` in reusing the
#: existing event channel, so the back wiring needs no new JNI/C entry point.
BACK_TOKEN: str = "__back__"

#: Reserved event-token prefix the host sends when the user dismisses an overlay
#: through a host-owned gesture (tapping a dialog's scrim, swiping a sheet down).
#: The token is ``"__dismiss__:<overlay_id>"``; the bridge strips the prefix and
#: routes the id to ``App.dismiss``. Like :data:`BACK_TOKEN` and the native
#: result prefix, it rides the existing event channel — no new JNI entry point.
DISMISS_TOKEN_PREFIX: str = "__dismiss__"

#: Reserved event token the device host sends once per frame (from its
#: ``withFrameNanos`` loop) while an animation is active. It carries no payload
#: and addresses no widget handler: the bridge routes it to
#: :meth:`~tempestroid.core.state.App._tick_from_device`, which advances the
#: animation clock one frame. Like :data:`BACK_TOKEN` it rides the existing event
#: channel — no new JNI entry point. Optional for the Qt simulator, which drives
#: its own clock via ``loop.call_later`` and never emits this token.
FRAME_TOKEN: str = "__frame__"

#: ``{widget_type: {handler_prop: event_type}}`` derived from each widget's
#: ``event_schemas`` classvar — the contract used to validate event payloads.
#: Handler-bearing widgets are kept via the ``if widget.event_schemas`` filter;
#: the handler-free animation widgets are added unconditionally afterward so they
#: still appear in the introspected contract.
EVENT_SCHEMAS: dict[str, dict[str, type[Event]]] = {
    widget.__name__: dict(widget.event_schemas)
    for widget in (
        Text,
        Button,
        Column,
        Row,
        Container,
        ScrollView,
        Stack,
        GestureDetector,
        Input,
        TextArea,
        Checkbox,
        Switch,
        Slider,
        DatePicker,
        FilePicker,
        Image,
        Icon,
        ProgressBar,
        Spinner,
        Navigator,
        TabView,
        TabBar,
        RouteDrawer,
        LazyColumn,
        LazyRow,
        LazyGrid,
        SectionList,
        RefreshControl,
        Dialog,
        BottomSheet,
        Toast,
        Tooltip,
        Menu,
        Popover,
        ActionSheet,
    )
    if widget.event_schemas
}
EVENT_SCHEMAS.update(
    {
        widget.__name__: dict(widget.event_schemas)
        for widget in (Animated, AnimatedList, Hero, Shimmer, Skeleton)
    }
)


def handler_token(path: Path, prop: str) -> str:
    """Build the stable token addressing a handler at ``path``/``prop``.

    Args:
        path: The node's path (child-index steps from the root; an overlay path
            begins with the reserved ``"overlay"`` token).
        prop: The handler prop name (e.g. ``"on_click"``).

    Returns:
        A token like ``"root:on_click"``, ``"0/2:on_click"``, or
        ``"overlay/0:on_dismiss"``.
    """
    location = "/".join(str(index) for index in path) if path else "root"
    return f"{location}:{prop}"


def event_type_for(widget_type: str, prop: str) -> type[Event] | None:
    """Look up the event type a widget's handler prop emits.

    Args:
        widget_type: The widget type tag (e.g. ``"Button"``).
        prop: The handler prop name.

    Returns:
        The event type, or ``None`` if the widget/prop emits no typed event.
    """
    return EVENT_SCHEMAS.get(widget_type, {}).get(prop)


class MountMessage(BaseModel):
    """Initial render: the full serialized tree.

    Attributes:
        kind: The message discriminator (``"mount"``).
        root: The serialized root node.
        overlays: The serialized overlay nodes, in ascending z-order (empty when
            no overlay is open). Each carries its stable id as ``key`` and a
            ``barrier`` prop; the host renders them above the root.
        can_pop: Whether the navigation stack can be popped (more than one route
            on the stack). The host reads this to enable/disable its system back
            handler without a synchronous round-trip: when ``False`` the device's
            default back action runs (e.g. close the app on Android); when
            ``True`` the host sends :data:`BACK_TOKEN` to pop a screen instead.
        has_animations: Whether at least one animation controller is active on
            the app's frame clock. The host reads this to start/stop its
            ``withFrameNanos`` loop: while ``True`` it sends :data:`FRAME_TOKEN`
            once per frame to drive the animation clock; while ``False`` it idles
            the frame loop. Re-evaluated on every mount/patch so the host's frame
            loop tracks the live set of active controllers.
    """

    model_config = ConfigDict(frozen=True)

    kind: str = "mount"
    root: dict[str, Any]
    overlays: list[dict[str, Any]] = []
    can_pop: bool = False
    has_animations: bool = False


class PatchMessage(BaseModel):
    """Incremental update: a list of serialized patches.

    Attributes:
        kind: The message discriminator (``"patch"``).
        patches: The serialized patches to apply.
        can_pop: Whether the navigation stack can be popped (see
            :class:`MountMessage`). Re-sent on every patch batch so the host's
            back handler tracks the live stack depth after each rebuild.
        has_animations: Whether at least one animation controller is active (see
            :class:`MountMessage`). Re-sent on every patch batch so the host's
            ``withFrameNanos`` loop starts when an animation begins and stops once
            the last controller settles.
    """

    model_config = ConfigDict(frozen=True)

    kind: str = "patch"
    patches: list[dict[str, Any]]
    can_pop: bool = False
    has_animations: bool = False


class EventMessage(BaseModel):
    """An event coming back from the device, addressed by handler token.

    Attributes:
        token: The handler token (see :func:`handler_token`).
        payload: The raw event payload, validated on dispatch.
    """

    model_config = ConfigDict(frozen=True)

    kind: str = "event"
    token: str
    payload: dict[str, Any] = {}
