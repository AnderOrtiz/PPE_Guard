# PPE_Guard — Guía para construir el frontend (React + WebSockets)

Todo lo que necesita saber quien vaya a hacer el frontend de este backend: rutas, qué recibe y qué devuelve cada una, permisos por rol, eventos del WebSocket, video en vivo y las trampas que no se ven a simple vista.

Está escrita a partir del código actual (`app/`), no de los roadmaps. Si algo de aquí contradice a `Road map frontend.md`, vale esto.

---

## 1. Datos de conexión

| Qué | Valor |
|---|---|
| Base HTTP | `http://localhost:8000` |
| Prefijo de la API REST | `/api/v1` |
| WebSocket | `ws://localhost:8000/ws/detections` (fuera de `/api/v1`) |
| Video en vivo (MJPEG) | `http://localhost:8000/api/v1/stream` |
| Archivos estáticos (evidencias) | `http://localhost:8000/static/...` |
| Swagger | `http://localhost:8000/docs` |

**CORS:** el backend solo acepta estos orígenes (`app/core/config.py`):

- `http://localhost:5173` (Vite)
- `http://localhost:3000`

Abre el frontend en `localhost`, no en `127.0.0.1`: son orígenes distintos y el segundo queda bloqueado. Si usas otro puerto, hay que agregarlo a `ALLOWED_ORIGINS`.

Variables sugeridas en el frontend (`.env` de Vite):

```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/detections
```

---

## 2. Cosas que hay que saber antes de escribir código

1. **El id llega como `_id`, no como `id`.** Todos los modelos que salen de Mongo (`UsuarioOut`, `MateriaInDB`, `PracticaInDB`, `AsistenciaInDB`, `PracticeInDB`, `AlumnoEnMateriaOut`) se serializan con el alias. Es un string de 24 caracteres hexadecimales.
2. **Las fechas de la API REST vienen en UTC pero sin zona horaria** (`"2026-10-06T14:02:11.532000"`, sin `Z`). `new Date()` las interpretaría como hora local. Hay que parsearlas como UTC (ver `parseFechaApi` en la sección 9). Los `timestamp` del WebSocket sí traen `+00:00`.
3. **La cámara es la del servidor, no la del navegador.** El frontend nunca pide `getUserMedia` ni sube imágenes. El registro facial y la práctica usan la cámara conectada a la máquina donde corre el backend.
4. **Solo puede haber una práctica activa en todo el servidor**, sin importar el docente.
5. **El WebSocket y el stream de video no piden token.** El resto de la API sí (salvo `/health`, `/practices` y `/auth/login`).
6. **Los errores siempre tienen la forma `{ "detail": ... }`.** `detail` es un string en los errores del backend, y un arreglo de objetos en los 422 automáticos de validación de FastAPI (campo faltante, tipo incorrecto).
7. **Los permisos los aplica el backend.** Ocultar botones según el rol es solo para que la interfaz tenga sentido.

---

## 3. Autenticación

### `POST /api/v1/auth/login` — público

Body:

```json
{ "codigo": "DOC001", "password": "cambiar123" }
```

Respuesta `200`:

```json
{ "access_token": "eyJ...", "token_type": "bearer", "rol": "docente", "nombre": "Docente Demo" }
```

Error `401`: `{ "detail": "Código o contraseña incorrectos" }`

### Uso del token

En cada petición protegida:

```
Authorization: Bearer <access_token>
```

- Dura **8 horas**. No hay refresh token ni endpoint de logout: cerrar sesión es borrar el token en el cliente.
- Sin token, o con token inválido o expirado → `401` (`"Token inválido o expirado"`). Ante cualquier `401` fuera del login: limpiar sesión y mandar a `/login`.
- Rol insuficiente → `403` (`"No tienes permiso para esta acción"`).

### El id del usuario no viene en la respuesta del login

No existe `/auth/me`. El id está dentro del JWT; hay que decodificar el payload:

```json
{ "sub": "DOC001", "uid": "6abaac83f1b16007538b67e7", "rol": "docente", "exp": 1790648451 }
```

- `sub` = código, `uid` = `_id` del usuario, `exp` = expiración en segundos Unix.
- Lo necesitas, por ejemplo, para mandar `coordinador_id` al crear un docente.

```ts
export function decodeToken(token: string) {
  const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(payload)) as { sub: string; uid: string; rol: Rol; exp: number };
}
```

### Usuarios de prueba (`python -m scripts.seed_usuarios`)

| Código | Contraseña | Rol |
|---|---|---|
| `ADMIN001` | `cambiar123` | admin |
| `COORD001` | `cambiar123` | coordinador |
| `DOC001` | `cambiar123` | docente |

---

## 4. Roles y permisos

Roles: `alumno`, `docente`, `coordinador`, `admin`. El admin pasa todas las validaciones de rol (hereda coordinador y docente) y además no tiene restricción de "solo lo mío".

| Acción | alumno | docente | coordinador | admin |
|---|:-:|:-:|:-:|:-:|
| Ver sus propias asistencias | ✅ | — | — | — |
| Listar / ver materias | ❌ | solo las que imparte | solo las de su cargo | todas |
| Crear / editar materia | ❌ | ❌ | ✅ (editar: solo las suyas) | ✅ |
| Matricular / quitar alumnos de una materia | ❌ | solo en las suyas | solo en las suyas | ✅ |
| Crear alumno (con captura facial) | ❌ | ✅ | ✅ | ✅ |
| Crear docente | ❌ | ❌ | ✅ | ✅ |
| Crear coordinador | ❌ | ❌ | ❌ | ✅ |
| Ver un usuario por id | ❌ | ✅ | ✅ | ✅ |
| Iniciar / confirmar / finalizar práctica | ❌ | ✅ | ❌ | ✅ |
| Ver asistencias de materias | ❌ | las suyas | las de su cargo | todas |
| Ver reporte de una práctica | ❌ | de sus materias | de su cargo | todos |

---

## 5. Modelos (tipos TypeScript)

Así llega el JSON, tal cual. Las fechas son strings ISO.

```ts
export type Rol = "alumno" | "docente" | "coordinador" | "admin";
export type Area = "civil" | "medicina";

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  rol: Rol;
  nombre: string;
}

export interface UsuarioOut {
  _id: string;
  codigo: string;
  nombre: string;
  rol: Rol;
  carrera: string | null;        // solo alumnos
  facultad: string | null;       // alumnos y docentes
  coordinador_id: string | null; // solo docentes
}

export interface AlumnoEnMateriaOut {
  _id: string;
  codigo: string;
  nombre: string;
  carrera: string | null;
  facultad: string | null;
}

export interface Materia {
  _id: string;
  nombre: string;
  area: Area;
  carrera: string;
  facultad: string;
  aula: string;
  docente_id: string;
  coordinador_id: string;
  alumnos_ids: string[];
}

export interface Practica {
  _id: string;
  materia_id: string;
  docente_id: string;
  fecha: string;
  hora_inicio: string;
  hora_fin: string | null;
  estado: "activa" | "finalizada";
}

export interface Asistencia {
  _id: string;
  practica_id: string;
  alumno_id: string;
  hora_identificacion: string;
  cumplio_indumentaria: boolean;
  faltantes: string[];           // ej. ["Hardhat"]
  evidencia_url: string | null;  // ruta relativa, ver sección 8
}

export interface FilaAsistencia {
  alumno_id: string;
  nombre: string;
  codigo: string;
  hora_identificacion: string | null;   // null si no asistió
  presente: boolean;
  cumplio_indumentaria: boolean | null; // null si no asistió
  faltantes: string[];
  evidencia_url: string | null;
}

export interface ReportePractica {
  practica_id: string;
  materia_nombre: string;
  docente_nombre: string;
  fecha: string;
  hora_inicio: string;
  hora_fin: string | null;
  total_matriculados: number;
  presentes: number;
  ausentes: number;
  cumplieron: number;
  no_cumplieron: number;
  detalle: FilaAsistencia[];
}

// Catálogo de PPE por área
export interface PracticeCatalogo {
  _id: string;
  area: Area;
  nombre: string;
  ppe_requerido: string[];
  created_at: string;
}
```

### Catálogo de PPE (lo que devuelve `GET /practices` tras el seed)

| área | `ppe_requerido` |
|---|---|
| `civil` | `["Hardhat", "Safety Vest"]` |
| `medicina` | `["Mask", "Gloves", "Gorro"]` |

Los nombres son las clases del modelo YOLO, en inglés. Conviene un mapa de traducción en el frontend:

```ts
export const PPE_LABEL: Record<string, string> = {
  Hardhat: "Casco",
  "Safety Vest": "Chaleco",
  Mask: "Mascarilla",
  Gloves: "Guantes",
  Gorro: "Gorro",
};
```

`faltantes` usa esos mismos nombres. Para pintar cada prenda en verde o rojo: toma `ppe_requerido` del área de la materia y marca en rojo las que estén en `faltantes`.

---

## 6. Endpoints REST

Todas las rutas llevan el prefijo `/api/v1`. "Auth" indica qué rol exige el backend (el admin siempre pasa).

### 6.1 Públicos

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/health` | `{ "status": "ok", "mongo": "connected" }` · `503` si Mongo no responde |
| GET | `/practices` | `PracticeCatalogo[]` |
| GET | `/stream` | Video MJPEG (sección 8) |
| POST | `/auth/login` | `TokenResponse` |

### 6.2 Usuarios

| Método | Ruta | Auth | Body | Devuelve |
|---|---|---|---|---|
| POST | `/usuarios/coordinadores` | admin | `{ codigo, password, nombre }` | `UsuarioOut` |
| POST | `/usuarios/docentes` | coordinador | `{ codigo, password, nombre, facultad, coordinador_id }` | `UsuarioOut` |
| POST | `/usuarios/alumnos` | coordinador, docente | `{ codigo, password, nombre, carrera, facultad }` | `UsuarioOut` |
| GET | `/usuarios?rol=` | coordinador, docente | query opcional `rol`: `alumno` \| `docente` \| `coordinador` | `UsuarioOut[]`. El coordinador ve sus docentes y los alumnos de sus materias; el docente, los alumnos de sus materias; el admin, todos |
| GET | `/usuarios/{usuario_id}` | coordinador, docente | — | `UsuarioOut`. Misma visibilidad que el listado (más uno mismo); fuera de ella responde `403` |

Errores:

- `409` — `"Ya existe un usuario con ese código"` (los tres POST).
- `422` — `"coordinador_id inválido"` / `"usuario_id inválido"` (no es un ObjectId).
- `404` — `"El coordinador indicado no existe"` / `"El usuario indicado no existe"`.

**Crear alumno captura el rostro en ese momento con la cámara del servidor.** Consecuencias para la UI:

- Antes de enviar, mostrar las indicaciones ("mira a la cámara", "quédate quieto", "solo una persona en cuadro").
- La petición tarda varios segundos (abrir cámara + calcular el vector facial). Mostrar estado de carga y deshabilitar el botón.
- `422` — `"No se detectó exactamente un rostro. Asegúrate de que solo una persona esté frente a la cámara."` → permitir reintentar sin perder el formulario.
- `500` si el servidor no puede abrir la cámara.
- El rostro se registra una sola vez; luego el alumno se matricula en las materias por su código.

Al crear un docente, un coordinador debe mandar su propio id en `coordinador_id` (el `uid` del JWT).

### 6.3 Materias

| Método | Ruta | Auth | Body / query | Devuelve |
|---|---|---|---|---|
| POST | `/materias` | coordinador | `{ nombre, area, carrera, facultad, aula, docente_id }` | `Materia` |
| GET | `/materias` | coordinador, docente | query opcional `docente_id` | `Materia[]` |
| GET | `/materias/{materia_id}` | coordinador, docente | — | `Materia` |
| PATCH | `/materias/{materia_id}` | coordinador | cualquier subconjunto de `{ nombre, carrera, facultad, aula }` | `Materia` |
| POST | `/materias/{materia_id}/alumnos` | coordinador, docente | `{ codigo }` | `Materia` actualizada |
| GET | `/materias/{materia_id}/alumnos` | coordinador, docente | — | `AlumnoEnMateriaOut[]` |
| DELETE | `/materias/{materia_id}/alumnos/{alumno_id}` | coordinador, docente | — | `Materia` actualizada |

Notas:

- `area` solo admite `"civil"` o `"medicina"`, y **no se puede cambiar** después (tampoco `docente_id`).
- Al crear, `coordinador_id` no se envía: el backend lo copia del docente elegido.
- `GET /materias` ya filtra por rol: el docente recibe las suyas (el query `docente_id` se ignora), el coordinador las de su cargo, el admin todas.
- Matricular es por **código** del alumno; quitar es por **`_id`** del alumno.

Errores:

- `422` — `"materia_id inválido"` / `"docente_id inválido"`.
- `404` — `"La materia indicada no existe"`, `"El docente indicado no existe"`, `"No existe un alumno con ese código"`, `"Ese alumno no está matriculado en esta materia"`.
- `403` — la materia no es tuya (docente que no la imparte, coordinador de otro cargo).
- `409` — `"El alumno ya está matriculado en esta materia"`.
- `400` — PATCH sin ningún campo.

### 6.4 Prácticas (sesión en vivo)

| Método | Ruta | Auth | Body | Devuelve |
|---|---|---|---|---|
| POST | `/practicas` | docente | `{ materia_id }` | `Practica` (estado `"activa"`) |
| GET | `/practicas/active` | docente | — | `Practica` o `null` |
| POST | `/practicas/{practica_id}/confirmar` | docente | `{ alumno_id }` | `{ "fase": "indumentaria", "alumno_id": "..." }` |
| POST | `/practicas/{practica_id}/end` | docente | — | `Practica` (estado `"finalizada"`, con `hora_fin`) |

Errores:

- `POST /practicas`
  - `409` — `"Ya hay una práctica en curso; finalízala antes de iniciar otra"`.
  - `403` — la materia no es del docente.
  - `404` — la materia no existe, o no hay PPE configurado para su área.
  - `500` — el servidor no pudo abrir la cámara.
- `POST .../confirmar`
  - `404` — `"No hay una práctica activa con ese id"`.
  - `409` — `"Ese alumno no es el último identificado, o la práctica ya está en modo indumentaria"`.
- `POST .../end`
  - `409` — `"Esta práctica ya fue finalizada"`.
  - `403` — la práctica es de otro docente.
  - `404` / `422` — id inexistente o inválido.

Iniciar la práctica enciende la cámara del servidor y arranca la detección; finalizarla la apaga.

### 6.5 Asistencias y reportes

| Método | Ruta | Auth | Query | Devuelve |
|---|---|---|---|---|
| GET | `/asistencias` | cualquier usuario logueado | `materia_id`, `docente_id`, `fecha_desde`, `fecha_hasta` (todos opcionales) | `Asistencia[]`, de la más reciente a la más antigua |
| GET | `/practicas/{practica_id}/reporte` | docente, coordinador | — | `ReportePractica` |

`GET /asistencias` según el rol:

- **alumno:** solo las suyas. Los filtros `materia_id` y `docente_id` se ignoran; los de fecha sí aplican.
- **docente:** las de sus materias; puede acotar con `materia_id`.
- **coordinador / admin:** las de su alcance; pueden acotar con `docente_id` y `materia_id`.
- `fecha_desde` / `fecha_hasta` son datetimes ISO (`2026-10-01T00:00:00Z`) y filtran por `hora_identificacion`. Usa `toISOString()`.
- Sin resultados devuelve `[]`, no un error.

`GET .../reporte` incluye a **todos** los matriculados de la materia: los que no asistieron salen con `presente: false`, `hora_identificacion: null` y `cumplio_indumentaria: null`. Las métricas de cabecera (`presentes`, `ausentes`, `cumplieron`, `no_cumplieron`) ya vienen calculadas. Errores: `422` id inválido, `404` práctica o materia inexistente, `403` fuera de tu alcance.

---

## 7. WebSocket — eventos en tiempo real

**URL:** `ws://localhost:8000/ws/detections`

- No pide token ni parámetros.
- Es de un solo sentido: el servidor emite, el cliente solo escucha. No hace falta enviar nada.
- Cada mensaje es un JSON con el campo `evento` como discriminador.
- Es un broadcast global: todos los clientes conectados reciben lo mismo. Filtra por `practica_id` cuando el evento lo trae.
- Al conectar **no se recibe ningún estado inicial**: solo llegan los eventos que ocurran a partir de ese momento.
- Solo hay eventos mientras exista una práctica activa.

### Ciclo de una práctica

```
POST /practicas
      │
      ▼
┌─────────────────── fase: identificacion ───────────────────┐
│  el servidor busca un rostro cada ~1 s                     │
│  ── evento: estudiante_identificado ──▶ mostrar tarjeta    │
│                                         + botón Confirmar  │
└──────────────────────────┬─────────────────────────────────┘
                           │ POST /practicas/{id}/confirmar { alumno_id }
                           ▼
┌─────────────────── fase: indumentaria (6 s fijos) ─────────┐
│  ── evento: fase_cambiada (fase: "indumentaria")           │
│  ── evento: detecciones_frame  (cada ~0.3 s) ▶ dibujar     │
│                                                 cajas      │
│  ── evento: asistencia_registrada ▶ mostrar resultado      │
│  ── evento: fase_cambiada (fase: "identificacion")         │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
              vuelve a identificacion (siguiente alumno)
                           │
                POST /practicas/{id}/end
```

### Eventos

```ts
export type EventoWS =
  | EstudianteIdentificado
  | FaseCambiada
  | DeteccionesFrame
  | AsistenciaRegistrada;

export interface EstudianteIdentificado {
  evento: "estudiante_identificado";
  practica_id: string;
  alumno_id: string;
  nombre: string;
  codigo: string;
  confianza: number;   // similitud facial, de 0.60 a 1
  timestamp: string;
}

export interface FaseCambiada {
  evento: "fase_cambiada";
  practica_id: string;
  fase: "identificacion" | "indumentaria";
  alumno_id?: string;  // solo viene cuando fase === "indumentaria"
  timestamp: string;
}

export interface DeteccionesFrame {
  evento: "detecciones_frame";   // este evento NO trae practica_id
  frame_width: number;           // píxeles del frame original (ancho máx. 640)
  frame_height: number;
  items: Deteccion[];
  timestamp: string;
}

export interface Deteccion {
  class_name: string;        // "Person", "Hardhat", "NO-Hardhat", "Safety Vest", ...
  confidence: number;        // 0 a 1
  track_id: number | null;
  bbox_norm: [number, number, number, number]; // [x1, y1, x2, y2] normalizado 0–1
  is_violation: boolean;     // true si class_name empieza con "NO-"
}

export interface AsistenciaRegistrada {
  evento: "asistencia_registrada";
  practica_id: string;
  alumno_id: string;
  cumplio_indumentaria: boolean;
  faltantes: string[];
  evidencia_url: string | null;  // solo hay foto cuando no cumplió
  timestamp: string;
}
```

### Detalles de comportamiento que afectan la UI

- **`estudiante_identificado` solo se emite cuando cambia la persona.** Si el mismo alumno sigue frente a la cámara, no se repite.
- **No hay evento cuando el rostro se pierde.** Si el alumno se retira, el servidor olvida la identificación en silencio y la tarjeta del frontend queda desactualizada. Si el docente pulsa Confirmar en ese estado, llega un `409`: en ese caso, limpiar la tarjeta y avisar que el alumno vuelva a mirar a la cámara.
- **Solo se puede confirmar al último identificado**, y solo en fase `identificacion`. Deshabilita el botón Confirmar durante `indumentaria`.
- **La revisión de indumentaria dura 6 segundos fijos.** Sirve para mostrar una cuenta regresiva desde que llega `fase_cambiada` con `indumentaria`.
- Al terminar llegan seguidos `asistencia_registrada` y `fase_cambiada` (a `identificacion`). Al volver a `identificacion`, limpia las cajas del overlay y la tarjeta del alumno.
- Si se confirma dos veces al mismo alumno en una práctica, se guardan dos asistencias; el reporte muestra solo una. Conviene marcar en la UI a los que ya pasaron.
- El alumno solo se reconoce si está **matriculado en la materia** de la práctica. Los alumnos matriculados después de iniciar la práctica no se reconocen hasta iniciar otra.

### Hook de React

```tsx
import { useEffect, useRef } from "react";

export function useDetectionsSocket(onEvento: (e: EventoWS) => void, activo = true) {
  const handler = useRef(onEvento);
  handler.current = onEvento;

  useEffect(() => {
    if (!activo) return;

    let ws: WebSocket | null = null;
    let reintento: ReturnType<typeof setTimeout>;
    let cerrado = false;

    const conectar = () => {
      ws = new WebSocket(import.meta.env.VITE_WS_URL);
      ws.onmessage = (msg) => handler.current(JSON.parse(msg.data));
      ws.onclose = () => {
        if (!cerrado) reintento = setTimeout(conectar, 2000);
      };
    };
    conectar();

    return () => {
      cerrado = true;
      clearTimeout(reintento);
      ws?.close();
    };
  }, [activo]);
}
```

- La función de limpieza es obligatoria: en desarrollo, `StrictMode` monta el efecto dos veces y sin ella quedan dos conexiones (eventos duplicados).
- `detecciones_frame` llega unas 3 veces por segundo. Guarda las detecciones en un `ref` y dibuja en un `<canvas>`, o al menos aíslalas en un componente propio, para no re-renderizar toda la pantalla.

Para probar el socket sin frontend: `python -m scripts.test_ws_client`.

---

## 8. Video en vivo y evidencias

### Stream

```tsx
<img src={`${import.meta.env.VITE_API_URL}/api/v1/stream`} alt="Cámara en vivo" />
```

- Es MJPEG (`multipart/x-mixed-replace`), a unos 8 fps. Va en un `<img>`, no en `<video>`. No necesita token.
- **Solo hay imagen mientras hay una práctica activa.** Sin práctica, la petición queda abierta sin enviar nada. Monta el `<img>` únicamente cuando haya práctica y desmóntalo al finalizar (para cerrar la conexión).
- El video llega limpio, sin cajas dibujadas. Las cajas se pintan en el frontend con `detecciones_frame`.

### Overlay de cajas

Como `bbox_norm` está normalizado, basta multiplicar por el tamaño con que se muestra la imagen:

```tsx
function Overlay({ items }: { items: Deteccion[] }) {
  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <img src={`${import.meta.env.VITE_API_URL}/api/v1/stream`} style={{ display: "block", width: "100%" }} />
      {items.map((d, i) => {
        const [x1, y1, x2, y2] = d.bbox_norm;
        return (
          <div
            key={d.track_id ?? i}
            style={{
              position: "absolute",
              left: `${x1 * 100}%`,
              top: `${y1 * 100}%`,
              width: `${(x2 - x1) * 100}%`,
              height: `${(y2 - y1) * 100}%`,
              border: `2px solid ${d.is_violation ? "red" : "limegreen"}`,
            }}
          />
        );
      })}
    </div>
  );
}
```

El contenedor debe medir exactamente lo mismo que la imagen (sin `object-fit: cover` ni padding), o las cajas quedan desplazadas.

### Evidencias

`evidencia_url` es una ruta relativa del servidor, por ejemplo:

```
/static/evidence/2026-10-06/<practica_id>-<alumno_id>.jpg
```

Hay que anteponerle la base: `` `${VITE_API_URL}${evidencia_url}` ``. Solo existe cuando el alumno **no** cumplió; la foto ya trae dibujada la caja roja y el texto de lo que falta. No requiere token.

---

## 9. Cliente HTTP base

```ts
const API = `${import.meta.env.VITE_API_URL}/api/v1`;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("token");

  const res = await fetch(`${API}${ruta}`, {
    ...opciones,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opciones.headers,
    },
  });

  if (res.status === 401 && ruta !== "/auth/login") {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const detail = data?.detail;
    // detail es string en errores del backend, y arreglo en los 422 de validación
    const mensaje = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg).join(", ")
        : "Error inesperado";
    throw new ApiError(res.status, mensaje);
  }

  return data as T;
}

// Las fechas REST llegan en UTC sin zona; las del WebSocket ya traen +00:00
export function parseFechaApi(valor: string): Date {
  const tieneZona = /(Z|[+-]\d{2}:\d{2})$/.test(valor);
  return new Date(tieneZona ? valor : `${valor}Z`);
}
```

Ejemplos de uso:

```ts
const sesion = await api<TokenResponse>("/auth/login", {
  method: "POST",
  body: JSON.stringify({ codigo, password }),
});

const materias = await api<Materia[]>("/materias");
const practica = await api<Practica>("/practicas", { method: "POST", body: JSON.stringify({ materia_id }) });
const activa = await api<Practica | null>("/practicas/active");
```

Los mensajes de `detail` ya vienen en español y redactados para el usuario: se pueden mostrar tal cual en un toast.

---

## 10. Pantallas sugeridas

| Ruta | Rol | Qué hace | Endpoints |
|---|---|---|---|
| `/login` | todos | Formulario código + contraseña; redirige según `rol` | `POST /auth/login` |
| `/materias` | docente, coordinador, admin | Lista de materias | `GET /materias` |
| `/materias/nueva` | coordinador, admin | Crear materia | `POST /materias` |
| `/materias/:id` | docente, coordinador, admin | Detalle, alumnos matriculados, matricular por código, quitar, editar | `GET /materias/{id}`, `GET/POST/DELETE .../alumnos`, `PATCH /materias/{id}` |
| `/usuarios/nuevo` | según tabla de permisos | Alta de alumno (con captura facial), docente o coordinador | `POST /usuarios/*` |
| `/practica` | docente, admin | Sesión en vivo: video, overlay, tarjeta del identificado, Confirmar, Finalizar | `POST /practicas`, `GET /practicas/active`, `.../confirmar`, `.../end`, WebSocket, stream |
| `/asistencias` | docente, coordinador, admin | Historial con filtros | `GET /asistencias` |
| `/practicas/:id/reporte` | docente, coordinador, admin | Cabecera con métricas + tabla por alumno | `GET /practicas/{id}/reporte` |
| `/mis-asistencias` | alumno | Su historial | `GET /asistencias` |

### Flujo de la pantalla de práctica

1. Al entrar, `GET /practicas/active`. Si devuelve una práctica, retomarla; si devuelve `null`, mostrar el selector de materia y el botón Iniciar.
2. Iniciar → `POST /practicas`. Guardar el `_id`.
3. Conectar el WebSocket y montar el `<img>` del stream.
4. Con `estudiante_identificado`: mostrar nombre, código y confianza, y habilitar Confirmar.
5. Confirmar → `POST /practicas/{id}/confirmar` con ese `alumno_id`.
6. Durante `indumentaria`: cuenta regresiva de 6 s y cajas en vivo.
7. Con `asistencia_registrada`: mostrar el resultado (cumplió / qué faltó / foto de evidencia) y sumar al alumno a la lista de "ya registrados".
8. Finalizar → `POST /practicas/{id}/end`, cerrar socket, desmontar el stream y ofrecer el enlace al reporte.

Para mostrar el nombre de la materia y el PPE requerido en esta pantalla: `GET /materias/{materia_id}` y `GET /practices` (filtrando por `area`).

---

## 11. Limitaciones actuales del backend

Cosas que el frontend va a necesitar y hoy no existen. Vale la pena resolverlas en el backend antes de construir esas pantallas.

| Qué falta | A qué afecta | Mientras tanto |
|---|---|---|
| **Listar las prácticas de una materia** | No hay forma directa de llegar al reporte de una práctica pasada | `GET /asistencias?materia_id=...` y agrupar por `practica_id`. Las prácticas sin ninguna asistencia no aparecen |
| **Endpoints para el alumno** | Sus asistencias solo traen `practica_id` y `alumno_id`; no puede consultar materias, prácticas ni usuarios (`403`), así que no hay cómo mostrarle el nombre de la materia | Mostrar fecha, resultado, faltantes y evidencia |
| **`/auth/me` y refresh de token** | El id y los datos del usuario | Decodificar el JWT; guardar `nombre` y `rol` del login |
| **Estado inicial en el WebSocket** | Si se recarga la página en plena revisión, no se sabe la fase actual ni a quién se identificó | Asumir `identificacion` y esperar el siguiente evento (como mucho 6 s) |
| **Recuperar la práctica tras reiniciar el servidor** | `GET /practicas/active` devuelve `null` aunque en la base haya quedado una práctica `activa`, y esa queda huérfana | Guardar el `_id` de la práctica en `localStorage` para poder llamar a `/end` |
| **Práctica activa por docente** | `/practicas/active` devuelve la práctica en curso aunque sea de otro docente | Comparar `docente_id` con el `uid` propio y mostrar "hay otra práctica en curso" |
| **Modelo de medicina** | En `weights/` solo está `civil.pt`; una práctica de área `medicina` inicia pero no detecta indumentaria | Probar con materias de área `civil` |
| **Autenticación en WebSocket, stream y evidencias** | Cualquiera en la red puede verlos | Aceptable en local; pendiente para producción |

---

## 12. Cómo levantar el backend para desarrollar

```bash
docker compose up -d                 # MongoDB
python -m scripts.seed_practices     # catálogo de PPE
python -m scripts.seed_usuarios      # ADMIN001, COORD001, DOC001
uvicorn app.main:app --reload        # http://localhost:8000
```

Detalle completo de instalación en `readme.md`. Para una primera prueba de punta a punta:

1. Login como `COORD001` → crear una materia de área `civil` con el `_id` de `DOC001` como `docente_id`.
2. Crear un alumno (frente a la cámara del servidor) y matricularlo en la materia por su código.
3. Login como `DOC001` → iniciar la práctica de esa materia y seguir el flujo de la sección 10.
