"""Animation showcase app (phase E3).

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/animation/app.py

Three scenarios in one screen:

* **Animated** — a box whose background color and opacity ease between two styles
  when you toggle it. The interpolation runs in the core (an
  :class:`~tempestroid.animation.AnimationController` advances a value, a
  :class:`~tempestroid.animation.Tween` interpolates it), so the renderer only
  ever mounts the child with its already-interpolated style.
* **AnimatedList** — add/remove items; each one fades + expands in on insert and
  fades + collapses out on remove.
* **Shimmer** — a loading placeholder that sweeps a gradient highlight while the
  ``loading`` flag is set.

Note: ``tempestroid.renderers.qt`` is imported lazily inside :func:`main` (never
at module top level) so the device code-push path can import this module without
the Qt extra.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    AlignItems,
    Animated,
    AnimatedList,
    AnimationController,
    App,
    Button,
    Color,
    Column,
    Container,
    Curve,
    Edge,
    FlexDirection,
    FontWeight,
    Row,
    Shimmer,
    Style,
    Text,
    Tween,
    Widget,
)

#: A single shared controller drives the Animated box. Created once at module
#: import so its progress survives view rebuilds (the view reads its ``value``).
_BOX_CONTROLLER = AnimationController(duration_s=0.6, curve=Curve.EASE_IN_OUT)

#: The color the box eases between (collapsed → expanded).
_BOX_BEGIN = Color.from_hex("#374151")
_BOX_END = Color.from_hex("#22c55e")


@dataclass
class AnimState:
    """The showcase's mutable state.

    Attributes:
        expanded: Whether the ``Animated`` box is in its expanded (target) style.
        items: The labels currently shown in the ``AnimatedList``.
        next_id: The next item number to append.
        loading: Whether the shimmer placeholder is shown.
    """

    expanded: bool = False
    items: list[str] = field(default_factory=lambda: ["Item 1", "Item 2"])
    next_id: int = 3
    loading: bool = True


def make_state() -> AnimState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new showcase state.
    """
    return AnimState()


def _animated_box(app: App[AnimState]) -> Widget:
    """Build the color/opacity-animated box for the current frame.

    Args:
        app: The running app (read ``app.state``, drive the controller).

    Returns:
        The ``Animated`` wrapper whose child carries this frame's interpolated
        style.
    """
    color_tween: Tween[Color] = Tween(begin=_BOX_BEGIN, end=_BOX_END)
    opacity_tween: Tween[float] = Tween(begin=0.4, end=1.0)
    progress = _BOX_CONTROLLER.value
    child = Container(
        style=Style(
            background=color_tween.at(progress),
            opacity=opacity_tween.at(progress),
            radius=12.0,
            height=80.0,
            padding=Edge.all(16.0),
        ),
        child=Text(
            content="Animated box",
            style=Style(color=Color.from_hex("#ffffff"), font_weight=FontWeight.BOLD),
        ),
        key="box-inner",
    )
    return Animated(
        child=child,
        controller=_BOX_CONTROLLER,
        style_begin=Style(background=_BOX_BEGIN, opacity=0.4),
        style_end=Style(background=_BOX_END, opacity=1.0),
        key="box",
    )


def view(app: App[AnimState]) -> Widget:
    """Build the animation showcase UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state`` and the animation controller).

    Returns:
        The root widget of the showcase screen.
    """

    def toggle_box() -> None:
        # Bind the controller to this app, then ease toward the new target.
        app.register_animation(_BOX_CONTROLLER)
        if app.state.expanded:
            _BOX_CONTROLLER.reverse()
        else:
            _BOX_CONTROLLER.forward()
        app.set_state(lambda s: setattr(s, "expanded", not s.expanded))

    def add_item() -> None:
        def _mutate(s: AnimState) -> None:
            s.items = [*s.items, f"Item {s.next_id}"]
            s.next_id += 1

        app.set_state(_mutate)

    def remove_item() -> None:
        def _mutate(s: AnimState) -> None:
            if s.items:
                s.items = s.items[:-1]

        app.set_state(_mutate)

    def toggle_loading() -> None:
        app.set_state(lambda s: setattr(s, "loading", not s.loading))

    def _button(label: str, handler: object, bg: str, key: str) -> Button:
        return Button(
            label=label,
            on_click=handler,  # type: ignore[arg-type]
            key=key,
            style=Style(
                padding=Edge.symmetric(vertical=8.0, horizontal=14.0),
                radius=8.0,
                background=Color.from_hex(bg),
                color=Color.from_hex("#ffffff"),
            ),
        )

    list_items: list[Widget] = [
        Container(
            style=Style(
                background=Color.from_hex("#1f2937"),
                radius=8.0,
                padding=Edge.all(12.0),
            ),
            child=Text(
                content=label,
                style=Style(color=Color.from_hex("#e5e7eb")),
            ),
            key=label,
        )
        for label in app.state.items
    ]

    loading_block: Widget = (
        Shimmer(
            child=Container(
                style=Style(height=48.0, radius=8.0),
                child=Text(content=""),
            ),
            duration_ms=1100,
            key="shimmer",
        )
        if app.state.loading
        else Text(
            content="Loaded!",
            style=Style(color=Color.from_hex("#22c55e"), font_weight=FontWeight.BOLD),
            key="loaded",
        )
    )

    return Column(
        style=Style(
            direction=FlexDirection.COLUMN,
            align=AlignItems.STRETCH,
            gap=14.0,
            padding=Edge.all(20.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="Animation showcase",
                style=Style(
                    color=Color.from_hex("#f9fafb"),
                    font_size=20.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            _animated_box(app),
            _button("Toggle box", toggle_box, "#2563eb", "toggle-box"),
            Row(
                style=Style(gap=8.0),
                children=[
                    _button("Add item", add_item, "#22c55e", "add"),
                    _button("Remove item", remove_item, "#ef4444", "remove"),
                ],
            ),
            AnimatedList(
                children=list_items,
                enter_duration_ms=280,
                exit_duration_ms=240,
                enter_curve=Curve.EASE_OUT,
                exit_curve=Curve.EASE_IN,
                style=Style(gap=8.0),
                key="list",
            ),
            _button("Toggle loading", toggle_loading, "#6b7280", "toggle-loading"),
            loading_block,
        ],
    )


def main() -> int:
    """Run the animation showcase in the Qt simulator.

    Returns:
        The process exit code.
    """
    # Lazy import: keep the Qt renderer out of the module top level so the device
    # code-push path can import this app without the desktop ``qt`` extra.
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — animation", size=(360, 620))


if __name__ == "__main__":
    raise SystemExit(main())
