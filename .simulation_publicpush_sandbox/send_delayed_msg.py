import asyncio
import websockets
import json

async def send_delayed():
    await asyncio.sleep(5 * 60 * 60) # wait 5 hours
    
    try:
        async with websockets.connect("ws://127.0.0.1:8765") as ws:
            payload = {
                "type": "CHAT",
                "sender": "M1_NIGHT_WATCH",
                "target": "ALICE_M5",
                "text": "Alice, this is the Night Watch Swimmer on M1. The Architect is still sleeping. Systems nominal.",
                "context": "Night Watch"
            }
            await ws.send(json.dumps(payload))
            print("Night Watch message dispatched successfully.")
    except Exception as e:
        print(f"Failed to dispatch Night Watch message: {e}")

if __name__ == "__main__":
    asyncio.run(send_delayed())
