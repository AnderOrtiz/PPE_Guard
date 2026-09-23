# PPE_Guard — Roadmap del backend

Todo lo que el backend necesita hacer, desde inicializar el proyecto hasta transmitir video y alertas en tiempo real al frontend. Ordenado por dependencia real: cada fase se apoya en la anterior.

---

## Fase 0 — Inicializar el proyecto

La estructura de carpetas define dónde vive cada responsabilidad, antes de que el proyecto crezca lo suficiente para que moverla sea doloroso.

- Repositorio Git con `.gitignore`
- Entorno conda `yolo` con Python 3.11 y `requirements.txt` fijado con `pip freeze`
- Estructura por capas: `core/`, `api/`, `services/`, `models/`, `websockets/`
- `README.md` con los pasos para levantar el proyecto desde cero

**Concepto clave:** la regla de dependencia — `api/` puede importar de `services/`, y `services/` de `core/`, pero nunca al revés.

---

## Fase 1 — Configuración centralizada con Pydantic

Ninguna credencial, ruta ni umbral debería estar escrito dentro del código.

- `core/config.py` con una clase `Settings` (`BaseSettings`)
- `.env` real (ignorado por Git) y `.env.template` versionado
- Variables de app, de Mongo, de CORS, y las rutas de los dos modelos de YOLO (`MODEL_PATHS` por área)

**Concepto clave:** Pydantic valida y convierte de tipo — un error en el `.env` falla al arrancar con un mensaje claro, no a mitad de una operación.

---

## Fase 2 — Infraestructura de base de datos con Docker

Docker solo orquesta lo que no necesita hardware local: MongoDB y Mongo Express. El backend corre siempre nativo (nunca se vuelve a dockerizar), porque necesita acceso directo a la cámara de la máquina y este proyecto no tiene fase de despliegue.

- `compose.yaml` con Mongo (autenticación activada) y Mongo Express
- Persistencia por bind mount
- Credenciales y puertos leídos desde el `.env`

**Ojo con esto:** dentro de la red de Docker, los servicios se llaman por su nombre (`db`). El backend, corriendo fuera de Docker, debe conectarse por `localhost`.

---

## Fase 3 — Conexión a MongoDB

Una sola conexión compartida, abierta al arrancar y cerrada al apagar.

- Cliente `AsyncMongoClient` creado en el `lifespan` de FastAPI
- Un `ping` al arrancar para fallar de inmediato si Mongo no responde
- Función `get_database()` expuesta al resto del proyecto
- Índices sobre `sessions.inicio`, `violations.session_id` y `violations.inicio`

---

## Fase 4 — Modelar los documentos y los esquemas

Define qué se guarda antes de escribir endpoints.

**Colecciones:**
- `practices` — catálogo de áreas y su PPE obligatorio (civil: casco, chaleco · medicina: mascarilla, guantes, gorro)
- `sessions` — cada práctica: área, docente a cargo, carrera, inicio, fin, estado
- `violations` — un documento por episodio de incumplimiento: `track_id`, sesión, faltantes, inicio, fin, estado, ruta de evidencia

**Qué construir:**
- Esquemas Pydantic separando entrada, salida, y el documento de Mongo
- Manejo de `ObjectId` como string serializable

---

## Fase 5 — API REST base y documentación

- Router principal con prefijo `/api/v1`, routers por recurso en `endpoints/`
- CORS habilitado para el origen del frontend en desarrollo (Vite, `localhost:5173`)
- Endpoint de salud que verifica también que Mongo responde
- Endpoint `GET /practices`

---

## Fase 6 — Servicio de YOLO: un modelo por área

El área se conoce antes de encender la cámara (se elige al crear la sesión), así que se puede cargar el modelo correcto sin correr dos modelos a la vez.

- `get_model(area)` que carga y cachea en memoria cada modelo la primera vez que se pide
- Inferencia de calentamiento justo después de cargar cada modelo
- Función de inferencia que devuelve clase, confianza, coordenadas y `track_id`
- Dependencia externa necesaria: `lapx` (requerida por el tracking de Ultralytics, no viene por defecto)


**Ojo con esto:** la inferencia es bloqueante y pesada en CPU — nunca se llama directo dentro de una función `async` sin sacarla a un hilo o executor.

---

## Fase 7 — Captura de video con OpenCV

Una API web responde a peticiones puntuales; una cámara produce datos continuamente. Son dos modelos de ejecución distintos conviviendo en el mismo proceso.

- Apertura de la cámara con `VideoCapture(0)`, con verificación de que abrió
- Warm-up: descartar los primeros frames mientras la cámara ajusta exposición
- Bucle de lectura en un hilo separado, con tasa controlada (5-10 FPS, no los 30 nativos)
- Redimensionado del frame antes de la inferencia
- Solo se guarda el "último frame" — nunca se acumula una cola de frames viejos

---

## Fase 8 — Seguimiento de personas con ByteTrack

Sin seguimiento, la misma persona incumpliendo se contaría como un incumplimiento nuevo en cada frame.

- Cambiar de `model.predict()` a `model.track(frame, persist=True, tracker="bytetrack.yaml")`
- `persist=True` mantiene la continuidad del `track_id` entre frames dentro del mismo bucle

**Concepto clave:** un `track_id` no es una identidad real, es una hipótesis del rastreador. Si la persona sale del cuadro o queda tapada, puede reaparecer con un `track_id` nuevo — eso se compensa en la fase 10, no aquí.

---

## Fase 9 — Orquestar el pipeline de detección

Captura, tracking, evaluación y transmisión se convierten en un ciclo continuo mientras haya una sesión activa.

- Un hilo propio (`detection_orchestrator`) que corre a un intervalo fijo (~0.3s), separado del hilo de captura de la cámara
- Arranque y parada ligados a la creación/finalización de la sesión

**Concepto clave:** patrón productor–consumidor — la cámara produce a su ritmo, el modelo consume al suyo, y no se acumula rezago porque cada ciclo trabaja con el frame más reciente disponible.

---

## Fase 10 — Reglas de cumplimiento y máquina de estados

El corazón del sistema: convierte "detecté esto" en "esta persona lleva rato incumpliendo, hay que registrarlo".

- **Asociación geométrica:** una falta (`NO-Hardhat`, etc.) se atribuye a una persona si el centro de su caja cae dentro de la caja de esa `Person`
- **Filtro de confianza mínima para personas**, más estricto que el umbral general del modelo, para evitar que ruido de fondo abra episodios falsos
- **Distinción entre "sin señal" y "cumple":** un frame donde el modelo simplemente no detectó nada relevante no debe resetear el progreso hacia confirmar ni hacia cerrar
- **Máquina de estados por `track_id`:** `cumple` → `posible` (sostenido N frames) → `confirmado` (se abre el episodio) → `cumple` de nuevo (sostenido M frames cumpliendo, o timeout del track)
- El conjunto de faltas (`missing`) se sigue actualizando mientras el episodio está `confirmado` — si la persona corrige una parte, se refleja sin cerrar y reabrir
- **Heurística anti-duplicado:** una lista de "episodios recién cerrados" (ventana de ~40s); si reaparece la misma combinación exacta de faltas cerca de donde se vio, se reabre ese episodio en vez de crear uno nuevo

**Pendiente:** los valores exactos de N y M frames se ajustan con el pipeline corriendo de punta a punta, no antes.

---

## Fase 11 — WebSockets en tiempo real

El frontend no pregunta si hay novedades — el backend empuja los datos apenas ocurren.

- `ConnectionManager` con soporte para múltiples clientes conectados
- Endpoint `/ws/detections`
- Puente seguro entre el hilo del orquestador (síncrono) y el event loop de FastAPI (asíncrono), vía `asyncio.run_coroutine_threadsafe`

**Tres tipos de mensaje:**
- `detecciones_frame` — se emite en cada ciclo del orquestador; coordenadas normalizadas (0-1) y `is_violation` ya calculado, para alimentar cajas dibujadas en vivo en el frontend
- `incumplimiento_iniciado` — al confirmarse un episodio: `episode_id`, `track_id`, `faltantes`, `evidencia_url`
- `incumplimiento_resuelto` — al cerrarse un episodio: solo `episode_id`

---

## Fase 12 — Streaming de video en vivo

El frontend necesita ver la cámara en vivo, no solo las cajas y alertas.

- Endpoint `GET /api/v1/stream` que sirve el último frame de `camera_service` como MJPEG (`multipart/x-mixed-replace`)
- Se consume directo desde un `<img>` en el frontend, sin JavaScript adicional

**Límite aceptado:** el video (MJPEG) y las cajas (WebSocket) son dos canales independientes sin frame ID compartido — quedan cerca en el tiempo, pero no perfectamente sincronizados. Suficiente para este proyecto.

---

## Fase 13 — Persistir episodios con evidencia

Un episodio, no un frame — y ese episodio necesita una imagen que respalde que el incumplimiento fue real.

- Al confirmarse el episodio: dibujar sobre una copia del frame completo un rectángulo y el texto de lo que falta
- Guardar esa imagen en disco; en Mongo solo se guarda la ruta
- Servir esa carpeta de evidencia como estática, para que `evidencia_url` del WebSocket apunte a un archivo real
- Capa de repositorio en `services/` para las operaciones de Mongo sobre `violations`
- Actualizar el mismo documento al cerrarse el episodio (hora de fin, estado)

**Nota:** no hace falta limpieza periódica de evidencia — proyecto de presentación única, no de uso continuo.

---

## Fase 14 — Historial y reportes

- Endpoints de consulta con filtros por fecha y por práctica/área
- Agrupación por día, ordenado por hora
- Paginación desde el inicio
- Agregaciones de Mongo para conteos (por área, por tipo de falta, por día)

---

## Fase 15 — Dashboard de sesiones y prácticas

Convierte el área en una elección del docente, no en una constante escondida en el código.

- CRUD de `practices`: cada área con su PPE obligatorio
- `POST /sessions` — crear una práctica con área, docente y carrera; dispara el encendido de la cámara y el pipeline con el modelo y las reglas correctas
- `GET /sessions/active` — consultar si hay una sesión en curso
- `POST /sessions/{id}/end` — botón "Finalizar práctica": apaga la cámara, detiene el orquestador, cierra por la fuerza los episodios que hayan quedado abiertos, marca la sesión como terminada

---

## Notas de cierre

- El modelo de medicina y los umbrales N/M de la máquina de estados son las únicas piezas que no bloquean el avance del resto — se pueden resolver en paralelo, sobre la marcha.