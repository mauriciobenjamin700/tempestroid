# Roadmap and phases

Development follows two tracks. **Track A** is the pure-Python framework
(desktop/CPython). **Track B** is the Android runtime (CPython 3.14 + Kotlin host
+ JNI bridge + Compose renderer). The full plan is in
[Design plan (EN)](plan.md).

## Track A — framework (pure Python)

| Phase | Scope | Status |
|---|---|---|
| A0 | Foundation: package, tooling, `tempest --help` | ✅ |
| A1 | Style model + typed widget primitives | ✅ |
| A2 | Reconciler: `build → diff → patch` | ✅ |
| A3 | Qt renderer: patches → `QWidget`s, `Style → Qt` | ✅ |
| A4 | Async event loop: asyncio ⨉ Qt (`qasync`) | ✅ |
| A5 | `tempest dev`: watcher, hot restart, command loop | ✅ |
| A6 | Typed event contract + introspection | ✅ |

## Track B — Android runtime

| Phase | Scope | Status |
|---|---|---|
| B0 | CPython 3.14 for arm64 | ✅ |
| B1 | Native wheels (pydantic-core) + device site-packages | ✅ |
| B2 | Kotlin host: embed CPython, boot the interpreter off the UI thread via JNI | ✅ |
| B3 | JNI bridge (native): bidirectional Python↔Kotlin transport | ✅ |
| B4 | Compose renderer (native): render the serialized tree, apply patches, route taps | ✅ |
| B5 | Dev server + QR (LAN code-push + log relay) | ✅ |
| B6 | Native capabilities (notifications) | ✅ |

## Polish and conformance

| Phase | Scope | Status |
|---|---|---|
| C | Polish: `new`/`build`/`run` + stateful hot reload | ✅ |
| D | Conformance golden snapshots (Qt vs Compose) | ✅ |

!!! note "Conformance suite (phase D)"
    `tests/conformance/` pins both `Style` translators: golden snapshots of
    `to_compose` + `to_qss`/`layout_alignment` for canonical styles (regenerate
    with `UPDATE_GOLDEN=1`), plus a per-field coverage-parity table that fails if
    either translator starts (or stops) handling a field without updating the
    documented divergences.

## Open follow-ups

- **Inputs on device (Compose):** the Kotlin renderer currently falls back for
  newer widgets; the matching cases still need to grow on the host. In the Qt
  simulator these widgets already work.
- **More native capabilities:** camera, sensors — following the `native_command`
  envelope + host module-router pattern.
