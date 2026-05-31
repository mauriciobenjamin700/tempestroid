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

| App | What it shows | Widgets / patches exercised |
|---|---|---|
| [`counter`](counter/app.py) | The basics: sync **and** `async` handlers. | `Text`, `Button`, `Row`/`Column`; `update`. |
| [`todo`](todo/app.py) | Tap-driven list (no text input yet — tasks come from a fixed pool). | Stable-key list; `insert` (add), `remove` (clear), `update` (toggle). |
| [`calculator`](calculator/app.py) | Dense button grid as the only input. | Nested `Row`/`Column`, 16 keyed buttons; `update` on the display. |
| [`stopwatch`](stopwatch/app.py) | Async-first loop: a coroutine handler ticks via `asyncio.sleep` while the UI stays responsive. | Coalesced rebuilds driven off the loop; `update`. |
| [`colorpicker`](colorpicker/app.py) | Dynamic `Style`: swatches re-color a live preview; toggles re-style its text. | `background` / `font_size` / `font_weight` updates through the diff. |
| [`device_counter`](device_counter/app.py) | Minimal device-only counter (no Qt import) for the code-push path. | Same contract, Qt-free. |

## Constraints (current widget set)

The device renderer supports **`Text` / `Button` / `Column` / `Row` / `Container`**
and **`on_click`** only — there is no text-input, date-picker, or file-picker
widget yet (planned framework evolution). So the gallery is **button-driven**:
the todo list adds from a preset pool rather than from typed text, and the
calculator uses its keypad as the input surface. Styles map cleanly to Compose
for `padding` / `gap` / `background` / `radius` / `color` / `font_size` /
`font_weight` / `text_align` / `arrangement` / `alignment`; `margin`, `border`,
and `grow` are not wired in the device renderer yet and degrade to the default.

> **Tip on handlers:** rebuilds compare handler props by identity, so a fresh
> `lambda` each build reads as a prop change (a known A2/A4 limitation). The
> examples still emit correct patches — just more than the strict minimum (e.g.
> tapping one calculator key re-sends every button's handler). Prefer stable
> handler references in production apps.
