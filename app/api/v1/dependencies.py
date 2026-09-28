from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token

bearer_scheme = HTTPBearer()

# Jerarquía: el admin hereda todos los permisos del coordinador
ROLE_EXPANSION = {"admin": {"admin", "coordinador"}}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = decode_access_token(credentials.credentials)
        return {"codigo": payload["sub"], "user_id": payload["uid"], "rol": payload["rol"]}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")


def require_role(*roles: str):
    allowed = set(roles)

    def dependency(user: dict = Depends(get_current_user)) -> dict:
        effective_roles = ROLE_EXPANSION.get(user["rol"], {user["rol"]})
        if not (effective_roles & allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para esta acción")
        return user

    return dependency