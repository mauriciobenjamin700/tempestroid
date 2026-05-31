# Widgets

Widgets are the declarative primitives of the IR — a tree of Pydantic models the
reconciler diffs and the renderers apply. Always import from the package level:
`from tempestroid import Text, Button, ...`.

## Layout and content

| Widget | Role | Main props |
|---|---|---|
| `Text` | Text label. | `content: str` |
| `Button` | Tappable button. | `label: str`, `on_click` |
| `Column` | Stacks children vertically. | `children: list[Widget]` |
| `Row` | Stacks children horizontally. | `children: list[Widget]` |
| `Container` | Wraps a single child. | `child: Widget \| None` |
| `ScrollView` | Scrollable area. | `horizontal: bool`, `child` |
| `SafeArea` | Insets its child past the system bars + notch. | `child`, `edges: list[SafeAreaEdge]` (default all) |

```python
from tempestroid import Button, Column, Row, ScrollView, Style, Text

ScrollView(
    child=Column(
        style=Style(gap=8.0),
        children=[
            Text(content="Hello", key="hi"),
            Row(children=[
                Button(label="-", on_click=dec, key="dec"),
                Button(label="+", on_click=inc, key="inc"),
            ]),
        ],
    ),
)
```

## Value-bearing inputs

The leaves that carry a value and emit a typed change event. Each declares its
change handler in `event_schemas`, so the boundary validates the payload.

| Widget | Value / props | Handler | Event |
|---|---|---|---|
| `Input` | `value`, `placeholder`, `secure`, `pattern`, `error`, `keyboard`, `max_length` | `on_change` | `TextChangeEvent` |
| `TextArea` | `value`, `placeholder`, `rows`, `max_length` | `on_change` | `TextChangeEvent` |
| `Checkbox` | `label`, `checked` | `on_change` | `ToggleEvent` |
| `Switch` | `label`, `checked` | `on_change` | `ToggleEvent` |
| `Slider` | `value`, `min_value`, `max_value`, `step` | `on_change` | `SlideEvent` |
| `DatePicker` | `value` (ISO `yyyy-mm-dd`), `label` | `on_change` | `DateChangeEvent` |
| `FilePicker` | `label`, `value` | `on_select` | `FileSelectEvent` |

```python
from tempestroid import Checkbox, DatePicker, Input, Slider, Switch, TextArea

Input(value=state.name, placeholder="Your name", on_change=on_name, key="name")
Input(value=state.pwd, secure=True, keyboard=KeyboardType.PASSWORD, on_change=on_pwd, key="pwd")
TextArea(value=state.bio, rows=4, max_length=280, on_change=on_bio, key="bio")
Switch(label="Notifications", checked=state.notify, on_change=on_notify, key="sw")
Slider(value=state.volume, min_value=0.0, max_value=100.0, step=1.0, on_change=on_vol, key="vol")
```

The handler receives the typed event (or may be declared zero-argument when the
value is not needed):

```python
def on_name(event: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "name", event.value))
```

### `Input` validation

`Input` carries validation on the widget itself: `secure` masks the text,
`pattern` is a regex the renderer can validate against, `error` displays an error
message, and `keyboard` (enum `KeyboardType`: `TEXT`, `NUMBER`, `EMAIL`, `PHONE`,
`URL`, `PASSWORD`) hints the device keyboard.

## Media

| Widget | Role | Props |
|---|---|---|
| `Image` | Image by URL/URI. | `src`, `fit` (`ImageFit`), `alt` |
| `Icon` | Named icon. | `name`, `size` |

`ImageFit` accepts `CONTAIN`, `COVER`, `FILL`, `NONE`.

## Indicators

| Widget | Role | Props |
|---|---|---|
| `ProgressBar` | Progress bar. | `value`, `indeterminate` |
| `Spinner` | Loading indicator. | `size` |

## Keys (`key`)

Give each child of a list a stable `key`. The reconciler uses keys to emit
`Reorder` instead of recreating widgets, and to match nodes across rebuilds.

## Walking the tree

Every widget exposes `child_nodes()` — use it to walk the tree generically,
without reaching into each type's internal storage. Leaves (`Text`, `Image`,
inputs) return `[]`.

!!! warning "Device support"
    The framework and the **Qt simulator** support the full widget set. The
    **device renderer (Compose)** tracks the base set (`Text` / `Button` /
    `Column` / `Row` / `Container` + `on_click`); newer widgets may fall back
    until the Kotlin host grows the matching cases (Track B follow-up). See the
    [roadmap](../roadmap.md).

## The event contract per widget

Each widget declares the event each handler emits via the `event_schemas`
classvar (e.g. `Button.event_schemas == {"on_click": TapEvent}`). This contract is
published by [`introspect()`](../referencia/api.md#introspection) and consumed by
the device boundary. See [Events](eventos.md).

## Recap

- Widgets are Pydantic models; always import from the package level
  (`from tempestroid import ...`).
- Layout: `Column`/`Row`/`Container`/`ScrollView`/`SafeArea`; content: `Text`,
  `Button`, media, and indicators.
- Value-bearing inputs emit a typed change event (`on_change` / `on_select`).
- Give list children a stable `key` — that's what lets the diff reorder instead
  of recreating.

## Next steps

➡️ Make widgets look good with **[Styles](estilos.md)**, understand typed
**[Events](eventos.md)**, or see full apps in the
**[Example gallery](exemplos.md)**.
