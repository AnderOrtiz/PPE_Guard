## Orden general: primero Mongo, luego el servidor, luego el cliente, y al final disparas la práctica

## Terminal 0 (antes de las 3 — solo si no lo tienes corriendo ya)

```bash
docker compose up -d
```

Levanta Mongo y Mongo Express. Solo hace falta una vez, no en cada prueba.

---

## Terminal 1 — el servidor FastAPI

```bash
uvicorn app.main:app --reload
```

Déjala corriendo todo el tiempo. Si la reinicias (por un cambio de código), recuerda que `practica_registry` se vacía en memoria — cualquier práctica "activa" que quede en Mongo de antes queda huérfana, como ya viste.

---

## Terminal 2 — el cliente de WebSocket (tu "frontend de mentira")

```bash
python -m scripts.test_ws_client
```

Ábrela **después** de que uvicorn ya esté corriendo (si no, la conexión falla porque no hay nada escuchando en el puerto 8000 todavía). Déjala abierta y mirando — aquí es donde vas a ver aparecer los eventos en vivo.

---

## Terminal 3 — donde disparas las acciones (login, iniciar, consultar, finalizar)

Con las otras dos ya corriendo, en este orden:

**1. Login y guardar el token:**
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"codigo": "DOC001", "password": "cambiar123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

**2. Confirma que no hay ninguna práctica activa todavía** (deberías ver `null`):
```bash
curl http://127.0.0.1:8000/api/v1/practicas/active -H "Authorization: Bearer $TOKEN"
```

**3. Inicia la práctica** (copia el `_id` que te devuelva — lo vas a necesitar en el paso 5):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/practicas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"materia_id": "6abb4962b4bea1a989cd2541"}'
```

**4. Párate frente a la cámara** — ve a la **Terminal 2** y confirma que empiezan a llegar eventos `estudiante_identificado`.

**5. Verifica cuál práctica está activa** (por si no anotaste el `_id` del paso 3 — así nunca vuelves a adivinar):
```bash
curl http://127.0.0.1:8000/api/v1/practicas/active -H "Authorization: Bearer $TOKEN"
```
Copia el `_id` que te devuelve **este** comando — es la fuente de verdad, no lo que recuerdes de antes.

**6. Finaliza, usando exactamente ese `_id`:**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/practicas/<PEGA_AQUI_EL_ID_DEL_PASO_5>/end \
  -H "Authorization: Bearer $TOKEN"
```

**7. Confirma en la Terminal 2** que los eventos dejaron de llegar, y en la Terminal 3 que `/practicas/active` vuelve a dar `null`:
```bash
curl http://127.0.0.1:8000/api/v1/practicas/active -H "Authorization: Bearer $TOKEN"
```


Después de identificarte (Terminal 2 muestra estudiante_identificado con tu alumno_id), dispara en Terminal 3:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/practicas/<practica_id>/confirmar \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"alumno_id": "<el alumno_id que viste en el evento>"}'
```
