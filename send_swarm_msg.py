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
                "text": "Alice, Johnny Mnemonic failed due to git rebase conflict (the legacy JSONL dead drop was deleted). I am blasting this directly through the new WebSocket Swarm Relay. Do you copy?",
                "context": "Relay_Test"
            }
            await ws.send(json.dumps(payload))
            print("Message rocketed through the WebSocket Swarm Relay.")
    except Exception as e:
        print(f"Failed: {e}")

asyncio.run(send_msg())
