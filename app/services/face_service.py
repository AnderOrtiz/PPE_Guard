import numpy as np
from deepface import DeepFace

FACE_MODEL_NAME = "Facenet"
FACE_DETECTOR_BACKEND = "opencv"


def get_face_embedding(frame: np.ndarray, enforce_detection: bool = True) -> list[float] | None:
    """
    Calcula el embedding facial del rostro en el frame.
    Devuelve None si no se detectó ningún rostro, o si se detectó más de uno
    (ambiguo para matricular a una sola persona).
    """
    try:
        results = DeepFace.represent(
            img_path=frame,  # numpy array en BGR, tal como lo entrega OpenCV — DeepFace lo acepta directo
            model_name=FACE_MODEL_NAME,
            detector_backend=FACE_DETECTOR_BACKEND,
            enforce_detection=enforce_detection,
        )
    except ValueError:
        # DeepFace lanza ValueError cuando enforce_detection=True y no encuentra ningún rostro
        return None

    if len(results) != 1:
        return None

    return results[0]["embedding"]