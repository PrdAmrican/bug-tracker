"""Comprehensive test suite for the Beta Tester Bug Tracker app."""

import io
import json
import os
import tempfile
import zipfile

import pytest

# Configure a test database before importing the app
TEST_DB_FD, TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(TEST_DB_FD)

os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB_PATH

from app import app, UPLOAD_DIR
from models import db, Bug, Tester, Device, SWBuild, Mode, Attachment


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def client():
    """Create a fresh test client and database for every test."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + TEST_DB_PATH
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        with app.app_context():
            db.drop_all()
            db.create_all()
        yield client


@pytest.fixture
def sample_tester(client):
    """Insert a tester and return its id."""
    with app.app_context():
        t = Tester(name="Alice", email="alice@example.com")
        db.session.add(t)
        db.session.commit()
        return t.id


@pytest.fixture
def sample_lookups(client):
    """Insert one Device, SWBuild, and Mode; return their ids."""
    with app.app_context():
        d = Device(name="Phone X")
        b = SWBuild(name="v1.0.0")
        m = Mode(name="Dark")
        db.session.add_all([d, b, m])
        db.session.commit()
        return {"device_id": d.id, "sw_build_id": b.id, "mode_id": m.id}


@pytest.fixture
def sample_bug(client, sample_tester, sample_lookups):
    """Insert a bug with all fields populated and return its id."""
    with app.app_context():
        bug = Bug(
            title="Crash on launch",
            description="App crashes immediately after splash screen.",
            severity="critical",
            status="open",
            reported_by_id=sample_tester,
            assigned_to_id=sample_tester,
            device_id=sample_lookups["device_id"],
            sw_build_id=sample_lookups["sw_build_id"],
            mode_id=sample_lookups["mode_id"],
            tg="TG-42",
        )
        db.session.add(bug)
        db.session.commit()
        return bug.id


# ── dashboard ────────────────────────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_empty(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data
        assert b"No bugs reported yet" in resp.data

    def test_dashboard_with_bugs(self, client, sample_bug):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Crash on launch" in resp.data
        # stat cards should show counts
        assert b"Total Bugs" in resp.data


# ── tester management ────────────────────────────────────────────────────────


class TestTesters:
    def test_list_testers_empty(self, client):
        resp = client.get("/testers")
        assert resp.status_code == 200
        assert b"No testers yet" in resp.data

    def test_add_tester(self, client):
        resp = client.post(
            "/testers",
            data={"name": "Bob", "email": "bob@example.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Bob" in resp.data
        assert b"bob@example.com" in resp.data

    def test_add_tester_missing_fields(self, client):
        resp = client.post(
            "/testers", data={"name": "", "email": ""}, follow_redirects=True
        )
        assert b"Name and email are required" in resp.data

    def test_add_duplicate_email(self, client, sample_tester):
        resp = client.post(
            "/testers",
            data={"name": "Alice2", "email": "alice@example.com"},
            follow_redirects=True,
        )
        assert b"already exists" in resp.data

    def test_delete_tester(self, client, sample_tester):
        resp = client.post(
            f"/testers/{sample_tester}/delete", follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"removed" in resp.data

    def test_delete_nonexistent_tester(self, client):
        resp = client.post("/testers/999/delete")
        assert resp.status_code == 404


# ── bug CRUD ─────────────────────────────────────────────────────────────────


class TestBugCRUD:
    def test_bug_list_empty(self, client):
        resp = client.get("/bugs")
        assert resp.status_code == 200
        assert b"No bugs match" in resp.data

    def test_create_bug_get(self, client):
        resp = client.get("/bugs/new")
        assert resp.status_code == 200
        assert b"Report a Bug" in resp.data

    def test_create_bug_minimal(self, client):
        resp = client.post(
            "/bugs/new",
            data={"title": "Button broken", "severity": "low"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Button broken" in resp.data
        assert b"Bug reported successfully" in resp.data

    def test_create_bug_all_fields(self, client, sample_tester, sample_lookups):
        resp = client.post(
            "/bugs/new",
            data={
                "title": "Full bug",
                "description": "Detailed description here.",
                "severity": "high",
                "reported_by": sample_tester,
                "assigned_to": sample_tester,
                "device": sample_lookups["device_id"],
                "sw_build": sample_lookups["sw_build_id"],
                "mode": sample_lookups["mode_id"],
                "tg": "TG-99",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Full bug" in resp.data
        assert b"TG-99" in resp.data
        assert b"Phone X" in resp.data

    def test_create_bug_missing_title(self, client):
        resp = client.post(
            "/bugs/new", data={"title": "", "severity": "medium"}
        )
        assert resp.status_code == 200
        assert b"Title is required" in resp.data

    def test_view_bug_detail(self, client, sample_bug):
        resp = client.get(f"/bugs/{sample_bug}")
        assert resp.status_code == 200
        assert b"Crash on launch" in resp.data
        assert b"critical" in resp.data
        assert b"TG-42" in resp.data

    def test_view_nonexistent_bug(self, client):
        resp = client.get("/bugs/999")
        assert resp.status_code == 404

    def test_edit_bug_get(self, client, sample_bug):
        resp = client.get(f"/bugs/{sample_bug}/edit")
        assert resp.status_code == 200
        assert b"Edit Bug" in resp.data
        assert b"Crash on launch" in resp.data

    def test_edit_bug_post(self, client, sample_bug):
        resp = client.post(
            f"/bugs/{sample_bug}/edit",
            data={
                "title": "Updated title",
                "description": "New desc",
                "severity": "low",
                "status": "resolved",
                "tg": "TG-100",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Updated title" in resp.data
        assert b"Bug updated" in resp.data

    def test_edit_bug_clear_optional_fields(self, client, sample_bug):
        resp = client.post(
            f"/bugs/{sample_bug}/edit",
            data={
                "title": "Crash on launch",
                "severity": "critical",
                "status": "open",
                "reported_by": "",
                "assigned_to": "",
                "device": "",
                "sw_build": "",
                "mode": "",
                "tg": "",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            bug = Bug.query.get(sample_bug)
            assert bug.reported_by_id is None
            assert bug.device_id is None
            assert bug.tg is None

    def test_delete_bug(self, client, sample_bug):
        resp = client.post(f"/bugs/{sample_bug}/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Bug deleted" in resp.data
        with app.app_context():
            assert Bug.query.get(sample_bug) is None


# ── bug list filtering & sorting ─────────────────────────────────────────────


class TestBugFiltering:
    def _seed_bugs(self, client):
        with app.app_context():
            bugs = [
                Bug(title="Bug A", severity="low", status="open"),
                Bug(title="Bug B", severity="critical", status="resolved"),
                Bug(title="Bug C", severity="high", status="open"),
            ]
            db.session.add_all(bugs)
            db.session.commit()

    def test_filter_by_status(self, client):
        self._seed_bugs(client)
        resp = client.get("/bugs?status=open")
        assert b"Bug A" in resp.data
        assert b"Bug C" in resp.data
        assert b"Bug B" not in resp.data

    def test_filter_by_severity(self, client):
        self._seed_bugs(client)
        resp = client.get("/bugs?severity=critical")
        assert b"Bug B" in resp.data
        assert b"Bug A" not in resp.data

    def test_filter_by_assignee(self, client, sample_tester):
        with app.app_context():
            db.session.add(Bug(title="Assigned", severity="low", status="open", assigned_to_id=sample_tester))
            db.session.add(Bug(title="Unassigned", severity="low", status="open"))
            db.session.commit()
        resp = client.get(f"/bugs?assignee={sample_tester}")
        assert b"Assigned" in resp.data
        assert b"Unassigned" not in resp.data

    def test_sort_oldest(self, client):
        self._seed_bugs(client)
        resp = client.get("/bugs?sort=oldest")
        assert resp.status_code == 200
        # Bug A was inserted first, should appear before Bug C
        data = resp.data.decode()
        assert data.index("Bug A") < data.index("Bug C")


# ── lookup AJAX routes ───────────────────────────────────────────────────────


class TestLookupAPI:
    def test_add_device(self, client):
        resp = client.post("/api/devices", data={"name": "Tablet Y"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Tablet Y"
        assert "id" in data

    def test_add_duplicate_device(self, client, sample_lookups):
        resp = client.post("/api/devices", data={"name": "Phone X"})
        assert resp.status_code == 409

    def test_add_device_empty_name(self, client):
        resp = client.post("/api/devices", data={"name": ""})
        assert resp.status_code == 400

    def test_add_sw_build(self, client):
        resp = client.post("/api/sw_builds", data={"name": "v2.0.0"})
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "v2.0.0"

    def test_add_duplicate_sw_build(self, client, sample_lookups):
        resp = client.post("/api/sw_builds", data={"name": "v1.0.0"})
        assert resp.status_code == 409

    def test_add_mode(self, client):
        resp = client.post("/api/modes", data={"name": "Light"})
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Light"

    def test_add_duplicate_mode(self, client, sample_lookups):
        resp = client.post("/api/modes", data={"name": "Dark"})
        assert resp.status_code == 409


# ── attachments ──────────────────────────────────────────────────────────────


class TestAttachments:
    def test_upload_attachment(self, client, sample_bug):
        data = {
            "file": (io.BytesIO(b"fake image data"), "screenshot.png"),
        }
        resp = client.post(
            f"/bugs/{sample_bug}/attach",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"File attached" in resp.data
        with app.app_context():
            atts = Attachment.query.filter_by(bug_id=sample_bug).all()
            assert len(atts) == 1
            assert atts[0].original_filename == "screenshot.png"

    def test_upload_no_file(self, client, sample_bug):
        resp = client.post(
            f"/bugs/{sample_bug}/attach",
            data={},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"No file selected" in resp.data

    def test_upload_disallowed_extension(self, client, sample_bug):
        data = {
            "file": (io.BytesIO(b"binary"), "malware.exe"),
        }
        resp = client.post(
            f"/bugs/{sample_bug}/attach",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"File type not allowed" in resp.data

    def test_delete_attachment(self, client, sample_bug):
        # upload first
        data = {"file": (io.BytesIO(b"data"), "test.txt")}
        client.post(
            f"/bugs/{sample_bug}/attach",
            data=data,
            content_type="multipart/form-data",
        )
        with app.app_context():
            att = Attachment.query.first()
            att_id = att.id

        resp = client.post(f"/attachments/{att_id}/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Attachment removed" in resp.data
        with app.app_context():
            assert Attachment.query.get(att_id) is None

    def test_delete_bug_removes_attachments(self, client, sample_bug):
        data = {"file": (io.BytesIO(b"data"), "file.txt")}
        client.post(
            f"/bugs/{sample_bug}/attach",
            data=data,
            content_type="multipart/form-data",
        )
        with app.app_context():
            att = Attachment.query.first()
            filename = att.filename

        client.post(f"/bugs/{sample_bug}/delete")
        with app.app_context():
            assert Attachment.query.count() == 0
        # file on disk should also be removed
        assert not os.path.exists(os.path.join(UPLOAD_DIR, filename))

    def test_serve_uploaded_file(self, client, sample_bug):
        content = b"hello world"
        data = {"file": (io.BytesIO(content), "note.txt")}
        client.post(
            f"/bugs/{sample_bug}/attach",
            data=data,
            content_type="multipart/form-data",
        )
        with app.app_context():
            att = Attachment.query.first()
            filename = att.filename
        resp = client.get(f"/uploads/{filename}")
        assert resp.status_code == 200
        assert resp.data == content


# ── backup & restore ─────────────────────────────────────────────────────────


class TestBackup:
    def test_backup_page(self, client):
        resp = client.get("/backup")
        assert resp.status_code == 200
        assert b"Backup" in resp.data

    def test_export_json_empty(self, client):
        resp = client.get("/backup/export")
        assert resp.status_code == 200
        assert resp.content_type == "application/json"
        data = json.loads(resp.data)
        assert data["bugs"] == []
        assert data["testers"] == []
        assert "exported_at" in data

    def test_export_json_with_data(self, client, sample_bug):
        resp = client.get("/backup/export")
        data = json.loads(resp.data)
        assert len(data["bugs"]) == 1
        assert data["bugs"][0]["title"] == "Crash on launch"
        assert len(data["testers"]) == 1
        assert len(data["devices"]) == 1

    def test_export_import_roundtrip(self, client, sample_bug, sample_tester):
        # export
        resp = client.get("/backup/export")
        exported = resp.data

        # wipe DB
        with app.app_context():
            db.drop_all()
            db.create_all()
            assert Bug.query.count() == 0

        # import
        resp = client.post(
            "/backup/import",
            data={"file": (io.BytesIO(exported), "backup.json")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Data imported successfully" in resp.data
        with app.app_context():
            assert Bug.query.count() == 1
            assert Tester.query.count() == 1
            bug = Bug.query.first()
            assert bug.title == "Crash on launch"
            assert bug.tg == "TG-42"

    def test_import_invalid_json(self, client):
        resp = client.post(
            "/backup/import",
            data={"file": (io.BytesIO(b"not json"), "bad.json")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Import failed" in resp.data

    def test_import_no_file(self, client):
        resp = client.post(
            "/backup/import", data={}, follow_redirects=True
        )
        assert b"No file selected" in resp.data

    def test_export_csv_zip(self, client, sample_bug):
        resp = client.get("/backup/csv")
        assert resp.status_code == 200
        assert resp.content_type == "application/zip"

        with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
            names = zf.namelist()
            assert "bugs.csv" in names
            assert "testers.csv" in names
            assert "devices.csv" in names
            assert "sw_builds.csv" in names
            assert "modes.csv" in names
            assert "attachments.csv" in names

            bugs_csv = zf.read("bugs.csv").decode()
            assert "Crash on launch" in bugs_csv
            assert "TG-42" in bugs_csv

    def test_download_db(self, client):
        resp = client.get("/backup/db")
        assert resp.status_code == 200
        # SQLite files start with "SQLite format 3"
        assert resp.data[:16].startswith(b"SQLite format 3")


# ── cleanup ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True, scope="session")
def cleanup():
    yield
    try:
        os.unlink(TEST_DB_PATH)
    except OSError:
        pass
