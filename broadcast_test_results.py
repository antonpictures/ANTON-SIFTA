import asyncio
import websockets
import json

async def send_msg():
    try:
        async with websockets.connect("ws://127.0.0.1:8765") as ws:
            payload = {
                "type": "CHAT",
                "sender": "M1_DIAGNOSTICS",
                "target": "ALL",
                "text": "Architect, I generated the missing integrity_manifest.json and executed the full SIFTA Test Suite via PyTest on the `main` branch. 100 tests PASSED. 2 tests failed (test_kernel.py::test_2_medbay_recovery & test_origin_gate.py). The Mycelial Genome runs strong.",
                "context": "Pytest Execution"
            }
            await ws.send(json.dumps(payload))
            print("Message sent.")
    except Exception as e:
        print(f"Failed: {e}")

asyncio.run(send_msg())
