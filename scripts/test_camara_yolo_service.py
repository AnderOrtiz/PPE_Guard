import cv2
from app.services.yolo_service import detect

cap = cv2.VideoCapture(0)

# Descarta los primeros frames mientras la cámara ajusta exposición
for _ in range(10):
    cap.read()

ret, frame = cap.read()
cap.release()

if not ret:
    raise RuntimeError("No se pudo capturar un frame de la cámara")

detecciones = detect(frame, area="civil")
print(detecciones)

#python -m scripts.test_camara_yolo_service
