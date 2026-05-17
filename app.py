import os
import io
import csv
import uuid
import json
import zipfile
from datetime import datetime, timezone
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    jsonify,
    Response,
)
from models import db, Tester, Bug, Attachment, Device, SWBuild, Mode
from sqlalchemy import func

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "pdf", "txt", "log", "zip"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "bugs.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

db.init_app(app)

with app.app_context():
    db.create_all()


# ── helpers ──────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── dashboard ────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    total = Bug.query.count()
    open_count = Bug.query.filter_by(status="open").count()
    in_progress = Bug.query.filter_by(status="in_progress").count()
    resolved = Bug.query.filter_by(status="resolved").count()
    closed = Bug.query.filter_by(status="closed").count()

    severity_counts = (
        db.session.query(Bug.severity, func.count(Bug.id))
        .group_by(Bug.severity)
        .all()
    )
    severity_map = {s: c for s, c in severity_counts}

    recent_bugs = Bug.query.order_by(Bug.created_at.desc()).limit(10).all()

    return render_template(
        "dashboard.html",
        total=total,
        open_count=open_count,
        in_progress=in_progress,
        resolved=resolved,
        closed=closed,
        severity_map=severity_map,
        recent_bugs=recent_bugs,
    )


# ── bug list ─────────────────────────────────────────────────────────────────

@app.route("/bugs")
def bug_list():
    query = Bug.query

    status = request.args.get("status")
    severity = request.args.get("severity")
    assignee = request.args.get("assignee")
    sort = request.args.get("sort", "newest")

    if status:
        query = query.filter_by(status=status)
    if severity:
        query = query.filter_by(severity=severity)
    if assignee:
        query = query.filter_by(assigned_to_id=int(assignee))

    if sort == "oldest":
        query = query.order_by(Bug.created_at.asc())
    else:
        query = query.order_by(Bug.created_at.desc())

    bugs = query.all()
    testers = Tester.query.order_by(Tester.name).all()

    return render_template(
        "bugs.html",
        bugs=bugs,
        testers=testers,
        current_status=status,
        current_severity=severity,
        current_assignee=assignee,
        current_sort=sort,
    )


# ── create bug ───────────────────────────────────────────────────────────────

@app.route("/bugs/new", methods=["GET", "POST"])
def bug_new():
    testers = Tester.query.order_by(Tester.name).all()
    devices = Device.query.order_by(Device.name).all()
    sw_builds = SWBuild.query.order_by(SWBuild.name).all()
    modes = Mode.query.order_by(Mode.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
            return render_template("bug_form.html", testers=testers, devices=devices, sw_builds=sw_builds, modes=modes, bug=None)

        bug = Bug(
            title=title,
            description=request.form.get("description", "").strip(),
            severity=request.form.get("severity", "medium"),
            status="open",
            reported_by_id=request.form.get("reported_by") or None,
            assigned_to_id=request.form.get("assigned_to") or None,
            device_id=request.form.get("device") or None,
            sw_build_id=request.form.get("sw_build") or None,
            mode_id=request.form.get("mode") or None,
            tg=request.form.get("tg", "").strip() or None,
        )
        db.session.add(bug)
        db.session.commit()
        flash("Bug reported successfully.", "success")
        return redirect(url_for("bug_detail", bug_id=bug.id))

    return render_template("bug_form.html", testers=testers, devices=devices, sw_builds=sw_builds, modes=modes, bug=None)


# ── edit bug ─────────────────────────────────────────────────────────────────

@app.route("/bugs/<int:bug_id>/edit", methods=["GET", "POST"])
def bug_edit(bug_id):
    bug = Bug.query.get_or_404(bug_id)
    testers = Tester.query.order_by(Tester.name).all()
    devices = Device.query.order_by(Device.name).all()
    sw_builds = SWBuild.query.order_by(SWBuild.name).all()
    modes = Mode.query.order_by(Mode.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
            return render_template("bug_form.html", testers=testers, devices=devices, sw_builds=sw_builds, modes=modes, bug=bug)

        bug.title = title
        bug.description = request.form.get("description", "").strip()
        bug.severity = request.form.get("severity", bug.severity)
        bug.status = request.form.get("status", bug.status)
        bug.reported_by_id = request.form.get("reported_by") or None
        bug.assigned_to_id = request.form.get("assigned_to") or None
        bug.device_id = request.form.get("device") or None
        bug.sw_build_id = request.form.get("sw_build") or None
        bug.mode_id = request.form.get("mode") or None
        bug.tg = request.form.get("tg", "").strip() or None
        db.session.commit()
        flash("Bug updated.", "success")
        return redirect(url_for("bug_detail", bug_id=bug.id))

    return render_template("bug_form.html", testers=testers, devices=devices, sw_builds=sw_builds, modes=modes, bug=bug)


# ── bug detail ───────────────────────────────────────────────────────────────

@app.route("/bugs/<int:bug_id>")
def bug_detail(bug_id):
    bug = Bug.query.get_or_404(bug_id)
    return render_template("bug_detail.html", bug=bug)


# ── delete bug ───────────────────────────────────────────────────────────────

@app.route("/bugs/<int:bug_id>/delete", methods=["POST"])
def bug_delete(bug_id):
    bug = Bug.query.get_or_404(bug_id)
    # remove attachment files
    for att in bug.attachments:
        filepath = os.path.join(UPLOAD_DIR, att.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    db.session.delete(bug)
    db.session.commit()
    flash("Bug deleted.", "info")
    return redirect(url_for("bug_list"))


# ── attachments ──────────────────────────────────────────────────────────────

@app.route("/bugs/<int:bug_id>/attach", methods=["POST"])
def bug_attach(bug_id):
    bug = Bug.query.get_or_404(bug_id)
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("bug_detail", bug_id=bug.id))

    if not allowed_file(file.filename):
        flash("File type not allowed.", "danger")
        return redirect(url_for("bug_detail", bug_id=bug.id))

    ext = file.filename.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_DIR, safe_name))

    attachment = Attachment(
        bug_id=bug.id,
        filename=safe_name,
        original_filename=file.filename,
    )
    db.session.add(attachment)
    db.session.commit()
    flash("File attached.", "success")
    return redirect(url_for("bug_detail", bug_id=bug.id))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/attachments/<int:att_id>/delete", methods=["POST"])
def attachment_delete(att_id):
    att = Attachment.query.get_or_404(att_id)
    bug_id = att.bug_id
    filepath = os.path.join(UPLOAD_DIR, att.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(att)
    db.session.commit()
    flash("Attachment removed.", "info")
    return redirect(url_for("bug_detail", bug_id=bug_id))


# ── testers ──────────────────────────────────────────────────────────────────

@app.route("/testers", methods=["GET", "POST"])
def tester_list():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        if not name or not email:
            flash("Name and email are required.", "danger")
        elif Tester.query.filter_by(email=email).first():
            flash("A tester with that email already exists.", "warning")
        else:
            tester = Tester(name=name, email=email)
            db.session.add(tester)
            db.session.commit()
            flash(f"Tester '{name}' added.", "success")
        return redirect(url_for("tester_list"))

    testers = Tester.query.order_by(Tester.name).all()
    return render_template("testers.html", testers=testers)


@app.route("/testers/<int:tester_id>/delete", methods=["POST"])
def tester_delete(tester_id):
    tester = Tester.query.get_or_404(tester_id)
    db.session.delete(tester)
    db.session.commit()
    flash(f"Tester '{tester.name}' removed.", "info")
    return redirect(url_for("tester_list"))


# ── lookup AJAX routes ───────────────────────────────────────────────────────

@app.route("/api/devices", methods=["POST"])
def api_add_device():
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if Device.query.filter_by(name=name).first():
        return jsonify({"error": "Device already exists"}), 409
    device = Device(name=name)
    db.session.add(device)
    db.session.commit()
    return jsonify({"id": device.id, "name": device.name})


@app.route("/api/sw_builds", methods=["POST"])
def api_add_sw_build():
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if SWBuild.query.filter_by(name=name).first():
        return jsonify({"error": "SW Build already exists"}), 409
    build = SWBuild(name=name)
    db.session.add(build)
    db.session.commit()
    return jsonify({"id": build.id, "name": build.name})


@app.route("/api/modes", methods=["POST"])
def api_add_mode():
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if Mode.query.filter_by(name=name).first():
        return jsonify({"error": "Mode already exists"}), 409
    mode = Mode(name=name)
    db.session.add(mode)
    db.session.commit()
    return jsonify({"id": mode.id, "name": mode.name})


# ── backup / export / import ─────────────────────────────────────────────────

def _export_data():
    """Serialize the entire database to a JSON-compatible dict."""
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "devices": [{"id": d.id, "name": d.name} for d in Device.query.all()],
        "sw_builds": [{"id": b.id, "name": b.name} for b in SWBuild.query.all()],
        "modes": [{"id": m.id, "name": m.name} for m in Mode.query.all()],
        "testers": [
            {"id": t.id, "name": t.name, "email": t.email,
             "created_at": t.created_at.isoformat() if t.created_at else None}
            for t in Tester.query.all()
        ],
        "bugs": [
            {
                "id": b.id, "title": b.title, "description": b.description,
                "severity": b.severity, "status": b.status,
                "reported_by_id": b.reported_by_id, "assigned_to_id": b.assigned_to_id,
                "device_id": b.device_id, "sw_build_id": b.sw_build_id,
                "mode_id": b.mode_id, "tg": b.tg,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "updated_at": b.updated_at.isoformat() if b.updated_at else None,
            }
            for b in Bug.query.all()
        ],
        "attachments": [
            {"id": a.id, "bug_id": a.bug_id, "filename": a.filename,
             "original_filename": a.original_filename,
             "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None}
            for a in Attachment.query.all()
        ],
    }
    return data


def _import_data(data):
    """Clear the database and import from a JSON dict."""
    # delete in dependency order
    Attachment.query.delete()
    Bug.query.delete()
    Tester.query.delete()
    Device.query.delete()
    SWBuild.query.delete()
    Mode.query.delete()
    db.session.commit()

    for d in data.get("devices", []):
        db.session.add(Device(id=d["id"], name=d["name"]))
    for b in data.get("sw_builds", []):
        db.session.add(SWBuild(id=b["id"], name=b["name"]))
    for m in data.get("modes", []):
        db.session.add(Mode(id=m["id"], name=m["name"]))
    for t in data.get("testers", []):
        db.session.add(Tester(
            id=t["id"], name=t["name"], email=t["email"],
            created_at=datetime.fromisoformat(t["created_at"]) if t.get("created_at") else None,
        ))
    db.session.commit()

    for b in data.get("bugs", []):
        db.session.add(Bug(
            id=b["id"], title=b["title"], description=b.get("description"),
            severity=b["severity"], status=b["status"],
            reported_by_id=b.get("reported_by_id"),
            assigned_to_id=b.get("assigned_to_id"),
            device_id=b.get("device_id"), sw_build_id=b.get("sw_build_id"),
            mode_id=b.get("mode_id"), tg=b.get("tg"),
            created_at=datetime.fromisoformat(b["created_at"]) if b.get("created_at") else None,
            updated_at=datetime.fromisoformat(b["updated_at"]) if b.get("updated_at") else None,
        ))
    for a in data.get("attachments", []):
        db.session.add(Attachment(
            id=a["id"], bug_id=a["bug_id"], filename=a["filename"],
            original_filename=a["original_filename"],
            uploaded_at=datetime.fromisoformat(a["uploaded_at"]) if a.get("uploaded_at") else None,
        ))
    db.session.commit()


@app.route("/backup")
def backup_page():
    return render_template("backup.html")


@app.route("/backup/export")
def backup_export():
    data = _export_data()
    json_str = json.dumps(data, indent=2)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=bug_tracker_backup_{timestamp}.json"},
    )


@app.route("/backup/import", methods=["POST"])
def backup_import():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("backup_page"))

    try:
        data = json.load(file)
        _import_data(data)
        flash("Data imported successfully.", "success")
    except (json.JSONDecodeError, KeyError, Exception) as e:
        flash(f"Import failed: {e}", "danger")

    return redirect(url_for("backup_page"))


@app.route("/backup/csv")
def backup_csv():
    """Export all tables as CSV files inside a ZIP archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # devices
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["id", "name"])
        for d in Device.query.all():
            w.writerow([d.id, d.name])
        zf.writestr("devices.csv", csv_buf.getvalue())

        # sw_builds
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["id", "name"])
        for b in SWBuild.query.all():
            w.writerow([b.id, b.name])
        zf.writestr("sw_builds.csv", csv_buf.getvalue())

        # modes
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["id", "name"])
        for m in Mode.query.all():
            w.writerow([m.id, m.name])
        zf.writestr("modes.csv", csv_buf.getvalue())

        # testers
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["id", "name", "email", "created_at"])
        for t in Tester.query.all():
            w.writerow([t.id, t.name, t.email, t.created_at.isoformat() if t.created_at else ""])
        zf.writestr("testers.csv", csv_buf.getvalue())

        # bugs
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["id", "title", "description", "severity", "status",
                     "reported_by", "assigned_to", "device", "sw_build", "mode", "tg",
                     "created_at", "updated_at"])
        for b in Bug.query.all():
            w.writerow([
                b.id, b.title, b.description or "", b.severity, b.status,
                b.reporter.name if b.reporter else "",
                b.assignee.name if b.assignee else "",
                b.device.name if b.device else "",
                b.sw_build.name if b.sw_build else "",
                b.mode.name if b.mode else "",
                b.tg or "",
                b.created_at.isoformat() if b.created_at else "",
                b.updated_at.isoformat() if b.updated_at else "",
            ])
        zf.writestr("bugs.csv", csv_buf.getvalue())

        # attachments
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["id", "bug_id", "filename", "original_filename", "uploaded_at"])
        for a in Attachment.query.all():
            w.writerow([a.id, a.bug_id, a.filename, a.original_filename,
                        a.uploaded_at.isoformat() if a.uploaded_at else ""])
        zf.writestr("attachments.csv", csv_buf.getvalue())

    buf.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        buf.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename=bug_tracker_csv_{timestamp}.zip"},
    )


@app.route("/backup/db")
def backup_db_file():
    """Download the raw SQLite database file."""
    return send_from_directory(BASE_DIR, "bugs.db", as_attachment=True)


# ── run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
