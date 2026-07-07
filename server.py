#!/usr/bin/env python3
"""Local dev server: static files + POST /api/upload"""
import cgi
import json
import mimetypes
import os
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
PORT = int(os.environ.get("PORT", "8765"))
MAX_BYTES = 50 * 1024 * 1024
ALLOWED = {"image/jpeg", "image/png", "image/gif", "image/webp"}
EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_OPTIONS(self):
        if self.path == "/api/upload":
            self.send_response(204)
            self._cors()
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/upload":
            self.send_error(404)
            return
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._json(400, {"error": "multipart/form-data が必要です"})
            return
        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": ctype,
                    "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                },
            )
            if "file" not in form:
                self._json(400, {"error": "file フィールドが必要です"})
                return
            item = form["file"]
            if not item.filename:
                self._json(400, {"error": "ファイルが空です"})
                return
            raw = item.file.read()
            if len(raw) > MAX_BYTES:
                mb = MAX_BYTES // 1024 // 1024
                self._json(400, {"error": f"ファイルが大きすぎます（{mb}MB以下）"})
                return
            mime = item.type or mimetypes.guess_type(item.filename)[0] or ""
            if not mime.startswith("image/"):
                ext = Path(item.filename).suffix.lower()
                mime = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
                }.get(ext, mime)
            if mime not in ALLOWED:
                self._json(400, {"error": "画像ファイル（JPEG/PNG/GIF/WebP）を選んでください"})
                return
            name = uuid.uuid4().hex + EXT_MAP[mime]
            (UPLOADS / name).write_bytes(raw)
            host = self.headers.get("Host", f"localhost:{PORT}")
            url = f"http://{host}/uploads/{name}"
            self._json(200, {"url": url})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    print(f"Serving {ROOT}")
    print(f"  App:    http://127.0.0.1:{PORT}/")
    print(f"  Upload: POST http://127.0.0.1:{PORT}/api/upload")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
