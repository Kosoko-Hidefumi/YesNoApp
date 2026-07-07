#!/usr/bin/env python3
"""Local dev server: static files + /api/upload + /api/share"""
import cgi
import json
import mimetypes
import os
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
SHARES = ROOT / "shares"
UPLOADS.mkdir(exist_ok=True)
SHARES.mkdir(exist_ok=True)
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
        path = self.path.split("?", 1)[0]
        if path in ("/api/upload", "/api/share"):
            self.send_response(204)
            self._cors()
            self.end_headers()
        else:
            self.send_error(404)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/share":
            qs = parse_qs(urlparse(self.path).query)
            sid = (qs.get("id") or [None])[0]
            if not sid:
                self._json(400, {"error": "リンクIDが必要です"})
                return
            share_file = SHARES / f"{sid}.json"
            if not share_file.is_file():
                self._json(404, {"error": "リンクが見つかりません"})
                return
            try:
                self._json(200, json.loads(share_file.read_text(encoding="utf-8")))
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/share":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                cfg = json.loads(self.rfile.read(length).decode("utf-8"))
                if not (cfg and cfg.get("q") and isinstance(cfg.get("n"), list) and isinstance(cfg.get("c"), list)):
                    self._json(400, {"error": "設定が不正です"})
                    return
                sid = str(uuid.uuid4())
                (SHARES / f"{sid}.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
                self._json(200, {"id": sid})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if path != "/api/upload":
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    print(f"Serving {ROOT}")
    print(f"  App:    http://127.0.0.1:{PORT}/")
    print(f"  Share:  GET/POST http://127.0.0.1:{PORT}/api/share")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
