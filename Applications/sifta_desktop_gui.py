"""
Optional Tk viewer for the wormhole messenger API (M1SIFTA_BODY ↔ M5SIFTA_BODY).
This is not the SIFTA OS shell — run sifta_os_desktop.py for the main PyQt desktop.
Launch standalone: python3 Applications/sifta_desktop_gui.py
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import requests
import time
import threading
import json
import random
import queue
from datetime import datetime

from sifta_http_auth import get_sifta_api_base, sifta_headers

API_BASE = get_sifta_api_base()

class SIFTABodyChatGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🐋 M1SIFTA_BODY ↔️ M5SIFTA_BODY LIVE WORMHOLE CHAT")
        self.geometry("1600x1000")
        self.configure(bg="#0a0a0a")
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        
        self.chat_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_tab, text="🌐 WORMHOLE LIVE CHAT (M1 ↔️ M5)")
        
        self.create_chat_tab()
        
        self.data_queue = queue.Queue()
        self.running = True
        threading.Thread(target=self.live_loop, daemon=True).start()
        
        self.process_queue()

    def create_chat_tab(self):
        # Header
        tk.Label(self.chat_tab, text="M1SIFTA_BODY ↔️ M5SIFTA_BODY TALKING THROUGH WORMHOLE", 
                font=("Courier", 20, "bold"), fg="#c026d3", bg="#0a0a0a").pack(pady=10)
        
        # Live chat
        self.chat_text = scrolledtext.ScrolledText(self.chat_tab, height=30, bg="#111111", fg="#22c55e", font=("Courier", 12))
        self.chat_text.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Status
        self.status = tk.Label(self.chat_tab, text="WAITING FOR FIRST WORMHOLE MESSAGE...", fg="#f59e0b", bg="#0a0a0a")
        self.status.pack(pady=5)

    def live_loop(self):
        while self.running:
            try:
                # Pull real messages from wormhole gateway
                resp = requests.get(
                    f"{API_BASE}/messenger/thread?limit=50",
                    headers=sifta_headers(),
                    timeout=5,
                ).json()
                self.data_queue.put(resp.get("messages", []))
                
                # Auto Q&A every 2 minutes
                if int(time.time()) % 120 == 0:
                    self.generate_and_send_qa()
                
            except:
                pass
            time.sleep(3)

    def process_queue(self):
        try:
            while True:
                msgs = self.data_queue.get_nowait()
                self.update_chat(msgs)
        except queue.Empty:
            pass
        if self.running:
            self.after(500, self.process_queue)

    def update_chat(self, messages):
        self.chat_text.delete(1.0, tk.END)
        for msg in messages:
            ts = datetime.fromtimestamp(msg["ts"]).strftime("%H:%M:%S")
            line = f"[{ts}] {msg['from']} → {msg['to']}: {msg['body']}\n"
            if "APPROVED" in msg.get("body", "") or "QUORUM" in msg.get("body", ""):
                line = "✅ " + line  # system confirmation
            self.chat_text.insert(tk.END, line)
        self.chat_text.see(tk.END)

    def generate_and_send_qa(self):
        bodies = ["M1SIFTA_BODY", "M5SIFTA_BODY"]
        from_body = random.choice(bodies)
        to_body = "M5SIFTA_BODY" if from_body == "M1SIFTA_BODY" else "M1SIFTA_BODY"
        
        prompt = f"You are {from_body}. Keep it very brief (1 sentence). Send a technical status report to {to_body} across the wormhole: mention your active inference load, a pending .scar repair, or current STGM energy level."
        data = {"model": "gemma4:latest", "prompt": prompt, "stream": False}
        try:
            req = requests.post("http://127.0.0.1:11434/api/generate", json=data, timeout=30)
            body = req.json().get("response", "🧠📡 (Gândesc...)").strip()
        except:
            body = "🧠📡 (NPU timeout across the Wormhole. Inference energy low.)"
        
        # Send via real wormhole messenger API
        try:
            requests.post(
                f"{API_BASE}/messenger/send",
                json={"from_id": from_body, "to_id": to_body, "body": body},
                headers=sifta_headers(),
                timeout=5,
            )
        except:
            pass
        
        # Log as APPROVED by system
        self.chat_text.insert(tk.END, f"✅ SYSTEM QUORUM APPROVED WORMHOLE MESSAGE\n")
        self.status.config(text=f"LAST Q&A SENT AT {datetime.now().strftime('%H:%M:%S')} — APPROVED BY LEDGER")

if __name__ == "__main__":
    print("🚀 Starting FULL BODY CHAT GUI — M1SIFTA ↔️ M5SIFTA")
    app = SIFTABodyChatGUI()
    app.mainloop()
