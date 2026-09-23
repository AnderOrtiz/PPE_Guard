from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class PracticeCreate(BaseModel):
    """Lo que se envía para crear una práctica en el catálogo."""
    area: str  # "civil" | "medicina"
    nombre: str
    ppe_requerido: list[str]


class PracticeInDB(PracticeCreate):
    """Lo que realmente vive en Mongo (incluye el _id que Mongo genera)."""
    id: PyObjectId = Field(alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}