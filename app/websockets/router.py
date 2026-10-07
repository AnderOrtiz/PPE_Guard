import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.api.v1.dependencies import user_from_token, tiene_rol
from app.services import practica_registry
from app.websockets.manager import manager

router = APIRouter()


def _estado_inicial() -> dict:
    orquestador = practica_registry.orquestador_activo()
    estado = orquestador.estado_actual() if orquestador is not None else {
        "practica_id": None,
        "fase": None,
        "identificado": None,
        "alumno_id": None,
        "segundos_restantes": None,
    }
    return {"evento": "estado_inicial", **estado, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    # El navegador no puede mandar headers en un WebSocket: el token va como ?token=
    try:
        user = user_from_token(websocket.query_params.get("token", ""))
    except HTTPException:
        user = None
    if user is None or not tiene_rol(user, "docente", "coordinador"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps(_estado_inicial()))
        while True:
            await websocket.receive_text()  # no esperamos nada del cliente; solo mantiene viva la conexión
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
