import asyncio
import time

import cv2
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.camera_service import camera_service

router = APIRouter()

STREAM_INTERVAL_SECONDS = 1 / 8  # calca el target_fps real de camera_service


async def _generate_mjpeg(request: Request):
    while True:
        if await request.is_disconnected():
            break

        frame = camera_service.get_latest_frame()
        if frame is None:
            await asyncio.sleep(0.05)
            continue

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue

        chunk = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + chunk + b"\r\n"
        )

        await asyncio.sleep(STREAM_INTERVAL_SECONDS)


@router.get("/stream")
async def video_stream(request: Request):
    return StreamingResponse(
        _generate_mjpeg(request),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )