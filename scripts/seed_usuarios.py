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

    await db["usuarios"].insert_many([
        {
            "username": "coordinador1",
            "password_hash": hash_password("cambiar123"),
            "rol": "coordinador",
            "nombre": "Coordinador Demo",
        },
        {
            "username": "docente1",
            "password_hash": hash_password("cambiar123"),
            "rol": "docente",
            "nombre": "Docente Demo",
        },
        # {
        #     "username": "ander-ortiz",
        #     "password_hash": hash_password("2212"),
        #     "rol": "alumno",
        #     "nombre": "Docente Demo",
        # },
    ])

    print("Usuarios de prueba insertados.")
    await client.close()


if __name__ == "__main__":
    asyncio.run(seed())


# python -m scripts.seed_usuarios

# POST /api/v1/auth/login
