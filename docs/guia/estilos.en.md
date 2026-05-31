# Styles

Style is described by **frozen** Pydantic value objects, diffed by value — which
is what lets the reconciler diff style cheaply. All divergence between Qt and
Compose is confined to the two `Style` translators.

```python
from tempestroid import (
    AlignItems, Color, Column, Edge, FlexDirection, FontWeight, Style, Text,
)

Column(
    style=Style(
        direction=FlexDirection.COLUMN,
        align=AlignItems.CENTER,
        gap=16.0,
        padding=Edge.all(24.0),
        background=Color.from_hex("#101418"),
    ),
    children=[
        Text(
            content="Title",
            style=Style(
                color=Color.from_hex("#ffffff"),
                font_size=24.0,
                font_weight=FontWeight.BOLD,
            ),
            key="t",
        ),
    ],
)
```

## `Style` fields, by group

`Style` is a single model; below are its fields grouped by intent.

| Group | Fields |
|---|---|
| **Layout** | `direction`, `justify`, `align`, `align_self`, `grow`, `gap` |
| **Box** | `padding`, `margin`, `border`, `radius` |
| **Paint** | `background`, `color`, `opacity`, `shadow` |
| **Typography** | `font_family`, `font_size`, `font_weight`, `font_style`, `text_align`, `text_decoration`, `letter_spacing`, `line_height`, `max_lines`, `text_overflow` |
| **Sizing** | `width`, `height`, `min_width`, `max_width`, `min_height`, `max_height`, `aspect_ratio` |
| **Animation** | `transition` |

## Value objects

| Type | Use |
|---|---|
| `Color` | Color; `Color.from_hex("#101418")`. |
| `Edge` | Insets; `Edge.all(24.0)` or `Edge.symmetric(vertical=8.0, horizontal=16.0)`. |
| `Border` | Uniform border (width, color). |
| `SideBorder` | Per-side border (`top`/`right`/`bottom`/`left`) — e.g. a bottom divider. |
| `Corners` | Per-corner radii for `Style.radius` (`top_left`/`top_right`/`bottom_right`/`bottom_left`) — e.g. top-rounded sheets. |
| `Shadow` | `box-shadow`/elevation (`color`/`blur`/`offset_x`/`offset_y`). Compose maps it to elevation; Qt to `QGraphicsDropShadowEffect`. |
| `Gradient` + `GradientStop` | A linear gradient usable wherever a background `Color` is (QSS `qlineargradient` / Compose `Brush`). |
| `Transition` | Implicit animation (`duration_ms`/`curve`/`delay_ms`). |

```python
from tempestroid import (
    Color, Corners, Gradient, GradientDirection, GradientStop, Shadow, Style,
)

Style(
    background=Gradient(
        stops=[GradientStop(color=Color.from_hex("#3b82f6"), position=0.0),
               GradientStop(color=Color.from_hex("#9333ea"), position=1.0)],
        direction=GradientDirection.LEFT_RIGHT,
    ),
    radius=Corners(top_left=16.0, top_right=16.0),
    shadow=Shadow(color=Color.from_hex("#00000040"), blur=12.0, offset_y=4.0),
    opacity=0.95,
)
```

## Enums

| Enum | Values |
|---|---|
| `FlexDirection` | `ROW`, `COLUMN`. |
| `JustifyContent` | `START`, `CENTER`, `END`, `SPACE_BETWEEN`, `SPACE_AROUND`, `SPACE_EVENLY`. |
| `AlignItems` | `START`, `CENTER`, `END`, `STRETCH`. |
| `TextAlign` | `LEFT`, `CENTER`, `RIGHT`, `JUSTIFY`. |
| `FontWeight` | `NORMAL`, `BOLD` (and numeric weights). |
| `FontStyle` | `NORMAL`, `ITALIC`. |
| `TextDecoration` | `NONE`, `UNDERLINE`, `LINE_THROUGH`. |
| `TextOverflow` | `CLIP`, `ELLIPSIS`. |
| `GradientDirection` | `TOP_BOTTOM`, `BOTTOM_TOP`, `LEFT_RIGHT`, `RIGHT_LEFT`. |
| `Curve` | `LINEAR`, `EASE_IN`, `EASE_OUT`, `EASE_IN_OUT` (`Transition` easing). |
| `ImageFit` | `CONTAIN`, `COVER`, `FILL`, `NONE` (used by `Image`). |
| `KeyboardType` | `TEXT`, `NUMBER`, `EMAIL`, `PHONE`, `URL`, `PASSWORD` (used by `Input`). |

## Animated transitions

`Style.transition` accepts a `Transition` object describing an implicit
animation — modelled on CSS `transition` / Flutter's implicitly-animated widgets:
when a styled prop changes between rebuilds, the renderer tweens to the new value
(Compose maps it to `animate*AsState`; on Qt the animation is renderer-imperative).

```python
from tempestroid import Curve, Style, Transition

Style(
    background=Color.from_hex("#3b82f6"),
    transition=Transition(duration_ms=200, curve=Curve.EASE_IN_OUT, delay_ms=0),
)
```

| Field | Type | Meaning |
|---|---|---|
| `duration_ms` | `int` | Animation duration in milliseconds. |
| `curve` | `Curve` | Easing curve. |
| `delay_ms` | `int` | Delay before starting, in milliseconds. |

## How each renderer translates

The same `Style` feeds both translators; the **conformance suite** (phase D) pins
both with golden snapshots to prevent silent divergence.

- **Qt** (`Style → Qt`): padding becomes QSS on leaves and `contentsMargins` on
  containers (no double-count); `justify`/`align` `START/CENTER/END` become Qt
  alignment flags; `grow` becomes the layout stretch factor.
- **Compose** (`to_compose(style)`): emits a serializable spec the Kotlin host
  turns into `Modifier` / `Arrangement` / `Alignment`.

!!! note "Known divergences"
    Not every field is honored equally on both sides yet. The conformance suite
    documents the divergences and fails if a translator starts (or stops) handling
    a field without updating the table.

## Immutability

`Style` and its value objects are frozen. To "change" a style, build a new
object — which is what `view` does on every rebuild, and what enables diffing by
value.
