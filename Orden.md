## Orden general: primero Mongo, luego el servidor, luego el cliente, y al final disparas la práctica

---

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

Déjala corriendo todo el tiempo. Si la reinicias (por un cambio de código), recuerda que `practica_registry` se vacía en memoria — cualquier práctica "activa" que quede en Mongo de antes queda huérfana.

---

## Terminal 2 — el cliente de WebSocket (tu "frontend de mentira")

```bash
python -m scripts.test_ws_client
```

Ábrela **después** de que uvicorn ya esté corriendo (si no, la conexión falla porque no hay nada escuchando en el puerto 8000 todavía). Déjala abierta y mirando — aquí es donde vas a ver aparecer todos los eventos en vivo, uno por uno, en el orden en que ocurren.

---

## Terminal 3 — donde disparas las acciones, en orden

Con las otras dos ya corriendo, sigue estos pasos en secuencia — es el ciclo completo de una práctica, de principio a fin.

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

**3. Inicia la práctica** — guarda el `_id` que te devuelva, lo vas a usar en los pasos 5 y 7:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/practicas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"materia_id": "6abb4962b4bea1a989cd2541"}'
```

**4. Párate frente a la cámara** — ve a la **Terminal 2** y espera a que llegue el evento `estudiante_identificado`. Guarda el `alumno_id` que trae ese evento, lo necesitas en el siguiente paso.

**5. Confirma la identificación** (usa el `_id` del paso 3 y el `alumno_id` del paso 4):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/practicas/<ID_DEL_PASO_3>/confirmar \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"alumno_id": "<ALUMNO_ID_DEL_PASO_4>"}'
```

**6. Mantente frente a la cámara unos segundos** — en la Terminal 2 deberías ver `fase_cambiada` a `"indumentaria"`, varios `detecciones_frame` seguidos, y al final `asistencia_registrada` junto con `fase_cambiada` de vuelta a `"identificacion"`. Ahí vuelve a quedar lista para identificar al siguiente alumno — repite los pasos 4-6 si quieres probar con más de uno.

**7. Cuando termines, verifica cuál práctica sigue activa** (así nunca dependes de tu memoria para el `_id` correcto):
```bash
curl http://127.0.0.1:8000/api/v1/practicas/active -H "Authorization: Bearer $TOKEN"
```
Usa el `_id` que devuelve **este** comando para el siguiente paso — es la fuente de verdad, no lo que recuerdes del paso 3.

**8. Finaliza la práctica**, con exactamente ese `_id`:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/practicas/<ID_DEL_PASO_7>/end \
  -H "Authorization: Bearer $TOKEN"
```

**9. Confirma que todo cerró bien:** en la Terminal 2, que los eventos dejaron de llegar; en la Terminal 3, que `/practicas/active` vuelve a dar `null`:
```bash
curl http://127.0.0.1:8000/api/v1/practicas/active -H "Authorization: Bearer $TOKEN"
```