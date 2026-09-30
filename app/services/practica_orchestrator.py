import threading
import time
from datetime import datetime, timezone

from app.services.camera_service import camera_service
from app.services.face_service import get_face_embedding, find_best_match
from app.services.yolo_service import detect
from app.services.compliance_engine import ComplianceEngine
from app.services.evidence_service import save_evidence
from app.services.asistencia_repository import create_asistencia
from app.websockets.manager import manager
from app.core import async_bridge

IDENTIFICATION_INTERVAL_SECONDS = 1.0
INDUMENTARIA_INTERVAL_SECONDS = 0.3
REVIEW_DURATION_SECONDS = 6  # ventana fija de evaluación tras confirmar


class PracticaOrchestrator:
    def __init__(self, practica_id: str, area: str, required_ppe: set[str], candidatos: list[dict]):
        self.practica_id = practica_id
        self.area = area
        self.required_ppe = required_ppe
        self.candidatos = candidatos

        self._running = False
        self._thread: threading.Thread | None = None
        self._fase = "identificacion"  # "identificacion" | "indumentaria"

        self._last_identified_id: str | None = None

        # Estado de la revisión de indumentaria en curso
        self._confirmed_alumno_id: str | None = None
        self._hora_identificacion: datetime | None = None
        self._compliance_engine: ComplianceEngine | None = None
        self._review_deadline: float = 0.0
        self._review_result = {"cumplio": True, "faltantes": [], "bbox": None}
        self._current_frame = None

    def start(self):
        if self._running:
            return
        camera_service.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def confirmar_identificacion(self, alumno_id: str) -> bool:
        """Cambia a modo indumentaria para el alumno indicado. Devuelve False
        si no coincide con el último identificado, o si ya se está revisando a otro."""
        if self._fase != "identificacion" or alumno_id != self._last_identified_id:
            return False

        self._confirmed_alumno_id = alumno_id
        self._hora_identificacion = datetime.now(timezone.utc)
        self._review_result = {"cumplio": True, "faltantes": [], "bbox": None}
        self._compliance_engine = ComplianceEngine(
            required_ppe=self.required_ppe,
            on_episode_started=self._on_episode_started,
            on_episode_updated=self._on_episode_updated,
            on_episode_resolved=self._on_episode_resolved,
        )
        self._review_deadline = time.time() + REVIEW_DURATION_SECONDS
        self._fase = "indumentaria"

        manager.broadcast_from_thread({
            "evento": "fase_cambiada",
            "practica_id": self.practica_id,
            "fase": "indumentaria",
            "alumno_id": alumno_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def _loop(self):
        while self._running:
            if self._fase == "identificacion":
                self._tick_identificacion()
                time.sleep(IDENTIFICATION_INTERVAL_SECONDS)
            elif self._fase == "indumentaria":
                self._tick_indumentaria()
                time.sleep(INDUMENTARIA_INTERVAL_SECONDS)

    def _tick_identificacion(self):
        frame = camera_service.get_latest_frame()
        if frame is None:
            return

        embedding = get_face_embedding(frame, enforce_detection=False)
        if embedding is None:
            self._last_identified_id = None
            return

        match = find_best_match(embedding, self.candidatos)
        if match is None:
            self._last_identified_id = None
            return

        alumno_id = str(match["_id"])
        if alumno_id == self._last_identified_id:
            return

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

    def _tick_indumentaria(self):
        frame = camera_service.get_latest_frame()
        if frame is not None:
            self._current_frame = frame
            detections = detect(frame, area=self.area)
            self._broadcast_detecciones(detections, frame.shape)
            self._compliance_engine.process(detections)

        if time.time() >= self._review_deadline:
            self._finalizar_revision()

    def _broadcast_detecciones(self, detections, frame_shape):
        height, width = frame_shape[:2]
        items = [{
            "class_name": d["class_name"],
            "confidence": d["confidence"],
            "track_id": d["track_id"],
            "bbox_norm": [d["bbox"][0] / width, d["bbox"][1] / height, d["bbox"][2] / width, d["bbox"][3] / height],
            "is_violation": d["class_name"].startswith("NO-"),
        } for d in detections]

        manager.broadcast_from_thread({
            "evento": "detecciones_frame",
            "frame_width": width,
            "frame_height": height,
            "items": items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _on_episode_started(self, episode_id, track_id, missing, bbox, is_reopen):
        self._review_result = {"cumplio": False, "faltantes": list(missing), "bbox": bbox}

    def _on_episode_updated(self, episode_id, missing):
        self._review_result["faltantes"] = list(missing)

    def _on_episode_resolved(self, episode_id):
        self._review_result = {"cumplio": True, "faltantes": [], "bbox": None}

    def _finalizar_revision(self):
        alumno_id = self._confirmed_alumno_id
        resultado = self._review_result

        evidencia_url = None
        if not resultado["cumplio"] and resultado["bbox"] is not None and self._current_frame is not None:
            evidencia_url = save_evidence(
                self._current_frame, resultado["bbox"], resultado["faltantes"],
                f"{self.practica_id}-{alumno_id}",
            )

        async_bridge.run_coroutine(create_asistencia(
            practica_id=self.practica_id,
            alumno_id=alumno_id,
            hora_identificacion=self._hora_identificacion,
            cumplio_indumentaria=resultado["cumplio"],
            faltantes=resultado["faltantes"],
            evidencia_url=evidencia_url,
        ))

        manager.broadcast_from_thread({
            "evento": "asistencia_registrada",
            "practica_id": self.practica_id,
            "alumno_id": alumno_id,
            "cumplio_indumentaria": resultado["cumplio"],
            "faltantes": resultado["faltantes"],
            "evidencia_url": evidencia_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Vuelve a modo identificación, libre para el siguiente alumno
        self._confirmed_alumno_id = None
        self._compliance_engine = None
        self._last_identified_id = None
        self._fase = "identificacion"

        manager.broadcast_from_thread({
            "evento": "fase_cambiada",
            "practica_id": self.practica_id,
            "fase": "identificacion",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        camera_service.stop()