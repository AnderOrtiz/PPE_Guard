import time
import uuid

# --- Umbrales, ajustables después con el pipeline corriendo de punta a punta ---
CONFIRM_FRAMES = 5             # frames seguidos con la misma falta antes de confirmar
UPDATE_FRAMES = 3              # frames seguidos con un nuevo conjunto antes de actualizar un episodio ya confirmado
CLOSE_FRAMES = 5               # frames seguidos cumpliendo antes de cerrar
TRACK_TIMEOUT_SECONDS = 5      # si un track no aparece en este tiempo, se da por perdido
REOPEN_WINDOW_SECONDS = 40     # ventana para reabrir un episodio en vez de duplicarlo
REOPEN_DISTANCE_THRESHOLD = 150  # píxeles de tolerancia para considerar "la misma zona"
MIN_PERSON_CONFIDENCE = 0.65   # filtra personas detectadas con poca certeza


def _center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _contains(person_bbox, point):
    x1, y1, x2, y2 = person_bbox
    px, py = point
    return x1 <= px <= x2 and y1 <= py <= y2


def _distance(bbox_a, bbox_b):
    ax, ay = _center(bbox_a)
    bx, by = _center(bbox_b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


class PersonState:
    def __init__(self, track_id, bbox):
        self.track_id = track_id
        self.bbox = bbox
        self.state = "cumple"  # cumple | posible | confirmado
        self.missing: set[str] = set()
        self.streak = 0
        self.episode_id: str | None = None
        self.last_seen = time.time()

        # Para exigir estabilidad antes de aceptar un cambio en un episodio ya confirmado
        self.pending_missing: set[str] | None = None
        self.pending_streak = 0


class ComplianceEngine:
    """
    Motor CON ESTADO, uno por sesión activa. Asocia PPE a cada persona por
    posición, sostiene una máquina de estados por track_id, y decide cuándo
    abrir, actualizar y cerrar un episodio de incumplimiento.
    """

    def __init__(self, required_ppe: set[str], on_episode_started=None,
                 on_episode_updated=None, on_episode_resolved=None):
        self.required_ppe = required_ppe
        self._ppe_related_classes = required_ppe | {f"NO-{item}" for item in required_ppe}

        self.on_episode_started = on_episode_started
        self.on_episode_updated = on_episode_updated
        self.on_episode_resolved = on_episode_resolved

        self._persons: dict[int, PersonState] = {}
        self._recently_closed: list[dict] = []

    def process(self, detections: list[dict]):
        now = time.time()

        people = [
            d for d in detections
            if d["class_name"] == "Person"
            and d["track_id"] is not None
            and d["confidence"] >= MIN_PERSON_CONFIDENCE
        ]
        ppe_items = [d for d in detections if d["class_name"] in self._ppe_related_classes]

        assignment = self._assign_ppe_to_people(people, ppe_items)
        seen_track_ids = set()

        for person in people:
            track_id = person["track_id"]
            seen_track_ids.add(track_id)
            missing, has_signal = assignment[track_id]

            if track_id not in self._persons:
                self._persons[track_id] = PersonState(track_id, person["bbox"])

            state = self._persons[track_id]
            state.bbox = person["bbox"]
            state.last_seen = now

            if has_signal:
                self._advance(state, missing)

        self._handle_disappeared(seen_track_ids, now)

    def _assign_ppe_to_people(self, people, ppe_items):
        """Cada ítem de PPE se atribuye a UNA sola persona: la más cercana
        entre las que geométricamente lo contienen. Evita que una prenda
        se le atribuya a dos personas a la vez cuando sus cajas se solapan."""
        result = {p["track_id"]: (set(), False) for p in people}

        for required in self.required_ppe:
            violation_class = f"NO-{required}"
            for item in ppe_items:
                if item["class_name"] not in (required, violation_class):
                    continue

                candidates = [p for p in people if _contains(p["bbox"], _center(item["bbox"]))]
                if not candidates:
                    continue

                best = min(candidates, key=lambda p: _distance(p["bbox"], item["bbox"]))
                track_id = best["track_id"]
                missing, _ = result[track_id]
                if item["class_name"] == violation_class:
                    missing.add(required)
                result[track_id] = (missing, True)

        return result

    def _advance(self, state: PersonState, missing: set[str]):
        if missing:
            if state.state == "cumple":
                state.state = "posible"
                state.missing = missing
                state.streak = 1

            elif state.state == "posible":
                if state.missing == missing:
                    state.streak += 1
                else:
                    state.missing = missing
                    state.streak = 1
                if state.streak >= CONFIRM_FRAMES:
                    self._confirm(state)

            elif state.state == "confirmado":
                state.streak = 0
                if missing == state.missing:
                    state.pending_missing = None
                    state.pending_streak = 0
                else:
                    if state.pending_missing == missing:
                        state.pending_streak += 1
                    else:
                        state.pending_missing = missing
                        state.pending_streak = 1

                    if state.pending_streak >= UPDATE_FRAMES:
                        print(f"[ACTUALIZADO] track={state.track_id} ahora falta={missing}")
                        state.missing = missing
                        state.pending_missing = None
                        state.pending_streak = 0
                        if self.on_episode_updated:
                            self.on_episode_updated(state.episode_id, missing)
        else:
            if state.state == "confirmado":
                state.streak += 1
                state.pending_missing = None
                state.pending_streak = 0
                if state.streak >= CLOSE_FRAMES:
                    self._close(state)
            else:
                state.state = "cumple"
                state.missing = set()
                state.streak = 0

    def _confirm(self, state: PersonState):
        state.state = "confirmado"
        state.streak = 0
        state.pending_missing = None
        state.pending_streak = 0

        reopened = self._find_reopen_candidate(state.missing, state.bbox)
        is_reopen = reopened is not None
        state.episode_id = reopened["episode_id"] if is_reopen else str(uuid.uuid4())

        if self.on_episode_started:
            self.on_episode_started(state.episode_id, state.track_id, state.missing, state.bbox, is_reopen)

    def _close(self, state: PersonState):
        if self.on_episode_resolved and state.episode_id:
            self.on_episode_resolved(state.episode_id)

        self._recently_closed.append({
            "episode_id": state.episode_id,
            "missing": state.missing,
            "bbox": state.bbox,
            "closed_at": time.time(),
        })

        state.state = "cumple"
        state.missing = set()
        state.streak = 0
        state.episode_id = None
        state.pending_missing = None
        state.pending_streak = 0

    def _find_reopen_candidate(self, missing, bbox):
        now = time.time()
        self._recently_closed = [c for c in self._recently_closed if now - c["closed_at"] < REOPEN_WINDOW_SECONDS]

        for candidate in self._recently_closed:
            if candidate["missing"] == missing and _distance(candidate["bbox"], bbox) < REOPEN_DISTANCE_THRESHOLD:
                self._recently_closed.remove(candidate)
                return candidate
        return None

    def _handle_disappeared(self, seen_track_ids: set[int], now: float):
        for track_id, state in list(self._persons.items()):
            if track_id in seen_track_ids:
                continue
            if now - state.last_seen > TRACK_TIMEOUT_SECONDS:
                if state.state == "confirmado":
                    self._close(state)
                del self._persons[track_id]