import asyncio
import websockets
import json

connected_clients = set()

async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            for client in connected_clients:
                if client != websocket:
                    try:
                        await client.send(message)
                    except websockets.exceptions.ConnectionClosed:
                        pass
    finally:
        connected_clients.remove(websocket)

async def main():
    print("M1 Swarm Relay starting on port 8765...")
    async with websockets.serve(handler, "0.0.0.0", 8765): # bind to all interfaces
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
