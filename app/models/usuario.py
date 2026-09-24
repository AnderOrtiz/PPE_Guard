from pydantic import BaseModel, Field, ConfigDict
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

"""
    {"username": "docente1","password": "cambiar123"}

    eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkb2NlbnRlMSIsInJvbCI6ImRvY2VudGUiLCJleHAiOjE3OTAyMzE1ODd9.7s5wX5KS1P8Iul7Mt_WIjRpfSzO2vSGbBrEDzW8Elbk

    {"username": "coordinador1","password": "cambiar123"}
    
    eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjb29yZGluYWRvcjEiLCJyb2wiOiJjb29yZGluYWRvciIsImV4cCI6MTc5MDIzMTcyOH0.FaBHAZC9QZd2FUKPLuiWHirQZdxxVpwavl_UwxF9VOg
"""