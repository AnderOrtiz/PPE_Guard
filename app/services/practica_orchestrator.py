import threading
import time
from datetime import datetime, timezone

from app.services.camera_service import camera_service
from app.services.face_service import get_face_embedding, find_best_match
from app.websockets.manager import manager

IDENTIFICATION_INTERVAL_SECONDS = 1.0  # identificar cada segundo es de sobra; no hace falta más rápido


class PracticaOrchestrator:
    def __init__(self, practica_id: str, candidatos: list[dict]):
        self.practica_id = practica_id
        self.candidatos = candidatos  # alumnos matriculados en la materia de esta práctica

        self._running = False
        self._thread: threading.Thread | None = None
        self._fase = "identificacion"  # única fase por ahora — "indumentaria" llega en el próximo paso

        self._last_identified_id: str | None = None

    def start(self):
        if self._running:
            return
        camera_service.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            if self._fase == "identificacion":
                self._tick_identificacion()
            time.sleep(IDENTIFICATION_INTERVAL_SECONDS)

    def _tick_identificacion(self):
        frame = camera_service.get_latest_frame()
        if frame is None:
            return

        embedding = get_face_embedding(frame, enforce_detection=False)
        if embedding is None:
            self._last_identified_id = None  # nadie en cuadro; libera para volver a anunciar después
            return

        match = find_best_match(embedding, self.candidatos)
        if match is None:
            self._last_identified_id = None
            return

        alumno_id = str(match["_id"])
        if alumno_id == self._last_identified_id:
            return  # ya se anunció; no repetir en cada tick mientras siga frente a la cámara

        self._last_identified_id = alumno_id

        manager.broadcast_from_thread({
            "evento": "estudiante_identificado",
            "practica_id": self.practica_id,
            "alumno_id": alumno_id,
            "nombre": match["nombre"],
            "codigo": match["codigo"],
            "confianza": match["similarity"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        camera_service.stop()