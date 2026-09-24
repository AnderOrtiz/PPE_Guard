import asyncio

from app.core.database import connect_to_mongo, close_mongo_connection, get_database
from app.services.camera_service import capture_single_frame
from app.services.face_service import get_face_embedding, find_best_match


async def main():
    await connect_to_mongo()

    frame = capture_single_frame()
    embedding = get_face_embedding(frame, enforce_detection=False)

    if embedding is None:
        print("No se detectó ningún rostro.")
        await close_mongo_connection()
        return

    database = get_database()
    estudiantes = [doc async for doc in database["estudiantes"].find()]

    match = find_best_match(embedding, estudiantes)

    if match is None:
        print("No se encontró ninguna coincidencia suficientemente confiable.")
    else:
        print(f"Identificado: {match['nombre']} (código {match['codigo']}) — similitud: {match['similarity']:.3f}")

    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())
    
    # python -m scripts.test_identification