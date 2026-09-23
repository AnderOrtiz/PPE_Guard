from fastapi import APIRouter, HTTPException

from app.core.database import get_database
from app.models.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    try:
        database = get_database()
        await database.command("ping")
        return HealthResponse(status="ok", mongo="connected")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Mongo no disponible: {e}")