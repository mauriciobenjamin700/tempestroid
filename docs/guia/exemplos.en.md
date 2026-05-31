# Example gallery

A set of runnable example apps lives in `examples/`. Each exposes the same
`make_state()` + `view(app)` contract, so it runs in the Qt simulator **and** on
the device via code-push, with no changes.

```bash
# Qt simulator on desktop (needs the `qt` extra; installed by `uv sync`)
uv run python examples/<name>/app.py
uv run tempest dev examples/<name>/app.py     # + hot reload on save

# On an Android device, via LAN code-push (phase B5)
adb reverse tcp:8765 tcp:8765                 # over USB; skip on the same Wi-Fi
uv run tempest serve examples/<name>/app.py
```

## Apps

| App | What it shows | Widgets / patches exercised |
|---|---|---|
| `counter` | The basics: sync **and** `async` handlers. | `Text`, `Button`, `Row`/`Column`; `update`. |
| `shell` | The composite components: a `Scaffold` with an `AppBar` on top and a `NavBar` at the bottom, body per tab. | `tempestroid.components` (`AppBar`/`Scaffold`/`NavBar`/`Header`) lowered to primitives via `Component.render`. |
| `todo` | Tap-driven list (no text input — items come from a fixed pool). | Stable-key list; `insert` / `remove` / `update`. |
| `calculator` | Dense button grid as the only input. | Nested `Row`/`Column`, 16 keyed buttons; `update` on the display. |
| `stopwatch` | Async-first loop: a coroutine handler ticks via `asyncio.sleep` without freezing the UI. | Coalesced rebuilds driven off the loop; `update`. |
| `colorpicker` | Dynamic `Style`: swatches re-color a live preview; toggles re-style its text. | `background` / `font_size` / `font_weight` updates through the diff. |
| `form` | The value-bearing inputs, each folding its typed event back into state. | `Input` / `Checkbox` / `DatePicker` / `FilePicker`; `TextChangeEvent` / `ToggleEvent` / `DateChangeEvent` / `FileSelectEvent`. |
| `gallery` | The expanded component set + input styling + an implicit `Style` transition. | `Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView` / `TextArea`; secure + regex `Input`; `SlideEvent`; `Style.transition`. |
| `device_counter` | Minimal device-only counter (no Qt import) for the code-push path. | Same contract, Qt-free. |

## Current widget set

The framework and the **Qt simulator** support the full set — `Text` / `Button`
/ `Column` / `Row` / `Container` plus the value-bearing inputs and the utility
widgets (`Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` /
`ScrollView` / `TextArea`) — with `on_click` and the typed change events.

The **device renderer (Compose)** currently renders `Text` / `Button` / `Column`
/ `Row` / `Container` and `on_click`; newer widgets fall back until the Kotlin
host grows the matching cases (Track B follow-up). So device-targeted apps stay
**button-driven**: `todo` adds from a preset pool instead of typed text, and
`calculator` uses its keypad as the input surface.

!!! tip "Stable handlers"
    Rebuilds compare handler props by identity, so a fresh `lambda` each build
    reads as a prop change (a known limitation). The examples still emit correct
    patches — just more than the strict minimum. Prefer stable handler references
    in production apps.
