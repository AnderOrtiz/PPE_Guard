# --- Umbrales, ajustables después con el pipeline corriendo de punta a punta ---
REVIEW_CONFIRM_FRAMES = 3      # frames de la revisión en los que debe verse una prenda para darla por llevada
REVIEW_PERSON_MARGIN = 0.10    # holgura de la caja de la persona (fracción de su tamaño): el casco suele asomar por arriba


def _center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _contains(person_bbox, point):
    x1, y1, x2, y2 = person_bbox
    px, py = point
    return x1 <= px <= x2 and y1 <= py <= y2


def _area(bbox):
    x1, y1, x2, y2 = bbox
    return (x2 - x1) * (y2 - y1)


def _expand(bbox, margin):
    x1, y1, x2, y2 = bbox
    dx, dy = (x2 - x1) * margin, (y2 - y1) * margin
    return (x1 - dx, y1 - dy, x2 + dx, y2 + dy)


class PpeReview:
    """
    Revisión de UN alumno durante una ventana fija. Toda prenda requerida parte
    como faltante y solo deja de estarlo si el modelo la detecta puesta: no ver
    la parte del cuerpo donde va (ni la prenda ni su "NO-") cuenta como faltante.

    Solo cuentan las prendas que están sobre el alumno revisado: en cada frame
    se toma a la persona más grande (la más cercana a la cámara) y se ignora
    todo lo que quede fuera de su caja. Un frame sin persona no cuenta nada.
    """

    def __init__(self, required_ppe: set[str]):
        self.required_ppe = required_ppe
        self._worn_frames = {item: 0 for item in required_ppe}
        self._violation_frames = {item: 0 for item in required_ppe}
        self.person_bbox = None  # última persona vista, para encuadrar la evidencia

    def process(self, detections: list[dict]):
        people = [d for d in detections if d["class_name"] == "Person"]
        if not people:
            return
        self.person_bbox = max(people, key=lambda d: _area(d["bbox"]))["bbox"]

        zona = _expand(self.person_bbox, REVIEW_PERSON_MARGIN)
        classes = {d["class_name"] for d in detections if _contains(zona, _center(d["bbox"]))}
        for item in self.required_ppe:
            if item in classes:
                self._worn_frames[item] += 1
            if f"NO-{item}" in classes:
                self._violation_frames[item] += 1

    def missing(self) -> list[str]:
        return sorted(
            item for item in self.required_ppe
            if self._worn_frames[item] < REVIEW_CONFIRM_FRAMES
            or self._worn_frames[item] <= self._violation_frames[item]
        )
