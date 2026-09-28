import asyncio
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.core.security import hash_password


async def seed():
    client = AsyncMongoClient(
        host=settings.MONGO_HOST,
        port=settings.MONGO_DB_PORT,
        username=settings.MONGO_USERNAME,
        password=settings.MONGO_PASSWORD,
    )
    db = client[settings.MONGO_DB_NAME]

    existentes = await db["usuarios"].count_documents({})
    if existentes > 0:
        print(f"Ya hay {existentes} usuarios. No se insertó nada.")
        await client.close()
        return

    coordinador = await db["usuarios"].insert_one({
        "codigo": "COORD001",
        "password_hash": hash_password("cambiar123"),
        "rol": "coordinador",
        "nombre": "Coordinador Demo",
    })

    await db["usuarios"].insert_many([
        {
            "codigo": "ADMIN001",
            "password_hash": hash_password("cambiar123"),
            "rol": "admin",
            "nombre": "Admin Demo",
        },
        {
            "codigo": "DOC001",
            "password_hash": hash_password("cambiar123"),
            "rol": "docente",
            "nombre": "Docente Demo",
            "facultad": "Ingeniería",
            "coordinador_id": str(coordinador.inserted_id),
        },
    ])

    print("Usuarios de prueba insertados: ADMIN001, COORD001, DOC001 (contraseña: cambiar123)")
    await client.close()


if __name__ == "__main__":
    asyncio.run(seed())