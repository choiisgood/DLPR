#!/usr/bin/env python3
"""
DLPR — yt-dlp Web App Backend
Requirements: pip3 install flask flask-cors yt-dlp gunicorn
Usage: gunicorn -w 2 -b 0.0.0.0:8080 server:app
"""

import os
import uuid
import threading
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
CORS(app)

# ─── Config ───────────────────────────────────────────────────────────────────
DEFAULT_DOWNLOAD_DIR = os.environ.get("YTDLP_DOWNLOAD_DIR", os.path.expanduser("~/downloads"))
SECRET_KEY           = os.environ.get("YTDLP_SECRET", "changeme123")
MAX_JOBS             = 5
BLOCKED_PATHS        = {'/', '/etc', '/bin', '/usr', '/sbin', '/sys', '/proc', '/root', '/boot', '/dev'}
# ──────────────────────────────────────────────────────────────────────────────

# In-memory job store (resets on server restart)
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


def run_download(job_id: str, url: str, quality: str, audio_only: bool, dest: str):
    """Run yt-dlp in a background thread."""
    with jobs_lock:
        jobs[job_id]["status"]     = "downloading"
        jobs[job_id]["started_at"] = datetime.now().isoformat()

    os.makedirs(dest, exist_ok=True)

    cmd = ["yt-dlp", "--no-playlist"]

    if audio_only:
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        fmt_map = {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
            "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
        }
        cmd += ["-f", fmt_map.get(quality, "best")]

    cmd += [
        "-o", os.path.join(dest, "%(title).80s.%(ext)s"),
        "--merge-output-format", "mp4",
        "--embed-thumbnail",
        "--add-metadata",
        url,
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        log_lines = []
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            log_lines.append(line)
            if "[download]" in line and "%" in line:
                try:
                    pct = float(line.split("%")[0].split()[-1])
                    with jobs_lock:
                        jobs[job_id]["progress"] = pct
                except (ValueError, IndexError):
                    pass
            with jobs_lock:
                jobs[job_id]["log"] = line

        proc.wait()

        with jobs_lock:
            if proc.returncode == 0:
                jobs[job_id]["status"]   = "done"
                jobs[job_id]["progress"] = 100
                jobs[job_id]["log"]      = "Download complete"
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["log"]    = "\n".join(log_lines[-5:]) or "Unknown error"
            jobs[job_id]["finished_at"] = datetime.now().isoformat()

    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"]      = "error"
            jobs[job_id]["log"]         = str(e)
            jobs[job_id]["finished_at"] = datetime.now().isoformat()


# ─── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json(silent=True) or {}

    if data.get("key") != SECRET_KEY:
        return jsonify({"error": "Authentication failed — invalid secret key."}), 403

    url = (data.get("url") or "").strip()
    if not url.startswith("http"):
        return jsonify({"error": "Please enter a valid URL."}), 400

    with jobs_lock:
        active = sum(1 for j in jobs.values() if j["status"] in ("queued", "downloading"))
    if active >= MAX_JOBS:
        return jsonify({"error": f"Too many active jobs (max {MAX_JOBS}). Please wait."}), 429

    quality    = data.get("quality", "best")
    audio_only = bool(data.get("audio_only", False))
    dest_raw   = (data.get("dest") or "").strip()
    job_id     = str(uuid.uuid4())[:8]

    # Resolve destination path
    if dest_raw:
        dest = os.path.normpath(dest_raw)
        if not dest.startswith("/"):
            return jsonify({"error": "Please enter an absolute path starting with /."}), 400
        if dest in BLOCKED_PATHS:
            return jsonify({"error": f"Path '{dest}' is not allowed."}), 400
    else:
        dest = DEFAULT_DOWNLOAD_DIR

    with jobs_lock:
        jobs[job_id] = {
            "id":          job_id,
            "url":         url,
            "quality":     "MP3" if audio_only else quality,
            "dest":        dest,
            "status":      "queued",
            "progress":    0,
            "log":         "Queued...",
            "created_at":  datetime.now().isoformat(),
            "started_at":  None,
            "finished_at": None,
        }

    threading.Thread(
        target=run_download,
        args=(job_id, url, quality, audio_only, dest),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id}), 202


@app.route("/api/status/<job_id>")
def job_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(job)


@app.route("/api/jobs")
def list_jobs():
    if request.args.get("key") != SECRET_KEY:
        return jsonify({"error": "Authentication failed."}), 403
    with jobs_lock:
        return jsonify(list(reversed(list(jobs.values()))))


@app.route("/api/clear", methods=["POST"])
def clear_jobs():
    data = request.get_json(silent=True) or {}
    if data.get("key") != SECRET_KEY:
        return jsonify({"error": "Authentication failed."}), 403
    with jobs_lock:
        to_del = [jid for jid, j in jobs.items() if j["status"] in ("done", "error")]
        for jid in to_del:
            del jobs[jid]
    return jsonify({"cleared": len(to_del)})


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 46)
    print("  DLPR — yt-dlp Web App")
    print("=" * 46)
    print(f"  URL         : http://0.0.0.0:8080")
    print(f"  Default dir : {DEFAULT_DOWNLOAD_DIR}")
    print(f"  Secret key  : {SECRET_KEY}")
    print("=" * 46)
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
