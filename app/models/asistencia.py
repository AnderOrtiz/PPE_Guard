from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class AsistenciaInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    aula_id: str
    estudiante_id: str
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hora_identificacion: datetime
    cumplio_indumentaria: bool
    faltantes: list[str] = []
    evidencia_url: str | None = None

    model_config = {"populate_by_name": True}