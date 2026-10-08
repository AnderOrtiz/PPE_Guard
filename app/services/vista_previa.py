import asyncio
import time

from app.services.camera_service import camera_service

# Segundos que una vista previa aguanta sin que su dueño lea frames de /stream
# antes de apagarse sola (pestaña cerrada, corte de red, <img> nunca montado).
GRACIA_SIN_LECTURA_SEGUNDOS = 10
VIGILANCIA_INTERVALO_SEGUNDOS = 1

# user_id -> momento de su última lectura del stream. Estar aquí es tener la vista previa encendida.
_ultima_lectura: dict[str, float] = {}
_lock = asyncio.Lock()  # encender, apagar y el vigilante no se pisan entre sí
_vigilante: asyncio.Task | None = None


def _consumidor(user_id: str) -> str:
    return f"vista_previa:{user_id}"


def activa(user_id: str) -> bool:
    return user_id in _ultima_lectura


def marcar_lectura(user_id: str):
    """La llama /stream cada vez que el usuario recibe un frame."""
    if user_id in _ultima_lectura:
        _ultima_lectura[user_id] = time.monotonic()


async def encender(user_id: str):
    """Enciende la vista previa del usuario. Repetirlo solo reinicia la gracia.
    Lanza RuntimeError si la cámara no abre; en ese caso no queda nada encendido."""
    global _vigilante
    async with _lock:
        # Abrir la cámara bloquea (dispositivo + warm-up): fuera del event loop
        await asyncio.to_thread(camera_service.adquirir, _consumidor(user_id))
        _ultima_lectura[user_id] = time.monotonic()
        if _vigilante is None or _vigilante.done():
            _vigilante = asyncio.create_task(_vigilar())


async def apagar(user_id: str):
    """Apaga la vista previa del usuario. La cámara sigue encendida si la usa
    una práctica u otra vista previa."""
    async with _lock:
        await _liberar(user_id)


async def _liberar(user_id: str):
    _ultima_lectura.pop(user_id, None)
    await asyncio.to_thread(camera_service.liberar, _consumidor(user_id))


async def _vigilar():
    """Apaga las vistas previas huérfanas. Solo libera su consumidor: nunca toca el de una práctica."""
    while _ultima_lectura:
        await asyncio.sleep(VIGILANCIA_INTERVALO_SEGUNDOS)
        async with _lock:
            limite = time.monotonic() - GRACIA_SIN_LECTURA_SEGUNDOS
            for user_id in [u for u, visto in _ultima_lectura.items() if visto < limite]:
                print(f"[vista previa] Apagada por inactividad (usuario {user_id})")
                await _liberar(user_id)


def detener():
    """Al apagar el servidor: olvida las vistas previas. La cámara la libera quien llama."""
    global _vigilante
    if _vigilante is not None:
        _vigilante.cancel()
        _vigilante = None
    _ultima_lectura.clear()
