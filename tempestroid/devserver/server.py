"""LAN code-push dev server (phase B5, dev-machine side).

Serves the app's source to the device over HTTP and relays the device's logs
back to the terminal — the Expo-style inner loop for on-device development:

* ``GET /version`` → ``{"hash": <sha256 of current source>}`` (cheap poll).
* ``GET /app``     → ``{"hash": ..., "source": <app source>}``.
* ``POST /log``    → body is printed to the terminal, prefixed ``[device]``.

The source is re-read from disk on every request, so saving the file is enough
for the device's poll loop to pick up the change and hot-restart.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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
    ) -> None:
        """Initialize the dev server.

        Args:
            app_path: Path to the app file to serve.
            host: The bind address (``0.0.0.0`` so the device on the LAN reaches it).
            port: The TCP port.
            log: Sink for relayed device logs and server notices.
        """
        self._app_path: Path = Path(app_path).resolve()
        self._host: str = host
        self._port: int = port
        self._log: Callable[[str], None] = log
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

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

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                """Serve ``/version`` and ``/app``."""
                source = server.read_source()
                digest = source_hash(source)
                if self.path == "/version":
                    self._send_json({"hash": digest})
                elif self.path == "/app":
                    self._send_json({"hash": digest, "source": source})
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
