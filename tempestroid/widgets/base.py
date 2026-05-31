"""Base widget node and event-handler typing.

A widget tree *is* the intermediate representation (IR): a declarative, typed,
serializable tree of Pydantic models. The reconciler (phase A2) diffs two such
trees and emits patches; the leaf renderers apply those patches. Everything a
renderer needs to walk the tree lives here, so the rest of the system can stay
backend-agnostic.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, ClassVar, TypeAlias

from pydantic import BaseModel, ConfigDict, WithJsonSchema

from tempestroid.style import Style
from tempestroid.widgets.events import (
    DateChangeEvent,
    Event,
    FileSelectEvent,
    LongPressEvent,
    SlideEvent,
    SwipeEvent,
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
)

__all__ = [
    "EventHandler",
    "TextChangeHandler",
    "ToggleHandler",
    "SlideHandler",
    "DateChangeHandler",
    "FileSelectHandler",
    "TapHandler",
    "LongPressHandler",
    "SwipeHandler",
    "Widget",
    "handler_accepts_event",
]

_POSITIONAL_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.VAR_POSITIONAL,
)


def handler_accepts_event(handler: Callable[..., Any]) -> bool:
    """Whether ``handler`` accepts a positional event argument.

    Value-bearing widgets pass the validated typed event to their handler, but
    only when the handler is declared to accept one — a zero-argument handler is
    called bare. Both the device bridge registry and the Qt renderer use this to
    agree on the calling convention.

    Args:
        handler: The handler callable to inspect.

    Returns:
        ``True`` if the handler can take one positional argument, ``False`` if it
        must be called with none (or its signature cannot be inspected).
    """
    try:
        params = inspect.signature(handler).parameters
    except (ValueError, TypeError):
        return False
    return any(p.kind in _POSITIONAL_KINDS for p in params.values())

_RawHandler: TypeAlias = Callable[[], Any] | Callable[[], Awaitable[Any]]

#: A zero-argument event callback. Async-first: handlers may be plain functions
#: or coroutine functions, and the runtime schedules awaitables on the loop. The
#: ``WithJsonSchema`` annotation lets introspection emit a schema for widgets
#: that carry handlers (a raw ``Callable`` has no JSON-schema representation).
EventHandler: TypeAlias = Annotated[
    _RawHandler,
    WithJsonSchema(
        {
            "type": "string",
            "title": "EventHandler",
            "description": "client-side handler; not serialized over the boundary",
        }
    ),
]

_HANDLER_SCHEMA: dict[str, str] = {
    "type": "string",
    "title": "EventHandler",
    "description": "client-side handler; not serialized over the boundary",
}

#: A value-carrying event callback: receives the validated typed event (so the
#: handler can read e.g. ``event.value``) or, for convenience, may be declared
#: zero-argument when the value is not needed. The runtime passes the event only
#: when the handler accepts a positional argument (see the bridge registry and
#: the Qt renderer); both call sites agree on this contract.
TextChangeHandler: TypeAlias = Annotated[
    Callable[[TextChangeEvent], Any]
    | Callable[[TextChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
ToggleHandler: TypeAlias = Annotated[
    Callable[[ToggleEvent], Any]
    | Callable[[ToggleEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
SlideHandler: TypeAlias = Annotated[
    Callable[[SlideEvent], Any]
    | Callable[[SlideEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
DateChangeHandler: TypeAlias = Annotated[
    Callable[[DateChangeEvent], Any]
    | Callable[[DateChangeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
FileSelectHandler: TypeAlias = Annotated[
    Callable[[FileSelectEvent], Any]
    | Callable[[FileSelectEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
TapHandler: TypeAlias = Annotated[
    Callable[[TapEvent], Any]
    | Callable[[TapEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
LongPressHandler: TypeAlias = Annotated[
    Callable[[LongPressEvent], Any]
    | Callable[[LongPressEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]
SwipeHandler: TypeAlias = Annotated[
    Callable[[SwipeEvent], Any]
    | Callable[[SwipeEvent], Awaitable[Any]]
    | _RawHandler,
    WithJsonSchema(_HANDLER_SCHEMA),
]


class Widget(BaseModel):
    """Base class for every node in the declarative UI tree.

    Attributes:
        key: Optional stable identity used by the reconciler to match nodes
            across rebuilds (analogous to a React ``key``).
        style: Optional inline style for this node.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    #: Names of fields that hold child widgets. Layout widgets override this so
    #: the reconciler can split "children" from renderable props generically,
    #: without inspecting concrete field types. Leaf widgets keep it empty.
    child_field_names: ClassVar[frozenset[str]] = frozenset()

    #: Maps a handler prop name to the event type its payload is validated into
    #: at the boundary. Used by introspection to publish each widget's event
    #: contract. Widgets that emit events override this.
    event_schemas: ClassVar[dict[str, type[Event]]] = {}

    key: str | None = None
    style: Style | None = None

    @property
    def widget_type(self) -> str:
        """The node's type tag, used by renderers and diffing.

        Returns:
            The concrete class name (e.g. ``"Text"``, ``"Column"``).
        """
        return type(self).__name__

    def child_nodes(self) -> list[Widget]:
        """Return this node's children in order.

        Leaf widgets return an empty list. Container/layout widgets override
        this to expose their children, giving the reconciler a uniform way to
        walk any tree regardless of how children are stored.

        Returns:
            The ordered child widgets (empty for leaf nodes).
        """
        return []
