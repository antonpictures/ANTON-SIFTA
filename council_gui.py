import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import requests
import json
import threading
import time
import os

API_BASE = "http://localhost:7433/api"

class CouncilRobinhoodApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Swarm Council - Robinhood View")
        # Ensure it looks sleek
        self.geometry("450x800")
        self.configure(bg="#000000") # Pure black
        
        # UI Setup
        self.balance_var = tk.StringVar(value="$0.00")
        self.today_var = tk.StringVar(value="▼ $0.00 (0.00%) Today")
        
        # Header Area
        header_frame = tk.Frame(self, bg="#000000")
        header_frame.pack(fill="x", padx=20, pady=20)
        
        tk.Label(header_frame, text="Investing", font=("Helvetica", 14, "bold"), fg="white", bg="#000000").pack(anchor="w")
        tk.Label(header_frame, textvariable=self.balance_var, font=("Helvetica", 36, "bold"), fg="white", bg="#000000").pack(anchor="w", pady=5)
        self.today_label = tk.Label(header_frame, textvariable=self.today_var, font=("Helvetica", 12, "bold"), fg="#FF3B30", bg="#000000")
        self.today_label.pack(anchor="w")
        
        # Buying Power 
        bp_frame = tk.Frame(self, bg="#000000")
        bp_frame.pack(fill="x", padx=20, pady=(10, 0))
        tk.Label(bp_frame, text="Buying power", font=("Helvetica", 12), fg="white", bg="#000000").pack(side="left")
        tk.Label(bp_frame, text="Unlimited STGM >", font=("Helvetica", 12), fg="#8e8e93", bg="#000000").pack(side="right")
        
        # Divider
        tk.Frame(self, bg="#222222", height=1).pack(fill="x", padx=20, pady=10)
        
        # Swimmer Fleet Label (Crypto section equivalent)
        tk.Label(self, text="Swimmers Fleet >", font=("Helvetica", 20, "bold"), fg="white", bg="#000000").pack(anchor="w", padx=20, pady=(10, 10))
        tk.Label(self, text="Offered by SIFTA Neural Network ⓘ", font=("Helvetica", 10), fg="#8e8e93", bg="#000000").pack(anchor="w", padx=20, pady=(0, 10))
        
        # List Frame (Scrollable theoretically, using frame for simplicity in desktop view)
        self.list_frame = tk.Frame(self, bg="#000000")
        self.list_frame.pack(fill="both", expand=True, padx=20)
        
        self.bounties = []
        self.agents = []
        
        self.refresh_data()
        
        # Auto refresh
        self.running = True
        threading.Thread(target=self.poll_loop, daemon=True).start()
        
    def poll_loop(self):
        while self.running:
            time.sleep(3)
            self.refresh_data()
            
    def refresh_data(self):
        try:
            agent_res = requests.get(f"{API_BASE}/agents?show_detectives=true", timeout=5).json()
            market_res = requests.get(f"{API_BASE}/wormhole_market", timeout=5).json()
            
            self.agents = agent_res
            self.bounties = market_res
            
            self.after(0, self.render_fleet)
        except Exception as e:
            # Silently ignore connection drops to avoid spamming the UI
            pass
            
    def render_fleet(self):
        # Clear existing
        for widget in self.list_frame.winfo_children():
            widget.destroy()
            
        total_balance = sum(float(a.get("stgm_balance", 0)) for a in self.agents)
        self.balance_var.set(f"${total_balance:,.2f}")
        
        # Calculate crude metric for daily today
        if total_balance > 0:
            self.today_var.set(f"▲ +$15.00 (Syncing%) Today")
            self.today_label.config(fg="#00C805")
        
        for agent in self.agents:
            agent_id = agent.get("id")
            nrg = agent.get("energy", 0)
            
            # Find active bounty for this agent
            job = next((b for b in self.bounties if b.get("source") == agent_id), None)
            
            # Create Row Frame
            row = tk.Frame(self.list_frame, bg="#000000")
            row.pack(fill="x", pady=15)
            
            # Left: Name & Energy
            info_frame = tk.Frame(row, bg="#000000")
            info_frame.grid(row=0, column=0, sticky="w")
            tk.Label(info_frame, text=agent_id, font=("Helvetica", 14, "bold"), fg="white", bg="#000000").pack(anchor="w")
            
            # Subtext (Energy)
            nrg_txt = f"{nrg} Energy" if nrg else "0 Energy"
            tk.Label(info_frame, text=nrg_txt, font=("Helvetica", 10), fg="#8e8e93", bg="#000000").pack(anchor="w")
            
            # Divider
            row.grid_columnconfigure(1, weight=1)
            
            # Fake sparkline graphic using label ASCII since it's simple tkinter, or just keep spacing clean
            tk.Label(row, text="〰️〰️〰️", fg="#FF3B30" if job else "#00C805", bg="#000000", font=("Courier", 10)).grid(row=0, column=1)
            
            # Right: Button Frame (Red or Green)
            btn_frame = tk.Frame(row, bg="#000000")
            btn_frame.grid(row=0, column=2, sticky="e")
            
            if job:
                # RED BUTTON (Job exists)
                # User Robinhood screenshot displays negative bounds -1,604.90 for red
                raw_reward = job.get("reward", "+15.0 STGM").replace("+", "").replace(" STGM", "").strip()
                reward_text = f"-${raw_reward}" 
                
                # In macOS Tkinter, we use highlighting or frames to color buttons natively
                red_bg = "#FF3B30"
                btn = tk.Button(btn_frame, text=reward_text, fg="black", highlightbackground=red_bg, font=("Helvetica", 12, "bold"), width=10,
                                command=lambda j=job: self.execute_job(j))
                # For cross-platform coloring:
                btn.config(bg=red_bg)
                btn.pack(pady=5)
            else:
                # PASSIVE IDLE STATE (No button)
                tk.Label(btn_frame, text="IDLE", font=("Helvetica", 12, "bold"), fg="#8e8e93", bg="#000000").pack(pady=5)
                
            tk.Frame(self.list_frame, bg="#111111", height=1).pack(fill="x", pady=2)
                
    def execute_job(self, job):
        target = job.get("source")
        # The physical extraction
        payload = f"INITIATE TRADE PROTOCOL: Acknowledging {target} order. Physical Defag executing on {job.get('file')}."
        self.transmit(target, payload, success_msg="Inference sold to M1! Cryptocurrency generated and physical job executed.")
        
    def dispatch_custom(self, agent_id):
        # Open simple Python text box asking for instruction
        instruction = simpledialog.askstring("Dispatch Worker", f"Agent {agent_id} is idle.\n\nEnter physical text prompt to send anywhere:\n(e.g., browse to file, audit code)", parent=self)
        if instruction:
            self.transmit(agent_id, f"CUSTOM DIRECTIVE: {instruction}", success_msg=f"Worker {agent_id} has been dispatched!")
            
    def transmit(self, target, payload, success_msg=""):
        try:
            resp = requests.post(f"{API_BASE}/swarm_communique", json={"target_node": target, "message": payload}, timeout=5)
            data = resp.json()
            if resp.status_code == 200 and data.get("status") == "success":
                messagebox.showinfo("Order Executed", success_msg)
            else:
                messagebox.showwarning("Order Reject", f"Network block: {data.get('reason', 'Unknown error')}")
            self.refresh_data()
        except Exception as e:
            messagebox.showerror("System Error", f"Offline or Network Failure: {e}")

if __name__ == "__main__":
    app = CouncilRobinhoodApp()
    app.mainloop()
