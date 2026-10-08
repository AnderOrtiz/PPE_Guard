# PPE_Guard

Sistema de reconocimiento facial y verificación de indumentaria de seguridad (PPE) para prácticas universitarias, usando YOLO (Ultralytics) para detección y DeepFace para identificación de estudiantes.

---

## Requisitos previos

- **Miniconda** instalado
- **Docker Desktop** instalado (solo para la base de datos — el backend nunca corre dentro de Docker)
- Permisos de cámara otorgados a tu terminal/IDE (Ajustes del Sistema → Privacidad y Seguridad → Cámara)

---

## 1. Clonar el proyecto y ubicarse en la raíz

```bash
git clone https://github.com/AnderOrtiz/PPE_Guard/tree/gemini

cd PPE_Guard
```

Todos los comandos de este documento asumen que estás parado en la raíz del proyecto.

---

## 2. Crear el entorno de conda

```bash
conda create -n yolo python=3.11 -y
conda activate yolo
```

Actívalo cada vez que trabajes en el proyecto — todo lo demás asume que `yolo` está activo.

---

## 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

Dos dependencias adicionales que no siempre quedan explícitas en algunos entornos, instálalas si el import falla al arrancar:

```bash
pip install lapx tf-keras
```

- `lapx` — lo necesita el tracking de Ultralytics (ByteTrack/BoT-SORT).
- `tf-keras` — lo necesita DeepFace para funcionar con versiones recientes de TensorFlow.

La primera vez que el backend use reconocimiento facial, DeepFace **descarga el modelo** (`Facenet`, ~90MB) desde internet — necesitas conexión esa primera vez; después queda cacheado en `~/.deepface/weights`.

---

## 4. Configurar el `.env`

Crea un archivo `.env` en la raíz con este contenido, ajustando lo que corresponda:

```dotenv
# App
APP_NAME=PPE_Guard
DEBUG=True

# MongoDB — localhost porque el backend corre fuera de Docker
MONGO_HOST=localhost
MONGO_DB_NAME=PPE_Guard_db
MONGO_DB_PORT=27017
MONGO_USERNAME=
MONGO_PASSWORD=

# Mongo Express
EXPRESS_DB_PORT=8181

# Autenticación (JWT)
JWT_SECRET_KEY=cambia-esto-por-algo-largo-y-aleatorio
JWT_EXPIRE_MINUTES=480

# Cifrado de los rostros registrados
FACE_EMBEDDING_KEY=
```

**Genera un valor real para `JWT_SECRET_KEY`** — no lo dejes con el texto de ejemplo:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copia lo que imprima y pégalo como valor de `JWT_SECRET_KEY`.

**Genera también `FACE_EMBEDDING_KEY`**, la clave con la que se cifran los rostros de los alumnos en la base:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Guarda una copia de esta clave en un lugar seguro. Si se pierde o se cambia, los rostros ya registrados no se pueden descifrar y hay que volver a registrar a todos los alumnos. Sin ella el backend no arranca.

---

## 5. Colocar los pesos del modelo YOLO

Los modelos entrenados van en:

```
PPE_Guard/
└── weights/
    ├── civil.pt
    └── medicina.pt   (cuando exista)
```

No renombres ni recomprimas manualmente estos archivos — un `.pt` es un zip interno de PyTorch, y manipularlo fuera de una transferencia directa puede corromperlo.

---

## 6. Levantar la base de datos (Docker)

```bash
docker compose up -d
```

Esto levanta **solo** `mongo` y `mongo-express` — nunca el backend.

Verifica que están corriendo:
```bash
docker compose ps
```

Mongo Express queda disponible en `http://localhost:8181`.

---

## 7. Poblar datos iniciales (seeds)

Con Mongo ya corriendo, y el entorno `yolo` activo:

```bash
python -m scripts.inicializar
```

Crea lo mínimo para usar el sistema sobre una base vacía: un admin (`ADMIN001` / `cambiar123`) y el catálogo de PPE por área. Todo lo demás (coordinadores, docentes, materias, alumnos) se crea desde la API con ese admin. Para elegir las credenciales: `python -m scripts.inicializar <codigo> <contraseña> "<nombre>"`.

Para un entorno de pruebas con usuarios de ejemplo de cada rol, en su lugar:

```bash
python -m scripts.seed_practices
python -m scripts.seed_usuarios
```

El primero crea el catálogo de PPE por área (civil/medicina). El segundo crea usuarios de prueba:

| Código | Contraseña | Rol |
|---|---|---|
| `ADMIN001` | `cambiar123` | admin |
| `COORD001` | `cambiar123` | coordinador |
| `DOC001` | `cambiar123` | docente |

Cambia estas contraseñas antes de usar el sistema fuera de un entorno de pruebas.

---

## 8. Levantar el backend

```bash
uvicorn app.main:app --reload
```

El servidor queda disponible en `http://127.0.0.1:8000`.

---

## 9. Verificar que todo funciona

- **Documentación interactiva:** `http://127.0.0.1:8000/docs`
- **Salud del backend + Mongo:** `GET /api/v1/health` → `{"status": "ok", "mongo": "connected"}`
- **Login de prueba:** `POST /api/v1/auth/login` con `{"codigo": "DOC001", "password": "cambiar123"}` → debe devolver un `access_token`
- **Video en vivo:** con una práctica activa, abre `http://127.0.0.1:8000/api/v1/stream?token=<access_token>` en el navegador (token de docente, coordinador o admin) — deberías ver el feed de la cámara

---

## Estructura del proyecto

```
PPE_Guard/
├── app/
│   ├── api/v1/           # Endpoints REST y router
│   ├── core/              # Config, conexión a Mongo, seguridad (JWT), puente async
│   ├── models/            # Esquemas Pydantic
│   ├── services/          # Lógica de negocio (YOLO, cámara, reconocimiento facial, orquestador, etc.)
│   ├── websockets/        # Manager y router de WebSocket
│   └── main.py
├── weights/               # Pesos de los modelos YOLO (.pt) — no se suben a git
├── static/evidence/       # Imágenes de evidencia generadas en runtime — no se suben a git
├── scripts/               # Scripts de prueba y de seed, se corren con `python -m scripts.<nombre>`
├── compose.yaml           # Solo Mongo + Mongo Express
├── requirements.txt
└── .env                   # No se sube a git
```

---

## Problemas comunes

**`ModuleNotFoundError: No module named 'app'` al correr un script de `scripts/`**
Corre el script como módulo, desde la raíz del proyecto, no como archivo suelto:
```bash
python -m scripts.nombre_del_script
```

**El login da "Usuario o contraseña incorrectos" con credenciales que deberían ser válidas**
Verifica en Mongo Express que la colección `usuarios` realmente tenga el documento esperado, y que no haya quedado vacía o con datos de una prueba anterior a medio insertar.

**Un token JWT copiado a mano da "inválido o expirado" aunque acabe de generarse**
Un JWT tiene tres partes separadas por puntos (`encabezado.payload.firma`). Es fácil que el copy-paste pierda un carácter o un punto. Evita copiarlo a mano — encadénalo directo desde el login:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"codigo": "DOC001", "password": "cambiar123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

**La cámara no captura nada útil al abrirla por primera vez (frame negro o vacío)**
Es normal — la cámara necesita unos frames de "calentamiento" antes de dar una imagen utilizable; el código ya contempla esto internamente.

**`RuntimeError: ... file in archive is not in a subdirectory` al cargar un modelo `.pt`**
El archivo de pesos está corrupto (zip interno mezclado con otro archivo). Verifica con `unzip -l weights/civil.pt` — si ves dos carpetas raíz distintas en el listado, pide que te reenvíen el archivo original sin recomprimirlo.