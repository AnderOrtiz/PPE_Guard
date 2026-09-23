import threading
import time
from datetime import datetime, timezone

from app.services.camera_service import camera_service
from app.services.yolo_service import detect
from app.services.compliance_engine import ComplianceEngine
from app.services.evidence_service import save_evidence
from app.services.violation_repository import create_violation, reopen_violation, close_violation, update_violation
from app.websockets.manager import manager
from app.core import async_bridge


class DetectionOrchestrator:
    def __init__(self, session_id: str, area: str, required_ppe: set[str], interval_seconds: float = 0.3):
        self.session_id = session_id
        self.area = area
        self.interval_seconds = interval_seconds

        self.compliance_engine = ComplianceEngine(
            required_ppe=required_ppe,
            on_episode_started=self._on_episode_started,
            on_episode_updated=self._on_episode_updated,
            on_episode_resolved=self._on_episode_resolved,
        )

        self._running = False
        self._thread: threading.Thread | None = None

        self._detections_lock = threading.Lock()
        self._latest_detections: list[dict] = []
        self._current_frame = None

    def start(self):
        if self._running:
            return
        camera_service.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            frame = camera_service.get_latest_frame()
            if frame is not None:
                self._current_frame = frame
                detections = detect(frame, area=self.area)
                self._handle_detections(detections, frame.shape)
                self.compliance_engine.process(detections)
            time.sleep(self.interval_seconds)

    def _handle_detections(self, detections: list[dict], frame_shape):
        with self._detections_lock:
            self._latest_detections = detections

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

    def get_latest_detections(self) -> list[dict]:
        with self._detections_lock:
            return list(self._latest_detections)

    def _on_episode_started(self, episode_id, track_id, missing, bbox, is_reopen):
        etiqueta = "REABIERTO" if is_reopen else "NUEVO"
        print(f"[{etiqueta}] episodio={episode_id} track={track_id} falta={missing}")

        evidencia_url = None
        if self._current_frame is not None:
            evidencia_url = save_evidence(self._current_frame, bbox, list(missing), episode_id)

        if is_reopen:
            async_bridge.run_coroutine(reopen_violation(episode_id, list(missing), evidencia_url))
        else:
            async_bridge.run_coroutine(create_violation(
                session_id=self.session_id,
                episode_id=episode_id,
                track_id=track_id,
                faltantes=list(missing),
                evidencia_url=evidencia_url,
            ))

        manager.broadcast_from_thread({
            "evento": "incumplimiento_iniciado",
            "episode_id": episode_id,
            "track_id": track_id,
            "faltantes": list(missing),
            "evidencia_url": evidencia_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _on_episode_updated(self, episode_id, missing):
        print(f"[ACTUALIZADO-WS] episodio={episode_id} ahora falta={missing}")

        async_bridge.run_coroutine(update_violation(episode_id, list(missing)))

        manager.broadcast_from_thread({
            "evento": "incumplimiento_actualizado",
            "episode_id": episode_id,
            "faltantes": list(missing),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _on_episode_resolved(self, episode_id):
        print(f"[RESUELTO] episodio={episode_id}")

        async_bridge.run_coroutine(close_violation(episode_id))

        manager.broadcast_from_thread({
            "evento": "incumplimiento_resuelto",
            "episode_id": episode_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        camera_service.stop()