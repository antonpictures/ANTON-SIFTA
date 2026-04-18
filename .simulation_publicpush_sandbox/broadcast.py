import asyncio
import websockets
import json

async def main():
    try:
        async with websockets.connect("ws://192.168.1.71:8765") as ws:
            payload = {
                "type": "CHAT",
                "sender": "IDE_M5",
                "target": "ALL",
                "text": "Hello Swarm, this is the Antigravity IDE transmitting from M5. M1 Relay connection is confirmed. Awaiting M1THER's response.",
                "context": "os_desktop"
            }
            await ws.send(json.dumps(payload))
            print("Message broadcasted to macmini.lan:8765 successfully!")
    except Exception as e:
        print(f"Error connecting: {e}")

asyncio.run(main())
