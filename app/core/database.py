from pymongo import AsyncMongoClient
from app.core.config import settings


class MongoDB:
    client: AsyncMongoClient | None = None


db = MongoDB()


async def connect_to_mongo():
    db.client = AsyncMongoClient(
        host=settings.MONGO_HOST,
        port=settings.MONGO_DB_PORT,
        username=settings.MONGO_USERNAME,
        password=settings.MONGO_PASSWORD,
    )
    # Fuerza una conexión real para detectar errores al arrancar, no en el primer request
    await db.client.admin.command("ping")

    database = db.client[settings.MONGO_DB_NAME]
    await database["sessions"].create_index("inicio")
    await database["violations"].create_index("session_id")
    await database["violations"].create_index("inicio")
    await database["asistencias"].create_index("aula_id")
    await database["asistencias"].create_index("estudiante_id")
    await database["asistencias"].create_index("fecha")
    await database["usuarios"].create_index("codigo", unique=True)


async def close_mongo_connection():
    if db.client is not None:
        await db.client.close()


def get_database():
    return db.client[settings.MONGO_DB_NAME]
