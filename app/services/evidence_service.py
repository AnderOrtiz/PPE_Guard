import os
from datetime import datetime, timezone

import cv2
import numpy as np

EVIDENCE_DIR = "static/evidence"


def save_evidence(frame: np.ndarray, bbox, faltantes: list[str], episode_id: str) -> str:
    evidence = frame.copy()
    x1, y1, x2, y2 = map(int, bbox)

    cv2.rectangle(evidence, (x1, y1), (x2, y2), (0, 0, 255), 2)

    texto = f"Falta: {', '.join(faltantes)}"
    (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    label_y = max(y1, th + 10)
    cv2.rectangle(evidence, (x1, label_y - th - 10), (x1 + tw + 6, label_y), (0, 0, 255), -1)
    cv2.putText(evidence, texto, (x1 + 3, label_y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = f"{EVIDENCE_DIR}/{today}"
    os.makedirs(folder, exist_ok=True)

    filepath = f"{folder}/{episode_id}.jpg"
    cv2.imwrite(filepath, evidence)

    return f"/{filepath}"