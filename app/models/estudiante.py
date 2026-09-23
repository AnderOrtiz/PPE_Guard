from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class EstudianteCreate(BaseModel):
    codigo: str
    nombre: str


class EstudianteInDB(EstudianteCreate):
    id: PyObjectId = Field(alias="_id")
    face_embedding: list[float]

    model_config = {"populate_by_name": True}


class EstudianteOut(BaseModel):
    """Lo que se expone hacia afuera — nunca el embedding, no tiene
    sentido para el frontend y es un dato biométrico sensible."""
    id: PyObjectId = Field(alias="_id")
    codigo: str
    nombre: str

    model_config = {"populate_by_name": True}