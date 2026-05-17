# Beta Tester Bug Tracker

A web-based bug tracking application built with Flask and SQLite, designed for managing beta tester bug reports.

## Features

- **Dashboard** — At-a-glance stats for open, in-progress, and resolved bugs with a severity breakdown chart
- **Bug Management** — Create, edit, view, and delete bug reports with filtering by status, severity, and assignee
- **Custom Fields** — Device, SW Build, and Mode dropdowns with inline add-new capability, plus a free-text TG field
- **Tester Management** — Add and manage testers, track who reported and is assigned to each bug
- **File Attachments** — Upload screenshots and files to bug reports (16 MB limit, image thumbnails displayed inline)
- **Backup & Restore** — Export data as JSON (re-importable) or CSV (ZIP of spreadsheets), download the raw SQLite database

## Requirements

- Python 3.10+

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/PrdAmrican/bug-tracker.git
cd bug-tracker

# 2. (Optional) Create a virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/macOS:
# source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Open http://localhost:5000 in your browser.

## Project Structure

```
bug_tracker/
├── app.py              # Flask application and all routes
├── models.py           # SQLAlchemy database models
├── requirements.txt    # Python dependencies
├── DEPLOYMENT.md       # Production deployment guide
├── templates/
│   ├── base.html       # Layout with navbar
│   ├── dashboard.html  # Stats dashboard (home page)
│   ├── bugs.html       # Bug list with filters
│   ├── bug_detail.html # Single bug view + attachments
│   ├── bug_form.html   # Create/edit bug form
│   ├── testers.html    # Manage testers
│   └── backup.html     # Backup & restore page
├── static/
│   └── style.css       # Custom styles
└── uploads/            # Uploaded attachment files (git-ignored)
```

## Database

The app uses SQLite — the database file `bugs.db` is created automatically on first run. No external database server is needed.

### Schema

- **bugs** — id, title, description, severity, status, reporter, assignee, device, sw_build, mode, tg, timestamps
- **testers** — id, name, email
- **devices** / **sw_builds** / **modes** — lookup tables for dropdowns
- **attachments** — file metadata linked to bugs

## Backup & Restore

Navigate to the **Backup** page in the app to:

- **Export as JSON** — Full data dump, can be re-imported to restore
- **Export as CSV** — ZIP archive with one CSV per table (Excel/Sheets compatible)
- **Download SQLite DB** — Raw `bugs.db` file
- **Import JSON** — Upload a previously exported JSON file to replace all data

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on running with Waitress/Gunicorn, setting up as a system service, and configuring a reverse proxy.

## License

This project is provided as-is for internal use.
