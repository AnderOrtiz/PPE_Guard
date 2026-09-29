from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class AsistenciaInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    practica_id: str
    alumno_id: str
    hora_identificacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cumplio_indumentaria: bool
    faltantes: list[str] = []
    evidencia_url: str | None = None

    model_config = {"populate_by_name": True}