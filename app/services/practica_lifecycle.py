from datetime import datetime, timedelta, timezone

from bson import ObjectId

from app.core.config import settings
from app.core.database import get_database
from app.services.face_service import get_candidatos_de_materia
from app.services.practica_orchestrator import PracticaOrchestrator
from app.services import practica_registry


async def arrancar_orquestador(database, practica_id: str, materia: dict, required_ppe: set[str]):
    """Enciende la cámara y la detección de una práctica y la deja en el registro."""
    candidatos = await get_candidatos_de_materia(database, str(materia["_id"]))

    orquestador = PracticaOrchestrator(practica_id, materia["area"], required_ppe, candidatos)
    orquestador.start()
    practica_registry.registrar(practica_id, orquestador)


async def _reanudar(database, practica: dict) -> bool:
    if not ObjectId.is_valid(practica["materia_id"]):
        return False
    materia = await database["materias"].find_one({"_id": ObjectId(practica["materia_id"])})
    if materia is None:
        return False
    catalogo = await database["practices"].find_one({"area": materia["area"]})
    if catalogo is None:
        return False

    try:
        await arrancar_orquestador(database, str(practica["_id"]), materia, set(catalogo["ppe_requerido"]))
    except Exception as exc:
        print(f"[practicas] No se pudo reanudar la práctica {practica['_id']}: {exc}")
        return False
    return True


async def recuperar_practica_activa():
    """Al arrancar el servidor: el orquestador vive en memoria, así que una práctica
    que quedó "activa" en la base está huérfana. Se reanuda la más reciente si
    todavía es reciente; cualquier otra se cierra."""
    database = get_database()
    ahora = datetime.now(timezone.utc)
    limite = ahora - timedelta(hours=settings.PRACTICA_RECUPERABLE_HORAS)

    cursor = database["practicas"].find({"estado": "activa"}).sort("hora_inicio", -1)
    activas = [practica async for practica in cursor]

    for indice, practica in enumerate(activas):
        hora_inicio = practica["hora_inicio"]
        if hora_inicio.tzinfo is None:  # Mongo devuelve UTC sin zona
            hora_inicio = hora_inicio.replace(tzinfo=timezone.utc)

        if indice == 0 and hora_inicio >= limite and await _reanudar(database, practica):
            print(f"[practicas] Práctica {practica['_id']} reanudada tras el reinicio")
            continue

        await database["practicas"].update_one(
            {"_id": practica["_id"]},
            {"$set": {"hora_fin": ahora, "estado": "finalizada"}},
        )
        print(f"[practicas] Práctica {practica['_id']} cerrada: quedó activa de una ejecución anterior")
