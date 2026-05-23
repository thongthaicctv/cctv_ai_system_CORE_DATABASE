import os
import base64
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


_http_server = None
_http_thread = None


def start_http_server(folder: str, port: int = 18080, username="", password=""):
    global _http_server, _http_thread

    if _http_server:
        print("[HTTP] Server already running")
        return

    if not os.path.exists(folder):
        raise FileNotFoundError(f"Folder not found: {folder}")

    auth_enabled = bool(username and password)

    class AuthHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=folder, **kwargs)

        def _check_auth(self):
            if not auth_enabled:
                return True

            auth = self.headers.get("Authorization", "")
            token = base64.b64encode(
                f"{username}:{password}".encode("utf-8")
            ).decode("utf-8")

            return auth == f"Basic {token}"

        def do_GET(self):
            if not self._check_auth():
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="ATG CCTV Video Index"')
                self.end_headers()
                self.wfile.write(b"Authentication required")
                return

            super().do_GET()

        def log_message(self, fmt, *args):
            print("[HTTP]", fmt % args)

    _http_server = ThreadingHTTPServer(("0.0.0.0", int(port)), AuthHandler)

    _http_thread = threading.Thread(
        target=_http_server.serve_forever,
        daemon=True
    )
    _http_thread.start()

    print("=" * 60)
    print("[HTTP] WebServer started")
    print(f"[HTTP] Folder : {folder}")
    print(f"[HTTP] Port   : {port}")
    print(f"[HTTP] Auth   : {'ON' if auth_enabled else 'OFF'}")
    print(f"[HTTP] Local  : http://127.0.0.1:{port}/index.html")
    print("=" * 60)


def stop_http_server():
    global _http_server, _http_thread

    if _http_server:
        _http_server.shutdown()
        _http_server.server_close()
        _http_server = None
        _http_thread = None
        print("[HTTP] WebServer stopped")