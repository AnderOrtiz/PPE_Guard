import asyncio

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop


def run_coroutine(coro):
    """Programa una corrutina para correr en el loop principal de FastAPI,
    de forma segura desde un hilo normal (cámara, orquestador)."""
    if _main_loop is None:
        raise RuntimeError("El loop principal todavía no se ha inicializado")
    future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
    future.add_done_callback(_log_if_error)
    return future


def _log_if_error(future):
    exc = future.exception()
    if exc is not None:
        print(f"[ERROR async] {exc}")