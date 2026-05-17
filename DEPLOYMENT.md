# Bug Tracker – Deployment Guide

## Part 1: Setting Up a Production Server

### Prerequisites

- Python 3.10+ installed
- pip (Python package manager)
- A server with network access (Windows or Linux)

### Step 1: Install Dependencies

```bash
cd bug_tracker
pip install -r requirements.txt
pip install waitress  # production WSGI server (works on Windows & Linux)
```

### Step 2: Configure the App for Production

Edit `app.py` and change the secret key to a strong random value:

```python
app.config["SECRET_KEY"] = "generate-a-long-random-string-here"
```

Generate one with Python:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 3: Run with a Production Server

**Do NOT use `python app.py` in production** — Flask's built-in server is for development only.

#### Option A: Waitress (recommended for Windows)

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

#### Option B: Gunicorn (Linux only)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Step 4: Run as a Background Service

#### Windows — NSSM (Non-Sucking Service Manager)

1. Download NSSM from https://nssm.cc/download
2. Install the service:

```powershell
nssm install BugTracker "C:\path\to\python.exe" "-m waitress --host=0.0.0.0 --port=5000 app:app"
nssm set BugTracker AppDirectory "C:\path\to\bug_tracker"
nssm start BugTracker
```

#### Linux — systemd

Create `/etc/systemd/system/bugtracker.service`:

```ini
[Unit]
Description=Bug Tracker App
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/bug_tracker
ExecStart=/opt/bug_tracker/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bugtracker
sudo systemctl start bugtracker
```

### Step 5: (Optional) Reverse Proxy with Nginx

For HTTPS and proper domain support, put Nginx in front:

```nginx
server {
    listen 80;
    server_name bugs.example.com;

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Part 2: Packaging and Moving to Another Server

### Method 1: Copy the Project Folder

This is the simplest approach since the app uses SQLite (single file DB).

#### On the source machine:

```bash
# 1. Export a backup first (optional safety net)
#    Visit http://localhost:5000/backup and click "Export as JSON"

# 2. Archive the entire project folder
#    Windows (PowerShell):
Compress-Archive -Path C:\Users\prdam\bug_tracker -DestinationPath C:\Users\prdam\bug_tracker.zip

#    Linux:
#    tar czf bug_tracker.tar.gz bug_tracker/
```

#### On the destination machine:

```bash
# 1. Extract the archive
#    Windows:
Expand-Archive -Path bug_tracker.zip -DestinationPath C:\apps\

#    Linux:
#    tar xzf bug_tracker.tar.gz -C /opt/

# 2. Create a virtual environment (recommended)
cd bug_tracker
python -m venv venv

#    Windows:
venv\Scripts\activate

#    Linux:
#    source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install waitress   # or gunicorn on Linux

# 4. Verify it works
python app.py
# Visit http://localhost:5000 to confirm

# 5. Set up as a service (see Part 1, Step 4)
```

### Method 2: JSON Export/Import (Data Only)

Use this if you want a clean install on the new server and only need to move data.

#### On the source machine:

1. Open http://localhost:5000/backup
2. Click **Export as JSON** — saves a `.json` file with all data

#### On the destination machine:

1. Set up the app fresh (clone or copy code, install deps, run once to create DB)
2. Open http://localhost:5000/backup
3. Upload the `.json` file using **Import JSON Backup**

> **Note:** Attachment *files* in the `uploads/` folder are NOT included in the JSON export.
> Copy the `uploads/` directory separately if you need them.

### What to Include When Moving

| Item | Required? | Notes |
|------|-----------|-------|
| `app.py` | Yes | Main application |
| `models.py` | Yes | Database models |
| `requirements.txt` | Yes | Python dependencies |
| `templates/` | Yes | All HTML templates |
| `static/` | Yes | CSS and assets |
| `bugs.db` | Yes* | The database (*or use JSON import instead) |
| `uploads/` | If needed | Uploaded attachment files |
| `venv/` | No | Recreate on destination |
| `__pycache__/` | No | Auto-generated |

---

## Quick Reference

| Task | Command |
|------|---------|
| Dev server | `python app.py` |
| Production (Windows) | `waitress-serve --host=0.0.0.0 --port=5000 app:app` |
| Production (Linux) | `gunicorn -w 4 -b 0.0.0.0:5000 app:app` |
| Export backup | Visit `/backup` → Export as JSON |
| Import backup | Visit `/backup` → Import JSON Backup |
| Reset database | Delete `bugs.db` and restart the app |
