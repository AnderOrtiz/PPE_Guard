from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class ViolationInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    episode_id: str
    session_id: str
    track_id: int
    faltantes: list[str]
    inicio: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fin: datetime | None = None
    estado: str = "abierto"  # "abierto" | "cerrado"
    evidencia_url: str | None = None

    model_config = {"populate_by_name": True}