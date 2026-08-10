"""Optional tiny HTTP server so free web-service hosts (e.g. Render) see an
open port and don't consider the bot's process inactive.

Only starts if a PORT environment variable is present (hosting platforms
set this automatically) - local development is unaffected.
"""
from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server naming convention)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # keep stdout focused on bot logs


def start_healthcheck_server_if_needed() -> None:
    port = os.getenv("PORT")
    if not port:
        return
    server = HTTPServer(("0.0.0.0", int(port)), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
