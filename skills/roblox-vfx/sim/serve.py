"""Serve the sim locally the way the Artifact host does (index.html gets the
same doctype/meta skeleton), for the built-in browser or any browser.

    python serve.py [port]      # default 8765 -> http://127.0.0.1:8765/
"""
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKELETON = ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>body{margin:0}</style></head><body>')


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = (SKELETON + open(os.path.join(ROOT, "index.html"), encoding="utf-8").read() + "</body></html>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        """POST /save?name=x.png with a data: URL body -> out/x.png (lets a
        headless check hand frame strips back to disk)."""
        import base64
        import re
        from urllib.parse import parse_qs, urlparse
        name = parse_qs(urlparse(self.path).query).get("name", ["frame.png"])[0]
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        data = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
        with open(os.path.join(ROOT, "out", name), "wb") as f:
            f.write(base64.b64decode(data.split(",", 1)[-1]))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"http://127.0.0.1:{port}/")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
