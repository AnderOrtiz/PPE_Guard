import asyncio
import sys

import websockets


async def main(token: str):
    uri = f"ws://localhost:8000/ws/detections?token={token}"
    async with websockets.connect(uri) as ws:
        print("Conectado. Esperando eventos...")
        async for message in ws:
            print(message)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m scripts.test_ws_client <access_token de docente, coordinador o admin>")
    asyncio.run(main(sys.argv[1]))


# python -m scripts.test_ws_client <access_token>
