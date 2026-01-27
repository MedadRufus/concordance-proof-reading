"""This module implements a simple web application for converting ODT files.

It provides a Flask-based web interface to upload an ODT file,
converts it to HTML with Bible references hyperlinked, and allows
the user to preview or download the result.
"""

import io
import logging
import os
import queue
import threading
import time
import uuid
import zipfile

from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, url_for
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
conversion_progress = {}  # upload_id -> {progress: int, status: str, error: str}

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
    # Allow inline scripts and connections for progress page functionality
    csp = "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self';"
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
    """Handle file upload, start conversion in background, and redirect to progress page."""
    logger.info("Upload route called")
    error_message, error_code = validate_request(request)
    if error_message:
        logger.warning(f"Upload validation failed: {error_message}")
        return error_message, error_code

    file = request.files["file"]
    filename = secure_filename(file.filename)[:200]
    logger.info(f"Processing file: {filename}")

    # Read in-memory and validate
    if not (file_bytes := file.read()):
        logger.warning("Received empty file")
        return "Empty file", 400

    if len(file_bytes) > app.config["MAX_CONTENT_LENGTH"]:
        logger.warning(f"File too large: {len(file_bytes)} bytes")
        return "File too large", 413

    if not is_valid_odt_bytes(file_bytes):
        logger.warning("Invalid ODT file received")
        return "Uploaded file does not look like a valid ODT", 400

    upload_id = uuid.uuid4().hex
    logger.info(f"Created upload_id: {upload_id}")

    # Initialize progress tracking
    conversion_progress[upload_id] = {"progress": 0, "status": "Queued", "error": None}
    logger.info(f"Initialized progress tracking for upload_id: {upload_id}")

    # Store initial upload info
    uploads[upload_id] = {
        "input_name": filename,
    }

    # Start conversion in background thread
    conversion_thread = threading.Thread(
        target=enhanced_convert_odt_with_progress, args=(upload_id, file_bytes)
    )
    conversion_thread.daemon = True
    conversion_thread.start()
    logger.info(f"Started conversion thread for upload_id: {upload_id}")

    # Redirect to progress page
    return redirect(url_for("progress_page", upload_id=upload_id))


@app.route("/result/<upload_id>", methods=["GET"])
def result(upload_id):
    """Display the result page for a given upload."""
    logger.info(f"Result page accessed for upload_id: {upload_id}")
    if not (info := uploads.get(upload_id)):
        logger.warning(f"Result page requested for non-existent upload_id: {upload_id}")
        abort(404)
    logger.info(
        f"Rendering result page for upload_id: {upload_id}, input_name: {info.get('input_name')}"
    )
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


@app.route("/api/progress/<upload_id>", methods=["GET"])
def get_progress(upload_id):
    """Return the current progress of a conversion."""
    progress_info = conversion_progress.get(
        upload_id, {"progress": 0, "status": "Not found", "error": "Upload ID not found"}
    )
    logger.info(f"Progress API called for upload_id: {upload_id}, returning: {progress_info}")
    return jsonify(progress_info)


@app.route("/progress/<upload_id>", methods=["GET"])
def progress_page(upload_id):
    """Display the progress page for a given upload."""
    if upload_id not in conversion_progress:
        abort(404)
    upload_info = uploads.get(upload_id, {})
    input_name = upload_info.get("input_name", "Processing...")
    return render_template("progress.html", upload_id=upload_id, input_name=input_name)


def convert_odt_with_progress(upload_id, file_bytes):
    """Run the conversion in a background thread with progress updates."""
    try:
        # Update progress to indicate conversion is starting
        conversion_progress[upload_id] = {
            "progress": 5,
            "status": "Starting conversion...",
            "error": None,
        }

        # Simulate progress during conversion
        # Since the actual conversion doesn't have built-in progress, we'll simulate it
        # by updating progress periodically during the conversion

        # Update progress to loading KJV data
        conversion_progress[upload_id] = {
            "progress": 10,
            "status": "Loading Bible data...",
            "error": None,
        }

        # Import here to avoid circular imports
        from add_hyperlinks import convert_odt_bytes_to_html

        # Update progress to processing
        conversion_progress[upload_id] = {
            "progress": 25,
            "status": "Processing document...",
            "error": None,
        }

        # Perform the actual conversion
        html_output = convert_odt_bytes_to_html(file_bytes)

        # Update progress to completion
        conversion_progress[upload_id] = {"progress": 95, "status": "Finalizing...", "error": None}

        # Store the result
        uploads[upload_id] = {
            "html": html_output,
            "ts": time.time(),
            "input_name": uploads[upload_id]["input_name"] if upload_id in uploads else "Unknown",
        }

        # Mark as complete
        conversion_progress[upload_id] = {"progress": 100, "status": "Complete", "error": None}

    except Exception as e:
        conversion_progress[upload_id] = {"progress": 0, "status": "Error", "error": str(e)}
        logger.exception("Conversion failed for upload %s: %s", upload_id, e)


def enhanced_convert_odt_with_progress(upload_id, file_bytes):
    """Enhanced conversion with better progress tracking by modifying the conversion process."""
    try:
        logger.info(f"Starting conversion for upload_id: {upload_id}")

        # Update progress to indicate conversion is starting
        conversion_progress[upload_id] = {
            "progress": 0,
            "status": "Starting conversion...",
            "error": None,
        }
        logger.info(f"Progress updated to 0% for upload_id: {upload_id}")

        # Define progress callback function
        def progress_callback(progress, status):
            conversion_progress[upload_id] = {"progress": progress, "status": status, "error": None}
            logger.info(
                f"Progress updated to {progress}% - Status: {status} for upload_id: {upload_id}"
            )

        # Import here to avoid circular imports
        from add_hyperlinks import convert_odt_bytes_to_html

        logger.info(f"Calling conversion function for upload_id: {upload_id}")

        # Call the conversion function with progress callback
        html_output = convert_odt_bytes_to_html(file_bytes, progress_callback)

        logger.info(
            f"Conversion completed for upload_id: {upload_id}, output length: {len(html_output)}"
        )

        # Store the result
        uploads[upload_id] = {
            "html": html_output,
            "ts": time.time(),
            "input_name": uploads[upload_id]["input_name"] if upload_id in uploads else "Unknown",
        }

        # Mark as complete
        conversion_progress[upload_id] = {"progress": 100, "status": "Complete", "error": None}
        logger.info(f"Conversion marked as complete for upload_id: {upload_id}")

    except Exception as e:
        logger.exception(f"Conversion failed for upload_id: {upload_id}, error: {str(e)}")
        conversion_progress[upload_id] = {"progress": 0, "status": "Error", "error": str(e)}
