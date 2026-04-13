import tkinter as tk
from tkinter import ttk, scrolledtext
import requests
import time
import threading
import json
import queue
from datetime import datetime

API_BASE = "http://localhost:7433/api"

class SIFTAGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🐋 ANTON-SIFTA LIVING SWARM GUI — Python Edition")
        self.geometry("1400x900")
        self.configure(bg="#0a0a0a")
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.beginner_tab = ttk.Frame(self.notebook, style="TFrame")
        self.architect_tab = ttk.Frame(self.notebook, style="TFrame")
        
        self.notebook.add(self.beginner_tab, text="🌊 BEGINNER — Watch the Swarm Breathe")
        self.notebook.add(self.architect_tab, text="🛠️ ARCHITECT — Deep System Control")
        
        self.create_beginner_tab()
        self.create_architect_tab()
        
        # Thread-safe queue for macOS Tkinter
        self.data_queue = queue.Queue()
        
        # Live update thread
        self.running = True
        self.thread = threading.Thread(target=self.live_update_loop, daemon=True)
        self.thread.start()
        
        self.process_queue()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_beginner_tab(self):
        # Header
        header = tk.Label(self.beginner_tab, text="THE SWARM IS ALIVE — PROOF OF USEFUL WORK IN REAL TIME",
                         font=("Courier", 18, "bold"), fg="#c026d3", bg="#0a0a0a")
        header.pack(pady=10)
        
        # Economy breathing panel
        self.economy_frame = tk.Frame(self.beginner_tab, bg="#0a0a0a")
        self.economy_frame.pack(fill="x", pady=10)
        
        self.stgm_label = tk.Label(self.economy_frame, text="STGM METABOLIC POOL: 0.00", 
                                  font=("Courier", 24, "bold"), fg="#f59e0b", bg="#0a0a0a")
        self.stgm_label.pack()
        
        # Swimmers grid
        self.swimmers_frame = tk.Frame(self.beginner_tab, bg="#0a0a0a")
        self.swimmers_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.swimmer_widgets = {}

    def create_architect_tab(self):
        # Terminal style
        tk.Label(self.architect_tab, text="ARCHITECT TERMINAL — CONTROL THE DNA BODY", 
                font=("Courier", 16, "bold"), fg="#22c55e", bg="#0a0a0a").pack(pady=5)
        
        # Wallet Inspector
        inspector_frame = tk.Frame(self.architect_tab, bg="#0a0a0a")
        inspector_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(inspector_frame, text="VIP WALLET INSPECTOR", font=("Courier", 14), fg="#22c55e", bg="#0a0a0a").pack(anchor="w")
        
        self.wallet_entry = tk.Entry(inspector_frame, font=("Courier", 12), width=30, bg="#111111", fg="#22c55e", insertbackground="#22c55e")
        self.wallet_entry.pack(side="left", padx=5)
        self.wallet_entry.insert(0, "GROK_CODER_0X0")
        
        tk.Button(inspector_frame, text="INSPECT", command=self.inspect_wallet, 
                 bg="#22c55e", fg="black", font=("Courier", 10, "bold")).pack(side="left")
        
        self.wallet_result = tk.Text(inspector_frame, height=6, width=80, bg="#111111", fg="#22c55e", font=("Courier", 11))
        self.wallet_result.pack(fill="x", pady=5)
        
        # Manual trade + controls
        control_frame = tk.Frame(self.architect_tab, bg="#0a0a0a")
        control_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Button(control_frame, text="🔥 TRIGGER M1THER → M5QUEEN INFERENCE TRADE", 
                 command=self.trigger_test_trade, bg="#f59e0b", fg="black", font=("Courier", 11, "bold")).pack(pady=5)
        
        # Live terminal log
        self.log_text = scrolledtext.ScrolledText(self.architect_tab, height=20, bg="#111111", fg="#22c55e", font=("Courier", 10))
        self.log_text.pack(fill="both", expand=True, padx=20, pady=10)

    def live_update_loop(self):
        while self.running:
            try:
                # Background thread specifically for HTTP blocking logic!
                economy = requests.get(f"{API_BASE}/inference_economy", timeout=3).json()
                ledger_tail = requests.get(f"{API_BASE}/ledger?limit=20", timeout=3).json()
                
                # Push data to thread-safe queue instead of crashing Tkinter renderer
                self.data_queue.put({"economy": economy, "ledger": ledger_tail})
            except Exception as e:
                pass  # silent fail, swarm stays alive
            time.sleep(2)
            
    def process_queue(self):
        # This function runs strictly on the main GUI thread
        try:
            while True:
                data = self.data_queue.get_nowait()
                economy = data["economy"]
                ledger_tail = data["ledger"]
                
                self.update_economy(economy)
                self.update_swimmers(economy.get("agents", []))
                self.update_log(ledger_tail)
        except queue.Empty:
            pass
            
        if self.running:
            self.after(500, self.process_queue)

    def update_economy(self, data):
        total = data.get("total_stgm", 0)
        self.stgm_label.config(text=f"STGM METABOLIC POOL: {total:.2f} 🐋")
        # Breathing animation
        self.stgm_label.after(800, lambda: self.stgm_label.config(fg="#f59e0b"))
        self.stgm_label.after(1600, lambda: self.stgm_label.config(fg="#eab308"))

    def update_swimmers(self, agents):
        # Clear old
        for widget in self.swimmers_frame.winfo_children():
            widget.destroy()
        
        for agent in agents[:12]:  # limit for layout
            frame = tk.Frame(self.swimmers_frame, bg="#1a1a1a", relief="solid", bd=2)
            frame.pack(side="left", padx=8, pady=8)
            
            ascii_body = agent.get("ascii", "<///[O_O]///>")
            name = agent.get("id", "SWIMMER")
            stgm = agent.get("stgm_balance", 0)
            pow_count = agent.get("proof_of_useful_work", 0)  # repairs
            
            tk.Label(frame, text=ascii_body, font=("Courier", 14), fg="#c026d3", bg="#1a1a1a").pack()
            tk.Label(frame, text=name, font=("Courier", 10, "bold"), fg="white", bg="#1a1a1a").pack()
            tk.Label(frame, text=f"{stgm:.2f} STGM", font=("Courier", 12, "bold"), fg="#f59e0b", bg="#1a1a1a").pack()
            tk.Label(frame, text=f"PROOF OF WORK: {pow_count}", font=("Courier", 9), fg="#22c55e", bg="#1a1a1a").pack()
            
            # Pulse if whale
            if name == "GROK_CODER_0X0":
                tk.Label(frame, text="FOUNDATION WHALE 🐋", font=("Courier", 9, "bold"), fg="#f59e0b", bg="#1a1a1a").pack()

    def inspect_wallet(self):
        agent_id = self.wallet_entry.get().strip()
        try:
            resp = requests.get(f"{API_BASE}/wallet/{agent_id}", timeout=3).json()
            self.wallet_result.delete(1.0, tk.END)
            self.wallet_result.insert(tk.END, json.dumps(resp, indent=2))
        except:
            self.wallet_result.delete(1.0, tk.END)
            self.wallet_result.insert(tk.END, "WALLET NOT FOUND OR SERVER OFFLINE")

    def trigger_test_trade(self):
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] TRIGGERING M1THER → M5QUEEN INFERENCE TRADE (50 STGM)...\n")
        self.log_text.see(tk.END)
        # Real API call (repo already has this endpoint)
        try:
            requests.post(f"{API_BASE}/inference_fee", json={
                "borrower": "M1THER_AGENT",
                "lender": "M5QUEEN",
                "tokens": 5000,
                "model": "llama4-maverick:17b"
            }, timeout=5)
        except:
            pass

    def update_log(self, tail):
        self.log_text.delete(1.0, tk.END)
        for entry in tail[-15:]:
            self.log_text.insert(tk.END, json.dumps(entry, indent=None) + "\n")
        self.log_text.see(tk.END)

    def on_close(self):
        self.running = False
        self.destroy()

if __name__ == "__main__":
    print("🚀 Starting SIFTA Python Desktop GUI...")
    print("Make sure server.py is running on http://localhost:7433")
    app = SIFTAGUI()
    app.mainloop()
