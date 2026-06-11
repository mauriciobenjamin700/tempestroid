"""Tests for the LAN code-push dev server and client (phase B5)."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any

from tempestroid.bridge.device import Bridge, LoopbackBridge
from tempestroid.devserver import DevServer, run_dev_client


def _bundle_bytes(source: str, entry: str = "main.py") -> bytes:
    """Build a single-file project bundle (manifest + entry) for tests.

    Mirrors what ``DevServer.bundle`` / ``tempest build`` produce: a zip with a
    ``tempest_bundle.json`` manifest naming the entry plus the entry source.
    """
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("tempest_bundle.json", json.dumps({"entry": entry}))
        archive.writestr(entry, source)
    return buffer.getvalue()


_APP_SRC = """
from dataclasses import dataclass
from tempestroid import App, Button, Column, Text, Widget


@dataclass
class State:
    n: int = 0


def make_state() -> State:
    return State()


def _inc(s: State) -> None:
    s.n += 1


def view(app):
    return Column(children=[
        Text(content="n=" + str(app.state.n)),
        Button(label="+", on_click=lambda: app.set_state(_inc)),
    ])
"""


_NAV_SRC = """
from dataclasses import dataclass
from tempestroid import App, Button, Column, Route, Text, Widget


@dataclass
class State:
    pass


def make_state() -> State:
    return State()


def view(app):
    return Column(children=[
        Text(content="route=" + app.nav.top.name),
        Button(label="go", on_click=lambda: app.push(Route(name="/b"))),
    ])
"""


def _get(url: str) -> str:
    """Fetch a URL body as text (blocking)."""
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
        return response.read().decode("utf-8")


def _get_bytes(url: str) -> bytes:
    """Fetch a URL body as raw bytes (blocking)."""
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
        return response.read()


def test_devserver_serves_bundle_and_reflects_edits(tmp_path: Path) -> None:
    """``/version`` tracks the tree and ``/bundle`` carries the whole project.

    Editing any file changes the ``/version`` signature without a restart, and
    ``/bundle`` returns a zip containing the manifest + every project file.
    """
    import io
    import zipfile

    app = tmp_path / "app.py"
    app.write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "helper.py").write_text("y = 2\n", encoding="utf-8")
    server = DevServer(app, host="127.0.0.1", port=0)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        first = json.loads(_get(f"{base}/version"))["hash"]
        assert first

        with zipfile.ZipFile(io.BytesIO(_get_bytes(f"{base}/bundle"))) as archive:
            names = set(archive.namelist())
        assert {"tempest_bundle.json", "app.py", "helper.py"} <= names

        # Editing any file changes the signature — no restart needed.
        (tmp_path / "helper.py").write_text("y = 30000\n", encoding="utf-8")
        assert json.loads(_get(f"{base}/version"))["hash"] != first
    finally:
        server.stop()


def test_devserver_on_fetch_fires_on_app_get(tmp_path: Path) -> None:
    """``on_fetch`` fires on ``GET /app`` (not ``/version``) — the one-shot hook.

    ``tempest build`` uses this to tear its short-lived server down once the
    device has fetched the app source.
    """
    app = tmp_path / "app.py"
    app.write_text("x = 1\n", encoding="utf-8")
    fetched = threading.Event()
    server = DevServer(app, host="127.0.0.1", port=0, on_fetch=fetched.set)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        _get(f"{base}/version")
        assert not fetched.is_set()  # a cheap poll must not trip the hook
        _get(f"{base}/app")
        assert fetched.wait(timeout=2.0)
    finally:
        server.stop()


async def test_code_push_round_trip() -> None:
    """The client mounts on first poll, then routes an event back to a patch."""
    bridges: list[LoopbackBridge] = []

    def make_bridge() -> Bridge:
        bridge = LoopbackBridge()
        bridges.append(bridge)
        return bridge

    sink: dict[str, Any] = {}

    def register_sink(cb: Any) -> None:
        sink["cb"] = cb

    responses: dict[str, bytes] = {
        "/version": json.dumps({"hash": "h1"}).encode(),
        "/bundle": _bundle_bytes(_APP_SRC),
    }

    async def fetch(url: str) -> bytes:
        for path, body in responses.items():
            if url.endswith(path):
                return body
        raise ValueError(url)

    await run_dev_client(
        "http://dev",
        make_bridge=make_bridge,
        register_sink=register_sink,
        fetch=fetch,
        poll_interval=0,
        max_polls=1,
        log=lambda _: None,
    )

    assert len(bridges) == 1
    assert bridges[0].sent[0]["kind"] == "mount"

    # Inject a tap on the "+" button (token "1:on_click"); expect a patch back.
    import asyncio

    sink["cb"]("1:on_click", "{}")
    await asyncio.sleep(0.05)
    assert any(m["kind"] == "patch" for m in bridges[0].sent)


async def test_dev_client_routes_native_result_to_resolver(
    monkeypatch: Any,
) -> None:
    """A native-result token is routed to the request/response resolver.

    Regression: the dev client's event sink must route the reserved
    ``__native_result__:<id>`` token to :func:`resolve_native_result` (as the
    on-device ``run_device`` does), or ``async`` capability calls (geolocation,
    camera, storage, clipboard, bluetooth) would hang forever over code-push.
    A regular widget token must still reach the app, not the resolver.
    """
    import asyncio

    from tempestroid.devserver import client as client_mod

    resolved: list[tuple[str, dict[str, Any]]] = []

    def _spy(request_id: str, payload: dict[str, Any]) -> bool:
        resolved.append((request_id, payload))
        return True

    monkeypatch.setattr(client_mod, "resolve_native_result", _spy)

    bridges: list[LoopbackBridge] = []

    def make_bridge() -> Bridge:
        bridge = LoopbackBridge()
        bridges.append(bridge)
        return bridge

    sink: dict[str, Any] = {}

    def register_sink(cb: Any) -> None:
        sink["cb"] = cb

    responses: dict[str, bytes] = {
        "/version": json.dumps({"hash": "h1"}).encode(),
        "/bundle": _bundle_bytes(_APP_SRC),
    }

    async def fetch(url: str) -> bytes:
        for path, body in responses.items():
            if url.endswith(path):
                return body
        raise ValueError(url)

    await run_dev_client(
        "http://dev",
        make_bridge=make_bridge,
        register_sink=register_sink,
        fetch=fetch,
        poll_interval=0,
        max_polls=1,
        log=lambda _: None,
    )

    # A native-result token goes to the resolver, not the widget handler.
    sink["cb"](f"{client_mod.NATIVE_RESULT_PREFIX}req-1", json.dumps({"ok": True}))
    await asyncio.sleep(0.05)
    assert resolved == [("req-1", {"ok": True})]

    # A regular widget token still reaches the app (produces a patch).
    sink["cb"]("1:on_click", "{}")
    await asyncio.sleep(0.05)
    assert any(m["kind"] == "patch" for m in bridges[0].sent)


async def test_dev_client_routes_back_token_to_pop() -> None:
    """The reserved BACK_TOKEN pops a navigation screen over code-push.

    Regression: the dev client's event sink must route BACK_TOKEN straight to
    ``App.pop`` (as the on-device ``run_device`` does), or the Android system
    back button would not pop under ``tempest serve`` — it would be dropped as
    an unmatched widget event even though the bundled-APK path pops correctly.
    """
    import asyncio

    from tempestroid.bridge.protocol import BACK_TOKEN

    bridges: list[LoopbackBridge] = []

    def make_bridge() -> Bridge:
        bridge = LoopbackBridge()
        bridges.append(bridge)
        return bridge

    sink: dict[str, Any] = {}

    def register_sink(cb: Any) -> None:
        sink["cb"] = cb

    responses: dict[str, bytes] = {
        "/version": json.dumps({"hash": "h1"}).encode(),
        "/bundle": _bundle_bytes(_NAV_SRC),
    }

    async def fetch(url: str) -> bytes:
        for path, body in responses.items():
            if url.endswith(path):
                return body
        raise ValueError(url)

    await run_dev_client(
        "http://dev",
        make_bridge=make_bridge,
        register_sink=register_sink,
        fetch=fetch,
        poll_interval=0,
        max_polls=1,
        log=lambda _: None,
    )

    # Push a screen via the button handler → the stack is now ["/", "/b"].
    sink["cb"]("1:on_click", "{}")
    await asyncio.sleep(0.05)
    assert any("route=/b" in json.dumps(m) for m in bridges[0].sent)

    # The system back token pops it → the latest patch reflects the root route.
    sink["cb"](BACK_TOKEN, "{}")
    await asyncio.sleep(0.05)
    assert "route=/" in json.dumps(bridges[0].sent[-1])


def test_dev_client_imports_without_typer() -> None:
    """The device code-push client imports without ``typer`` installed.

    Regression: the Android runtime does not bundle ``typer``, but the dev
    client imports :func:`spec_from_source` from :mod:`tempestroid.cli`, whose
    package ``__init__`` must not eagerly import the Typer-based ``main``.
    Run in a subprocess with ``typer`` blocked so a stray import fails loudly
    instead of silently passing because the test process already loaded it.
    """
    code = (
        "import sys; sys.modules['typer'] = None;"
        " import tempestroid.devserver.client;"
        " import tempestroid.cli.app_loader;"
        " assert hasattr(tempestroid.devserver.client, 'serve_device');"
        " print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


async def test_dev_client_routes_reserved_stream_tokens(monkeypatch: Any) -> None:
    """The dev client mirrors jni.py and routes the E8 reserved stream tokens.

    Regression (lesson E0d): the dev client's event sink must route the reserved
    sensor / lifecycle / connectivity tokens to the same native dispatch hooks
    ``run_device`` uses — otherwise the ``tempest serve`` code-push path silently
    drops them (no widget handler matches).
    """
    import asyncio

    from tempestroid.bridge.protocol import (
        BACKGROUND_TOKEN_PREFIX,
        CONNECTIVITY_TOKEN_PREFIX,
        LIFECYCLE_TOKEN,
        SENSOR_TOKEN_PREFIX,
    )
    from tempestroid.devserver import client as client_mod

    calls: list[tuple[str, Any]] = []

    def _spy_sensor(sensor_type: str, payload: dict[str, Any]) -> None:
        calls.append(("sensor", (sensor_type, payload)))

    def _spy_lifecycle(payload: dict[str, Any]) -> None:
        calls.append(("lifecycle", payload))

    def _spy_connectivity(payload: dict[str, Any]) -> None:
        calls.append(("connectivity", payload))

    def _spy_background(name: str) -> None:
        calls.append(("background", name))

    monkeypatch.setattr(client_mod, "dispatch_sensor_event", _spy_sensor)
    monkeypatch.setattr(client_mod, "dispatch_lifecycle_event", _spy_lifecycle)
    monkeypatch.setattr(client_mod, "dispatch_connectivity_event", _spy_connectivity)
    monkeypatch.setattr(client_mod, "dispatch_background_task", _spy_background)

    sink: dict[str, Any] = {}

    def register_sink(cb: Any) -> None:
        sink["cb"] = cb

    responses: dict[str, bytes] = {
        "/version": json.dumps({"hash": "h1"}).encode(),
        "/bundle": _bundle_bytes(_APP_SRC),
    }

    async def fetch(url: str) -> bytes:
        for path, body in responses.items():
            if url.endswith(path):
                return body
        raise ValueError(url)

    await run_dev_client(
        "http://dev",
        make_bridge=LoopbackBridge,
        register_sink=register_sink,
        fetch=fetch,
        poll_interval=0,
        max_polls=1,
        log=lambda _: None,
    )

    sink["cb"](f"{SENSOR_TOKEN_PREFIX}:gyroscope", json.dumps({"values": [1.0]}))
    sink["cb"](LIFECYCLE_TOKEN, json.dumps({"state": "foreground"}))
    sink["cb"](f"{CONNECTIVITY_TOKEN_PREFIX}:mobile", json.dumps({"state": "mobile"}))
    sink["cb"](f"{BACKGROUND_TOKEN_PREFIX}:sync", "{}")
    await asyncio.sleep(0.05)

    assert ("sensor", ("gyroscope", {"values": [1.0]})) in calls
    assert ("lifecycle", {"state": "foreground"}) in calls
    assert ("connectivity", {"state": "mobile"}) in calls
    assert ("background", "sync") in calls


_BROKEN_APP_SRC = """
# Top-level import the device cannot satisfy — the same shape as an app file
# importing the Qt renderer (absent on the device). A guaranteed-missing module
# is used so the load fails in any environment (the test host *has* PySide6).
import tempest_missing_module_xyz  # noqa: F401

def make_state():
    return None

def view(app):
    raise AssertionError("never reached: the import above already failed")
"""


async def test_dev_client_mounts_error_screen_on_broken_app() -> None:
    """A bundle that fails to load mounts an on-device error screen, not a crash.

    Regression: an app file with a top-level ``import`` the device cannot satisfy
    (e.g. the Qt renderer) used to white-screen silently — the load exception was
    only logged and the renderer never received a mount. The client now catches
    it and mounts a red error screen carrying the traceback, and the poll loop
    keeps running so the next saved edit recovers.
    """
    bridges: list[LoopbackBridge] = []

    def make_bridge() -> Bridge:
        bridge = LoopbackBridge()
        bridges.append(bridge)
        return bridge

    logs: list[str] = []
    responses: dict[str, bytes] = {
        "/version": json.dumps({"hash": "h1"}).encode(),
        "/bundle": _bundle_bytes(_BROKEN_APP_SRC),
    }

    async def fetch(url: str) -> bytes:
        for path, body in responses.items():
            if url.endswith(path):
                return body
        raise ValueError(url)

    await run_dev_client(
        "http://dev",
        make_bridge=make_bridge,
        register_sink=lambda _cb: None,
        fetch=fetch,
        poll_interval=0,
        max_polls=1,
        log=logs.append,
    )

    # An error screen was mounted (not left blank), and the failure was logged.
    assert len(bridges) == 1
    mount = bridges[0].sent[0]
    assert mount["kind"] == "mount"
    blob = json.dumps(mount)
    assert "App failed to load" in blob
    # The traceback names the offending import.
    assert "tempest_missing_module_xyz" in blob
    assert any("app failed to load" in line.lower() for line in logs)


async def test_dev_client_recovers_after_error_screen() -> None:
    """After an error screen, the next (fixed) push starts the app clean.

    The poll loop must not get stuck on the error state: once the source is
    fixed and the version changes, the client starts a fresh app rather than
    trying to hot-reload the error screen's throwaway state.
    """
    bridges: list[LoopbackBridge] = []

    def make_bridge() -> Bridge:
        bridge = LoopbackBridge()
        bridges.append(bridge)
        return bridge

    # Poll 1 serves the broken app (h1); once its bundle is fetched, flip to the
    # fixed app (h2) so poll 2 sees a new version and recovers — deterministic,
    # no gather/sleep race.
    state: dict[str, Any] = {"hash": "h1", "bundle": _bundle_bytes(_BROKEN_APP_SRC)}

    async def fetch(url: str) -> bytes:
        if url.endswith("/version"):
            return json.dumps({"hash": state["hash"]}).encode()
        if url.endswith("/bundle"):
            served = state["bundle"]
            state["hash"] = "h2"
            state["bundle"] = _bundle_bytes(_APP_SRC)
            return served
        raise ValueError(url)

    await run_dev_client(
        "http://dev",
        make_bridge=make_bridge,
        register_sink=lambda _cb: None,
        fetch=fetch,
        poll_interval=0,
        max_polls=2,
        log=lambda _: None,
    )

    # First bridge = error screen; second = the recovered real app, mounted.
    assert len(bridges) == 2
    assert "App failed to load" in json.dumps(bridges[0].sent[0])
    assert bridges[1].sent[0]["kind"] == "mount"
    assert "n=0" in json.dumps(bridges[1].sent[0])
