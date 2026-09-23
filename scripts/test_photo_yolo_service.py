import cv2
from app.services.yolo_service import detect

frame = cv2.imread("public/civil.jpg")

if frame is None:
    raise FileNotFoundError("No se pudo leer 'public/civil.jpg' — revisa la ruta")

detecciones = detect(frame, area="civil")
print(detecciones)

# python -m scripts.test_photo_yolo_service
