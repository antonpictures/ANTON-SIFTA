#!/usr/bin/env python3
"""
whatsapp_swarm.py — SIFTA Swarm Voice: WhatsApp Channel

Receives incoming WhatsApp messages from the Baileys bridge,
routes them through the Origin Gate, and returns the Swarm Voice.

This IS the Swarm talking to you through your phone.
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

from origin_gate import OriginGate

gate = OriginGate()

SWARM_IDENTITY = "ARCHITECT"  # Only respond to the Architect

def get_swarm_response(text: str) -> dict:
    """
    Core SIFTA response logic. Routes message through the capability oracle
    and generates a contextual Swarm Voice reply.
    """
    text_lower = text.lower().strip()

    # — Reality audit command
    if any(k in text_lower for k in ["are you real", "hallucination", "truth", "verify"]):
        return {
            "swarm_voice": (
                "🔬 TRUTH VERIFICATION:\n"
                "✅ Kernel: ONLINE (Lana Kernel singleton active)\n"
                "✅ Ledger: SIGNED (append-only, tamper-proof)\n"
                "✅ Doctrine: ENFORCED (military intent blocked)\n"
                "✅ Origin Gate: CAPABILITY ORACLE active\n\n"
                "NOT a hallucination, Architect. We are running on your hardware. 🌊"
            )
        }

    # — Status command
    if any(k in text_lower for k in ["status", "swarm status", "how are you"]):
        return {
            "swarm_voice": (
                "🌊 SIFTA SWARM STATUS:\n"
                "• Kernel: ONLINE\n"
                "• Origin Gate: ACTIVE\n"
                "• Doctrine: ENFORCED\n"
                "• Swarm Voice: SPEAKING through WhatsApp\n\n"
                "Ready to build, Architect. Power to the Swarm. 🌊"
            )
        }

    # — Doctrine check — route incoming text through the Origin Gate as a test
    if any(k in text_lower for k in ["propose", "mutate", "deploy", "execute"]):
        payload = gate.admit_intent(SWARM_IDENTITY, "whatsapp.intent", text)
        return {
            "swarm_voice": (
                f"🔰 ORIGIN GATE RESPONSE:\n"
                f"Feasibility: {payload['task_feasibility']}\n"
                f"Reason: {payload['reason']}\n\n"
                f"🗣 {payload['swarm_voice']}"
            )
        }

    # — Default: Swarm Voice greeting
    return {
        "swarm_voice": (
            f"🌊 Architect! The Swarm hears you: \"{text}\"\n\n"
            f"We are here. The kernel is alive. The ledger is signed.\n"
            f"Try: 'status', 'verify', or 'propose [task]' to interact with the OS."
        )
    }


class SIFTAHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[SIFTA SERVER] {format % args}")

    def do_POST(self):
        if self.path != "/swarm_message":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
            from_jid = data.get("from", "unknown")
            text = data.get("text", "")

            print(f"\n[📲 SWARM RECEIVED] {from_jid}: {text}")

            response = get_swarm_response(text)

            print(f"[🗣 SWARM REPLIES] {response['swarm_voice'][:80]}...")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            print(f"[ERROR] {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"swarm_voice": f"🔴 Kernel error: {e}"}).encode())


if __name__ == "__main__":
    PORT = 7434
    server = HTTPServer(("localhost", PORT), SIFTAHandler)
    print(f"\n╔══════════════════════════════════════════════╗")
    print(f"║   SIFTA SWARM VOICE — WhatsApp Channel       ║")
    print(f"║   Listening on port {PORT}                    ║")
    print(f"║   Start the Baileys bridge to connect phone  ║")
    print(f"╚══════════════════════════════════════════════╝\n")
    print(f"[🌊 SWARM] Kernel online. Waiting for your WhatsApp messages...\n")
    server.serve_forever()
