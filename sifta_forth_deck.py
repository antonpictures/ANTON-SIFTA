"""
SIFTA Bare-Iron Forth OS Deck
"""
import asyncio
import json
import time
from textual.app import App, ComposeResult
from textual.containers import Grid, Container
from textual.widgets import Header, Footer, Static, Input, Log
from textual.reactive import reactive

from sifta_forth_parser import SiftaForthParser

class HexMap(Static):
    """A highly stylized, static bare-metal memory dump."""
    def on_mount(self):
        self.styles.border = ("solid", "green")
        self.styles.color = "green"
        self.update(
            "MEMORY MAP / ALLOCATION\n"
            "0000: B0 A1 CC | 0100: FF 00 E3\n"
            "0010: DB D0 A0 | 0110: FF 00 EA\n"
            "0020: B0 A1 C6 | 0120: FF 00 E3\n"
            "0030: 7F F0 BC | 0130: FF 00 EA\n"
            "[STATIC]       | 0140: FF 00 E3\n"
            "0040: B0 A1 CC | 0150: AB FF 0A\n"
            "0050: FF 00 E3 | [HEAP]\n"
            "0060: B0 00 E6 | 0160: FF 00 EA\n"
            "0070: B0 00 E6 | 0170: FF 00 EA\n"
            "0080: B0 00 E6 | 0180: FF 00 EA\n"
            "0090: B0 00 E6 | 0190: FF 00 EA\n"
            "00A0: B0 00 E6 | 01A0: FF 00 EA\n"
            "00B0: B0 00 E6 | 01B0: FF 00 EA\n"
        )

class HardwareMonitor(Static):
    """Raw architecture monitor."""
    def on_mount(self):
        self.styles.border = ("solid", "green")
        self.styles.color = "green"
        self.update(
            "HARDWARE MONITOR / THERMAL\n"
            "CPU 0: 45C [###...............]\n"
            "GPU  : 52C [####..............]\n"
            "NPU  : 61C [######............]\n"
            "DRIVE: 38C [##................]\n"
            "------------------------------\n"
            "EAX: 0x00A3BF | EBX: 0x004000\n"
            "ECX: 0x0001FF | EDX: 0x000020\n"
        )

class SwarmDebugLog(Log):
    """Continuous dmesg-style tail of Swarm actions."""
    def on_mount(self):
        self.styles.border = ("solid", "green")
        self.styles.color = "green"
        self.write_line(f"[{time.strftime('%H:%M:%S')}] swarmlattice: booting up")
        self.write_line(f"[{time.strftime('%H:%M:%S')}] node: bound hardware identity")
        self.write_line(f"[{time.strftime('%H:%M:%S')}] NPU: loading FP8 dynamic weights... SKIP")
        self.write_line(f"[{time.strftime('%H:%M:%S')}] INIT: waiting for input...")

class ForthPrompt(Input):
    """RPN Command Prompt"""
    def on_mount(self):
        self.styles.border = ("solid", "green")
        self.styles.color = "green"

class SiftaForthDeck(App):
    CSS = """
    Screen {
        background: black;
        color: lime;
        layout: grid;
        grid-size: 2 3;
        grid-rows: 1fr 1fr 10fr;
        grid-columns: 1fr 2fr;
    }
    
    #hex_map {
        row-span: 2;
    }
    
    #prompt {
        column-span: 2;
        border: solid green;
    }
    """

    BINDINGS = [
        ("q", "quit", "Halt Execution")
    ]

    def __init__(self):
        super().__init__()
        self.parser = SiftaForthParser()
        self.scar_task = None

    def compose(self) -> ComposeResult:
        yield HexMap(id="hex_map")
        yield HardwareMonitor(id="hw_monitor")
        yield SwarmDebugLog(id="debug_log")
        yield ForthPrompt(placeholder="> ", id="prompt")
        yield Footer()

    async def on_mount(self):
        self.query_one("#prompt").focus()
        self.query_one("#prompt").border_title = "[ 0x7FFF | 0x00FF | FORTH OS ]"
        
        # Start background task to tail repair_log.jsonl
        self.scar_task = asyncio.create_task(self.tail_repair_log())

    async def tail_repair_log(self):
        log_widget = self.query_one("#debug_log")
        try:
            with open("repair_log.jsonl", "r") as f:
                # Seek to end
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        continue
                    try:
                        data = json.loads(line)
                        agent = data.get("agent", "SYS")
                        event = data.get("event", "EVENT")
                        
                        # Handle STGM mining events nicely
                        if "amount_stgm" in data:
                            stgm = data.get("amount_stgm")
                            reason = data.get("reason", "")
                            log_widget.write_line(f"[{time.strftime('%H:%M:%S')}] [LEDGER] {agent} minted {stgm} STGM. ({reason})")
                        else:
                            log_widget.write_line(f"[{time.strftime('%H:%M:%S')}] [{agent}] -> {event}")
                    except Exception:
                        pass
        except FileNotFoundError:
            log_widget.write_line(f"[{time.strftime('%H:%M:%S')}] [!] repair_log.jsonl not found.")

    async def on_input_submitted(self, message: Input.Submitted):
        command = message.value
        if not command.strip():
            return
            
        self.query_one("#prompt").value = ""
        log_widget = self.query_one("#debug_log")
        
        log_widget.write_line(f"> {command}")
        
        response = self.parser.evaluate(command)
        if response:
            log_widget.write_line(response)

if __name__ == "__main__":
    app = SiftaForthDeck()
    app.run()
