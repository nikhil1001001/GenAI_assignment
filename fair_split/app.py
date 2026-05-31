from __future__ import annotations

import json
import logging
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from fair_split.pipeline.orchestrator import split_bill
from fair_split.serialization import result_to_contract

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


class FairSplitHandler(BaseHTTPRequestHandler):
    server_version = "FairSplit/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._json({"status": "ok"})
            return
        file_path = FRONTEND / ("index.html" if path in {"/", ""} else path.lstrip("/"))
        if not _inside(file_path, FRONTEND) or not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/split":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"error": "Invalid Content-Length"}, HTTPStatus.BAD_REQUEST)
            return
        if length > 10_000_000:
            self._json({"error": "Request body exceeds 10 MB"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json({"error": "Request body must be JSON"}, HTTPStatus.BAD_REQUEST)
            return
        receipt_base64 = payload.get("receipt_base64")
        description = payload.get("description")
        if not isinstance(receipt_base64, str) or not isinstance(description, str):
            self._json(
                {"error": "Expected JSON body with string receipt_base64 and description"},
                HTTPStatus.BAD_REQUEST,
            )
            return
        result = split_bill(receipt_base64, description)
        self._json(result_to_contract(result))

    def log_message(self, fmt: str, *args: object) -> None:
        logging.getLogger("fair_split.access").info(fmt, *args)

    def _json(self, body: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), FairSplitHandler)
    print(f"Fair Split listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()

