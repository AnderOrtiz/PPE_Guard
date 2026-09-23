import asyncio
import threading
import time

import cv2

from app.core.database import connect_to_mongo, close_mongo_connection
from app.core import async_bridge
from app.services.camera_service import camera_service
from app.services.detection_orchestrator import DetectionOrchestrator


def _run_event_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    async_bridge.set_main_loop(loop)
    loop.run_until_complete(connect_to_mongo())
    loop.run_forever()


# --- Arrancar un loop de asyncio en su propio hilo, solo para Mongo/WebSocket ---
loop = asyncio.new_event_loop()
loop_thread = threading.Thread(target=_run_event_loop, args=(loop,), daemon=True)
loop_thread.start()

time.sleep(1)  # dale un momento a que Mongo termine de conectar

orchestrator = DetectionOrchestrator(
    session_id="test-session-001",
    area="civil",
    required_ppe={"Hardhat", "Safety Vest"},
)
orchestrator.start()

VIOLATION_PREFIX = "NO-"

try:
    while True:
        frame = camera_service.get_latest_frame()

        if frame is not None:
            display_frame = frame.copy()
            detections = orchestrator.get_latest_detections()

            for det in detections:
                x1, y1, x2, y2 = map(int, det["bbox"])
                is_violation = det["class_name"].startswith(VIOLATION_PREFIX)
                color = (0, 0, 255) if is_violation else (0, 200, 0)

                label = f'{det["class_name"]} #{det["track_id"]}'
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(display_frame, label, (x1, max(y1 - 8, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            cv2.imshow("PPE_Guard - vista de depuración", display_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    orchestrator.stop()
    cv2.destroyAllWindows()
    asyncio.run_coroutine_threadsafe(close_mongo_connection(), loop)
    loop.call_soon_threadsafe(loop.stop)

# python -m scripts.test_orchestrator_view