# UI testing (the "Playwright for native") 🎯

You already know how to build screens, wire events and run them in the simulator.
Now let's **test** a screen the way Playwright tests a web page — except with no
browser, no pixels and no magic `sleep`.

The tempestroid test driver drives your **tree (the IR)**: it mounts the app,
finds nodes by `key`/text/semantics, injects the same typed events a real tap
produces, and asserts the result — with **auto-wait** built into every action and
assertion (the tree must settle before proceeding).

!!! tip "Why it's stronger than Playwright"
    Playwright talks to the DOM. Here the "DOM" is our **IR** — identical across
    renderers. So the **same script** runs on the headless backend (fast, local)
    and on the `emulator` backend (a REAL Compose app on an Android emulator) —
    with no change to the test.

## The minimal example

A UI test file is an **ordinary app module** — it defines `view(app)` and
`make_state()` (the same contract a runnable app satisfies) — plus one or more
`async def test_*(page)` functions.

Let's test the counter. `examples/counter/app.py` already exists; we add an
`examples/counter/test_counter.py` next to it:

```python
from app import make_state, view  # re-use the sibling app's contract

from tempestroid.testing import Page

__all__ = ["make_state", "view"]


async def test_counter_starts_at_zero(page: Page) -> None:
    await page.expect_text("Count: 0")


async def test_increment_button_updates_count(page: Page) -> None:
    await page.expect_text("Count: 0")
    await page.tap(page.get_by_key("inc"))   # tap the "+" button
    await page.expect_text("Count: 1")       # auto-wait until the UI settles
```

Run it with:

```bash
uv run tempest uitest examples/counter/test_counter.py
```

Output:

```text
[PASS] test_counter_starts_at_zero
[PASS] test_increment_button_updates_count

2/2 passed on target 'headless'.
```

🚀 Done: an end-to-end flow test (event → state → re-render) **with no renderer
and no timing flake**.

## Understanding it piece by piece

### `page` — the mounted app

Each `test_*` receives a `page`: an app **freshly mounted** on a backend. Every
test gets its own `page` and its own state, so one test never contaminates
another.

### Locators — lazy queries

A **locator** is a *query*, not a captured node. It resolves against the
**current** tree every time an action or assertion needs it — so it survives a
rebuild. Create them off the `page`:

```python
page.get_by_key("inc")                       # by the stable IR key
page.get_by_text("Count: 0")                 # by text (substring)
page.get_by_text("Count: 0", exact=True)     # whole-text exact match
page.get_by_role("button", name="Save")      # by Semantics role/label (E9)
page.get_by_semantics(label="counter")       # by accessibility semantics
```

!!! note "Always late resolution"
    `locator.first` / `locator.all()` / `locator.count()` walk the **live** scene.
    An action (`tap`/`fill`) uses `locator.resolve()`, which requires **exactly
    one** node: zero or many → a clear error, never a silent "the first one".

### Actions — injected typed events

```python
await page.tap(locator)          # inject a TapEvent into the node's on_click/on_tap
await page.fill(locator, "abc")  # inject a TextChangeEvent(value="abc") into on_change
await page.back()                # pop the navigation stack (system back)
```

The action resolves the locator, picks the node's handler, validates the payload
into the **typed event** the widget declares (via `event_schemas`) and calls the
handler — exactly the path the device's `dispatchEvent` and Qt's `_invoke` take.

### Auto-wait — the end of `sleep`

Every assertion waits for the tree to **settle** before checking:

```python
await page.expect_text("Count: 2")     # until some node's text contains it
await page.expect_visible(locator)     # until the locator matches ≥ 1 node
await page.expect_count(locator, 3)    # until the locator matches exactly 3 nodes
```

"Settle" = no rebuild pending in the coalesced cycle (A4) **and** two consecutive
snapshots equal. No `sleep`: the wait ends the instant the UI stops changing, or
times out (default 5s) with the current tree dumped for diagnosis.

!!! check "Async handlers work for free"
    An `async` handler that `await`s before `set_state` is awaited by the action
    before the `settle`. The "+ (async)" button test passes with no `sleep`.

### `snapshot()` — the IR "screenshot"

```python
dump = page.snapshot()   # JSON-able dict: {"root": {...}, "overlays": [...]}
```

It is the headless analogue of a screenshot: a stable serialization of the tree
(types, keys, string/number props, children) for golden comparison.

!!! info "Pixel screenshots belong to the renderer"
    A real pixel screenshot is the Qt/device backend's job and lands with Trilho
    F8. The headless `snapshot()` covers what a flow test cares about: the tree's
    shape.

## Failures produce diagnostics

When an assertion does not hold within the timeout, the error carries the **tree
at the moment of failure**:

```text
[FAIL] test_increment
  AssertionError: expected text 'Count: 9' to be visible
    Traceback (most recent call last):
      ...
  tree at failure:
    {'root': {'type': 'Column', 'key': None, 'props': {}, 'children': [...]}}
```

## Targets (`--target`)

```bash
uv run tempest uitest examples/counter/test_counter.py --target headless
```

| Target | State | What it drives |
| --- | --- | --- |
| `headless` | ✅ available | The IR/state/events in-process, no renderer |
| `emulator` | ✅ available | A REAL app through the **Compose** renderer on an Android emulator |
| `qt` | ⏳ reserved | The Qt simulator in-process |
| `device` | ⏳ reserved | Compose on a physical device, over the bridge |

Since they all speak the **same IR + typed events**, your headless test runs on
the other targets unchanged.

### The `emulator` target — REAL Compose render + N in parallel

```bash
# one emulator (reuses a running one, e.g. emulator-5554)
uv run tempest uitest examples/counter/test_counter.py --target emulator

# N isolated emulators in parallel (capped by host CPU/RAM)
uv run tempest uitest examples/ --target emulator -j 3
```

The `emulator` backend (`EmulatorBackend`) drives a **real** app through the
**Compose** renderer: it owns a `DevServer` in **harness mode**, `adb -s <serial>
reverse`s, and launches the host in dev mode. The device's code-push client:

- **device → host:** POSTs the `mount` JSON and every `patch` batch back; the
  server keeps a host-side **mirror** (`Scene`, via
  `tempestroid.testing.mirror`). `page.scene()` reads that mirror.
- **host → device:** `page.tap(...)` reads the handler **token** from the
  mirrored node (`{"$handler": token}`), enqueues the event; the client
  long-polls, consumes it, and feeds `DeviceApp.handle_event` — **the same path a
  real Compose tap takes** — and the resulting patch flows back and updates the
  mirror. **No `adb input tap` by coordinate, no C/JNI change.**

**Auto-wait** (`settle`) polls the mirror *revision* until it has been quiet for a
short window AND the enqueued event was consumed — no fixed `sleep` as the primary
mechanism. `EmulatorPool` allocates/recycles N isolated instances (port
`5554 + i*2`), reusing running emulators and **capping N by the host's CPU/RAM**.

!!! check "REAL pixel screenshots"
    On the `emulator` target every test saves a screenshot under
    `docs/assets/emulator/uitest/<test>.png` captured via `adb exec-out
    screencap` — **real Compose pixels**, not the tree dump. That is the proof the
    device leaf behaves like the core.

## In code (no CLI)

You can also drive a backend directly, handy inside a `pytest`:

```python
from tempestroid.testing import HeadlessBackend, Page

page = Page(HeadlessBackend(make_state, view))
await page.mount()
await page.tap(page.get_by_key("inc"))
await page.expect_text("Count: 1")
```

## Recap

- A UI test is an **app + `async def test_*(page)` functions**.
- **Locators** (`get_by_key`/`get_by_text`/`get_by_role`/`get_by_semantics`)
  resolve against the **live IR**.
- **Actions** (`tap`/`fill`/`back`) inject **typed events** — the same path the
  real renderer takes.
- **Assertions** (`expect_text`/`expect_visible`/`expect_count`) **auto-wait**:
  they wait for the tree to settle, no `sleep`, no flake.
- The `headless` backend drives the **renderer-agnostic core**; the `emulator`
  backend runs the **same script** against a REAL Compose app on an Android
  emulator (`-j N` in parallel, a pixel screenshot per test). ✅
