# DLPR — yt-dlp Web App

> A self-hosted web app that downloads videos to your Linux server by simply pasting a URL from your phone.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-FF0000?style=flat-square&logo=youtube&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Features

- **Paste & download** — supports any site yt-dlp supports (YouTube, Instagram, TikTok, Twitter, etc.)
- **Quality selector** — BEST / 1080p / 720p / 480p
- **Audio only** — extract MP3 at highest quality
- **Custom save path** — type any absolute path on your server (e.g. `/media/drive/movies`)
- **Real-time progress** — live percentage and log output, polled every 1.5 seconds
- **Password auth** — simple password gate so only you can use it
- **Clipboard auto-fill** — tapping the URL field automatically pastes your clipboard

---

## File Structure

```
dlpr/
├── server.py      # Flask backend (REST API + yt-dlp runner)
├── index.html     # Frontend web UI (single file, no build step)
├── install.sh     # One-command install script
├── .gitignore
└── README.md
```

---

## Quick Start

### Automated install (recommended)

```bash
git clone https://github.com/yourname/dlpr.git
cd dlpr
chmod +x install.sh
bash install.sh
```

The script handles everything:

1. Installs `python3`, `ffmpeg`, `pip3`
2. Installs `yt-dlp`, `flask`, `flask-cors`, `gunicorn`
3. Prompts you to set a secret key
4. Registers and starts a systemd service

### Manual install

```bash
sudo apt update && sudo apt install -y python3 python3-pip ffmpeg
pip3 install yt-dlp flask flask-cors gunicorn

export YTDLP_SECRET="your_password_here"

cd dlpr
gunicorn -w 2 -b 0.0.0.0:8080 server:app
```

Then open `http://your-server-ip:8080` in your browser.

---

## Configuration

All configuration is done via environment variables.

| Variable | Default | Description |
|---|---|---|
| `YTDLP_SECRET` | `changeme123` | Secret key for web UI authentication |
| `YTDLP_DOWNLOAD_DIR` | `~/downloads` | Fallback download directory when no path is entered |

You can also edit the constants at the top of `server.py` directly:

```python
DEFAULT_DOWNLOAD_DIR = os.environ.get("YTDLP_DOWNLOAD_DIR", os.path.expanduser("~/downloads"))
SECRET_KEY           = os.environ.get("YTDLP_SECRET", "changeme123")
MAX_JOBS             = 5   # max concurrent downloads
```

---

## Firewall Setup

### Oracle Cloud

Oracle Cloud has two independent firewall layers — both must be opened.

**1. Console — Security List**

`Networking → VCN → Security Lists → Add Ingress Rule`

| Field | Value |
|---|---|
| Source CIDR | `0.0.0.0/0` |
| Protocol | TCP |
| Destination Port | `8080` |

**2. Server — firewalld**

```bash
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

**3. iptables (if needed)**

```bash
sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
sudo apt install iptables-persistent -y
sudo netfilter-persistent save
```

### Other providers (AWS, GCP, etc.)

Open inbound TCP port `8080` in your instance's security group / firewall rules.

---

## API Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `GET /` | GET | — | Serve the web UI |
| `POST /api/download` | POST | body `key` | Start a download job |
| `GET /api/status/:id` | GET | — | Poll job status |
| `GET /api/jobs` | GET | query `key` | List all jobs |
| `POST /api/clear` | POST | body `key` | Delete done/errored jobs |

**Download request body**

```json
{
  "key": "your_secret",
  "url": "https://youtube.com/watch?v=xxxxx",
  "quality": "720",
  "audio_only": false,
  "dest": "/media/drive/videos"
}
```

`dest` — absolute path on the server. If omitted, falls back to `YTDLP_DOWNLOAD_DIR`.

**Job status response**

```json
{
  "id": "a1b2c3d4",
  "url": "https://...",
  "quality": "720",
  "dest": "/media/drive/videos",
  "status": "downloading",
  "progress": 45.3,
  "log": "[download]  45.3% of 123.45MiB",
  "created_at": "2026-01-01T12:00:00",
  "started_at": "2026-01-01T12:00:01",
  "finished_at": null
}
```

---

## Service Management

```bash
# Check status
sudo systemctl status ytdlp-webapp

# Restart
sudo systemctl restart ytdlp-webapp

# Live logs
sudo journalctl -u ytdlp-webapp -f

# Stop
sudo systemctl stop ytdlp-webapp
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask, Gunicorn |
| Downloader | yt-dlp, ffmpeg |
| Frontend | Vanilla HTML / CSS / JS (no build step) |
| Fonts | Space Mono, Sora (Google Fonts) |
| Process manager | systemd |

---

## License

MIT
