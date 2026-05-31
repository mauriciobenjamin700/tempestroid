# Events

Events are the typed contract of the Python↔Kotlin boundary. When the native side
reports a tap or a value change, the payload arrives raw and is **validated
before** entering a handler — like FastAPI validates a request body.

## Event types

All inherit from `Event` (frozen Pydantic).

| Event | Fields | Emitted by |
|---|---|---|
| `TapEvent` | `x: float \| None`, `y: float \| None` | `Button.on_click` |
| `TextChangeEvent` | `value: str`, `valid: bool` (against the input's `pattern`) | `Input.on_change`, `TextArea.on_change` |
| `ToggleEvent` | `checked: bool` | `Checkbox.on_change`, `Switch.on_change` |
| `SlideEvent` | `value: float` | `Slider.on_change` |
| `DateChangeEvent` | `value: str` (ISO `yyyy-mm-dd`) | `DatePicker.on_change` |
| `FileSelectEvent` | `uri: str`, `name: str \| None` | `FilePicker.on_select` |

## The validation gate: `parse_event`

`parse_event(event_type, raw)` turns a raw payload (a mapping) into a typed event,
or raises `EventValidationError` with structured per-field errors (JSON-
serializable):

```python
from tempestroid import EventValidationError, TextChangeEvent, parse_event

event = parse_event(TextChangeEvent, {"value": "hi"})   # -> TextChangeEvent(value="hi")

try:
    parse_event(TextChangeEvent, {})                      # missing required field
except EventValidationError as exc:
    print(exc.errors)   # [{"loc": ("value",), "type": "missing", ...}]
```

## Handlers

A handler may receive the typed event **or** be zero-argument when the value is
not needed. The runtime detects the arity and passes (or omits) the event:

```python
# Receives the typed event:
def on_name(event: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "name", event.value))

# Zero-argument (ignores the payload):
Button(label="+", on_click=lambda: app.set_state(...))
```

Handlers may be sync or `async` — the runtime schedules coroutines on the asyncio
loop without freezing the UI.

## Typed handler alias

To annotate handler props, the package exports **`EventHandler`** — the generic
typed handler-prop wrapper (e.g. `on_click`, `on_change`). It carries a
`WithJsonSchema` annotation so handler-bearing widgets don't break JSON-schema
generation.

## The contract as data

Each widget declares the event each handler emits via the `event_schemas`
classvar. The [`introspect()`](../referencia/api.md#introspection) function
publishes all of this as JSON — widget prop schemas, the event each handler emits,
and each event's payload schema. This is what powers `tempest spec` and the device
boundary.

## Recap

- Events are frozen Pydantic models (`TapEvent`, `TextChangeEvent`, …).
- `parse_event` is the gate that validates the raw payload before the handler —
  like FastAPI validating a request body.
- Handlers may take the typed event or be zero-argument; sync or `async`.
- The contract (`event_schemas` + `introspect()`) is published as JSON by
  `tempest spec`.

## Next steps

➡️ Inspect the contract with the **[CLI (`tempest spec`)](cli.md)**, or see real
handlers in the **[Example gallery](exemplos.md)**.
