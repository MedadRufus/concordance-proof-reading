import os
import tempfile
import uuid

from flask import (Flask, abort, redirect, render_template, request, send_file,
                   url_for)
from werkzeug.utils import secure_filename

from add_hyperlinks import convert_odt_to_html

app = Flask(__name__)

# In-memory mapping of upload ids -> file info (simple, non-persistent)
uploads = {}

ALLOWED_EXTENSIONS = {"odt"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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

    filename = secure_filename(file.filename)
    tmpdir = tempfile.mkdtemp(prefix="odtconv_")
    input_path = os.path.join(tmpdir, filename)
    output_path = os.path.join(tmpdir, "converted.html")

    file.save(input_path)

    try:
        convert_odt_to_html(input_path, output_path)
    except Exception as e:
        # Return error message for now
        return f"Conversion error: {e}", 500

    upload_id = uuid.uuid4().hex
    uploads[upload_id] = {"html": output_path, "tmpdir": tmpdir, "input_name": filename}

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
    return send_file(info["html"], mimetype="text/html")


@app.route("/download/<upload_id>", methods=["GET"])
def download(upload_id):
    info = uploads.get(upload_id)
    if not info:
        abort(404)
    # send as attachment
    return send_file(
        info["html"],
        as_attachment=True,
        download_name=(info.get("input_name") or "converted.html"),
    )


if __name__ == "__main__":
    app.run(debug=True)
