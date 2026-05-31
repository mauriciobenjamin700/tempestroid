# Installation

## Development (this repository)

The development workflow uses [uv](https://docs.astral.sh/uv/). A single command
installs the core, the tooling, and the Qt simulator:

```bash
uv sync        # core + dev tooling + Qt simulator
```

Beyond the runtime dependencies, this installs:

- the dev group (`ruff`, `pyright`, `pytest`, `pytest-asyncio`);
- the Qt simulator (`PySide6`, `qasync`) — part of the dev/test loop;
- the documentation site (`mkdocs-material` + the language plugin).

## End users

Consumers install via `pip`. The **core** depends only on `pydantic`; Qt is an
optional extra:

```bash
pip install tempestroid          # core only (needs just pydantic)
pip install "tempestroid[qt]"    # with the desktop simulator (PySide6 + qasync)
```

## Documentation

The documentation site (this content) is built with MkDocs Material, installed by
`uv sync`:

```bash
uv run mkdocs serve              # local server with hot reload at http://127.0.0.1:8000
uv run mkdocs build --strict     # production build; fails on any warning
```

The header includes a **PT-BR / EN-US language switcher** powered by the
`mkdocs-static-i18n` plugin.

## Prerequisites per target

| Target | Needs |
|---|---|
| Qt simulator (desktop) | Python ≥ 3.11 + the `qt` extra (`PySide6`/`qasync`). |
| Android device | Android SDK/NDK + the `android-host/` tree (Track B). Does not run without the toolchain. |

!!! warning "Track B (Android) needs the toolchain"
    Packaging and running on a device require Android SDK/NDK and the
    `android-host/` tree. See the [Android runtime research](research/android-runtime.md)
    and the [runbook](research/android-runbook.md).
