from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websockets.manager import manager

router = APIRouter()


@router.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # no esperamos nada del cliente; solo mantiene viva la conexión
    except WebSocketDisconnect:
        await manager.disconnect(websocket)