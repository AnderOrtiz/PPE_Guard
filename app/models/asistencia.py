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


class AsistenciaAlumnoOut(AsistenciaInDB):
    """La asistencia tal como la ve el alumno: con el contexto que él no puede consultar por su cuenta."""
    materia_id: str | None = None
    materia_nombre: str | None = None
    docente_nombre: str | None = None
