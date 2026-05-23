import os
import threading
from functools import wraps
from flask import Flask, request, Response, send_from_directory, redirect, session, render_template_string


_web_thread = None
_app = None


LOGIN_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>ATG Login</title>
<style>
body{background:#0f1115;color:#fff;font-family:Arial;display:flex;align-items:center;justify-content:center;height:100vh}
.box{background:#171a21;padding:30px;border-radius:14px;width:360px;border:1px solid #2a2f3a}
h2{text-align:center}
input{width:100%;padding:12px;margin:8px 0;background:#0f1115;color:#fff;border:1px solid #333;border-radius:8px}
button{width:100%;padding:12px;background:#0f62fe;color:white;border:0;border-radius:8px;font-weight:bold}
.err{color:#ff5555;text-align:center}
</style>
</head>
<body>
<div class="box">
<h2>ATG Video Index Login</h2>
{% if error %}<div class="err">{{error}}</div>{% endif %}
<form method="post">
<input name="username" placeholder="Tài khoản">
<input name="password" type="password" placeholder="Mật khẩu">
<button>Đăng nhập</button>
</form>
</div>
</body>
</html>
"""


def start_web_server(folder: str, port: int = 18080, username="admin", password="123456"):
    global _web_thread, _app

    if _web_thread:
        print("[WEB] Server already running")
        return

    folder = os.path.abspath(folder)

    if not os.path.exists(folder):
        raise FileNotFoundError(folder)

    app = Flask(__name__)
    app.secret_key = "ATG_VIDEO_INDEX_SECRET_KEY"

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("logged_in") is True:
                return fn(*args, **kwargs)
            return redirect("/login")
        return wrapper

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = ""
        if request.method == "POST":
            u = request.form.get("username", "")
            p = request.form.get("password", "")

            if u == username and p == password:
                session["logged_in"] = True
                return redirect("/index.html")

            error = "Sai tài khoản hoặc mật khẩu"

        return render_template_string(LOGIN_HTML, error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.route("/")
    def home():
        return redirect("/index.html")

    @app.route("/index.html")
    @login_required
    def index():
        return send_from_directory(folder, "index.html")

    @app.route("/<path:filename>")
    @login_required
    def files(filename):
        return send_from_directory(folder, filename, as_attachment=False)

    def run():
        print("=" * 60)
        print("[WEB] Flask Web Login started")
        print(f"[WEB] Folder : {folder}")
        print(f"[WEB] Port   : {port}")
        print(f"[WEB] URL    : http://127.0.0.1:{port}/index.html")
        print(f"[WEB] User   : {username}")
        print("=" * 60)
        app.run(host="0.0.0.0", port=int(port), debug=False, threaded=True)

    _app = app
    _web_thread = threading.Thread(target=run, daemon=True)
    _web_thread.start()