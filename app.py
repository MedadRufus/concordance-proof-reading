"""This module implements a simple web application for converting ODT files.

It provides a Flask-based web interface to upload an ODT file,
converts it to HTML with Bible references hyperlinked, and allows
the user to preview or download the result.
"""

import io
import logging
import os
import threading
import time
import uuid
import zipfile

from flask import Flask, abort, make_response, redirect, render_template, request, url_for
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
    """Check if the given filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_client_ip():
    """Get the client's IP address, handling proxies."""
    # Respect X-Forwarded-For if behind a proxy (cPanel/passenger usually provides REMOTE_ADDR)
    if forwarded := request.headers.get("X-Forwarded-For", ""):
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def is_valid_odt_bytes(bts):
    """Validate if the given bytes represent a valid ODT file."""
    try:
        bio = io.BytesIO(bts)
        if not zipfile.is_zipfile(bio):
            return False
        with zipfile.ZipFile(bio) as z:
            # A minimal check: ODT should contain content.xml
            return "content.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def rate_limit_ok(ip):
    """Check if the given IP is within the upload rate limits."""
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
    """Periodically clean up stale uploads from memory."""
    while True:
        now = time.time()
        stale = [
            uid for uid, info in list(uploads.items()) if now - info.get("ts", now) > UPLOAD_TTL
        ]
        for uid in stale:
            uploads.pop(uid, None)
            logger.info("Cleaned stale upload %s", uid)
        time.sleep(CLEANUP_INTERVAL)


# Start background cleanup thread
t = threading.Thread(target=cleanup_worker, daemon=True)
t.start()


@app.after_request
def set_security_headers(response):
    """Set security headers for all responses."""
    # Prevent script execution, restrict frames, enforce secure headers
    csp = "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=()"
    # HSTS: only useful when serving HTTPS
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.route("/", methods=["GET"])
def index():
    """Render the main upload page."""
    return render_template("upload.html")


def validate_request(file_request):
    """Validate the incoming file upload request."""
    if "file" not in file_request.files:
        return "No file part", 400
    file = file_request.files["file"]
    if file.filename == "":
        return "No selected file", 400
    if not allowed_file(file.filename):
        return "Only .odt files are allowed", 400

    client_ip = get_client_ip()
    if not rate_limit_ok(client_ip):
        return "Rate limit exceeded", 429

    return None, None


@app.route("/upload", methods=["POST"])
def upload():
    """Handle file upload, conversion, and redirection."""
    error_message, error_code = validate_request(request)
    if error_message:
        return error_message, error_code

    file = request.files["file"]
    filename = secure_filename(file.filename)[:200]

    # Read in-memory and validate
    if not (file_bytes := file.read()):
        return "Empty file", 400

    if len(file_bytes) > app.config["MAX_CONTENT_LENGTH"]:
        return "File too large", 413

    if not is_valid_odt_bytes(file_bytes):
        return "Uploaded file does not look like a valid ODT", 400

    try:
        html_output = convert_odt_bytes_to_html(file_bytes)
    except Exception as e:  # pylint: disable=broad-except
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
    """Display the result page for a given upload."""
    if not (info := uploads.get(upload_id)):
        abort(404)
    return render_template("result.html", upload_id=upload_id, input_name=info.get("input_name"))


@app.route("/preview/<upload_id>", methods=["GET"])
def preview(upload_id):
    """Show the HTML preview of a converted file."""
    if not (info := uploads.get(upload_id)):
        abort(404)
    resp = make_response(info["html"])
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.route("/download/<upload_id>", methods=["GET"])
def download(upload_id):
    """Provide the converted HTML file for download."""
    if not (info := uploads.get(upload_id)):
        abort(404)

    html_bytes = info["html"].encode("utf-8")
    safe_name = secure_filename(info.get("input_name") or "converted.html")
    download_name = safe_name if safe_name.lower().endswith(".html") else safe_name + ".html"
    response = make_response(html_bytes)
    response.headers["Content-Type"] = "text/html"
    response.headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return response


if __name__ == "__main__":
    # Do not run with debug=True in production
    app.run()
