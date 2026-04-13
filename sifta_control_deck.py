#!/usr/bin/env python3
"""
sifta_control_deck.py
=====================
The primary interactive control dashboard for SIFTA.
Built on Textual/Rich. Operates strictly within the Terminal layer,
guaranteeing 0% collision with macOS WindowServer when spawning Physics sims.
"""

import os
import sys
import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Log, ListItem, ListView, Static, Label
from textual import work

class TitleBar(Static):
    """A cool title banner."""
    def compose(self) -> ComposeResult:
        yield Label("🌊 SIFTA × SwarmRL — TERMINAL DECK", id="banner-title")
        yield Label("Architectural Verification Suite", id="banner-subtitle")

class ActionItem(ListItem):
    """A custom styled list item."""
    def __init__(self, title: str, subtitle: str, script_name: str, args: list = None, **kwargs):
        super().__init__(**kwargs)
        self.action_title = title
        self.action_subtitle = subtitle
        self.script_name = script_name
        self.args = args or []

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.action_title, classes="action-title"),
            Label(self.action_subtitle, classes="action-subtitle")
        )

class SIFTAControlDeck(App):
    """The main terminal application."""
    
    CSS = """
    Screen {
        background: #050508;
    }
    
    #banner-title {
        color: #c084fc;
        text-style: bold;
        padding: 1 2 0 2;
    }
    
    #banner-subtitle {
        color: #64748b;
        padding: 0 2 1 2;
        border-bottom: hkey #1e1e30;
    }
    
    #left-panel {
        width: 45;
        border-right: vkey #1e1e30;
        background: #08080f;
    }
    
    #right-panel {
        width: 1fr;
        padding: 1 2;
        background: #030305;
    }
    
    ListView {
        background: transparent;
        padding: 1;
    }
    
    ActionItem {
        padding: 1;
        margin: 0 0 1 0;
        border: round #1e1e30;
        background: #11111a;
    }
    
    ActionItem:focus {
        background: #1a1a2e;
        border: round #c084fc;
    }
    
    .action-title {
        color: #e2e8f0;
        text-style: bold;
    }
    
    .action-subtitle {
        color: #64748b;
    }
    
    Log {
        border: round #1a1a2e;
        background: black;
        color: #94a3b8;
    }
    
    #console-header {
        color: #60a5fa;
        text-style: bold;
        margin-bottom: 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit System"),
        ("k", "kill_process", "Halt Execution")
    ]
    
    def __init__(self):
        super().__init__()
        self.active_process = None

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            with Vertical(id="left-panel"):
                yield TitleBar()
                yield ListView(
                    ActionItem(
                        "1. 'Without a Thought'", 
                        "Colloid Physics Simulation",
                        "trigger",  # We handle this specifically 
                        []
                    ),
                    ActionItem(
                        "2. Cryptographic Lattice", 
                        "SwarmRL Consensus Merge",
                        "test_bridge_consensus.py"
                    ),
                    ActionItem(
                        "3. Proof of Swimming", 
                        "Portable Hardware Identity",
                        "test_proof_of_swimming.py"
                    ),
                    ActionItem(
                        "4. Jellyfish Trigger", 
                        "Autonomic Panic Mode",
                        "test_jellyfish_trigger.py"
                    ),
                    id="action-list"
                )
            with Vertical(id="right-panel"):
                yield Label("TERMINAL OUTPUT STREAM", id="console-header")
                yield Log(id="console", highlight=True)
                
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected):
        item = event.item
        if isinstance(item, ActionItem):
            self.run_task(item.script_name, item.args, item.action_title)

    def write_log(self, text: str):
        log_widget = self.query_one(Log)
        log_widget.write(text)

    def action_kill_process(self):
        if self.active_process is not None:
            self.write_log("[bold red]>>> SENDING SIGTERM TO ACTIVE PROCESS...[/]")
            self.active_process.terminate()
            self.active_process = None

    @work(exclusive=True, thread=True)
    def run_task(self, script_name: str, args: list, title: str):
        """Runs the script in a background thread and streams output."""
        if self.active_process is not None:
            self.app.call_from_thread(self.write_log, "[bold yellow]>>> A PROCESS IS ALREADY RUNNING. PRESS 'K' TO HALT.[/]")
            return

        self.app.call_from_thread(self.write_log, f"\n[bold magenta]=== {title} ===[/]")
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        python_path = os.path.join(os.getcwd(), ".venv", "bin", "python")
        if not os.path.exists(python_path):
            python_path = "python3"
            
        import subprocess
        
        if script_name == "trigger":
            # Special case for the Colloid sim
            self.app.call_from_thread(self.write_log, "[cyan]Spawning Colloid Simulation Window (Detached)...[/]")
            subprocess.Popen([python_path, "sifta_colloid_sim.py", "--target", "bureau_of_identity/test_target.py"], env=env)
            
            self.app.call_from_thread(self.write_log, "[cyan]Firing Stigmergic Trigger Engine...[/]\n")
            cmd = [python_path, "trigger_inference.py"]
        else:
            self.app.call_from_thread(self.write_log, f"[cyan]Executing: {script_name}[/]\n")
            cmd = [python_path, script_name] + args

        self.active_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )

        try:
            for line in iter(self.active_process.stdout.readline, ''):
                if line:
                    self.app.call_from_thread(self.write_log, line.strip())
        except Exception as e:
            self.app.call_from_thread(self.write_log, f"[bold red]Exception reading output: {e}[/]")
            
        self.active_process.wait()
        
        exit_code = self.active_process.returncode
        if exit_code == 0:
            self.app.call_from_thread(self.write_log, "\n[bold green]=== EXECUTION COMPLETED SECURELY ===[/]")
        elif exit_code == -15:  # SIGTERM
            self.app.call_from_thread(self.write_log, "\n[bold red]=== EXECUTION HALTED BY USER ===[/]")
        else:
            self.app.call_from_thread(self.write_log, f"\n[bold red]=== EXECUTION TERMINATED WITH CODE {exit_code} ===[/]")
            
        self.active_process = None


if __name__ == "__main__":
    app = SIFTAControlDeck()
    app.run()
