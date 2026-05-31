# Quick start

Every tempestroid app honors the same contract: a `make_state()` factory and a
`view(app)` builder. That contract runs **unchanged** in the Qt simulator and on
the device.

## A minimal counter

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Style, Text, Widget
from tempestroid.renderers.qt import run_qt


@dataclass
class CounterState:
    value: int = 0


def make_state() -> CounterState:
    return CounterState()


def view(app: App[CounterState]) -> Widget:
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

Run it directly in the simulator:

```bash
uv run python app.py
```

## The `make_state` / `view` contract

- **`make_state() -> S`** — returns the initial state. Called on every hot
  restart, so it must build clean state.
- **`view(app: App[S]) -> Widget`** — builds the UI tree from `app.state`. Wire
  handlers to `app.set_state(...)`; each change schedules a coalesced rebuild (one
  diff per tick).

`set_state` takes a function that **mutates** state in place; `App` rebuilds the
`view`, diffs it against the previous tree, and hands the patches to the renderer.

## Development loop

```bash
uv run tempest dev app.py        # simulator + hot reload on save
```

In the `tempest dev` cockpit: `r` hot-reloads (state preserved), `R` restarts
clean, `s` raises the window, `q` quits. Saving the file triggers a hot reload; if
the reload is incompatible with the live state, it falls back to a clean restart.

## Async handlers

Handlers may be `async` — the runtime schedules them on the asyncio loop without
freezing the UI:

```python
import asyncio


async def increment_later() -> None:
    await asyncio.sleep(0.5)
    app.set_state(lambda s: setattr(s, "value", s.value + 1))
```

See the full example at
[`examples/counter/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/counter/app.py)
and the [gallery](guia/exemplos.md) for more apps.
