from datetime import datetime
from pydantic import BaseModel


class FilaAsistencia(BaseModel):
    alumno_id: str
    nombre: str
    codigo: str
    hora_identificacion: datetime | None
    presente: bool
    cumplio_indumentaria: bool | None  # None cuando no asistió — no aplica
    faltantes: list[str]
    evidencia_url: str | None


class ReportePractica(BaseModel):
    practica_id: str
    materia_nombre: str
    docente_nombre: str
    fecha: datetime
    hora_inicio: datetime
    hora_fin: datetime | None
    total_matriculados: int
    presentes: int
    ausentes: int
    cumplieron: int
    no_cumplieron: int
    detalle: list[FilaAsistencia]