import numpy as np
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# Un rostro no se puede guardar como hash (como las contraseñas): para reconocer
# a alguien hay que comparar los números del vector, y un hash los destruye.
# Se cifra con una clave (FACE_EMBEDDING_KEY) y se descifra solo en memoria.
_fernet = Fernet(settings.FACE_EMBEDDING_KEY)


def cifrar_embedding(embedding: list[float]) -> str:
    """Devuelve el vector facial cifrado, listo para guardar en Mongo."""
    datos = np.asarray(embedding, dtype=np.float64).tobytes()
    return _fernet.encrypt(datos).decode("ascii")


def esta_cifrado(valor) -> bool:
    return isinstance(valor, str)


def descifrar_embedding(valor) -> np.ndarray:
    """Recupera el vector facial. Acepta también la lista en claro de los
    alumnos registrados antes de que existiera el cifrado."""
    if not esta_cifrado(valor):
        return np.asarray(valor, dtype=np.float64)

    try:
        datos = _fernet.decrypt(valor.encode("ascii"))
    except InvalidToken:
        raise RuntimeError("No se pudo descifrar un rostro registrado: FACE_EMBEDDING_KEY no es la clave con la que se guardó")
    return np.frombuffer(datos, dtype=np.float64)
