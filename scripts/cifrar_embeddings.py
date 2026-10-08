import asyncio
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.core.cifrado import cifrar_embedding


async def cifrar():
    """Cifra los rostros que quedaron en claro (alumnos registrados antes del cifrado).
    Se puede correr varias veces: los que ya están cifrados no se tocan."""
    client = AsyncMongoClient(
        host=settings.MONGO_HOST,
        port=settings.MONGO_DB_PORT,
        username=settings.MONGO_USERNAME,
        password=settings.MONGO_PASSWORD,
    )
    usuarios = client[settings.MONGO_DB_NAME]["usuarios"]

    cifrados = 0
    async for alumno in usuarios.find({"face_embedding": {"$type": "array"}}, {"face_embedding": 1}):
        await usuarios.update_one(
            {"_id": alumno["_id"]},
            {"$set": {"face_embedding": cifrar_embedding(alumno["face_embedding"])}},
        )
        cifrados += 1

    ya_cifrados = await usuarios.count_documents({"face_embedding": {"$type": "string"}}) - cifrados
    print(f"Rostros cifrados ahora: {cifrados}. Ya estaban cifrados: {ya_cifrados}.")
    await client.close()


if __name__ == "__main__":
    asyncio.run(cifrar())

# python -m scripts.cifrar_embeddings
