"""Zero-dependency HTTP server for the RefundRoute web application.

A thin shell over `RefundService`, built only on the Python standard
library so it runs anywhere Python does -- no pip install required.

Run from the repository root:

    python -m server.app          # serves the API on :8000

Environment variables:
    PORT                    port to listen on (default 8000)
    REFUNDS_DATA_DIR        where cases and files are stored
    REFUNDS_WEB_DIST        built front-end to serve (optional, single-host)
    REFUNDS_ALLOWED_ORIGIN  browser origin allowed for CORS (split-host deploy)
    REFUNDS_ACCESS_CODE     closed-beta gate: required to start a new claim
    REFUNDS_OPERATOR_KEY    enables the operator console; required to view it
    ANTHROPIC_API_KEY       enables Claude vision reading of scanned contracts
    GEMINI_API_KEY          adds Gemini as a second, cross-checking reader
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import secrets
import sys
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

from server.service import (  # noqa: E402
    AccessDenied,
    RefundService,
    ServiceError,
)

DATA_DIR = os.environ.get(
    "REFUNDS_DATA_DIR", os.path.join(_REPO_ROOT, "server", "_data")
)
WEB_DIST = os.path.abspath(
    os.environ.get("REFUNDS_WEB_DIST", os.path.join(_REPO_ROOT, "web", "dist"))
)
ALLOWED_ORIGIN = os.environ.get("REFUNDS_ALLOWED_ORIGIN", "")
ACCESS_CODE = os.environ.get("REFUNDS_ACCESS_CODE", "")
OPERATOR_KEY = os.environ.get("REFUNDS_OPERATOR_KEY", "")
MAX_BODY_BYTES = 25 * 1024 * 1024

SERVICE = RefundService(DATA_DIR)


def _cors_origin(request_origin: str) -> str:
    """Resolve the Access-Control-Allow-Origin value for a request.

    REFUNDS_ALLOWED_ORIGIN may be:
      - unset                  -> no CORS (same-origin / local dev)
      - "*"                    -> allow any origin (fine for a beta whose
                                  real gate is the access code + tokens)
      - one origin, or a comma-separated list -> allow exact matches,
        tolerant of stray trailing slashes and surrounding whitespace.
    The browser's actual Origin is echoed back, so the value always
    matches exactly what the browser expects.
    """
    if not ALLOWED_ORIGIN:
        return ""
    if ALLOWED_ORIGIN.strip() == "*":
        return request_origin or "*"
    allowed = {
        item.strip().rstrip("/")
        for item in ALLOWED_ORIGIN.split(",")
        if item.strip()
    }
    return request_origin if request_origin.rstrip("/") in allowed else ""


class Handler(BaseHTTPRequestHandler):
    server_version = "RefundRoute/0.1"
    protocol_version = "HTTP/1.1"

    # -- response helpers -------------------------------------------------

    def _set_cors(self) -> None:
        # CORS headers are sent only for an allowed origin (see
        # _cors_origin). A same-origin or dev-proxy setup needs none.
        allow = _cors_origin(self.headers.get("Origin", ""))
        if not allow:
            return
        self.send_header("Access-Control-Allow-Origin", allow)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Case-Token, X-Access-Code, X-Operator-Key",
        )

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
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            raise ServiceError(
                f"Request too large (limit {MAX_BODY_BYTES // (1024 * 1024)} MB)."
            )
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
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
        token = (params.get("token") or [None])[0]
        if token is None:
            token = self.headers.get("X-Case-Token")
        try:
            if self._route(method, path, token):
                return
            if method == "GET" and not path.startswith("/api"):
                self._serve_static(path)
            else:
                self._send_json(404, {"error": "Not found."})
        except AccessDenied as exc:
            self._send_json(403, {"error": str(exc)})
        except ServiceError as exc:
            self._send_json(400, {"error": str(exc)})
        except KeyError:
            self._send_json(404, {"error": "Case or file not found."})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"Server error: {exc}"})

    def _require_access_code(self) -> None:
        """Closed-beta gate on starting a new claim."""
        if not ACCESS_CODE:
            return
        provided = self.headers.get("X-Access-Code", "")
        if not provided or not secrets.compare_digest(provided, ACCESS_CODE):
            raise AccessDenied(
                "RefundRoute is in a closed beta. A valid access code is "
                "required to start a claim."
            )

    def _require_operator(self) -> None:
        """Gate on the operator console; disabled unless a key is set."""
        if not OPERATOR_KEY:
            raise AccessDenied(
                "The operator console is not enabled on this server."
            )
        provided = self.headers.get("X-Operator-Key", "")
        if not provided or not secrets.compare_digest(provided, OPERATOR_KEY):
            raise AccessDenied("Invalid operator key.")

    def _route(self, method: str, path: str, token: str | None) -> bool:
        if method == "GET" and path == "/api/health":
            self._send_json(200, {"ok": True})
            return True

        if method == "POST" and path == "/api/cases":
            self._require_access_code()
            self._send_json(200, SERVICE.create_case(self._read_json()))
            return True

        if method == "GET" and path == "/api/operator/overview":
            self._require_operator()
            self._send_json(200, SERVICE.operator_overview())
            return True

        match = re.fullmatch(r"/api/operator/cases/([A-Za-z0-9]+)", path)
        if match and method == "GET":
            self._require_operator()
            self._send_json(200, SERVICE.operator_case(match.group(1)))
            return True

        match = re.fullmatch(r"/api/cases/([A-Za-z0-9]+)", path)
        if match and method == "GET":
            SERVICE.authorize(match.group(1), token)
            self._send_json(200, SERVICE.get_case(match.group(1)))
            return True

        match = re.fullmatch(r"/api/cases/([A-Za-z0-9]+)/documents", path)
        if match and method == "POST":
            SERVICE.authorize(match.group(1), token)
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
            SERVICE.authorize(match.group(1), token)
            body = self._read_json()
            view = SERVICE.confirm_services(match.group(1), body.get("keep") or [])
            self._send_json(200, view)
            return True

        match = re.fullmatch(r"/api/cases/([A-Za-z0-9]+)/generate", path)
        if match and method == "POST":
            SERVICE.authorize(match.group(1), token)
            self._send_json(200, SERVICE.generate(match.group(1)))
            return True

        match = re.fullmatch(
            r"/api/cases/([A-Za-z0-9]+)/files/([A-Za-z0-9._-]+)", path
        )
        if match and method == "GET":
            SERVICE.authorize(match.group(1), token)
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
    os.umask(0o077)  # cases and files are created private to this user
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
