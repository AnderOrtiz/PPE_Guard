import threading
import time
import cv2


class CameraService:
    def __init__(self, camera_index: int = 0, target_fps: int = 8, resize_width: int = 640):
        self.camera_index = camera_index
        self.target_fps = target_fps
        self.resize_width = resize_width

        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._running = False

        self._lock = threading.Lock()
        self._latest_frame = None

    def start(self):
        if self._running:
            return  # ya está corriendo — evita abrir la cámara dos veces

        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara (índice {self.camera_index})")

        # Warm-up: descarta los primeros frames mientras la cámara ajusta exposición
        for _ in range(10):
            self._cap.read()

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self):
        frame_interval = 1.0 / self.target_fps

        while self._running:
            start_time = time.time()

            ret, frame = self._cap.read()
            if not ret:
                # la cámara falló momentáneamente o se desconectó; no tumbar el hilo
                time.sleep(frame_interval)
                continue

            frame = self._resize(frame)

            with self._lock:
                self._latest_frame = frame

            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _resize(self, frame):
        height, width = frame.shape[:2]
        if width <= self.resize_width:
            return frame
        scale = self.resize_width / width
        new_height = int(height * scale)
        return cv2.resize(frame, (self.resize_width, new_height))

    def get_latest_frame(self):
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        with self._lock:
            self._latest_frame = None


camera_service = CameraService()