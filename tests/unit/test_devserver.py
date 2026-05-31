"""Tests for the LAN code-push dev server and client (phase B5)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from tempestroid.bridge.device import Bridge, LoopbackBridge
from tempestroid.devserver import DevServer, run_dev_client, source_hash

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


def _get(url: str) -> str:
    """Fetch a URL body (blocking)."""
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
        return response.read().decode("utf-8")


def test_devserver_serves_and_reflects_edits(tmp_path: Path) -> None:
    """``/version`` and ``/app`` reflect the file, including edits after start."""
    app = tmp_path / "app.py"
    app.write_text("x = 1\n", encoding="utf-8")
    server = DevServer(app, host="127.0.0.1", port=0)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        version = json.loads(_get(f"{base}/version"))
        assert version["hash"] == source_hash("x = 1\n")

        payload = json.loads(_get(f"{base}/app"))
        assert payload["source"] == "x = 1\n"

        # Editing the file changes what the server reports — no restart needed.
        app.write_text("x = 2\n", encoding="utf-8")
        assert json.loads(_get(f"{base}/version"))["hash"] == source_hash("x = 2\n")
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

    responses = {
        "/version": json.dumps({"hash": "h1"}),
        "/app": json.dumps({"hash": "h1", "source": _APP_SRC}),
    }

    async def fetch(url: str) -> str:
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
