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

        # Quién está usando la cámara (una práctica, una vista previa...). El
        # dispositivo se abre con el primero y se libera cuando no queda ninguno.
        # RLock aparte del de frames: abrir y cerrar tarda, y no debe frenar las lecturas.
        self._consumidores: set[str] = set()
        self._consumidores_lock = threading.RLock()

    @property
    def encendida(self) -> bool:
        return self._running

    def consumidores(self) -> set[str]:
        with self._consumidores_lock:
            return set(self._consumidores)

    def adquirir(self, consumidor: str):
        """Registra a un consumidor y enciende la cámara si era el primero.
        Adquirir dos veces con el mismo nombre no cuenta doble. Si el dispositivo
        no abre, lanza RuntimeError y el consumidor no queda registrado."""
        with self._consumidores_lock:
            if consumidor in self._consumidores:
                return
            if not self._consumidores:
                self._abrir()
            self._consumidores.add(consumidor)

    def liberar(self, consumidor: str):
        """Quita a un consumidor y apaga la cámara si era el último.
        Liberar sin haber adquirido no hace nada."""
        with self._consumidores_lock:
            if consumidor not in self._consumidores:
                return
            self._consumidores.discard(consumidor)
            if not self._consumidores:
                self._cerrar()

    def liberar_todos(self):
        """Apaga la cámara sin importar quién la tenga. Solo para el apagado del servidor."""
        with self._consumidores_lock:
            self._consumidores.clear()
            self._cerrar()

    def _abrir(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"No se pudo abrir la cámara (índice {self.camera_index})")

        # Warm-up: descarta los primeros frames mientras la cámara ajusta exposición
        for _ in range(10):
            cap.read()

        # Deja un frame listo antes de volver, para que quien adquiere no vea la cámara vacía
        ret, frame = cap.read()
        if ret:
            with self._lock:
                self._latest_frame = self._resize(frame)

        self._cap = cap
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

    def _cerrar(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        with self._lock:
            self._latest_frame = None


camera_service = CameraService()


def capture_single_frame(camera_index: int = 0, warmup_frames: int = 10):
    """Abre la cámara, descarta los primeros frames, captura uno solo, y la libera.
    Si el CameraService global ya está corriendo en el mismo índice, usa su
    último frame para evitar conflictos de acceso al dispositivo."""
    if camera_service.camera_index != camera_index:
        return _capturar_directo(camera_index, warmup_frames)

    # Con el candado de consumidores nadie enciende ni apaga la cámara a mitad de la captura
    with camera_service._consumidores_lock:
        if camera_service.encendida:
            frame = camera_service.get_latest_frame()
            if frame is not None:
                return frame
        return _capturar_directo(camera_index, warmup_frames)


def _capturar_directo(camera_index: int, warmup_frames: int):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir la cámara (índice {camera_index})")

    try:
        for _ in range(warmup_frames):
            cap.read()
        ret, frame = cap.read()
        if not ret:
            raise RuntimeError("No se pudo capturar un frame de la cámara")
        return frame
    finally:
        cap.release()
