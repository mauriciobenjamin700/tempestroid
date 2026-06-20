"""H2 base action/entry kit showcase (Trilho H, phase H2).

Renders the H2 styled base kit across a few variant / size / color_scheme
combinations so both renderers have something to draw: Buttons + IconButtons
(SOLID/OUTLINE/GHOST/LINK), Inputs in OUTLINE/FILLED/FLUSHED, a Checkbox, a
Switch, a RadioGroup, and a Slider. State is wired so the device-verify can
exercise the tap / change paths (tap counter, toggles, slider value).

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/h2gallery/app.py
    # or: make run APP=examples/h2gallery/app.py

On the device the same ``view``/``make_state`` are loaded by the Compose host;
each component maps to its Material 3 affordance (OutlinedTextField / filled
TextField / Checkbox / Switch / Slider / FilledIconButton …) over the resolved
``Style`` colors. The screen is wrapped in a ``ScrollView`` so the full kit is
reachable on a phone.

Each styled component is built with ``theme=app.theme`` so the whole kit follows
the app's theme (e.g. dark mode via ``make_theme``/``App.set_theme``): a component
resolves its base ``Style`` against the ``theme`` it is given, so passing the live
app theme makes the resting look — not just the interaction state layers — adapt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import FieldVariant, IconButton, Size, Variant
from tempest_core.tokens import ColorRole
from tempest_core.widgets.events import (
    SlideEvent,
    TextChangeEvent,
    ToggleEvent,
)

from tempestroid import (
    AlignItems,
    App,
    Button,
    Checkbox,
    Color,
    Column,
    Edge,
    FontWeight,
    Input,
    RadioGroup,
    Row,
    ScrollView,
    Slider,
    Style,
    Switch,
    Text,
    Widget,
)


@dataclass
class GalleryState:
    """The showcase's mutable state.

    Attributes:
        taps: How many times any showcase button/icon-button has been tapped.
        name: The current value of the demo text input.
        agreed: Whether the demo checkbox is checked.
        enabled: Whether the demo switch is on.
        plan_index: The index of the selected radio option.
        volume: The current slider value.
        plans: The radio option labels, in order.
    """

    taps: int = 0
    name: str = ""
    agreed: bool = False
    enabled: bool = True
    plan_index: int = 0
    volume: float = 40.0
    plans: list[str] = field(default_factory=lambda: ["Free", "Pro", "Team"])


def make_state() -> GalleryState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new gallery state with default values.
    """
    return GalleryState()


def _section(title: str, *, key: str, children: list[Widget]) -> Widget:
    """Build a titled section block.

    Args:
        title: The section heading text.
        key: The stable diff key for the section.
        children: The widgets shown under the heading.

    Returns:
        A ``Column`` with a heading label above the section content.
    """
    return Column(
        style=Style(gap=8.0),
        key=key,
        children=[
            Text(
                content=title,
                style=Style(
                    color=Color.from_hex("#6b7280"),
                    font_size=12.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="heading",
            ),
            *children,
        ],
    )


def view(app: App[GalleryState]) -> Widget:
    """Build the H2 base-kit showcase UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget: a scrollable column of titled component sections.
    """
    # Pull the page chrome (surface / on-surface / accent) from the active theme
    # so the showcase itself adapts to dark mode — the components already do, and
    # a design-system gallery that stayed white in dark mode would contradict them.
    scheme = app.theme.scheme()
    surface = scheme.role(ColorRole.SURFACE)
    on_surface = scheme.role(ColorRole.ON_SURFACE)
    accent = scheme.role(ColorRole.PRIMARY)

    def bump() -> None:
        """Increment the tap counter (the button/icon-button tap-path proof)."""
        app.set_state(lambda s: setattr(s, "taps", s.taps + 1))

    def buttons_section() -> Widget:
        """Build a row of Buttons across the four variants at MD/primary."""
        return Row(
            style=Style(gap=12.0, align=AlignItems.CENTER),
            key="buttons-row",
            children=[
                Button(
                    label=variant.value,
                    on_click=bump,
                    variant=variant,
                    size=Size.MD,
                    color_scheme="primary",
                    theme=app.theme,
                    key=f"btn:{variant.value}",
                )
                for variant in Variant
            ],
        )

    def icon_buttons_section() -> Widget:
        """Build a row of IconButtons across the four variants."""
        return Row(
            style=Style(gap=12.0, align=AlignItems.CENTER),
            key="iconbtn-row",
            children=[
                IconButton(
                    icon="add",
                    on_click=bump,
                    variant=variant,
                    size=Size.MD,
                    color_scheme="primary",
                    theme=app.theme,
                    label=f"add ({variant.value})",
                    key=f"iconbtn:{variant.value}",
                )
                for variant in Variant
            ],
        )

    def inputs_section() -> Widget:
        """Build the three field variants over the demo text value."""

        def set_name(event: TextChangeEvent) -> None:
            """Mirror the input value into state."""
            app.set_state(lambda s: setattr(s, "name", event.value))

        inputs: list[Widget] = [
            Input(
                value=app.state.name,
                placeholder=f"{fv.value} field",
                on_change=set_name,
                field_variant=fv,
                size=Size.MD,
                color_scheme="primary",
                theme=app.theme,
                key=f"input:{fv.value}",
            )
            for fv in FieldVariant
        ]
        return Column(style=Style(gap=8.0), key="inputs-col", children=inputs)

    def toggles_section() -> Widget:
        """Build the checkbox + switch toggles."""

        def toggle_agreed(event: ToggleEvent) -> None:
            """Mirror the checkbox state."""
            app.set_state(lambda s: setattr(s, "agreed", event.checked))

        def toggle_enabled(event: ToggleEvent) -> None:
            """Mirror the switch state."""
            app.set_state(lambda s: setattr(s, "enabled", event.checked))

        toggles: list[Widget] = [
            Checkbox(
                label="I agree to the terms",
                checked=app.state.agreed,
                on_change=toggle_agreed,
                size=Size.MD,
                color_scheme="primary",
                theme=app.theme,
                key="checkbox",
            ),
            Switch(
                label="Notifications enabled",
                checked=app.state.enabled,
                on_change=toggle_enabled,
                size=Size.MD,
                color_scheme="secondary",
                theme=app.theme,
                key="switch",
            ),
        ]
        return Column(style=Style(gap=8.0), key="toggles-col", children=toggles)

    def radio_section() -> Widget:
        """Build the radio group over the plan options."""

        def pick_plan(index: int) -> None:
            """Mirror the selected plan index."""
            app.set_state(lambda s: setattr(s, "plan_index", index))

        return RadioGroup(
            options=app.state.plans,
            selected=app.state.plan_index,
            on_select=pick_plan,
            size=Size.MD,
            color_scheme="primary",
            theme=app.theme,
            key="radio-group",
        )

    def slider_section() -> Widget:
        """Build the slider over the volume value."""

        def set_volume(event: SlideEvent) -> None:
            """Mirror the slider value."""
            app.set_state(lambda s: setattr(s, "volume", event.value))

        return Slider(
            value=app.state.volume,
            min_value=0.0,
            max_value=100.0,
            on_change=set_volume,
            size=Size.MD,
            color_scheme="primary",
            theme=app.theme,
            key="slider",
        )

    body = Column(
        style=Style(
            gap=20.0,
            padding=Edge.all(24.0),
            background=surface,
        ),
        children=[
            Text(
                content="H2 base kit",
                style=Style(
                    color=on_surface,
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            Text(
                content=(
                    f"taps: {app.state.taps}  ·  name: {app.state.name or '—'}  ·  "
                    f"plan: {app.state.plans[app.state.plan_index]}  ·  "
                    f"vol: {int(app.state.volume)}"
                ),
                style=Style(color=accent, font_size=14.0),
                key="status",
            ),
            _section("BUTTONS", key="sec-buttons", children=[buttons_section()]),
            _section(
                "ICON BUTTONS", key="sec-iconbtns", children=[icon_buttons_section()]
            ),
            _section("INPUTS", key="sec-inputs", children=[inputs_section()]),
            _section("TOGGLES", key="sec-toggles", children=[toggles_section()]),
            _section("RADIO GROUP", key="sec-radio", children=[radio_section()]),
            _section("SLIDER", key="sec-slider", children=[slider_section()]),
        ],
    )
    return ScrollView(children=[body], key="scroll")


def main() -> int:
    """Run the showcase in the Qt simulator.

    Returns:
        The process exit code.
    """
    # Import the Qt renderer lazily so this module stays renderer-agnostic: the
    # Android device loads ``view``/``make_state`` from this same file and has no
    # PySide6, so a top-level Qt import would crash the on-device load.
    from tempestroid.renderers.qt import run_qt

    return run_qt(
        make_state(), view, title="tempestroid — H2 base kit", size=(440, 640)
    )


if __name__ == "__main__":
    raise SystemExit(main())
