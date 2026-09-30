import numpy as np
from deepface import DeepFace
from bson import ObjectId

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


SIMILARITY_THRESHOLD = 0.60  # equivalente al umbral oficial de DeepFace para Facenet + coseno


def find_best_match(embedding: list[float], candidates: list[dict]) -> dict | None:
    """
    candidates: documentos de estudiantes, cada uno con su 'face_embedding'.
    Devuelve el candidato con mayor similitud si supera el umbral (con la
    similitud agregada bajo 'similarity'), o None si nadie califica.
    """
    if not candidates:
        return None

    query = np.array(embedding)
    best_candidate = None
    best_similarity = -1.0

    for candidate in candidates:
        known_vec = np.array(candidate["face_embedding"])
        similarity = _cosine_similarity(query, known_vec)
        if similarity > best_similarity:
            best_similarity = similarity
            best_candidate = candidate

    if best_similarity >= SIMILARITY_THRESHOLD:
        return {**best_candidate, "similarity": best_similarity}

    return None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def get_candidatos_de_materia(database, materia_id: str) -> list[dict]:
    """
    Devuelve los documentos de alumno (con su face_embedding) matriculados
    en una materia específica — nunca todos los alumnos del sistema.
    """
    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    if materia is None or not materia["alumnos_ids"]:
        return []

    ids_validos = [ObjectId(aid) for aid in materia["alumnos_ids"]]
    cursor = database["usuarios"].find({"_id": {"$in": ids_validos}, "rol": "alumno"})
    return [doc async for doc in cursor]