# Quick start

This guide takes you from zero to a running app in the simulator in a few
minutes — even if this is your first time with tempestroid. The path is always
the same: **create** a project, **run** it in the simulator, **edit** it and see
the change live.

!!! tip "Prerequisites"
    - **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/) installed.
    - The framework with the Qt simulator: `pip install "tempestroid[qt]"` (or,
      in this development repository, `uv sync`). Details in
      [Installation](instalacao.en.md).
    - On WSL/Linux without a graphical environment, the Qt simulator needs a
      display server. See [Run on device / WSL](guia/dispositivo-wsl.en.md).

## Step 1 — Create a project

You are already inside your project folder (and its virtualenv). Run
`tempest new` with **no arguments** to generate the starter files **right here** —
an `app.py` (example counter), `pyproject.toml`, `README.md` and `.gitignore` —
using the **current folder name as the app id**. No extra wrapping directory.

```bash
mkdir my-app && cd my-app            # your project folder (with its venv)
uv run tempest new                   # scaffold HERE; id = "my-app"
```

> Want a subdirectory? Pass a name: `uv run tempest new OtherApp` creates
> `OtherApp/`. But the recommended flow is the in-place one above.
>
> Installed via `pip`? The binary is available as `tempest new` (without
> `uv run`). Throughout this guide we use `uv run tempest …` because it is the
> repository flow; drop the `uv run ` if you installed via `pip`.

The generated `app.py` is **pure Python**, with no Qt import at module level —
so the **same file** runs in the desktop simulator, ships to the device via
`tempest serve`, and packages with `tempest build` without changing a line.

## Step 2 — Run it in the simulator

```bash
uv run tempest dev                     # opens the Qt simulator + hot reload
```

`tempest dev` (with no argument) reads the app path from `[tool.tempest] app` in
`pyproject.toml`, so you run it from the project root without pointing at the
file. A window opens with the counter (`-`, the value, `+`). The terminal becomes an
interactive *cockpit*:

| Key | Action |
|---|---|
| `r` | Hot reload — reloads the code **preserving the current state**. |
| `R` | Hot restart — reloads from scratch (clean state via `make_state`). |
| `s` | Raises the simulator window to the front. |
| `q` | Quits. |

## Step 3 — Edit and see it live

With the simulator open, open `app.py` in your editor and change some text
— for example the title inside `Text`. **Save the file.** `tempest dev` detects
the write and hot-reloads automatically: the window updates without losing the
counter.

If an edit breaks the app, the error is printed in the terminal and the loop
**survives** — fix it and save again. If the reload is incompatible with the
live state, it falls back automatically to a clean restart.

That's the full development cycle. The rest of this guide explains **what** you
just ran.

## The mental model

Every tempestroid app honors a **two-function** contract:

- **`make_state() -> S`** — returns the **initial state**. Called on every hot
  restart, so it must build clean state. `S` is any object of yours (a
  `@dataclass` is the natural choice).
- **`view(app: App[S]) -> Widget`** — takes the app and returns the **UI tree**
  for the current state. It's a pure function of state → widgets: given the same
  state, it returns the same tree.

The cycle that connects the two:

```text
   state ──view(app)──▶ widget tree ──diff──▶ patches ──▶ screen
     ▲                                                       │
     └─────────────── app.set_state(...) ◀── event handler ◀─┘
```

1. `view` builds the tree from `app.state`.
2. You wire *handlers* (click, etc.) to `app.set_state(...)`.
3. When a handler calls `set_state`, `App` rebuilds the `view`, diffs it against
   the previous tree, and hands only the *patches* (minimal changes) to the
   renderer. Multiple `set_state` calls in the same *tick* become a **single**
   coalesced rebuild.

`set_state` takes a function that **mutates state in place**:

```python
app.set_state(lambda s: setattr(s, "value", s.value + 1))
```

You never touch the screen directly — you only describe the UI as a function of
state and change the state. The framework handles the rest.

## A counter from scratch

The scaffold already gives you a full counter, but it's worth building the
minimum by hand to understand each piece. Create an `app.py`:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Style, Text, Widget
from tempestroid.renderers.qt import run_qt


@dataclass
class CounterState:
    """The app's state: a single counter."""

    value: int = 0


def make_state() -> CounterState:
    """Return the initial state (called on every hot restart)."""
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Build the UI tree for the current state."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        style=Style(gap=8.0),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(run_qt(make_state(), view, title="counter"))
```

Reading top to bottom:

- **`CounterState`** — your state, a simple `dataclass` with a `value` field.
- **`make_state`** — the initial-state factory.
- **`view`** — describes the screen: a `Column` (stacks vertically) with a `Text`
  showing the value and a `Button` that increments. `app.state.value` reads the
  state; `increment` calls `set_state` to change it.
- **`key="..."`** — identifies each widget so the *diff* can match the old widget
  to the new one across rebuilds. Give stable *keys* to list children.
- **`Style(gap=8.0)`** — spacing between children. Styles are typed, immutable
  objects (see the [style guide](guia/estilos.en.md)).
- **`if __name__ == "__main__"`** — `run_qt` opens the window when you run the
  file directly. Keep the Qt import **inside** this block (or only here at the
  top, unused by `view`/`make_state`) so the file still runs on the device, which
  has no Qt.

Run it directly, without the cockpit:

```bash
uv run python app.py
```

Or with hot reload (recommended during development):

```bash
uv run tempest dev app.py
```

## Async handlers

Handlers may be `async` — the runtime schedules them on the asyncio loop without
freezing the UI. Useful for awaiting I/O (network, disk) before updating state:

```python
import asyncio


def view(app: App[CounterState]) -> Widget:
    async def increment_later() -> None:
        await asyncio.sleep(0.5)
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Button(label="+0.5s", on_click=increment_later, key="inc")
```

## Common problems

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: tempestroid` | Framework not installed in the env. Run `uv sync` (repo) or `pip install "tempestroid[qt]"`. |
| `PySide6` / Qt import error when running `dev` | The `qt` extra is not installed. Use `pip install "tempestroid[qt]"`. |
| `app.py must define a make_state()` / `view` | The file must expose **both** functions at module level, with those exact names. |
| The window doesn't open on headless WSL/Linux | No display server. See [device / WSL](guia/dispositivo-wsl.en.md). |
| Edits don't reload | Make sure you're running via `tempest dev` (not `python app.py`) and that you saved the file; or press `r`. |

## Next steps

- [Widgets](guia/widgets.en.md) — all primitives (`Text`, `Column`, `Row`,
  `Button`, inputs, media…).
- [Styles](guia/estilos.en.md) — the typed `Style` model.
- [Events](guia/eventos.en.md) — the typed event contract.
- [CLI](guia/cli.en.md) — all `tempest` commands.
- [Example gallery](guia/exemplos.en.md) — full apps to study.

See also the reference example at
[`examples/counter/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/counter/app.py).
