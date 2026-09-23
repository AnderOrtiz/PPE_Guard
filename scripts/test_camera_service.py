import time
from app.services.camera_service import camera_service

camera_service.start()

time.sleep(1)  # dale tiempo al hilo de capturar al menos un par de frames

frame = camera_service.get_latest_frame()
if frame is None:
    print("Todavía no hay frame disponible")
else:
    print("Frame shape:", frame.shape)

camera_service.stop()

# python -m scripts.test_camera_service