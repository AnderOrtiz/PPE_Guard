import time
import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.camera_service import camera_service

router = APIRouter()


def _generate_mjpeg():
    while True:
        frame = camera_service.get_latest_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue

        chunk = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + chunk + b"\r\n"
        )


@router.get("/stream")
def video_stream():
    return StreamingResponse(
        _generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )