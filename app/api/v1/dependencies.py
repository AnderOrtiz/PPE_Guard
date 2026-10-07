from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token

bearer_scheme = HTTPBearer()
bearer_opcional = HTTPBearer(auto_error=False)

# Jerarquía: el admin hereda todos los permisos del coordinador
ROLE_EXPANSION = {"admin": {"admin", "coordinador", "docente"}}


def user_from_token(token: str) -> dict:
    try:
        payload = decode_access_token(token)
        return {"codigo": payload["sub"], "user_id": payload["uid"], "rol": payload["rol"]}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    return user_from_token(credentials.credentials)


def get_current_user_media(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_opcional),
    token: str | None = None,
) -> dict:
    """Para recursos que el navegador pide desde un <img> (stream, evidencias),
    donde no se puede mandar el header: acepta el token también como ?token=."""
    raw = credentials.credentials if credentials is not None else token
    if raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
    return user_from_token(raw)


def tiene_rol(user: dict, *roles: str) -> bool:
    effective_roles = ROLE_EXPANSION.get(user["rol"], {user["rol"]})
    return bool(effective_roles & set(roles))


def require_role(*roles: str, auth=get_current_user):
    def dependency(user: dict = Depends(auth)) -> dict:
        if not tiene_rol(user, *roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para esta acción")
        return user

    return dependency
