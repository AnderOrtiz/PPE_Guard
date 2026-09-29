from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from app.models.common import PyObjectId


class MateriaCreate(BaseModel):
    nombre: str
    area: Literal["civil", "medicina"]
    carrera: str
    facultad: str
    aula: str
    docente_id: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nombre": "Cálculo II",
                    "area": "civil",
                    "carrera": "Ingeniería Civil",
                    "facultad": "Ingenieria",
                    "aula": "Edificio B - Aula 204",
                    "docente_id": "6abaaf8708ac6806607fb904",
                }
            ]
        }
    )


class MateriaInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    nombre: str
    area: Literal["civil", "medicina"]
    carrera: str
    facultad: str
    aula: str
    docente_id: str
    coordinador_id: str
    alumnos_ids: list[str] = []

    model_config = {"populate_by_name": True}