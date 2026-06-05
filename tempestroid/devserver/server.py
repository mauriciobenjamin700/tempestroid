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
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from tempestroid.cli.bundle import (
    build_bundle,
    resolve_project,
    tree_signature,
)

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
                    self._send_json({"hash": server.signature()})
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

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                """Relay a device log line posted to ``/log``."""
                if self.path != "/log":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8", "replace")
                server._log(f"[device] {body}")
                self.send_response(204)
                self.end_headers()

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
