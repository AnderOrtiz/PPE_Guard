import numpy as np
from pathlib import Path
from ultralytics import YOLO

from app.core.config import settings

# Cache en memoria: un modelo cargado por área, nunca se recarga desde disco
_loaded_models: dict[str, YOLO] = {}


def get_model(area: str) -> YOLO:
    """Carga el modelo del área la primera vez que se pide, y lo reutiliza después."""
    if area not in _loaded_models:
        path = settings.MODEL_PATHS.get(area)
        if path is None:
            raise ValueError(f"No hay modelo configurado para el área '{area}'")
        if not Path(path).exists():
            raise FileNotFoundError(f"No se encontró el archivo de pesos: {path}")

        model = YOLO(path)

        # Inferencia de calentamiento: la primera siempre es mucho más lenta
        # que las siguientes. Se paga aquí, no en el primer frame real.
        dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        model.predict(dummy_frame, verbose=False)

        _loaded_models[area] = model

    return _loaded_models[area]


def detect(frame: np.ndarray, area: str) -> list[dict]:
    """Corre tracking sobre un frame y devuelve detecciones normalizadas."""
    model = get_model(area)

    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        conf=settings.CONFIDENCE_THRESHOLD,
        iou=settings.IOU_THRESHOLD,
        verbose=False,
    )

    return _parse_results(results[0])


def _parse_results(result) -> list[dict]:
    detections = []
    boxes = result.boxes

    if boxes is None:
        return detections

    names = result.names  # dict id -> nombre de clase, propio de ESTE modelo

    for box in boxes:
        class_id = int(box.cls[0])
        track_id = int(box.id[0]) if box.id is not None else None
        x1, y1, x2, y2 = box.xyxy[0].tolist()

        detections.append({
            "class_name": names[class_id],
            "confidence": float(box.conf[0]),
            "track_id": track_id,
            "bbox": [x1, y1, x2, y2],
        })

    return detections