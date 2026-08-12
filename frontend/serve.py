"""Tiny static server for the frontend that injects an env-driven config.js.

Serves ./frontend and intercepts /config.js so the browser gets
window.API_BASE_URL from the API_BASE_URL env var (default http://localhost:8000).
The committed config.js keeps "" for production (same-origin via Caddy).
"""

import functools
import http.server
import os

HOST = os.environ.get("HOST", "localhost")
PORT = int(os.environ.get("PORT", "8080"))
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(
            *args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs
        )

    def do_GET(self):
        if self.path in ("/config.js", "/config.js?"):
            body = f"window.API_BASE_URL = {API_BASE_URL!r};\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    server = http.server.ThreadingHTTPServer((HOST, PORT), functools.partial(Handler))
    print(f"Serving frontend at http://{HOST}:{PORT} (API_BASE_URL={API_BASE_URL})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
