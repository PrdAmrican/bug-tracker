from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"<Device {self.name}>"


class SWBuild(db.Model):
    __tablename__ = "sw_builds"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"<SWBuild {self.name}>"


class Mode(db.Model):
    __tablename__ = "modes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"<Mode {self.name}>"


class Tester(db.Model):
    __tablename__ = "testers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    reported_bugs = db.relationship(
        "Bug", foreign_keys="Bug.reported_by_id", back_populates="reporter"
    )
    assigned_bugs = db.relationship(
        "Bug", foreign_keys="Bug.assigned_to_id", back_populates="assignee"
    )

    def __repr__(self):
        return f"<Tester {self.name}>"


class Bug(db.Model):
    __tablename__ = "bugs"

    SEVERITY_CHOICES = ["low", "medium", "high", "critical"]
    STATUS_CHOICES = ["open", "in_progress", "resolved", "closed"]

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="open")
    reported_by_id = db.Column(db.Integer, db.ForeignKey("testers.id"), nullable=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("testers.id"), nullable=True)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=True)
    sw_build_id = db.Column(db.Integer, db.ForeignKey("sw_builds.id"), nullable=True)
    mode_id = db.Column(db.Integer, db.ForeignKey("modes.id"), nullable=True)
    tg = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    reporter = db.relationship(
        "Tester", foreign_keys=[reported_by_id], back_populates="reported_bugs"
    )
    assignee = db.relationship(
        "Tester", foreign_keys=[assigned_to_id], back_populates="assigned_bugs"
    )
    device = db.relationship("Device", foreign_keys=[device_id])
    sw_build = db.relationship("SWBuild", foreign_keys=[sw_build_id])
    mode = db.relationship("Mode", foreign_keys=[mode_id])
    attachments = db.relationship(
        "Attachment", back_populates="bug", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Bug #{self.id}: {self.title}>"


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    bug_id = db.Column(db.Integer, db.ForeignKey("bugs.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    bug = db.relationship("Bug", back_populates="attachments")

    def __repr__(self):
        return f"<Attachment {self.original_filename}>"
