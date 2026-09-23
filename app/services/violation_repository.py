from datetime import datetime, timezone
from app.core.database import get_database


async def create_violation(session_id: str, episode_id: str, track_id: int,
                            faltantes: list[str], evidencia_url: str | None):
    database = get_database()
    await database["violations"].insert_one({
        "episode_id": episode_id,
        "session_id": session_id,
        "track_id": track_id,
        "faltantes": faltantes,
        "inicio": datetime.now(timezone.utc),
        "fin": None,
        "estado": "abierto",
        "evidencia_url": evidencia_url,
    })


async def reopen_violation(episode_id: str, faltantes: list[str], evidencia_url: str | None):
    database = get_database()
    await database["violations"].update_one(
        {"episode_id": episode_id},
        {"$set": {
            "fin": None,
            "estado": "abierto",
            "faltantes": faltantes,
            "evidencia_url": evidencia_url,
        }},
    )


async def close_violation(episode_id: str):
    database = get_database()
    await database["violations"].update_one(
        {"episode_id": episode_id},
        {"$set": {"fin": datetime.now(timezone.utc), "estado": "cerrado"}},
    )
    
async def update_violation(episode_id: str, faltantes: list[str]):
    database = get_database()
    await database["violations"].update_one(
        {"episode_id": episode_id},
        {"$set": {"faltantes": faltantes}},
    )