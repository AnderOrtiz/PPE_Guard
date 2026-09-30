from app.services.practica_orchestrator import PracticaOrchestrator

_activos: dict[str, PracticaOrchestrator] = {}


def hay_practica_activa() -> bool:
    return len(_activos) > 0


def registrar(practica_id: str, orquestador: PracticaOrchestrator):
    _activos[practica_id] = orquestador


def obtener(practica_id: str) -> PracticaOrchestrator | None:
    return _activos.get(practica_id)


def eliminar(practica_id: str):
    _activos.pop(practica_id, None)