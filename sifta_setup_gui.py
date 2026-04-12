#!/usr/bin/env python3
"""
sifta_setup_gui.py — SIFTA Setup Wizard
A minimalist, web-based setup wizard for SIFTA nodes.
"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="SIFTA Setup Wizard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional: Mount 'static' if we want external css/js
# In this app, we will serve our html from 'static/setup.html'
ROOT_DIR = Path(__file__).parent
STATIC_DIR = ROOT_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Try to serve static if needed, though we will explicitly serve the HTML on `/`
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_gui():
    html_path = STATIC_DIR / "setup.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Setup GUI not found!</h1><p>Please ensure static/setup.html exists.</p>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


def _run_script(command_args: list[str]) -> dict:
    """Helper to run a subprocess and return its output."""
    try:
        result = subprocess.run(
            ["python3", *command_args],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True
        )
        return {"status": "success", "output": result.stdout, "error": result.stderr}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "output": e.stdout, "error": e.stderr}
    except Exception as e:
        return {"status": "error", "output": "", "error": str(e)}


@app.post("/api/setup/keygen")
def generate_keys():
    """Generate Architect keys."""
    res = _run_script(["sifta_relay.py", "--keygen"])
    if res["status"] != "success":
        raise HTTPException(status_code=500, detail=res)
    return res


@app.post("/api/setup/provision")
def provision_node():
    """Provision this node."""
    res = _run_script(["sifta_first_boot.py", "--provision"])
    if res["status"] != "success":
        raise HTTPException(status_code=500, detail=res)
    return res


@app.post("/api/setup/activate")
def activate_node():
    """Activate the provisioned node."""
    res = _run_script(["sifta_first_boot.py", "--activate"])
    if res["status"] != "success":
        raise HTTPException(status_code=500, detail=res)
    return res


@app.post("/api/setup/whatsapp")
def launch_whatsapp():
    """Launch WhatsApp Swarm and stream output for QR scan."""
    def iter_process_output():
        process = subprocess.Popen(
            ["/bin/bash", "start_swarm_whatsapp.sh"],
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in iter(process.stdout.readline, ''):
            yield line
        process.stdout.close()
        process.wait()

    return StreamingResponse(iter_process_output(), media_type="text/plain")


import json
@app.post("/api/setup/channels/save")
async def save_channels(request: Request):
    """Save Telegram and Discord tokens to sifta_channels.json."""
    data = await request.json()
    config_path = ROOT_DIR / "sifta_channels.json"
    
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except Exception:
            config = {}
    else:
        config = {}
        
    if "telegram" in data and data["telegram"]:
        config["TELEGRAM_BOT_TOKEN"] = data["telegram"]
    if "discord" in data and data["discord"]:
        config["DISCORD_BOT_TOKEN"] = data["discord"]
        
    config_path.write_text(json.dumps(config, indent=4))
    
    return {"status": "success", "message": "Channels saved successfully."}


if __name__ == "__main__":
    PORT = 5050
    # Auto-open browser before server starts (delaying slightly so server binds)
    def open_browser():
        time.sleep(1)
        webbrowser.open(f"http://localhost:{PORT}")
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("🚀 Starting SIFTA Setup Wizard on http://localhost:5050")
    uvicorn.run("sifta_setup_gui:app", host="127.0.0.1", port=PORT, log_level="warning")
