from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class PracticaInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    materia_id: str
    docente_id: str
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hora_inicio: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hora_fin: datetime | None = None
    estado: Literal["activa", "finalizada"] = "activa"

    model_config = {"populate_by_name": True}