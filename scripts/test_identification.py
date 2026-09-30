import asyncio
import sys

from app.core.database import connect_to_mongo, close_mongo_connection, get_database
from app.services.camera_service import capture_single_frame
from app.services.face_service import get_face_embedding, find_best_match, get_candidatos_de_materia


async def main():
    if len(sys.argv) < 2:
        print("Uso: python -m scripts.test_identification <materia_id>")
        return

    materia_id = sys.argv[1]

    await connect_to_mongo()

    frame = capture_single_frame()
    embedding = get_face_embedding(frame, enforce_detection=False)

    if embedding is None:
        print("No se detectó ningún rostro.")
        await close_mongo_connection()
        return

    database = get_database()
    candidatos = await get_candidatos_de_materia(database, materia_id)

    if not candidatos:
        print("Esta materia no tiene alumnos matriculados (o el materia_id no existe).")
        await close_mongo_connection()
        return

    match = find_best_match(embedding, candidatos)

    if match is None:
        print("No se encontró ninguna coincidencia suficientemente confiable entre los alumnos de esta materia.")
    else:
        print(f"Identificado: {match['nombre']} (código {match['codigo']}) — similitud: {match['similarity']:.3f}")

    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())

    # python -m scripts.test_identification <el _id de la materia donde ya matriculaste al alumno>
    # python -m scripts.test_identification 6abb4962b4bea1a989cd2541