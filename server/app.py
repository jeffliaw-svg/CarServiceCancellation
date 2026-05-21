"""Zero-dependency HTTP server for the RefundRoute web application.

A thin shell over `RefundService`, built only on the Python standard
library so it runs anywhere Python does -- no pip install required.

Run from the repository root:

    python -m server.app          # serves the API on :8000

Environment variables:
    PORT                port to listen on (default 8000)
    REFUNDS_DATA_DIR    where cases and files are stored
    REFUNDS_WEB_DIST    built front-end to serve (optional, single-host)
    ANTHROPIC_API_KEY   enables Claude vision OCR for scanned contracts
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

from server.service import RefundService, ServiceError  # noqa: E402

DATA_DIR = os.environ.get(
    "REFUNDS_DATA_DIR", os.path.join(_REPO_ROOT, "server", "_data")
)
WEB_DIST = os.path.abspath(
    os.environ.get("REFUNDS_WEB_DIST", os.path.join(_REPO_ROOT, "web", "dist"))
)

SERVICE = RefundService(DATA_DIR)


class Handler(BaseHTTPRequestHandler):
    server_version = "RefundRoute/0.1"
    protocol_version = "HTTP/1.1"

    # -- response helpers -------------------------------------------------

    def _set_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        download_name: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if download_name:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{download_name}"'
            )
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ServiceError("Request body must be valid JSON.")

    # -- verbs ------------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    # -- routing ----------------------------------------------------------

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        path = path.rstrip("/") or "/"
        try:
            if self._route(method, path):
                return
            if method == "GET" and not path.startswith("/api"):
                self._serve_static(path)
            else:
                self._send_json(404, {"error": "Not found."})
        except ServiceError as exc:
            self._send_json(400, {"error": str(exc)})
        except KeyError:
            self._send_json(404, {"error": "Case or file not found."})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"Server error: {exc}"})

    def _route(self, method: str, path: str) -> bool:
        if method == "GET" and path == "/api/health":
            self._send_json(200, {"ok": True})
            return True

        if method == "POST" and path == "/api/cases":
            self._send_json(200, SERVICE.create_case(self._read_json()))
            return True

        match = re.fullmatch(r"/api/cases/([A-Za-z0-9]+)", path)
        if match and method == "GET":
            self._send_json(200, SERVICE.get_case(match.group(1)))
            return True

        match = re.fullmatch(r"/api/cases/([A-Za-z0-9]+)/documents", path)
        if match and method == "POST":
            body = self._read_json()
            data = base64.b64decode(body.get("content_base64") or "")
            view = SERVICE.add_document(
                match.group(1),
                filename=body.get("filename") or "contract.txt",
                data=data,
                kind=body.get("kind") or "contract",
            )
            self._send_json(200, view)
            return True

        match = re.fullmatch(r"/api/cases/([A-Za-z0-9]+)/confirm", path)
        if match and method == "POST":
            body = self._read_json()
            view = SERVICE.confirm_services(match.group(1), body.get("keep") or [])
            self._send_json(200, view)
            return True

        match = re.fullmatch(r"/api/cases/([A-Za-z0-9]+)/generate", path)
        if match and method == "POST":
            self._send_json(200, SERVICE.generate(match.group(1)))
            return True

        match = re.fullmatch(
            r"/api/cases/([A-Za-z0-9]+)/files/([A-Za-z0-9._-]+)", path
        )
        if match and method == "GET":
            data, content_type = SERVICE.get_file(match.group(1), match.group(2))
            self._send_bytes(
                200, data, content_type, download_name=match.group(2)
            )
            return True

        return False

    def _serve_static(self, path: str) -> None:
        """Optional single-host hosting of the built front-end."""
        if not os.path.isdir(WEB_DIST):
            self._send_json(
                404, {"error": "API is running; front-end build not present."}
            )
            return
        relative = path.lstrip("/") or "index.html"
        candidate = os.path.normpath(os.path.join(WEB_DIST, relative))
        if not candidate.startswith(WEB_DIST):
            self._send_json(404, {"error": "Not found."})
            return
        if not os.path.isfile(candidate):
            candidate = os.path.join(WEB_DIST, "index.html")  # SPA fallback
            if not os.path.isfile(candidate):
                self._send_json(404, {"error": "Not found."})
                return
        with open(candidate, "rb") as handle:
            data = handle.read()
        content_type = mimetypes.guess_type(candidate)[0] or "text/html"
        self._send_bytes(200, data, content_type)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"RefundRoute API listening on http://0.0.0.0:{port}")
    print(f"  data dir: {DATA_DIR}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
