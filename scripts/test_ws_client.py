import asyncio
import websockets


async def main():
    uri = "ws://localhost:8000/ws/detections"
    async with websockets.connect(uri) as ws:
        print("Conectado. Esperando eventos...")
        async for message in ws:
            print(message)


if __name__ == "__main__":
    asyncio.run(main())


# python -m scripts.test_ws_client
