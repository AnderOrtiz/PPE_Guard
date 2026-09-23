from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class SessionCreate(BaseModel):
    """Lo que llega desde el formulario 'Agregar práctica' del frontend."""
    area: str
    docente: str
    carrera: str


class SessionInDB(SessionCreate):
    id: PyObjectId = Field(alias="_id")
    inicio: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fin: datetime | None = None
    estado: str = "activa"  # "activa" | "finalizada"

    model_config = {"populate_by_name": True}