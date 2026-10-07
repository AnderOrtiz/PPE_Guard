from pydantic import BaseModel


class ResumenCoordinacion(BaseModel):
    materias: int
    materias_nuevas: int
    materias_lab_activo: int
    docentes: int
    docentes_activos_hoy: int
    alumnos: int
