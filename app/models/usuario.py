from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class UsuarioLogin(BaseModel):
    username: str
    password: str


class UsuarioInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    username: str
    password_hash: str
    rol: str  # "alumno" | "docente" | "coordinador"
    nombre: str

    model_config = {"populate_by_name": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str
    nombre: str