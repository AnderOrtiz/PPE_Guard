from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class UsuarioLogin(BaseModel):
    codigo: str
    password: str


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
    coordinador_id: str


class AlumnoCreate(_UsuarioBaseCreate):
    carrera: str
    facultad: str


class UsuarioOut(BaseModel):
    """Lo que se expone hacia afuera: nunca password_hash ni face_embedding."""
    id: PyObjectId = Field(alias="_id")
    codigo: str
    nombre: str
    rol: str
    carrera: str | None = None
    facultad: str | None = None
    coordinador_id: str | None = None

    model_config = {"populate_by_name": True}


"""
    {"codigo": "ADMIN001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJBRE1JTjAwMSIsInVpZCI6IjZhYmFhYzgzZjFiMTYwMDc1MzhiNjdlNiIsInJvbCI6ImFkbWluIiwiZXhwIjoxNzkwNjQ3NzMxfQ.vg43hOjwI6ofG3cRUgJYsLy7RyQielXHKUmKFPNNV5Q

    {"username": "COORD001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJDT09SRDAwMSIsInVpZCI6IjZhYmFhYzgyZjFiMTYwMDc1MzhiNjdlNSIsInJvbCI6ImNvb3JkaW5hZG9yIiwiZXhwIjoxNzkwNjQ4MDc2fQ.A5t7iPm9zHUBYB5Xpb9ChLdqcSdCvP-qOqMX6QkGNwo

    {"username": "DOC001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJET0MwMDEiLCJ1aWQiOiI2YWJhYWM4M2YxYjE2MDA3NTM4YjY3ZTciLCJyb2wiOiJkb2NlbnRlIiwiZXhwIjoxNzkwNjQ4NDUxfQ.HrD6yp7LI7OWgJ87G4Pg8vh1Ij5ZfgUGGxGIwC0BFNY

"""
