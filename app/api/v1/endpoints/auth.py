from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_database
from app.core.security import hash_password, verify_password, create_access_token
from app.api.v1.dependencies import get_current_user
from app.models.usuario import UsuarioLogin, TokenResponse, UsuarioOut, PerfilUpdate, PasswordCambio

router = APIRouter()


async def _usuario_del_token(user: dict) -> dict:
    database = get_database()
    usuario = await database["usuarios"].find_one({"_id": ObjectId(user["user_id"])})
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
    return usuario


def _token_response(usuario: dict) -> TokenResponse:
    token = create_access_token(str(usuario["_id"]), usuario["codigo"], usuario["rol"])
    return TokenResponse(access_token=token, rol=usuario["rol"], nombre=usuario["nombre"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UsuarioLogin):
    database = get_database()
    usuario = await database["usuarios"].find_one({"codigo": credentials.codigo})

    if usuario is None or not verify_password(credentials.password, usuario["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código o contraseña incorrectos")

    return _token_response(usuario)


@router.get("/auth/me", response_model=UsuarioOut)
async def yo(user: dict = Depends(get_current_user)):
    return UsuarioOut(**await _usuario_del_token(user))


@router.patch("/auth/me", response_model=UsuarioOut)
async def actualizar_perfil(data: PerfilUpdate, user: dict = Depends(get_current_user)):
    usuario = await _usuario_del_token(user)

    cambios = data.model_dump(exclude_none=True)
    if not cambios:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se envió ningún campo para actualizar")

    database = get_database()
    await database["usuarios"].update_one({"_id": usuario["_id"]}, {"$set": cambios})

    actualizado = await database["usuarios"].find_one({"_id": usuario["_id"]})
    return UsuarioOut(**actualizado)


@router.post("/auth/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def cambiar_password(data: PasswordCambio, user: dict = Depends(get_current_user)):
    usuario = await _usuario_del_token(user)

    # Se pide la actual: un token robado o una sesión abierta no bastan para quedarse con la cuenta.
    if not verify_password(data.password_actual, usuario["password_hash"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La contraseña actual no es correcta")

    database = get_database()
    await database["usuarios"].update_one(
        {"_id": usuario["_id"]},
        {"$set": {"password_hash": hash_password(data.password_nueva)}},
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refrescar_token(user: dict = Depends(get_current_user)):
    # Se relee el usuario: si lo borraron o le cambiaron el rol, el token nuevo lo refleja.
    return _token_response(await _usuario_del_token(user))
