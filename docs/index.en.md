# tempestroid

Build **native Android apps** in **typed Python**.

You write one declarative, fully typed widget tree (a Pydantic IR). A
**renderer-agnostic reconciler** diffs it into patches. Two leaf renderers apply
those patches: **Qt** for the desktop simulator and **Jetpack Compose** for the
device. The runtime is **async-first**, with an Expo-style dev loop (hot reload in
the simulator and LAN code-push on the device).

!!! note "A framework, not a web service"
    There is no FastAPI, SQLAlchemy, Redis, or HTTP layering here. The focus is
    the typed UI tree and the reconciler. See the [design plan](plan.md) for the
    full design and the [phase roadmap](roadmap.md).

!!! tip "🤖 Read the project with your AI (`llms.txt`)"
    This site publishes two files following the
    [llmstxt.org](https://llmstxt.org/) convention so you can hand your AI
    assistant (Claude, ChatGPT, Cursor, etc.) the whole project as a reference —
    **no server, no MCP**:

    - **[`/llms.txt`](https://mauriciobenjamin700.github.io/tempestroid/llms.txt)**
      — a lean index (summary + links to every page). Use it when your AI can
      follow the links.
    - **[`/llms-full.txt`](https://mauriciobenjamin700.github.io/tempestroid/llms-full.txt)**
      — the **entire** documentation concatenated into one Markdown file. Use it
      to paste/attach everything at once when your AI cannot browse.

    **How to use:** paste the URL (or the content) of `llms-full.txt` into your
    assistant's context and ask it to use it as the tempestroid reference. The
    files are regenerated on every docs deploy, so they are always current.

## Why

- **Typed end to end.** Style model, widget primitives, events, and the
  Python↔Kotlin boundary contract are all Pydantic v2 / fully typed. `pyright`
  runs in strict mode.
- **One tree, two targets.** The reconciler is pure data-in → patches-out. All
  platform divergence is confined to the two `Style` translators (Qt and Compose).
- **Async-first.** Event handlers and lifecycle hooks may be sync or `async`;
  Python runs on a background asyncio loop, never the UI thread.
- **Fast inner loop.** `tempest dev` watches your file and hot-reloads the Qt
  simulator on save — no device or emulator needed for UI work.

## How it works

```text
   view(app) ──build──▶  Node tree (IR)
                              │
                            diff           pure, renderer-agnostic
                              ▼
                          [ Patch ]        Insert / Remove / Update / Reorder / Replace
                         ╱          ╲
                  Qt renderer      Compose renderer
                  (simulator)        (device)
```

1. `view(app) -> Widget` builds a declarative widget tree from current state.
2. `build` lowers it to a `Node` IR; `diff` compares old vs. new and emits a
   minimal `Patch` list.
3. A renderer applies patches to live widgets. State changes coalesce into one
   rebuild per tick.

## Next steps

- [Installation](instalacao.md) — install the framework and the simulator.
- [Quick start](inicio-rapido.md) — your first app in a few lines.
- [Architecture](arquitetura.md) — IR, reconciler, renderers, and the bridge.
- [User guide](guia/widgets.md) — widgets, styles, events, and the CLI.
