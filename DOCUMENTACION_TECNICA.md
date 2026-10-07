# PPE_Guard — Documentación técnica del backend

Cómo funciona el sistema por dentro y por qué está hecho así. Pensada para responder las preguntas de un programador que llega nuevo al proyecto.

- Para **instalar y levantar** el backend: `readme.md`.
- Para **consumir la API** desde el frontend (rutas, tipos, eventos): `FRONTEND.md`.
- Este documento explica el **funcionamiento interno** y los **parámetros ajustables**.

Está escrita a partir del código en `app/`. Si algo aquí contradice al código, vale el código.

---

## Índice

1. [Qué hace el sistema](#1-qué-hace-el-sistema)
2. [Arquitectura general](#2-arquitectura-general)
3. [Contraseñas y hashes](#3-contraseñas-y-hashes)
4. [Tokens de sesión (JWT)](#4-tokens-de-sesión-jwt)
5. [Roles y alcance de los datos](#5-roles-y-alcance-de-los-datos)
6. [La cámara](#6-la-cámara)
7. [Reconocimiento facial](#7-reconocimiento-facial)
8. [Detección de indumentaria](#8-detección-de-indumentaria)
9. [Ciclo de vida de una práctica](#9-ciclo-de-vida-de-una-práctica)
10. [Hilos y el puente asíncrono](#10-hilos-y-el-puente-asíncrono)
11. [WebSocket, video y evidencias](#11-websocket-video-y-evidencias)
12. [Base de datos](#12-base-de-datos)
13. [Parámetros ajustables](#13-parámetros-ajustables)
14. [Limitaciones y riesgos conocidos](#14-limitaciones-y-riesgos-conocidos)
15. [Preguntas frecuentes](#15-preguntas-frecuentes)

---

## 1. Qué hace el sistema

PPE_Guard pasa lista en prácticas de laboratorio y comprueba que cada alumno lleve el equipo de protección personal (EPP, en inglés PPE) que exige su área.

El flujo, en una frase: el docente inicia una práctica, cada alumno se para frente a la cámara, el sistema lo reconoce por el rostro, el docente confirma, y durante 6 segundos el sistema revisa si lleva las prendas requeridas. El resultado queda guardado como una asistencia, con foto de evidencia si no cumplió.

Hay dos modelos de inteligencia artificial, con trabajos distintos:

| Modelo | Para qué | Librería |
|---|---|---|
| Facenet | Saber **quién** es el alumno | DeepFace |
| YOLO | Saber **qué prendas** lleva | Ultralytics |

---

## 2. Arquitectura general

```
                    ┌──────────────────────────── servidor ────────────────────────────┐
  navegador         │                                                                  │
 ┌─────────┐  REST  │  FastAPI ── endpoints ──► MongoDB                                │
 │ React   │◄──────►│     ▲                                                            │
 │         │   WS   │     │ eventos                                                    │
 │         │◄───────│  ConnectionManager ◄── PracticaOrchestrator (hilo propio)        │
 │         │  MJPEG │     ▲                      │        │                            │
 │         │◄───────│  /stream                   ▼        ▼                            │
 └─────────┘        │     ▲                  DeepFace    YOLO                          │
                    │     └──── CameraService (hilo propio) ◄── cámara USB/integrada   │
                    └──────────────────────────────────────────────────────────────────┘
```

| Carpeta | Contenido |
|---|---|
| `app/api/v1/endpoints/` | Las rutas REST, un archivo por recurso |
| `app/api/v1/dependencies.py` | Lectura del token y comprobación de roles |
| `app/core/` | Configuración, conexión a Mongo, seguridad (hash y JWT), puente asíncrono |
| `app/models/` | Esquemas Pydantic: qué entra y qué sale de la API |
| `app/services/` | La lógica: cámara, rostro, YOLO, revisión de prendas, orquestador, evidencias |
| `app/websockets/` | Conexiones WebSocket y difusión de eventos |
| `scripts/` | Seeds y scripts de prueba manual |
| `weights/` | Pesos de los modelos YOLO (`.pt`) |
| `static/evidence/` | Fotos de evidencia generadas en ejecución |

**Punto clave:** la cámara es la del servidor, no la del navegador. El frontend nunca captura ni sube imágenes; solo recibe el video y los eventos.

---

## 3. Contraseñas y hashes

Código: `app/core/security.py`.

Las contraseñas **nunca se guardan en texto plano**. Se guarda un *hash* generado con **bcrypt**, en el campo `password_hash` del usuario.

### Qué es un hash

Es el resultado de pasar la contraseña por una función de un solo sentido: de la contraseña se obtiene el hash, pero del hash no se puede volver a la contraseña. Si alguien roba la base de datos, no obtiene las contraseñas.

### Cómo funciona aquí

**Al crear un usuario** (`hash_password`):

1. bcrypt genera una *sal*: un valor aleatorio distinto para cada usuario.
2. Mezcla la sal con la contraseña y aplica el algoritmo muchas veces.
3. Devuelve un texto que contiene todo junto: versión, costo, sal y hash.

```
$2b$12$N9qo8uLOickgx2ZMRZoMye.IjZAgcfl7p92ldGxad68LJZdL17lhW
 │   │  └────────── sal ───────┘└──────────── hash ───────────┘
 │   └ costo: 2^12 = 4096 rondas
 └ versión de bcrypt
```

**Al iniciar sesión** (`verify_password`): bcrypt lee la sal y el costo del hash guardado, repite el cálculo con la contraseña que escribió el usuario y compara los resultados. Por eso no hace falta guardar la sal en un campo aparte.

### Por qué bcrypt y no un hash común (SHA-256, MD5)

- **Es lento a propósito.** Un SHA-256 se calcula millones de veces por segundo, así que un atacante puede probar contraseñas a esa velocidad. bcrypt tarda décimas de segundo por intento.
- **La sal impide los ataques con tablas precalculadas**, y hace que dos usuarios con la misma contraseña tengan hashes distintos.
- **El costo es ajustable.** Si el hardware mejora, se sube el número de rondas.

### Cosas a saber

- El costo es el que trae la librería por defecto (12). No está parametrizado en `config.py`.
- bcrypt solo considera los primeros **72 bytes** de la contraseña.
- `password_hash` y `face_embedding` nunca salen de la API: el modelo `UsuarioOut` no los incluye.
- No existe todavía un endpoint para cambiar la contraseña.

---

## 4. Tokens de sesión (JWT)

Código: `app/core/security.py`, `app/api/v1/dependencies.py`, `app/api/v1/endpoints/auth.py`.

Al iniciar sesión, el servidor entrega un **JWT** (JSON Web Token): un texto firmado que el cliente manda en cada petición para demostrar quién es.

### Qué lleva dentro

```json
{ "sub": "DOC001", "uid": "6abaac83f1b16007538b67e7", "rol": "docente", "exp": 1790648451 }
```

| Campo | Significado |
|---|---|
| `sub` | Código del usuario |
| `uid` | `_id` del usuario en Mongo |
| `rol` | Rol con el que inició sesión |
| `exp` | Fecha de expiración (segundos Unix) |

### Firma, no cifrado

El token se firma con **HS256** usando `JWT_SECRET_KEY`. La firma garantiza que nadie lo modificó, pero **no lo oculta**: cualquiera puede leer el contenido. Por eso no lleva datos sensibles.

Consecuencia directa: quien conozca `JWT_SECRET_KEY` puede fabricar tokens de cualquier usuario, incluido un admin. Esa clave debe ser larga, aleatoria y distinta en cada entorno.

### Sin estado

El servidor no guarda sesiones: valida cada token solo con la firma y la fecha. Es simple y rápido, pero tiene dos efectos:

- **No se puede revocar un token.** Si se borra un usuario o se le cambia el rol, su token viejo sigue sirviendo hasta que expire (máximo 8 horas).
- **"Cerrar sesión" es borrar el token en el cliente.** No hay endpoint de logout.

Las excepciones son `GET /auth/me` y `POST /auth/refresh`, que sí consultan la base y responden `401` si el usuario ya no existe.

### Renovación

`POST /auth/refresh` entrega un token nuevo con otras 8 horas, siempre que el actual siga vigente. Un token ya expirado no se renueva: hay que volver a iniciar sesión.

### Dónde viaja el token

| Recurso | Cómo se manda | Por qué |
|---|---|---|
| API REST | Header `Authorization: Bearer <token>` | Es lo estándar |
| WebSocket, video, evidencias | Query `?token=<token>` | El navegador no permite mandar headers desde un `WebSocket` ni desde un `<img>` |

El token en la URL queda en el historial del navegador y en los logs del servidor. Es un costo aceptado; ver sección 14.

---

## 5. Roles y alcance de los datos

Roles: `alumno`, `docente`, `coordinador`, `admin`.

### Jerarquía

`require_role(...)` en `dependencies.py` comprueba el rol. El **admin hereda** los permisos de coordinador y docente (`ROLE_EXPANSION`), así que pasa cualquier comprobación de esos roles. No hereda el de alumno.

### "Solo lo mío"

Además del rol, casi todos los endpoints filtran por pertenencia. La regla se repite en todo el código:

| Rol | Qué ve |
|---|---|
| docente | Las materias que imparte (`materias.docente_id`), sus prácticas, los alumnos matriculados en ellas |
| coordinador | Las materias a su cargo (`materias.coordinador_id`), sus docentes (`usuarios.coordinador_id`), los alumnos de esas materias |
| admin | Todo |
| alumno | Sus propias asistencias, materias y fotos de evidencia |

Un detalle importante: **los alumnos no tienen dueño propio**. Su visibilidad se deduce de `alumnos_ids` de las materias. Un alumno recién creado que no está matriculado en ninguna materia solo lo ve el admin.

---

## 6. La cámara

Código: `app/services/camera_service.py`.

### Una sola cámara, un solo servicio

`camera_service` es una instancia única compartida por todo el servidor. De aquí sale la regla de que **solo puede haber una práctica activa a la vez**: hay un solo dispositivo.

### Cómo captura

1. `start()` abre la cámara con OpenCV (`cv2.VideoCapture`).
2. Descarta los primeros 10 frames (*warm-up*): la cámara necesita un momento para ajustar la exposición, y esos frames salen oscuros.
3. Lanza un **hilo propio** que lee frames en bucle a 8 por segundo.
4. Cada frame se reduce a 640 px de ancho y se guarda como "el último frame".

### El último frame, no una cola

El servicio guarda **solo el frame más reciente**. Quien lo pide (`get_latest_frame()`) recibe una copia. No hay cola de frames.

Esto es intencional: si la detección es más lenta que la cámara, se saltan frames en vez de acumular retraso. Siempre se analiza lo que está pasando ahora.

El acceso está protegido con un `Lock`, porque el hilo de captura escribe el frame mientras otros hilos lo leen.

### Quién usa la cámara

| Consumidor | Cuándo |
|---|---|
| Orquestador de la práctica | Durante toda la práctica (rostro y prendas) |
| `GET /stream` | Para mandar el video al navegador |
| `POST /usuarios/alumnos` | Una sola foto, para registrar el rostro |

El registro de un alumno usa `capture_single_frame()`: si la cámara ya está encendida por una práctica, toma el último frame; si no, la abre, captura una foto y la cierra.

### Cuándo está encendida

Solo mientras hay una práctica activa. Se enciende al iniciarla y se apaga al finalizarla. Sin práctica, `/stream` queda abierto sin enviar nada.

---

## 7. Reconocimiento facial

Código: `app/services/face_service.py`.

### La idea: convertir un rostro en números

El modelo **Facenet** recibe la imagen de un rostro y devuelve un *embedding*: una lista de 128 números. Esa lista funciona como una huella: dos fotos de la misma persona dan listas parecidas, y fotos de personas distintas dan listas diferentes.

El sistema **no guarda fotos de los rostros**. Guarda solo esos 128 números, en el campo `face_embedding` del alumno.

### Registro (una sola vez por alumno)

Al crear un alumno (`POST /usuarios/alumnos`):

1. Se captura una foto con la cámara del servidor.
2. DeepFace localiza el rostro y calcula el embedding.
3. Si no hay **exactamente un rostro**, se rechaza con `422`. Cero rostros no sirve, y dos sería ambiguo.
4. El embedding se guarda en Mongo.

### Identificación (durante la práctica)

Cada segundo, mientras la práctica está en fase de identificación:

1. Se toma el último frame y se calcula su embedding.
2. Se compara contra los embeddings de los **alumnos matriculados en esa materia**, no contra todos los del sistema.
3. Se elige el más parecido. Si su similitud es al menos 0.60, es una coincidencia.
4. Si cambió la persona respecto al segundo anterior, se emite el evento `estudiante_identificado`.

Comparar solo contra los matriculados hace la búsqueda más rápida y reduce los falsos positivos: es más difícil confundirse entre 30 personas que entre 3000.

La lista de candidatos se carga **al iniciar la práctica**. Un alumno matriculado después no se reconoce hasta la siguiente práctica.

### Por qué DeepFace y no otras alternativas

Se consideraron tres librerías:

| Librería | Qué es | Por qué sí o por qué no |
|---|---|---|
| **face_recognition** (basada en dlib) | La librería clásica para esto en Python, la que más tutoriales tiene | **Descartada.** Exige compilar dlib desde el código fuente, lo que requiere `cmake` y un compilador de C++ funcionando. Es una fuente habitual de problemas de instalación, sobre todo en Mac |
| **InsightFace** usada directamente | La librería de bajo nivel detrás de los modelos más precisos (la familia ArcFace) | **Descartada.** Es más rápida y precisa, pero obliga a programar a mano la carga de los modelos ONNX, el preprocesamiento de las imágenes y la comparación. Es mucho código propio para algo que no es el centro del proyecto |
| **DeepFace** | Un envoltorio que por debajo puede usar varios modelos (Facenet, VGG-Face, ArcFace y otros) | **Elegida.** Ofrece una sola función simple, `DeepFace.represent()`, y se instala con `pip`, sin compilar nada |

**Por qué ganó DeepFace en este proyecto:**

- **Funciona en CPU, sin tarjeta gráfica.** Permite elegir un modelo liviano (Facenet, el que se usa) en lugar de obligar al más pesado.
- **La población es pequeña (unos 15 alumnos por materia).** Con tan pocos candidatos, la diferencia de precisión entre Facenet y un modelo más pesado como ArcFace no se nota en la práctica.
- **Había un plazo de entrega.** Menos piezas que puedan fallar al instalar significa menos tiempo perdido depurando `cmake` y más tiempo construyendo el sistema. El proyecto trata de PPE y asistencia, no de construir un reconocimiento facial desde cero.

Ventajas adicionales que se aprovechan en el código:

- **Resuelve todo el proceso en una llamada:** detecta el rostro, lo recorta, lo alinea y calcula el embedding.
- **Permite cambiar de modelo con una línea** (`FACE_MODEL_NAME`), sin reescribir código.
- **Publica umbrales ya calibrados** para cada combinación de modelo y métrica; no hubo que calibrar el umbral desde cero.

**El costo de esta elección:**

- **Arrastra TensorFlow como dependencia.** La instalación es más pesada que con InsightFace, y por eso el `readme.md` pide instalar `tf-keras` aparte. El primer arranque del modelo también es lento.
- **El detector de rostros `opencv` que se usa es rápido pero limitado:** falla con rostros de perfil o con poca luz.
- **No escala bien a poblaciones grandes.** Si se pasara de unos 15 a unos 500 alumnos, o hiciera falta más precisión o velocidad, convendría reconsiderar e ir directo a InsightFace, sacrificando la comodidad de la función simple a cambio de más control. Para el alcance actual, ese cambio no se justifica.

### Por qué la similitud del coseno

Para decidir si dos embeddings son de la misma persona hay que medir qué tan parecidos son. La similitud del coseno mide el **ángulo** entre los dos vectores, ignorando su longitud:

```
                 a · b
similitud = ─────────────
             |a| × |b|
```

| Valor | Significado |
|---|---|
| 1 | Apuntan en la misma dirección: misma persona |
| 0 | No tienen relación |
| -1 | Direcciones opuestas |

Por qué el coseno y no la distancia "en línea recta" (euclidiana):

- **Lo que identifica a una persona es la dirección del vector, no su tamaño.** La longitud cambia con la iluminación, el contraste o la calidad de la imagen. El coseno ignora esas variaciones.
- **El resultado es fácil de interpretar**: un número acotado entre -1 y 1, al que se le puede poner un umbral.
- **Es la métrica para la que DeepFace publica el umbral de Facenet.** La librería define una distancia coseno máxima de 0.40, que equivale a una similitud mínima de **0.60**. De ahí sale `SIMILARITY_THRESHOLD`.

### El umbral es un equilibrio

| Si se sube (ej. 0.70) | Si se baja (ej. 0.50) |
|---|---|
| Menos confusiones entre alumnos | Reconoce con peor luz o ángulo |
| Más alumnos sin reconocer | Más riesgo de confundir a dos alumnos |

### Protecciones adicionales

- **Confirmación humana.** El sistema nunca registra una asistencia solo. Muestra a quién reconoció y el docente debe pulsar Confirmar.
- **Solo se puede confirmar al último identificado.** Si el alumno se fue de cuadro, el servidor olvida la identificación y la confirmación da `409`.

---

## 8. Detección de indumentaria

Código: `app/services/yolo_service.py`, `app/services/compliance_engine.py` (clase `PpeReview`).

### El modelo

**YOLO** es un modelo de detección de objetos: recibe una imagen y devuelve una lista de rectángulos ("cajas"), cada uno con una clase y un nivel de confianza.

Hay un archivo de pesos por área, definido en `MODEL_PATHS`. El modelo de civil (`weights/civil.pt`) reconoce estas clases:

```
Hardhat, NO-Hardhat, Mask, NO-Mask, Safety Vest, NO-Safety Vest,
Person, Safety Cone, machinery, vehicle
```

Hay dos tipos de clases de prenda:

- **Positiva** (`Hardhat`): el modelo ve la prenda puesta.
- **Negativa** (`NO-Hardhat`): el modelo ve la parte del cuerpo **sin** la prenda.

Si el modelo no ve esa parte del cuerpo, no devuelve ninguna de las dos.

### Carga del modelo

- Se carga **la primera vez que se usa** y queda en memoria; no se relee del disco.
- Tras cargarlo se hace una inferencia de calentamiento con una imagen vacía, porque la primera siempre es mucho más lenta.
- Se usa en modo *tracking* (ByteTrack), que asigna un `track_id` a cada objeto para seguirlo entre frames.

### Qué prendas se exigen

Vienen del catálogo en Mongo (colección `practices`), según el área de la materia:

| Área | `ppe_requerido` |
|---|---|
| `civil` | `Hardhat`, `Safety Vest` |
| `medicina` | `Mask`, `Gloves`, `Gorro` |

Los nombres deben coincidir exactamente con las clases del modelo.

### La regla de la revisión

Cuando el docente confirma a un alumno, empieza una revisión de **6 segundos** en la que se analiza un frame cada 0.3 s aproximadamente (unos 12 a 20 frames, según lo que tarde el modelo).

**Principio: toda prenda requerida parte como faltante.** Solo deja de serlo si el modelo la detecta puesta.

En cada frame:

1. **Se elige al alumno revisado:** la persona con la caja más grande, es decir, la más cercana a la cámara.
2. **Se amplía su caja un 10 %** (`REVIEW_PERSON_MARGIN`), porque el casco suele asomar por encima.
3. **Solo cuentan las detecciones cuyo centro cae dentro de esa zona.** Lo que esté fuera se ignora.
4. Por cada prenda requerida se suma un punto a "vista puesta" o a "vista ausente", según la clase detectada.
5. **Si no se detecta a ninguna persona, el frame no cuenta nada.**

Al terminar los 6 segundos, una prenda se da por **llevada** solo si cumple las dos condiciones:

- Se vio puesta en **al menos 3 frames** (`REVIEW_CONFIRM_FRAMES`).
- Se vio puesta **más veces** de las que se vio ausente.

Todo lo demás queda en `faltantes`. Si la lista queda vacía, el alumno cumplió.

### Por qué está diseñado así

| Decisión | Motivo |
|---|---|
| Faltante por defecto | Antes, si el modelo no veía la cabeza, el alumno salía como "cumplió". Ahora la duda nunca aprueba |
| Mínimo de 3 frames | Una detección suelta puede ser un falso positivo del modelo |
| Más positivos que negativos | Resuelve el caso en que el modelo duda y alterna entre ambas clases |
| Solo lo que está dentro de la persona | Evita que cuente el casco de un compañero o uno colgado en la pared |
| La persona más grande | Es una forma simple de elegir al que está al frente |

### El costo de exigir que la prenda esté sobre la persona

Esta regla tiene un caso desfavorable que hay que conocer.

**El caso:** el modelo ve el casco y el chaleco, pero **no detecta a la persona**. Como no hay caja de persona contra la cual comparar, ningún frame cuenta, y el alumno queda con **todas las prendas como faltantes aunque las lleve puestas**.

**Cuándo ocurre:**

- El alumno está muy pegado a la cámara y solo se ve el torso o la cara.
- Está cortado por el borde del encuadre.
- Hay poca luz o un fondo que confunde al modelo.
- El modelo detecta a la persona con una confianza menor a `CONFIDENCE_THRESHOLD` (0.50), y la descarta.

**Por qué se aceptó:** la alternativa era contar cualquier casco visible en la imagen, lo que permite aprobar a un alumno con el casco de otro. Entre "reprobar a alguien que sí cumple" y "aprobar a alguien que no cumple", se eligió lo primero, porque es el error que se nota y se corrige en el momento.

**Un segundo caso relacionado:** si un compañero se para **más cerca de la cámara** que el alumno revisado, su caja será la más grande y el sistema lo evaluará a él.

**Cómo reducirlo:**

- Indicar al alumno que se pare **solo, de cuerpo entero y a una distancia fija** de la cámara. Una marca en el piso basta.
- Mejorar la iluminación.
- Si los cascos no se cuentan estando sobre la persona, subir `REVIEW_PERSON_MARGIN`.
- Si hay demasiados "no cumplió" con alumnos que sí cumplen, bajar `REVIEW_CONFIRM_FRAMES` a 2.

Si el alumno reprueba por error, la foto de evidencia lo muestra con las prendas puestas, lo que permite corregirlo.

### Evidencia

Si el alumno no cumple, se guarda una foto del último frame con una caja roja y el texto de lo que falta. La caja rodea a la persona; si no se detectó a ninguna, rodea el frame completo.

Ruta: `static/evidence/<fecha>/<practica_id>-<alumno_id>.jpg`.

---

## 9. Ciclo de vida de una práctica

Código: `app/api/v1/endpoints/practicas.py`, `app/services/practica_orchestrator.py`, `app/services/practica_lifecycle.py`, `app/services/practica_registry.py`.

### Dos lugares donde vive una práctica

| Dónde | Qué guarda | Sobrevive a un reinicio |
|---|---|---|
| **MongoDB** (colección `practicas`) | El registro: materia, docente, horas, estado | Sí |
| **Memoria** (`practica_registry`) | El orquestador: el hilo que usa la cámara y los modelos | No |

Casi toda la complejidad del ciclo de vida viene de mantener esos dos lugares de acuerdo.

### Las etapas

```
POST /practicas
      │  valida materia, permisos y catálogo de PPE
      │  guarda la práctica como "activa" en Mongo
      │  carga los alumnos matriculados (candidatos)
      │  enciende la cámara y arranca el orquestador
      ▼
┌──────────── fase: identificacion ────────────┐
│  cada 1 s busca un rostro conocido           │◄──────────┐
│  evento: estudiante_identificado             │           │
└──────────────────┬───────────────────────────┘           │
                   │ POST /practicas/{id}/confirmar        │
                   ▼                                       │
┌──────────── fase: indumentaria (6 s) ────────┐           │
│  cada 0.3 s analiza prendas                  │           │
│  evento: detecciones_frame                   │           │
│  al terminar: guarda asistencia y evidencia  │           │
│  evento: asistencia_registrada               │───────────┘
└──────────────────────────────────────────────┘
                   │
        POST /practicas/{id}/end
      detiene el orquestador, apaga la cámara
      marca la práctica como "finalizada"
```

### Inicio

`POST /practicas` hace las comprobaciones **antes** de tocar la cámara: que no haya otra práctica en curso, que la materia exista y sea del docente, y que haya catálogo de PPE para el área.

Si la cámara no abre, **el registro recién creado se borra** y se responde `500`. Sin esto quedaría una práctica "activa" que nunca funcionó.

### Recuperación tras un reinicio

Si el servidor se reinicia en plena práctica, el orquestador desaparece (vivía en memoria), pero el registro en Mongo sigue diciendo "activa". Esa práctica queda huérfana.

Al arrancar, `recuperar_practica_activa()` busca las prácticas en estado "activa" y decide:

| Caso | Qué hace |
|---|---|
| La más reciente, iniciada hace menos de 8 horas | La **reanuda**: vuelve a encender la cámara y el orquestador |
| Iniciada hace más de 8 horas | La marca como `finalizada` |
| No se puede reanudar (materia borrada, sin catálogo, cámara no abre) | La marca como `finalizada` |
| Hay más de una activa | Reanuda solo la más reciente y cierra las demás |

El límite de horas (`PRACTICA_RECUPERABLE_HORAS`) existe por una razón concreta: sin él, una práctica olvidada el viernes encendería la cámara sola al arrancar el servidor el lunes.

**Efecto a tener presente:** la cámara puede encenderse sola al arrancar el servidor. En desarrollo con `uvicorn --reload`, cada recarga de código reanuda la práctica.

Al reanudar se pierde el estado de la revisión en curso: la práctica vuelve a la fase de identificación.

### Apagado

Al detener el servidor se paran los orquestadores y se libera la cámara, pero **la práctica se deja "activa" en Mongo**, justamente para poder reanudarla al volver.

### Práctica por docente

Aunque solo hay una práctica en todo el servidor, cada docente solo ve y controla la suya:

- `GET /practicas/active` devuelve la práctica solo si es del docente que pregunta.
- Solo el dueño puede confirmar alumnos y finalizarla.
- Si otro docente intenta iniciar una, recibe `409` indicando que hay una práctica de otro docente.

---

## 10. Hilos y el puente asíncrono

Código: `app/core/async_bridge.py`.

FastAPI trabaja con un **bucle asíncrono** (*event loop*): un solo hilo que atiende todas las peticiones turnándose. Funciona bien mientras nadie lo bloquee.

El problema es que leer la cámara y correr los modelos son tareas lentas y bloqueantes. Si se hicieran en el bucle principal, la API entera se congelaría mientras YOLO procesa un frame.

### La solución: hilos separados

| Hilo | Qué hace |
|---|---|
| Principal (event loop) | Atiende REST, WebSocket y Mongo |
| Captura | Lee frames de la cámara |
| Orquestador | Corre DeepFace y YOLO |

### El puente

El orquestador necesita dos cosas que solo se pueden hacer desde el bucle principal: **guardar en Mongo** y **enviar por WebSocket**. Un hilo normal no puede llamar funciones `async` directamente.

`async_bridge.run_coroutine()` resuelve eso: recibe la tarea asíncrona y la programa en el bucle principal de forma segura (`asyncio.run_coroutine_threadsafe`). El bucle se registra al arrancar la app (`set_main_loop`).

### Cosas a saber

- **Los errores en esas tareas no detienen nada.** Se imprimen en consola con el prefijo `[ERROR async]`. Si una asistencia no se guarda, ese es el lugar donde mirar.
- **El hilo del orquestador no tiene captura de errores.** Si DeepFace o YOLO lanzan una excepción, el hilo muere en silencio: la práctica sigue "activa" pero ya no detecta nada. El caso conocido es iniciar una práctica de un área sin archivo de pesos.
- **Abrir la cámara sí bloquea el bucle principal** durante un instante al iniciar una práctica.

---

## 11. WebSocket, video y evidencias

### WebSocket (`/ws/detections`)

Canal de un solo sentido: el servidor emite, el cliente escucha.

- **Autenticación:** token por `?token=`. Solo docente, coordinador y admin. Si falla, la conexión se rechaza con el código `1008`.
- **Difusión global:** todos los clientes conectados reciben los mismos eventos.
- **Estado inicial:** el primer mensaje de cada conexión es `estado_inicial`, con la fase, el último alumno identificado y los segundos que quedan de la revisión. Permite reconstruir la pantalla tras recargar la página.

Eventos: `estado_inicial`, `estudiante_identificado`, `fase_cambiada`, `detecciones_frame`, `asistencia_registrada`. El detalle de cada uno está en `FRONTEND.md`, sección 7.

### Video (`/api/v1/stream`)

Formato **MJPEG**: una sucesión de imágenes JPEG sobre una conexión HTTP que no se cierra. Se muestra en un `<img>`, no en un `<video>`.

- Es simple y no requiere nada especial en el navegador. A cambio, consume más ancho de banda que un video comprimido.
- El video llega **limpio**, sin cajas. Las cajas las dibuja el frontend con las coordenadas de `detecciones_frame`, que vienen normalizadas entre 0 y 1.

### Evidencias (`/static/evidence/...`)

No es una carpeta pública. Cada foto pasa por un endpoint que comprueba:

1. Que el token sea válido.
2. Que la ruta pedida **esté registrada en una asistencia**. Esto da el permiso y, a la vez, impide leer archivos fuera de la carpeta.
3. Que quien pide tenga alcance: el alumno ve las suyas, el docente las de sus materias, el coordinador las de su cargo.

---

## 12. Base de datos

MongoDB, con el driver asíncrono de `pymongo`.

| Colección | Qué guarda | Campos clave |
|---|---|---|
| `usuarios` | Todos los roles | `codigo` (único), `rol`, `password_hash`, `face_embedding` (alumnos), `coordinador_id` (docentes) |
| `materias` | Las materias | `area`, `docente_id`, `coordinador_id`, `alumnos_ids` |
| `practices` | Catálogo de PPE por área | `area`, `ppe_requerido` |
| `practicas` | Las sesiones de práctica | `materia_id`, `docente_id`, `hora_inicio`, `hora_fin`, `estado` |
| `asistencias` | El resultado de cada alumno | `practica_id`, `alumno_id`, `cumplio_indumentaria`, `faltantes`, `evidencia_url` |

### Cosas a saber

- **`practices` y `practicas` son colecciones distintas.** La primera es el catálogo fijo (qué PPE exige cada área); la segunda, las sesiones reales.
- **Las referencias se guardan como texto**, no como `ObjectId`. Por eso el código convierte con `ObjectId(...)` al buscar por `_id`.
- **El `_id` sale de la API como `_id`**, no como `id`.
- **Las fechas se guardan en UTC** y la API las devuelve sin zona horaria.
- **Las materias no tienen fecha de creación.** Cuando hace falta (panel del coordinador), se usa la fecha contenida en su `_id`.
- **Los índices se crean al arrancar** (`connect_to_mongo`), incluido el índice único sobre `codigo`.
- **No hay migraciones.** Los cambios de esquema se hacen a mano.

---

## 13. Parámetros ajustables

Valores que dependen del entorno: la cámara, la luz, el aula, el hardware y el nivel de seguridad que se quiera.

### En `.env` o `app/core/config.py`

Se pueden cambiar con una variable de entorno, sin tocar código.

| Parámetro | Valor | Qué controla | Cuándo cambiarlo |
|---|---|---|---|
| `JWT_SECRET_KEY` | (obligatorio) | Clave con la que se firman los tokens | Debe ser única y secreta en cada entorno |
| `JWT_EXPIRE_MINUTES` | 480 | Duración del token (8 horas) | Bajarlo si se quiere más seguridad; subirlo si las jornadas son más largas |
| `JWT_ALGORITHM` | `HS256` | Algoritmo de firma | Normalmente no se toca |
| `ALLOWED_ORIGINS` | `localhost:5173`, `localhost:3000` | Desde qué direcciones puede llamar el frontend (CORS) | Al desplegar, o si el frontend usa otro puerto |
| `MONGO_HOST`, `MONGO_DB_PORT`, `MONGO_DB_NAME`, `MONGO_USERNAME`, `MONGO_PASSWORD` | (obligatorios) | Conexión a la base | Por entorno |
| `MODEL_PATHS` | `weights/civil.pt`, `weights/medicina.pt` | Archivo de pesos de cada área | Al agregar un área o cambiar de modelo |
| `CONFIDENCE_THRESHOLD` | 0.50 | Confianza mínima para aceptar una detección de YOLO | Subirlo si hay detecciones falsas; bajarlo si no detecta prendas que sí están |
| `IOU_THRESHOLD` | 0.45 | Cuánto pueden solaparse dos cajas antes de considerarlas el mismo objeto | Rara vez |
| `PRACTICA_RECUPERABLE_HORAS` | 8 | Antigüedad máxima de una práctica para reanudarla tras un reinicio | Según la duración real de las prácticas |

### Cámara — `app/services/camera_service.py`

| Parámetro | Valor | Qué controla | Cuándo cambiarlo |
|---|---|---|---|
| `camera_index` | 0 | Qué cámara del equipo se usa | Si el servidor tiene varias cámaras y abre la equivocada |
| `target_fps` | 8 | Frames por segundo que se capturan | Subirlo da video más fluido y más carga de CPU |
| `resize_width` | 640 | Ancho al que se reduce cada frame | Subirlo mejora la detección de lejos y la hace más lenta |
| `warmup_frames` | 10 | Frames descartados al abrir la cámara | Subirlo si las primeras imágenes salen oscuras |

### Reconocimiento facial — `app/services/face_service.py`

| Parámetro | Valor | Qué controla | Cuándo cambiarlo |
|---|---|---|---|
| `SIMILARITY_THRESHOLD` | 0.60 | Similitud mínima para aceptar que es el mismo alumno | Subirlo si confunde alumnos; bajarlo si no los reconoce |
| `FACE_MODEL_NAME` | `Facenet` | Modelo que genera el embedding | **Cambiarlo invalida todos los rostros registrados** |
| `FACE_DETECTOR_BACKEND` | `opencv` | Cómo se localiza el rostro en la imagen | Cambiarlo a uno más preciso (y más lento) si falla con perfiles o poca luz |

### Práctica — `app/services/practica_orchestrator.py`

| Parámetro | Valor | Qué controla | Cuándo cambiarlo |
|---|---|---|---|
| `IDENTIFICATION_INTERVAL_SECONDS` | 1.0 | Cada cuánto se busca un rostro | Bajarlo para reconocer más rápido, a costa de CPU |
| `INDUMENTARIA_INTERVAL_SECONDS` | 0.3 | Pausa entre análisis de prendas | Bajarlo da más frames por revisión |
| `REVIEW_DURATION_SECONDS` | 6 | Duración de la revisión de prendas | Subirlo si el hardware es lento y salen pocos frames. El frontend muestra una cuenta regresiva con este valor |

### Revisión de prendas — `app/services/compliance_engine.py`

| Parámetro | Valor | Qué controla | Cuándo cambiarlo |
|---|---|---|---|
| `REVIEW_CONFIRM_FRAMES` | 3 | En cuántos frames debe verse una prenda puesta para darla por llevada | Bajarlo a 2 si reprueban alumnos que sí cumplen; subirlo si aprueban por detecciones falsas |
| `REVIEW_PERSON_MARGIN` | 0.10 | Cuánto se amplía la caja de la persona al decidir si una prenda es suya | Ver abajo |

**`REVIEW_PERSON_MARGIN` en detalle.** Una prenda solo cuenta si su centro cae dentro de la caja de la persona. Pero la caja que dibuja el modelo alrededor de la persona a veces queda justa, y un casco puede sobresalir por arriba. El margen amplía la caja hacia los cuatro lados en una fracción de su propio tamaño.

Con `0.10`, una persona cuya caja mide 200 × 400 px se evalúa con una zona de 240 × 480 px (20 px más a cada lado, 40 px más arriba y abajo).

| Si se sube (ej. 0.25) | Si se baja (ej. 0.0) |
|---|---|
| Cuenta cascos que sobresalen mucho | Solo cuenta lo que está estrictamente dentro |
| Puede contar prendas de alguien que está muy pegado | Puede ignorar el casco del propio alumno |

### Otros

| Parámetro | Archivo | Valor | Qué controla |
|---|---|---|---|
| `STREAM_INTERVAL_SECONDS` | `endpoints/stream.py` | 1/8 | Ritmo del video; debe coincidir con `target_fps` |
| `DIAS_RECIENTE` | `endpoints/coordinacion.py` | 7 | Ventana de "materia nueva" y "laboratorio activo" en el panel del coordinador |
| `EVIDENCE_DIR` | `services/evidence_service.py` | `static/evidence` | Dónde se guardan las fotos |

### Qué ajustar primero en un aula nueva

1. `camera_index`, si no abre la cámara correcta.
2. Colocar la cámara y marcar en el piso dónde debe pararse el alumno.
3. `SIMILARITY_THRESHOLD`, si el reconocimiento falla o confunde.
4. `REVIEW_CONFIRM_FRAMES` y `REVIEW_PERSON_MARGIN`, según los resultados de las revisiones.
5. `CONFIDENCE_THRESHOLD`, solo si lo anterior no alcanza.

---

## 14. Limitaciones y riesgos conocidos

### Funcionales

| Limitación | Efecto |
|---|---|
| **No existe el modelo de medicina** | En `weights/` solo está `civil.pt`. Una práctica de área `medicina` inicia, pero el hilo de detección falla al revisar al primer alumno y la práctica deja de responder |
| **Una práctica a la vez** | Hay una sola cámara. Dos docentes no pueden dar práctica simultáneamente |
| **Asistencias duplicadas** | Si se confirma dos veces al mismo alumno, se guardan dos asistencias. El reporte muestra una sola |
| **Un solo rostro por alumno** | Se registra con una única foto. Si salió mal, el reconocimiento será malo, y no hay endpoint para volver a registrarlo |
| **No hay aviso cuando el rostro se pierde** | Si el alumno se retira, la tarjeta del frontend queda desactualizada hasta el siguiente evento |
| **Candidatos fijos** | Los alumnos matriculados durante una práctica no se reconocen hasta la siguiente |
| **Sin persona detectada, todo falta** | Explicado en la sección 8 |

### De seguridad y privacidad

| Riesgo | Detalle |
|---|---|
| **Datos biométricos** | Los embeddings faciales son datos personales sensibles y se guardan en Mongo sin cifrar. Conviene revisar qué exige la normativa local sobre su tratamiento y el consentimiento de los alumnos |
| **Fotos de evidencia en disco** | Se guardan sin cifrar en `static/evidence/` y no hay política de borrado |
| **Token en la URL** | En WebSocket, video y evidencias el token queda en el historial y en los logs |
| **Tokens no revocables** | Un token robado sirve hasta que expira |
| **Sin límite de intentos de login** | No hay protección contra probar contraseñas en masa |
| **Sin detección de vida** | El reconocimiento facial no distingue un rostro real de una foto. La confirmación del docente es la única barrera |
| **Sin HTTPS propio** | El servidor habla HTTP. En producción debe ir detrás de un proxy con HTTPS, o los tokens y el video viajan en claro |

### De mantenimiento

- **No hay pruebas automatizadas.** Los archivos de `scripts/` son pruebas manuales.
- **Los errores se imprimen en consola** con `print`; no hay sistema de logs.
- **El estado de la práctica vive en la memoria de un proceso.** El servidor debe correr con **un solo worker**: con varios, cada uno tendría su propio registro de prácticas y su propia cámara.

---

## 15. Preguntas frecuentes

**¿Se guardan las fotos de los rostros de los alumnos?**
No. Se guarda solo el embedding, una lista de 128 números. De esos números no se puede reconstruir la foto. Sí se guardan fotos cuando un alumno no cumple con la indumentaria (evidencia).

**¿Por qué el sistema no reconoce a un alumno?**
Las causas habituales, en orden: no está matriculado en la materia de la práctica, se matriculó después de iniciarla, hay poca luz o está de perfil, hay dos rostros en cuadro, o su foto de registro salió mal.

**¿Por qué un alumno con todo el equipo salió como "no cumplió"?**
Lo más probable es que el modelo no haya detectado a la persona o que la prenda se haya visto en menos de 3 frames. Revisar la foto de evidencia y la sección 8.

**¿Por qué no se puede iniciar una práctica?**
Ya hay otra en curso (propia o de otro docente), la materia no es del docente, no hay catálogo de PPE para el área, o la cámara no abre.

**¿Qué pasa si se cae el servidor en plena práctica?**
Al volver a arrancar se reanuda sola si empezó hace menos de 8 horas. La revisión que estuviera en curso se pierde; hay que volver a confirmar a ese alumno.

**¿Se puede cambiar Facenet por otro modelo?**
Sí, con `FACE_MODEL_NAME`, pero cada modelo genera embeddings incompatibles: habría que volver a registrar el rostro de todos los alumnos y recalibrar `SIMILARITY_THRESHOLD`.

**¿Cómo se agrega un área nueva (por ejemplo, química)?**
Hace falta: entrenar un modelo YOLO con las clases de esa área, poner el archivo en `weights/`, agregarlo a `MODEL_PATHS`, insertar el área en la colección `practices` con su `ppe_requerido`, y ampliar los valores permitidos de `area` en `app/models/materia.py`.

**¿Dónde miro si algo falla sin dar error?**
En la consola de uvicorn. Buscar `[ERROR async]` (fallo al guardar o al emitir un evento), `[practicas]` (recuperación al arrancar) o un *traceback* del hilo del orquestador.

**¿Se puede correr con varios workers de uvicorn?**
No. El estado de la práctica y la cámara viven en la memoria de un solo proceso.
