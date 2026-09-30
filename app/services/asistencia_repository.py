from datetime import datetime

from app.core.database import get_database


async def create_asistencia(
    practica_id: str,
    alumno_id: str,
    hora_identificacion: datetime,
    cumplio_indumentaria: bool,
    faltantes: list[str],
    evidencia_url: str | None,
):
    database = get_database()
    await database["asistencias"].insert_one({
        "practica_id": practica_id,
        "alumno_id": alumno_id,
        "hora_identificacion": hora_identificacion,
        "cumplio_indumentaria": cumplio_indumentaria,
        "faltantes": faltantes,
        "evidencia_url": evidencia_url,
    })