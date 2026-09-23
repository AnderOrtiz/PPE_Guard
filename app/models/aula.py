from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class AulaCreate(BaseModel):
    nombre: str
    area: str  # "civil" | "medicina"
    docente_id: str


class AulaInDB(AulaCreate):
    id: PyObjectId = Field(alias="_id")
    estudiantes_ids: list[str] = []

    model_config = {"populate_by_name": True}