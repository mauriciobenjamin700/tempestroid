# Examples — tempestroid gallery

Each example is a single `app.py` exposing the standard contract — `make_state()`
+ `view(app)` — so it runs **two ways with no changes**:

```bash
# Desktop Qt simulator (needs the `qt` extra; installed by `uv sync`)
uv run python examples/<name>/app.py
uv run tempest dev examples/<name>/app.py     # + hot restart on save

# On a real Android device, over LAN code-push (phase B5)
adb reverse tcp:8765 tcp:8765                 # USB; skip on same Wi-Fi
uv run tempest serve examples/<name>/app.py
adb shell am start -n org.tempestroid.host/.MainActivity \
    --es tempest_dev_url http://localhost:8765
```

The gallery apps import Qt **lazily** (inside `if __name__ == "__main__"`), so the
device code-push path — which `exec`s the module on-device where Qt is absent —
only ever touches `make_state` / `view`.

## Apps

The **Device** column marks whether the example renders fully on the Compose
(Android) renderer today; a 〜 means it runs but some widgets degrade to the
default until the Kotlin host grows the matching cases (see *Constraints* below).

| App | What it shows | Widgets / patches exercised | Device |
|---|---|---|:--:|
| [`counter`](counter/app.py) | The basics: sync **and** `async` handlers, styled buttons. | `Text`, `Button`, `Row`/`Column`; `update`. | ✅ |
| [`tabs`](tabs/app.py) | Tabbed navigation: a persistent tab bar swaps the body while shared state survives the switch. | `Container` cards, view switching via `Replace`; `Input` / `Checkbox` state carried across tabs. | ✅ |
| [`shell`](shell/app.py) | The whole component set: a `Scaffold` with `AppBar`+`Burger`/`Drawer`, bottom `NavBar`, a `Card` of `ListTile`/`Avatar`/`Divider`, plus `Clock` + `Calendar`. | `tempestroid.components` lowering to primitives via `Component.render`. | ✅ |
| [`todo`](todo/app.py) | Type a task into the `Input`, tap to add/toggle/clear. | `Input` (`TextChangeEvent`); `insert` / `remove` / `update`. | ✅ |
| [`calculator`](calculator/app.py) | Dense button grid as the only input. | Nested `Row`/`Column`, 16 keyed buttons; `update` on the display. | ✅ |
| [`stopwatch`](stopwatch/app.py) | Async-first loop: a coroutine handler ticks via `asyncio.sleep` while the UI stays responsive. | Coalesced rebuilds driven off the loop; `update`. | ✅ |
| [`colorpicker`](colorpicker/app.py) | Dynamic `Style`: swatches re-color a live preview; toggles re-style its text. | `background` / `font_size` / `font_weight` updates through the diff. | ✅ |
| [`form`](form/app.py) | The value-bearing input widgets, each folding its typed event back into state. | `Input` / `Checkbox` / `DatePicker` / `FilePicker`; `TextChangeEvent` / `ToggleEvent` / `DateChangeEvent` / `FileSelectEvent`. | ✅ |
| [`gallery`](gallery/app.py) | The expanded component set + input styling + an implicit `Style` transition. | `Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView` / `TextArea`; secure + regex `Input`; `SlideEvent`; `Style.transition`. | 〜 |
| [`device_counter`](device_counter/app.py) | Minimal device-only counter (no Qt import) for the code-push path. | Same contract, Qt-free; styled button. | ✅ |
| [`onnxspike`](onnxspike/app.py) | Trilho G proof: `import numpy` + a computation run on the embedded interpreter. | numpy-on-android (needs `[vision]`). | ✅ (emu) |
| [`visionspike`](visionspike/app.py) | On-device ONNX vision: real image → `BitmapFactory` decode → `ort-vision-sdk` `Classifier` via the native AAR → top-1 + latency. Model embedded **or** downloaded; fp32 `.onnx` or quantized `.int8.ort`. | G1–G4: AAR backend, image decode, `tempest optimize`, model delivery. Needs `[vision]` + `--feature vision`. | ✅ (emu) |

## Constraints (current widget set)

The framework and the **Qt simulator** support the full widget set —
**`Text` / `Button` / `Column` / `Row` / `Container` / `ScrollView`** plus the
value-bearing inputs **`Input` / `TextArea` / `Checkbox` / `Switch` / `Slider` /
`DatePicker` / `FilePicker`** and the presentation widgets **`Image` / `Icon` /
`ProgressBar` / `Spinner`** (see the `form` and `gallery` examples) — with
`on_click` and the typed change events (`TextChangeEvent` / `ToggleEvent` /
`SlideEvent` / `DateChangeEvent` / `FileSelectEvent`).

The **device (Compose) renderer** renders **`Text` / `Button` / `Column` /
`Row` / `Container`** plus the value widgets **`Input` / `Checkbox` /
`DatePicker` / `FilePicker`**; the remaining widgets (`TextArea` / `Switch` /
`Slider` / `Image` / `Icon` / `ProgressBar` / `Spinner` / `ScrollView`) render as
an empty box until the Kotlin host grows the matching cases (Trilho B follow-up).
Value widgets carry a typed change event — `Input.on_change` (`TextChangeEvent`),
`Checkbox.on_change` (`ToggleEvent`), `DatePicker.on_change` (`DateChangeEvent`),
`FilePicker.on_select` (`FileSelectEvent`) — and the bridge passes the validated
event to any handler that accepts a positional argument (declare it
zero-argument to ignore the value). The text field is **controlled**: its value
lives in Python state, so each edit round-trips through `on_change`. Styles map
cleanly to Compose for `padding` / `gap` / `background` / `radius` / `color` /
`font_size` / `font_weight` / `text_align` / `arrangement` / `alignment`;
`margin`, `border`, and `grow` are not wired in the device renderer yet and
degrade to the default. The device-ready examples set an explicit `background`
on every `Button` (rather than leaning on the host's Material default), so they
read consistently across the Qt simulator and Compose; honoring that background
on the Compose `Button` itself is a tracked Trilho B follow-up.

> **Tip on handlers:** rebuilds compare handler props by identity, so a fresh
> `lambda` each build reads as a prop change (a known A2/A4 limitation). The
> examples still emit correct patches — just more than the strict minimum (e.g.
> tapping one calculator key re-sends every button's handler). Prefer stable
> handler references in production apps.
