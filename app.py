import io
import logging
import os
import threading
import time
import uuid
import zipfile
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, abort, make_response, redirect,
                   render_template, request, send_file, url_for)
from werkzeug.utils import secure_filename

from add_hyperlinks import convert_odt_bytes_to_html

# Configuration
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 5 MiB
UPLOAD_TTL = int(os.environ.get("UPLOAD_TTL", 10 * 60))  # seconds (default 10 minutes)
CLEANUP_INTERVAL = int(os.environ.get("CLEANUP_INTERVAL", 60))  # seconds
UPLOAD_RATE_LIMIT = int(os.environ.get("UPLOAD_RATE_LIMIT", 30))  # per IP per window
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", 60 * 60))  # 1 hour

ALLOWED_EXTENSIONS = {"odt"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
# Security-related defaults
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# In-memory stores
uploads = {}  # upload_id -> {html: str, ts: float, input_name: str}
uploads_by_ip = {}  # ip -> [timestamp1, timestamp2, ...]

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_client_ip():
    # Respect X-Forwarded-For if behind a proxy (cPanel/passenger usually provides REMOTE_ADDR)
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def is_valid_odt_bytes(bts):
    try:
        bio = io.BytesIO(bts)
        if not zipfile.is_zipfile(bio):
            return False
        with zipfile.ZipFile(bio) as z:
            # A minimal check: ODT should contain content.xml
            return "content.xml" in z.namelist()
    except Exception:
        return False


def rate_limit_ok(ip):
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    stamps = uploads_by_ip.get(ip, [])
    # prune
    stamps = [s for s in stamps if s >= window_start]
    if len(stamps) >= UPLOAD_RATE_LIMIT:
        uploads_by_ip[ip] = stamps
        return False
    stamps.append(now)
    uploads_by_ip[ip] = stamps
    return True


def cleanup_worker():
    while True:
        now = time.time()
        stale = [
            uid
            for uid, info in list(uploads.items())
            if now - info.get("ts", now) > UPLOAD_TTL
        ]
        for uid in stale:
            uploads.pop(uid, None)
            logger.info(f"Cleaned stale upload {uid}")
        time.sleep(CLEANUP_INTERVAL)


# Start background cleanup thread
t = threading.Thread(target=cleanup_worker, daemon=True)
t.start()


@app.after_request
def set_security_headers(response):
    # Prevent script execution, restrict frames, enforce secure headers
    csp = "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=()"
    # HSTS: only useful when serving HTTPS
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    # Prevent caching of user content
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return response


@app.route("/", methods=["GET"])
def index():
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return "No file part", 400
    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400
    if not allowed_file(file.filename):
        return "Only .odt files are allowed", 400

    client_ip = get_client_ip()
    if not rate_limit_ok(client_ip):
        return "Rate limit exceeded", 429

    filename = secure_filename(file.filename)[:200]

    # Read in-memory and validate
    file_bytes = file.read()
    if not file_bytes:
        return "Empty file", 400

    if len(file_bytes) > app.config["MAX_CONTENT_LENGTH"]:
        return "File too large", 413

    if not is_valid_odt_bytes(file_bytes):
        return "Uploaded file does not look like a valid ODT", 400

    try:
        html_output = convert_odt_bytes_to_html(file_bytes)
    except Exception as e:
        logger.exception("Conversion failed")
        return f"Conversion error: {e}", 500

    upload_id = uuid.uuid4().hex
    uploads[upload_id] = {
        "html": html_output,
        "ts": time.time(),
        "input_name": filename,
    }

    return redirect(url_for("result", upload_id=upload_id))


@app.route("/result/<upload_id>", methods=["GET"])
def result(upload_id):
    info = uploads.get(upload_id)
    if not info:
        abort(404)
    return render_template(
        "result.html", upload_id=upload_id, input_name=info.get("input_name")
    )


@app.route("/preview/<upload_id>", methods=["GET"])
def preview(upload_id):
    info = uploads.get(upload_id)
    if not info:
        abort(404)
    resp = make_response(info["html"])
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    # Ensure browsers do not cache sensitive content
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/download/<upload_id>", methods=["GET"])
def download(upload_id):
    info = uploads.get(upload_id)
    if not info:
        abort(404)

    html_bytes = info["html"].encode("utf-8")
    bio = io.BytesIO(html_bytes)
    bio.seek(0)
    safe_name = secure_filename(info.get("input_name") or "converted.html")
    # return file as attachment
    return send_file(
        bio,
        mimetype="text/html",
        as_attachment=True,
        download_name=(
            safe_name if safe_name.lower().endswith(".html") else safe_name + ".html"
        ),
    )


if __name__ == "__main__":
    # Do not run with debug=True in production
    app.run()
