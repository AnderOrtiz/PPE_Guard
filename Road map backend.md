# PPE_Guard — Roadmap del backend (v4: sin requerimientos duplicados, admin = superusuario)

Ajustes sobre el rediseño anterior (materias/prácticas/roles): el PPE exigido ya no se guarda por materia — se consulta desde `practices` según el área, porque solo existen dos modelos fijos y duplicar esa lista por materia no aporta nada. El admin ahora hereda también los permisos de docente, además de los de coordinador.

Alcance: ~15 estudiantes (demo). Login simple con JWT, identificado por `codigo`. Sin recuperación de contraseña. Backend siempre nativo, Docker solo para Mongo + Mongo Express.

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

## Fase 4 — Autenticación: usuarios unificados y roles jerárquicos

**Colección `usuarios` (unificada, login por `codigo` en vez de `username`):**
- Comunes: `codigo`, `password_hash`, `rol` (`alumno` | `docente` | `coordinador` | `admin`), `nombre`
- `rol == "alumno"`: `carrera`, `facultad`, `face_embedding`
- `rol == "docente"`: `facultad`, `coordinador_id`
- `coordinador` / `admin`: sin campos adicionales

**Jerarquía de permisos:**
- `admin` hereda TODO lo de `coordinador` **y** TODO lo de `docente` (puede iniciar prácticas, además de crear materias/docentes/coordinadores)
- Ningún rol hereda hacia arriba — un docente sigue sin poder crear materias aunque el admin sí pueda hacer lo que hace un docente

**Endpoints:**
- `POST /auth/login` — recibe `codigo` + `password`, devuelve JWT con `uid` (id del usuario), `sub` (código), `rol`
- `POST /usuarios/coordinadores` — solo `admin`
- `POST /usuarios/docentes` — `coordinador` o `admin`
- `POST /usuarios/alumnos` — `coordinador`, `docente` o `admin` (incluye captura facial, fase 6)

**Concepto clave:** ninguna relación "hacia arriba" (alumno→docente, docente→materias) se guarda como campo fijo — sale de qué documentos referencian el `_id` de quién. La única excepción es `docente.coordinador_id`, porque esa sí es una relación fija de uno a uno.

---

## Fase 5 — Modelar materias, prácticas y asistencias

**Colección `materias`:**
- `nombre`, `area` (`civil` | `medicina`, fija), `carrera`, `facultad`, `aula` (texto libre — ubicación física, ej. "Laboratorio de Física")
- `docente_id`, `coordinador_id` (autocompletado desde `docente.coordinador_id`)
- `alumnos_ids: list[str]`
- **Sin campo de PPE requerido** — se consulta desde `practices` por `area` en el momento en que se necesita (fase 11, fase 16), no se duplica aquí

**Colección `practicas`:**
- `materia_id`, `docente_id`, `fecha`, `hora_inicio`, `hora_fin`, `estado` (`activa` | `finalizada`)

**Colección `asistencias`:**
- `practica_id`, `alumno_id`, `hora_identificacion`, `cumplio_indumentaria`, `faltantes`, `evidencia_url`

**Endpoints:**
- `POST /materias` — solo `coordinador` (el admin, si necesita crear una, lo hace por su expansión de permisos aunque conceptualmente esta acción siga siendo "de coordinador")
- `GET /materias?docente_id=...` — filtra automáticamente por el `coordinador_id`/`docente_id` del usuario autenticado; el parámetro opcional permite a un coordinador o admin acotar a un docente específico, sin poder ver materias ajenas a su alcance

**Índices:** `usuarios.codigo` (único), `materias.docente_id`, `materias.coordinador_id`, `practicas.materia_id`, `asistencias.practica_id`, `asistencias.alumno_id`

---

## Fase 6 — Matriculación facial de alumnos
*(Ya construida y probada — DeepFace + Facenet, captura en vivo, sin subir fotos. Permitida para coordinador, docente y admin.)*

---

## Fase 7 — Servicio de identificación facial
*(Ya construido y probado — similitud coseno, umbral 0.60 validado contra la tabla oficial de DeepFace.)*

**Pendiente:** filtrar los candidatos a los `alumnos_ids` de la materia de la práctica activa, en vez de comparar contra todos los alumnos del sistema.

---

## Fase 8 — Servicio de YOLO por área
*(Sin cambios — un modelo por área, cacheado en memoria.)*

**Nota de esta fase, reforzada por la simplificación de hoy:** el PPE que evalúa `compliance_engine` para una práctica se obtiene consultando `practices` por el `area` de la materia — nunca hay que sincronizar nada adicional entre modelo y materia, porque la fuente de verdad es una sola.

---

## Fase 9 — Captura de video con OpenCV
*(Sin cambios.)*

---

## Fase 10 — Seguimiento de personas con ByteTrack
*(Sin cambios.)*

---

## Fase 11 — Orquestar el flujo de dos fases dentro de una práctica

- El docente (o el admin, ahora que hereda ese permiso) inicia una práctica → se crea el documento en `practicas`
- Al iniciar, se resuelve `required_ppe` consultando `practices` por el `area` de la materia — un solo lugar de donde sale ese dato, siempre
- **Modo identificación:** compara solo contra los embeddings de `materias.alumnos_ids` de esa materia
- **Confirmación (botón):** fija el `alumno_id` y cambia a modo indumentaria
- **Modo indumentaria:** pipeline ya existente, resultado asociado a `practica_id` + `alumno_id`
- Al resolverse, se guarda la `asistencia`; al finalizar la práctica, `practicas.estado = "finalizada"`

---

## Fase 12 — Reglas de cumplimiento y máquina de estados
*(Sin cambios — ya construida y probada.)*

---

## Fase 13 — WebSockets en tiempo real
*(Sin cambios en los tipos de mensaje ya definidos.)*

---

## Fase 14 — Streaming de video en vivo
*(Sin cambios.)*

---

## Fase 15 — Persistir asistencias con evidencia
*(Sin cambios de mecanismo — documento de `asistencias` con `practica_id`.)*

---

## Fase 16 — Reportes de asistencia por rol

- Cabecera: materia, docente, fecha/hora; resumen de presentes/ausentes/cumplieron/no cumplieron
- Tabla detallada por alumno, con estado de indumentaria por prenda
- **Filtros por rol:** alumno (lo suyo), docente (sus materias), coordinador (sus docentes), admin (todo) — aplicados en el backend según el token, nunca según un parámetro que mande el frontend

---

## Fase 17 — Gestión de materias y control de prácticas

- Endpoint de inscripción: agregar un `alumno_id` existente a `materias.alumnos_ids`
- `POST /practicas` — `require_role("docente")`; el admin pasa automáticamente por la expansión de permisos de la fase 4
- `POST /practicas/{id}/end` — mismo permiso, botón "Finalizar práctica"

---

## Notas de cierre

- Piezas resolubles en paralelo: modelo de medicina, umbrales de frames de la máquina de estados, umbral de similitud facial.
- Fuera de alcance: recuperación de contraseña, múltiples cámaras, robustez/logging/pruebas formales.