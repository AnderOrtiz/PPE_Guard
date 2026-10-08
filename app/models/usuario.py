from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.common import PyObjectId


class UsuarioLogin(BaseModel):
    codigo: str
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "codigo": "COORD001",
                    "password": "cambiar123",
                }
            ]
        }
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str
    nombre: str


class _UsuarioBaseCreate(BaseModel):
    codigo: str
    password: str
    nombre: str


class CoordinadorCreate(_UsuarioBaseCreate):
    pass


class DocenteCreate(_UsuarioBaseCreate):
    facultad: str
    coordinador_id: str | None = None  # solo lo manda el admin; un coordinador crea docentes a su cargo


class AlumnoCreate(_UsuarioBaseCreate):
    # El resto del perfil lo completa el propio alumno después (PATCH /auth/me)
    carrera: str | None = None
    facultad: str | None = None
    materias_ids: list[str] = []  # materias en las que queda matriculado al crearlo


class PerfilUpdate(BaseModel):
    """Lo que cada usuario puede cambiar de sí mismo. El código y el rol no se tocan."""
    nombre: str | None = Field(default=None, min_length=1)
    correo: EmailStr | None = None
    carrera: str | None = None
    facultad: str | None = None
    estatus_academico: str | None = None


class PasswordCambio(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=1)


class PasswordReset(BaseModel):
    password_nueva: str = Field(min_length=1)


class UsuarioOut(BaseModel):
    """Lo que se expone hacia afuera: nunca password_hash ni face_embedding."""
    id: PyObjectId = Field(alias="_id")
    codigo: str
    nombre: str
    rol: str
    correo: str | None = None
    carrera: str | None = None
    estatus_academico: str | None = None
    facultad: str | None = None
    coordinador_id: str | None = None

    model_config = {"populate_by_name": True}

class AlumnoEnMateriaOut(BaseModel):
    id: PyObjectId = Field(alias="_id")
    codigo: str
    nombre: str
    carrera: str | None = None
    facultad: str | None = None

    model_config = {"populate_by_name": True}

"""
    {"codigo": "ADMIN001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJBRE1JTjAwMSIsInVpZCI6IjZhYmFhYzgzZjFiMTYwMDc1MzhiNjdlNiIsInJvbCI6ImFkbWluIiwiZXhwIjoxNzkwNjQ3NzMxfQ.vg43hOjwI6ofG3cRUgJYsLy7RyQielXHKUmKFPNNV5Q

    {"codigo": "COORD001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJDT09SRDAwMSIsInVpZCI6IjZhYmFhYzgyZjFiMTYwMDc1MzhiNjdlNSIsInJvbCI6ImNvb3JkaW5hZG9yIiwiZXhwIjoxNzkwNjQ4MDc2fQ.A5t7iPm9zHUBYB5Xpb9ChLdqcSdCvP-qOqMX6QkGNwo

    {"codigo": "DOC001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJET0MwMDEiLCJ1aWQiOiI2YWJhYWM4M2YxYjE2MDA3NTM4YjY3ZTciLCJyb2wiOiJkb2NlbnRlIiwiZXhwIjoxNzkwNjQ4NDUxfQ.HrD6yp7LI7OWgJ87G4Pg8vh1Ij5ZfgUGGxGIwC0BFNY

"""
