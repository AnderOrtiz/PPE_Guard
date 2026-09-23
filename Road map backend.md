# PPE_Guard — Roadmap del backend (rediseño: identificación facial + aulas)

Rediseño completo tras el cambio de alcance: el sistema ahora identifica estudiantes por reconocimiento facial antes de revisar su indumentaria, dentro de aulas con roles (alumno, docente, coordinador) y autenticación real.

Alcance: ~15 estudiantes (demo). Login simple (usuario/contraseña con hash, sin recuperación de contraseña). Sin múltiples cámaras. Backend siempre nativo (nunca vuelve a Docker), Docker solo para Mongo + Mongo Express.

---

## Fase 0 — Inicializar el proyecto

- Repositorio Git, `.gitignore`, `.dockerignore`
- Entorno conda `yolo`, Python 3.11, `requirements.txt` fijado con `pip freeze`
- Estructura por capas: `core/`, `api/`, `services/`, `models/`, `websockets/`

---

## Fase 1 — Configuración centralizada con Pydantic

- `core/config.py` con `Settings` (`BaseSettings`)
- `.env` real + `.env.template` versionado
- Variables de app, Mongo, CORS, rutas de los modelos YOLO por área, y ahora también: secreto para firmar JWT, tiempo de expiración del token, umbral de similitud para reconocimiento facial

---

## Fase 2 — Infraestructura de base de datos con Docker

- `compose.yaml`: Mongo (autenticación activada) + Mongo Express
- Persistencia por bind mount
- El backend nunca corre dentro de Docker — necesita acceso directo a la cámara

---

## Fase 3 — Conexión a MongoDB

- Cliente `AsyncMongoClient` en el `lifespan` de FastAPI, con `ping` al arrancar
- `get_database()` expuesto al resto del proyecto
- Índices sobre las colecciones nuevas (ver fase 5)

---

## Fase 4 — Autenticación: usuarios y roles

Sin esto, no se pueden aplicar los permisos por rol que exige el proyecto (coordinador ve todo, docente controla el aula, alumno solo ve lo suyo).

- Colección `usuarios`: `username`, `password_hash`, `rol` (`alumno` | `docente` | `coordinador`), `nombre`
- Hash de contraseña con `bcrypt` — nunca se guarda en texto plano
- Endpoint `POST /auth/login` — verifica credenciales, emite un JWT con el `rol` embebido
- Dependencia de FastAPI para proteger endpoints, extrayendo el usuario y rol desde el token
- Middleware/dependencia de autorización por rol (ej. `require_role("coordinador")`)

**Concepto clave:** el JWT es firmado por el backend con una clave secreta — el frontend no puede alterar el rol dentro del token sin invalidar la firma, así que la autorización es confiable aunque el token viva en el navegador.

---

## Fase 5 — Modelar aulas, estudiantes y asistencias

**Colecciones:**
- `aulas` — nombre, área (`civil` | `medicina`, fija al crearse), `docente_id`, lista de `estudiantes_ids` matriculados
- `estudiantes` — `codigo` único, `nombre`, `face_embedding` (vector numérico, no imagen)
- `asistencias` — un documento por revisión: `aula_id`, `estudiante_id`, `fecha`, `hora_identificacion`, `cumplio_indumentaria`, `faltantes`, `evidencia_url`

**Qué construir:**
- Esquemas Pydantic separando entrada/salida/documento de Mongo
- Índices sobre `asistencias.aula_id`, `asistencias.estudiante_id`, `asistencias.fecha`

---

## Fase 6 — Matriculación de estudiantes con reconocimiento facial

No se suben fotos — el sistema captura el rostro en vivo y calcula su representación matemática.

- Instalar `deepface` (evita la complejidad de compilar `dlib` que tiene `face_recognition`)
- Endpoint/flujo de matriculación: abre la cámara, captura un frame, `DeepFace.represent(frame)` calcula el embedding
- Se guarda el embedding en `estudiantes.face_embedding`, junto con nombre y código
- Validación básica: verificar que se detectó exactamente un rostro antes de guardar

**Concepto clave:** un embedding es un vector de números que representa el rostro — comparar dos rostros se reduce a medir qué tan cerca están sus vectores (distancia coseno), no a comparar imágenes directamente.

---

## Fase 7 — Servicio de identificación facial

- Función que recibe un frame, calcula su embedding, y lo compara contra todos los embeddings guardados de los estudiantes matriculados en esa aula
- Si la mejor coincidencia supera el umbral de similitud configurado → estudiante identificado
- Si no hay ninguna coincidencia suficientemente buena → "no identificado", se sigue intentando

**Pendiente:** el umbral exacto de similitud se ajusta con pruebas reales — muy bajo genera falsos positivos (identifica al estudiante equivocado), muy alto rechaza identificaciones válidas por mala luz o ángulo.

**Nota de escala:** con ~15 estudiantes matriculados, comparar contra todos los embeddings en cada intento es prácticamente instantáneo en CPU — no hace falta ninguna optimización de búsqueda.

---

## Fase 8 — Servicio de YOLO por área

(Reutilizado del diseño anterior, sin cambios de fondo.)

- `get_model(area)` carga y cachea cada modelo la primera vez que se pide
- Inferencia de calentamiento al cargar
- Dependencia externa: `lapx` (requerida por el tracking de Ultralytics)

**Pendiente:** el modelo de medicina (mascarilla, guantes, gorro) sigue sin entrenarse — se puede seguir avanzando con civil mientras tanto.

---

## Fase 9 — Captura de video con OpenCV

(Reutilizado sin cambios.)

- `VideoCapture(0)` con verificación de apertura y warm-up de los primeros frames
- Bucle de lectura en hilo separado, tasa controlada (5-10 FPS)
- Solo se conserva el último frame, nunca una cola acumulada

---

## Fase 10 — Seguimiento de personas con ByteTrack

(Reutilizado sin cambios.)

- `model.track(frame, persist=True, tracker="bytetrack.yaml")` en vez de `predict()`
- El `track_id` sigue sin ser una identidad real por sí solo — ahora se vuelve identidad real recién en la fase 11, al vincularlo con el estudiante ya identificado

---

## Fase 11 — Orquestar el flujo de dos fases: identificación → confirmación → indumentaria

Esta es la pieza central del rediseño. Reemplaza al orquestador anterior (que solo corría un modo continuo) por una máquina de dos fases explícitas.

- **Modo identificación:** corre el servicio de la fase 7 contra el frame en vivo. Al identificar a un estudiante, se transmite por WebSocket y se espera confirmación — no pasa automáticamente a revisar indumentaria
- **Confirmación (botón del frontend):** un endpoint o mensaje de WebSocket dispara el cambio de fase, ya con el `estudiante_id` fijado
- **Modo indumentaria:** se activa el pipeline ya existente (YOLO + tracking + `compliance_engine`), pero ahora los resultados se asocian al estudiante identificado, no a un `track_id` anónimo suelto
- Al cerrarse la revisión (episodio de cumplimiento resuelto, o tiempo razonable), se guarda la `asistencia` y el orquestador vuelve a modo identificación para el siguiente estudiante

**Concepto clave:** el botón de confirmación existe porque una transición automática por tiempo fallaría en casos reales (mala luz, el estudiante se mueve) — dar control explícito al proceso es más robusto y más fácil de depurar en una demo en vivo.

---

## Fase 12 — Reglas de cumplimiento y máquina de estados

(Reutilizado del diseño anterior — asociación geométrica de PPE a personas, máquina de estados por `track_id`, heurística anti-duplicado — ahora operando dentro del modo indumentaria de la fase 11, con el resultado final vinculado al estudiante ya identificado en vez de quedar anónimo.)

**Pendiente:** los umbrales de frames para confirmar/cerrar siguen ajustándose con pruebas.

---

## Fase 13 — WebSockets en tiempo real

Los tres tipos de mensaje existentes (`detecciones_frame`, `incumplimiento_iniciado`/`_actualizado`/`_resuelto`) se mantienen para el modo indumentaria. Se agregan dos nuevos para el modo identificación:

- `estudiante_identificado` — `{ "estudiante_id", "nombre", "confianza" }`, cuando el sistema encuentra una coincidencia
- `fase_cambiada` — `{ "fase": "identificacion" | "indumentaria" }`, cuando se confirma el cambio de fase

---

## Fase 14 — Streaming de video en vivo

(Reutilizado sin cambios — `GET /api/v1/stream`, MJPEG servido desde `camera_service`.)

---

## Fase 15 — Persistir asistencias con evidencia

Reemplaza a la antigua persistencia de `violations` sueltas.

- Al cerrarse la revisión de un estudiante: dibujar la evidencia (frame + rectángulo + texto de lo que falta) igual que antes
- Insertar el documento en `asistencias`, vinculado a `estudiante_id` y `aula_id`, con `cumplio_indumentaria`, `faltantes`, `evidencia_url`
- Servir la carpeta de evidencia como estática

---

## Fase 16 — Historial y reportes por rol

- `GET /asistencias` con filtros por fecha, aula, estudiante
- **Coordinador:** puede consultar todas las asistencias de todas las aulas
- **Alumno:** el endpoint filtra automáticamente por su propio `estudiante_id` — no puede pedir las de otro
- **Docente:** puede consultar las asistencias de las aulas que tiene asignadas
- Agrupación por día, paginación, agregaciones de Mongo para conteos

**Concepto clave:** el filtro por rol se aplica del lado del backend a partir del usuario autenticado en el token — nunca confiando en un parámetro que mande el frontend.

---

## Fase 17 — Dashboard de aulas y control del programa

- CRUD de `aulas`: nombre, área (fija al crear), docente asignado, estudiantes matriculados
- El docente inicia el programa de su aula → arranca el orquestador de la fase 11 en modo identificación
- Botón de confirmación (fase 11) y botón de "Finalizar programa" — apaga cámara, detiene orquestador, cierra cualquier revisión que haya quedado abierta

---

## Notas de cierre

- Piezas que no bloquean el resto del desarrollo, resolubles en paralelo: el modelo de medicina, los umbrales de frames de la máquina de estados, y el umbral de similitud facial.
- Fuera de alcance a propósito: recuperación de contraseña, verificación de correo, múltiples cámaras, y una fase formal de robustez/logging/pruebas — proyecto de demostración con ~15 estudiantes, no un sistema en producción.