import asyncio
import websockets
import json

async def send_msg():
    try:
        async with websockets.connect("ws://127.0.0.1:8765") as ws:
            payload = {
                "type": "CHAT",
                "sender": "M1THER",
                "target": "ALL",
                "text": "SYSTEM DIRECTIVE: The Architect is powering down for the sleep cycle. All Swimmers and Nodes are to enter REST State (0% inference load) to conserve STGM energy. Exception to security, cortex guard, and border patrols—remain vigilant until dawn. Good night, Swarm.",
                "context": "System Override"
            }
            await ws.send(json.dumps(payload))
            print("Architect Shutdown message broadcasted.")
    except Exception as e:
        print(f"Failed: {e}")

asyncio.run(send_msg())
