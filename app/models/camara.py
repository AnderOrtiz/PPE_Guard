from pydantic import BaseModel


class VistaPreviaEstado(BaseModel):
    activa: bool  # la vista previa de quien pregunta
    camara_encendida: bool  # puede seguir en true con la vista previa apagada (práctica en curso)
    gracia_segundos: int  # cuánto aguanta sin lecturas de /stream antes de apagarse sola
