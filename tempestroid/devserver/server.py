"""LAN code-push dev server (phase B5, dev-machine side).

Serves the app's project to the device over HTTP and relays the device's logs
back to the terminal — the Expo-style inner loop for on-device development:

* ``GET /version`` → ``{"hash": <tree signature>}`` (cheap poll, no archive).
* ``GET /bundle``  → the project ``.zip`` bytes (whole multi-file tree).
* ``GET /app``     → ``{"hash": ..., "source": <entry source>}`` (legacy
  single-file fallback for older hosts).
* ``POST /log``    → body is printed to the terminal, prefixed ``[device]``.

The tree is re-stat'd on every ``/version`` poll, so saving any file in the
project is enough for the device's poll loop to pick up the change and
hot-reload. The full archive is rebuilt lazily — only when the signature
changes — so polling stays cheap on large projects.

**Harness mode (F9 emulator backend).** When constructed with ``harness=True``
the server also acts as the host-side end of the UI test driver: it accepts the
device's POSTed mount/patch JSON, keeps a host-side
:class:`~tempest_core.core.ir.Scene` mirror in step (via
:mod:`tempestroid.testing.mirror`), exposes that mirror plus a monotonic
``revision`` to the in-process owner (the :class:`EmulatorBackend`), and serves a
queue of host→device events the client long-polls. Harness mode is **off by
default**, so a normal ``tempest serve`` is byte-for-byte unaffected — the extra
endpoints simply 404.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from tempest_core.core.ir import Scene

from tempestroid.cli.bundle import (
    build_bundle,
    resolve_project,
    tree_signature,
)
from tempestroid.testing.mirror import apply_patches, deserialize_scene

__all__ = ["DevServer", "source_hash"]


def source_hash(source: str) -> str:
    """Return the stable content hash used to detect source changes.

    Args:
        source: The app source.

    Returns:
        A hex SHA-256 digest.
    """
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class DevServer:
    """An HTTP server that pushes app source to a device and relays its logs."""

    def __init__(
        self,
        app_path: str | Path,
        *,
        host: str = "0.0.0.0",
        port: int = 8765,
        log: Callable[[str], None] = print,
        on_fetch: Callable[[], None] | None = None,
        harness: bool = False,
    ) -> None:
        """Initialize the dev server.

        Args:
            app_path: Path to the app file to serve.
            host: The bind address (``0.0.0.0`` so the device on the LAN reaches it).
            port: The TCP port.
            log: Sink for relayed device logs and server notices.
            on_fetch: Optional callback invoked each time the device fetches the
                project (``GET /bundle`` or legacy ``GET /app``). The one-shot
                ``tempest deploy`` uses it to know the device has the app and
                tear the short-lived server down; ``tempest serve`` leaves it
                unset.
            harness: Enable the F9 UI-test harness endpoints (mount/patch mirror
                + host→device event queue). Off by default so a normal serve is
                unaffected. The client learns it is in harness mode from
                ``GET /version`` (which carries ``"harness": true``).
        """
        self._app_path: Path = Path(app_path).resolve()
        self._host: str = host
        self._port: int = port
        self._log: Callable[[str], None] = log
        self._on_fetch: Callable[[], None] | None = on_fetch
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        # Lazily-rebuilt project bundle, cached by tree signature so /version
        # polls only stat the tree and the archive is built only on change.
        self._cached_signature: str | None = None
        self._cached_bundle: bytes = b""
        # --- F9 harness state (only used when harness=True) ---
        self._harness: bool = harness
        self._harness_lock = threading.Lock()
        self._scene: Scene | None = None
        self._revision: int = 0
        # Pending host→device events the client polls for, FIFO.
        self._command_queue: list[dict[str, Any]] = []
        # Bumps every time the client consumes a command, so the owner can tell
        # an in-flight event has been picked up (the auto-wait quiet condition).
        self._consumed: int = 0

    @property
    def harness(self) -> bool:
        """Whether the F9 harness endpoints are enabled.

        Returns:
            ``True`` when this server was constructed with ``harness=True``.
        """
        return self._harness

    def current_scene(self) -> Scene | None:
        """Return the host-side mirror of the device's live scene.

        Returns:
            The mirrored :class:`~tempest_core.core.ir.Scene`, or ``None`` before
            the device has POSTed its first mount.
        """
        with self._harness_lock:
            return self._scene

    def revision(self) -> int:
        """Return the monotonic mirror revision (bumped on every mount/patch).

        Returns:
            The current revision counter. Polling this from the owner is how the
            emulator backend auto-waits: it waits for the revision to go quiet.
        """
        with self._harness_lock:
            return self._revision

    def consumed_count(self) -> int:
        """Return how many host→device commands the client has consumed.

        Returns:
            A monotonic counter incremented each time the client polls and a
            command is handed to it.
        """
        with self._harness_lock:
            return self._consumed

    def pending_commands(self) -> int:
        """Return the number of host→device commands still queued.

        Returns:
            The current command-queue length.
        """
        with self._harness_lock:
            return len(self._command_queue)

    def enqueue_event(self, token: str, payload: dict[str, Any]) -> None:
        """Queue a host→device event for the client to consume and dispatch.

        Args:
            token: The handler token addressing a device-side handler (see
                :func:`tempestroid.bridge.protocol.handler_token`).
            payload: The raw event payload (validated device-side on dispatch).
        """
        with self._harness_lock:
            self._command_queue.append({"token": token, "payload": payload})

    def _record_mount(self, mount: dict[str, Any]) -> None:
        """Replace the mirror with a freshly-deserialized mount, bumping revision.

        Args:
            mount: A serialized :class:`~tempestroid.bridge.protocol.MountMessage`.
        """
        scene = deserialize_scene(mount)
        with self._harness_lock:
            self._scene = scene
            self._revision += 1

    def _record_patches(self, patches: list[dict[str, Any]]) -> None:
        """Apply a serialized patch batch to the mirror, bumping revision.

        A patch arriving before any mount is ignored (there is nothing to patch);
        the next mount re-establishes the mirror.

        Args:
            patches: A list of serialized patches (see
                :func:`tempestroid.bridge.serializer.serialize_patch`).
        """
        with self._harness_lock:
            if self._scene is None:
                return
            self._scene = apply_patches(self._scene, patches)
            self._revision += 1

    def _next_command(self) -> dict[str, Any] | None:
        """Pop the next queued host→device command, if any, bumping the counter.

        Returns:
            The next command dict, or ``None`` when the queue is empty.
        """
        with self._harness_lock:
            if not self._command_queue:
                return None
            self._consumed += 1
            return self._command_queue.pop(0)

    def signature(self) -> str:
        """Return the current project's cheap change signature.

        Returns:
            The tree signature (see :func:`tree_signature`).
        """
        return tree_signature(resolve_project(self._app_path))

    def bundle(self) -> tuple[str, bytes]:
        """Return the current project bundle, rebuilding only on change.

        Returns:
            A ``(signature, zip_bytes)`` pair; the archive is rebuilt only when
            the tree signature differs from the cached one.
        """
        layout = resolve_project(self._app_path)
        signature = tree_signature(layout)
        if signature != self._cached_signature:
            self._cached_bundle = build_bundle(layout)
            self._cached_signature = signature
        return signature, self._cached_bundle

    @property
    def port(self) -> int:
        """The bound port.

        Returns:
            The TCP port.
        """
        return self._port

    def read_source(self) -> str:
        """Read the current app source from disk.

        Returns:
            The file contents.
        """
        return self._app_path.read_text(encoding="utf-8")

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        """Build the request handler bound to this server.

        Returns:
            A ``BaseHTTPRequestHandler`` subclass.
        """
        server = self

        class Handler(BaseHTTPRequestHandler):
            """Per-request handler for the dev endpoints."""

            def _send_json(self, payload: dict[str, Any]) -> None:
                """Write a JSON response with status 200."""
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                # Flush so the bytes reach the socket before any on_fetch handler
                # tears the (short-lived ``tempest build``) server down — without
                # it the buffered body can be lost on shutdown and the device sees
                # a truncated response.
                self.wfile.flush()

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                """Serve ``/version``, ``/bundle``, and the legacy ``/app``.

                A dropped connection (the device's poll timed out and gave up
                mid-transfer) raises ``BrokenPipeError``/``ConnectionError`` from
                the socket write; swallow it so a flaky USB/LAN poll does not
                spew a traceback per request — the device simply retries.
                """
                try:
                    self._do_get()
                except (BrokenPipeError, ConnectionError):
                    pass

            def _do_get(self) -> None:
                """Dispatch the GET endpoints (wrapped by :meth:`do_GET`)."""
                if self.path == "/version":
                    self._send_json(
                        {"hash": server.signature(), "harness": server.harness}
                    )
                elif self.path == "/poll":
                    self._serve_poll()
                elif self.path == "/bundle":
                    signature, data = server.bundle()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("X-Tempest-Hash", signature)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    self.wfile.flush()
                    if server._on_fetch is not None:
                        server._on_fetch()
                elif self.path == "/app":
                    # Legacy single-file fallback for older hosts: the entry
                    # source only. Multi-file projects require the /bundle path.
                    source = server.read_source()
                    self._send_json({"hash": server.signature(), "source": source})
                    if server._on_fetch is not None:
                        server._on_fetch()
                else:
                    self.send_error(404)

            def _serve_poll(self) -> None:
                """Long-poll the host→device command queue (harness only).

                Blocks up to a few seconds for a queued event, then returns it
                (or ``{"token": null}`` when none arrived) so the client's poll
                loop stays cheap yet responsive. A 404 when harness is off keeps
                a normal serve unaffected.
                """
                if not server.harness:
                    self.send_error(404)
                    return
                deadline = time.monotonic() + 2.0
                command = server._next_command()
                while command is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                    command = server._next_command()
                self._send_json(command or {"token": None})

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                """Relay a device log line, or accept harness mount/patch POSTs.

                A dropped connection raises ``BrokenPipeError``/``ConnectionError``
                from the socket write; swallow it like :meth:`do_GET` so a flaky
                poll does not spew a traceback per request.
                """
                try:
                    self._do_post()
                except (BrokenPipeError, ConnectionError):
                    pass

            def _read_json_body(self) -> dict[str, Any]:
                """Read and parse the request body as a JSON object.

                Returns:
                    The decoded JSON object (empty dict on an empty body).
                """
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8", "replace")
                if not raw:
                    return {}
                parsed: dict[str, Any] = json.loads(raw)
                return parsed

            def _do_post(self) -> None:
                """Dispatch the POST endpoints (wrapped by :meth:`do_POST`)."""
                if self.path == "/log":
                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(length).decode("utf-8", "replace")
                    server._log(f"[device] {body}")
                    self.send_response(204)
                    self.end_headers()
                    return
                if self.path == "/mount" and server.harness:
                    server._record_mount(self._read_json_body())
                    self.send_response(204)
                    self.end_headers()
                    return
                if self.path == "/patch" and server.harness:
                    body = self._read_json_body()
                    patches: list[dict[str, Any]] = body.get("patches", [])
                    server._record_patches(patches)
                    self.send_response(204)
                    self.end_headers()
                    return
                self.send_error(404)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                """Silence the default per-request stderr logging."""

        return Handler

    def start(self) -> None:
        """Start serving on a background thread."""
        self._httpd = ThreadingHTTPServer(
            (self._host, self._port), self._handler_class()
        )
        # Reflect the actually-bound port (useful when port=0 picks a free one).
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="tempest-devserver", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the server and join the background thread."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
