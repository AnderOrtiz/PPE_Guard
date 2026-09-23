from fastapi import APIRouter, HTTPException, status

from app.core.database import get_database
from app.core.security import verify_password, create_access_token
from app.models.usuario import UsuarioLogin, TokenResponse

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UsuarioLogin):
    database = get_database()
    usuario = await database["usuarios"].find_one({"username": credentials.username})

    if usuario is None or not verify_password(credentials.password, usuario["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos")

    token = create_access_token(usuario["username"], usuario["rol"])
    return TokenResponse(access_token=token, rol=usuario["rol"], nombre=usuario["nombre"])