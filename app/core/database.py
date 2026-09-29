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
    await db.client.admin.command("ping")

    database = db.client[settings.MONGO_DB_NAME]
    await database["usuarios"].create_index("codigo", unique=True)
    await database["materias"].create_index("docente_id")
    await database["materias"].create_index("coordinador_id")
    await database["practicas"].create_index("materia_id")
    await database["asistencias"].create_index("practica_id")
    await database["asistencias"].create_index("alumno_id")


async def close_mongo_connection():
    if db.client is not None:
        await db.client.close()


def get_database():
    return db.client[settings.MONGO_DB_NAME]
