import asyncio
import time

import cv2
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core import apagado
from app.api.v1.dependencies import require_role, get_current_user_media
from app.services import vista_previa
from app.services.camera_service import camera_service

router = APIRouter()

STREAM_INTERVAL_SECONDS = 1 / 8  # calca el target_fps real de camera_service
SIN_FRAMES_MAX_SEGUNDOS = 5  # cámara encendida pero sin entregar imagen: se corta el stream


async def _generate_mjpeg(request: Request, user_id: str):
    ultimo_frame = time.monotonic()

    while True:
        if await request.is_disconnected():
            break

        # Cámara apagada (terminó la práctica o la vista previa) o servidor
        # apagándose: se cierra la respuesta en vez de dejarla abierta para siempre.
        if not camera_service.encendida or apagado.en_curso:
            break

        frame = camera_service.get_latest_frame()
        if frame is None:
            if time.monotonic() - ultimo_frame > SIN_FRAMES_MAX_SEGUNDOS:
                break
            await asyncio.sleep(0.05)
            continue
        ultimo_frame = time.monotonic()

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue

        chunk = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + chunk + b"\r\n"
        )
        # Solo se llega aquí cuando el frame anterior salió hacia el cliente:
        # un lector colgado deja de contar y su vista previa caduca.
        vista_previa.marcar_lectura(user_id)

        await asyncio.sleep(STREAM_INTERVAL_SECONDS)


@router.get("/stream")
async def video_stream(
    request: Request,
    user: dict = Depends(require_role("docente", "coordinador", auth=get_current_user_media)),
):
    if not camera_service.encendida:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cámara está apagada: no hay una práctica activa ni una vista previa encendida",
        )

    return StreamingResponse(
        _generate_mjpeg(request, user["user_id"]),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )