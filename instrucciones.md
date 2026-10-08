# PPE_Guard — Roles: qué puede hacer cada uno y cómo funciona

Este documento explica los roles del sistema tal como están implementados hoy en el backend. Para el contrato exacto de cada endpoint (bodies, respuestas, errores) está `FRONTEND.md`; para el porqué técnico, `DOCUMENTACION_TECNICA.md`.

---

## 1. Los cuatro roles

| Rol | Quién es | Para qué entra al sistema |
|---|---|---|
| **alumno** | El estudiante que asiste a las prácticas | Consultar sus materias, sus asistencias y sus fotos de evidencia |
| **docente** | Quien imparte las materias | Dar las prácticas en vivo, matricular alumnos y ver los reportes de sus materias |
| **coordinador** | Quien tiene docentes y materias a su cargo | Crear materias, docentes y alumnos, y supervisar todo lo de su cargo |
| **admin** | El administrador del sistema | Todo lo anterior sin límites, y crear coordinadores |

Cada usuario tiene **un solo rol**, que se fija al crearlo y **no se puede cambiar** después. Todos viven en la misma colección (`usuarios`) e inician sesión igual: con su código y su contraseña.

---

## 2. Las dos reglas que explican todo

Cada petición pasa por dos comprobaciones. Entender estas dos reglas basta para predecir qué puede hacer cada quien.

### Regla 1: el rol decide qué acciones existen para ti

Cada endpoint declara qué roles lo pueden usar. Si tu rol no está, la respuesta es `403` — `"No tienes permiso para esta acción"`.

**El admin hereda al coordinador y al docente:** pasa cualquier comprobación de esos dos roles. No hereda al alumno: las pantallas "mis materias" y "mis asistencias" son solo para alumnos.

### Regla 2: "solo lo mío" decide sobre qué datos

Tener permiso para una acción no significa poder hacerla sobre cualquier dato. Casi todo se filtra por pertenencia:

| Rol | Qué es "lo suyo" |
|---|---|
| alumno | Sus propias asistencias, las materias donde está matriculado y sus fotos de evidencia |
| docente | Las materias que imparte, las prácticas de esas materias y los alumnos matriculados en ellas |
| coordinador | Las materias a su cargo, los docentes a su cargo y los alumnos matriculados en esas materias |
| admin | Todo. No tiene esta restricción |

Fuera de lo suyo, la respuesta es `403` con un mensaje que lo explica (por ejemplo, `"No puedes ver una materia fuera de tu cargo"`), o simplemente el dato no aparece en los listados.

### De dónde sale la pertenencia

Nadie "asigna" alumnos a un coordinador. La pertenencia se deduce de tres enlaces:

```
coordinador ──tiene a su cargo──► docente      (usuarios.coordinador_id)
docente ─────imparte────────────► materia      (materias.docente_id)
materia ─────pertenece a────────► coordinador  (materias.coordinador_id, copiado del docente al crearla)
materia ─────tiene matriculados─► alumnos      (materias.alumnos_ids)
```

Consecuencias directas:

- Un docente tiene **un** coordinador. Un coordinador puede tener varios docentes.
- Una materia tiene **un** docente, y pertenece al coordinador de ese docente.
- Un alumno puede estar en varias materias, con varios docentes e incluso de varios coordinadores.
- **El alumno no tiene dueño.** Solo "pertenece" a alguien mientras esté matriculado en una de sus materias.

---

## 3. Tabla de permisos

| Acción | alumno | docente | coordinador | admin |
|---|:-:|:-:|:-:|:-:|
| Iniciar sesión, ver su perfil | ✅ | ✅ | ✅ | ✅ |
| Editar su nombre y correo | ✅ | ✅ | ✅ | ✅ |
| Cambiar su propia contraseña | ✅ | ✅ | ✅ | ✅ |
| Editar carrera, facultad y estatus académico | ❌ | ❌ | los suyos y los de alumnos y docentes de su cargo | los de cualquiera |
| Resetear la contraseña de otro | ❌ | ❌ | alumnos y docentes de su cargo | cualquiera |
| Crear alumno (con captura del rostro) | ❌ | ✅ | ✅ | ✅ |
| Crear docente | ❌ | ❌ | ✅ (queda a su cargo) | ✅ (elige el coordinador) |
| Crear coordinador | ❌ | ❌ | ❌ | ✅ |
| Listar / ver usuarios | ❌ | alumnos de sus materias | sus docentes y los alumnos de sus materias | todos |
| Crear materia | ❌ | ❌ | para sus docentes | para cualquier docente |
| Editar materia | ❌ | ❌ | las de su cargo | todas |
| Listar / ver materias | solo las suyas (`/alumno/materias`) | las que imparte | las de su cargo | todas |
| Matricular / quitar alumnos de una materia | ❌ | en las que imparte | en las de su cargo | en todas |
| Iniciar, confirmar y finalizar una práctica | ❌ | ✅ (solo la suya) | ❌ | ✅ |
| Ver el video en vivo y los eventos de la práctica | ❌ | ✅ | ✅ | ✅ |
| Encender la vista previa de la cámara | ❌ | ✅ | ✅ | ✅ |
| Ver asistencias | solo las suyas | las de sus materias | las de su cargo | todas |
| Ver el reporte de una práctica | ❌ | de sus materias | de su cargo | todos |
| Ver una foto de evidencia | solo las suyas | de sus materias | de su cargo | todas |
| Panel de resumen de coordinación | ❌ | ❌ | de su cargo | global |

---

## 4. Cada rol en detalle

### Alumno

Es el único rol que tiene **rostro registrado**. No administra nada: solo consulta.

- **Puede:** ver las materias donde está matriculado, su historial de asistencias (con qué prendas le faltaron) y las fotos de evidencia de sus propias faltas.
- **Puede editar de sí mismo:** nombre, correo y contraseña.
- **No puede:** cambiar su carrera, facultad ni estatus académico (los fija el coordinador); ver a otros alumnos; ver el video en vivo; matricularse solo en una materia.
- **Cómo nace:** lo crea un docente, un coordinador o el admin, frente a la cámara del servidor. Su rostro se registra **una sola vez** y sirve para todas sus materias.

### Docente

Es quien opera el sistema en el aula.

- **Puede:** iniciar la práctica de una materia que imparte, confirmar a cada alumno identificado y finalizarla; ver el video y las detecciones en vivo; crear alumnos; matricular y quitar alumnos en sus materias; ver asistencias, reportes y evidencias de sus materias.
- **Puede editar de sí mismo:** nombre, correo y contraseña.
- **No puede:** crear ni editar materias; crear docentes; cambiar su facultad ni los datos académicos de un alumno; resetear contraseñas; ver materias o alumnos de otros docentes.
- **Al crear un alumno** solo manda código, nombre y contraseña (y, si quiere, las materias donde matricularlo, que deben ser suyas). Si manda carrera o facultad, recibe `403`.
- **Cómo nace:** lo crea un coordinador (queda a su cargo) o el admin (que indica a qué coordinador asignarlo).

### Coordinador

Administra una parte del sistema: sus docentes, sus materias y los alumnos de esas materias.

- **Puede:** crear materias para sus docentes y editarlas; crear docentes y alumnos; matricular alumnos en sus materias; editar la carrera, facultad y estatus académico de sus alumnos y docentes; resetearles la contraseña; ver asistencias, reportes, evidencias y el panel de resumen de su cargo; ver el video en vivo.
- **Puede editar de sí mismo:** nombre, correo, contraseña y también sus datos académicos.
- **No puede:** iniciar ni controlar una práctica (eso es del docente); crear coordinadores; tocar nada de otro coordinador; modificar a otro coordinador o al admin.
- **Cómo nace:** solo lo crea el admin.

### Admin

- **Puede todo** lo que pueden el coordinador y el docente, **sin** la regla de "solo lo mío": ve y modifica todo el sistema.
- **Es el único** que crea coordinadores, y el único que puede resetear la contraseña de un coordinador.
- **Puede iniciar prácticas** de cualquier materia. La práctica queda a nombre del docente de la materia, no del admin.
- **No tiene** pantallas de alumno: no tiene asistencias ni materias propias.
- **Cómo nace:** no hay endpoint para crear admins. El primero sale del script `python -m scripts.seed_inicializar`.

---

## 5. Perfil y contraseñas

### El perfil

Todos los usuarios tienen los mismos datos: `codigo`, `nombre`, `correo`, `carrera`, `estatus_academico`, `facultad`. Al crear un usuario se pide lo mínimo y el resto se completa después.

| Al crear un… | Se pide | Lo crea |
|---|---|---|
| alumno | código, nombre, contraseña, rostro. Opcional: materias donde matricularlo. Carrera y facultad solo si lo crea un coordinador o el admin | docente, coordinador, admin |
| docente | código, nombre, contraseña, facultad. El admin además indica el coordinador | coordinador, admin |
| coordinador | código, nombre, contraseña | admin |

Después, cada dato tiene un responsable:

| Dato | Quién lo cambia |
|---|---|
| `nombre`, `correo` | El propio usuario, desde su perfil. El correo nunca se pide al crear: lo agrega el usuario cuando ya inició sesión |
| `carrera`, `facultad`, `estatus_academico` | El coordinador (para alumnos y docentes de su cargo, y para sí mismo) y el admin |
| `codigo`, `rol` | Nadie. El código es la credencial de acceso |

Si un alumno o docente intenta cambiar un dato académico propio, la petición entera se rechaza con `403`; no se guarda ni el nombre que viniera en ella.

### Las contraseñas

| Caso | Quién | Pide la contraseña actual |
|---|---|---|
| Cambiar la propia | Cualquier usuario | Sí |
| Resetear la de otro | Coordinador (alumnos y docentes de su cargo) y admin (cualquiera) | No |

- Si un alumno o docente olvida su contraseña, se la resetea su coordinador. Si la olvida un coordinador, el admin.
- No hay recuperación por correo ni regla de complejidad: solo se rechaza la contraseña vacía.
- Las contraseñas se guardan cifradas con bcrypt. Nadie puede verlas, ni el admin: solo reemplazarlas.
- El rostro de cada alumno también se guarda cifrado, y ningún rol puede verlo ni descargarlo: la API nunca lo devuelve.

---

## 6. Cómo funciona por dentro

### La sesión

1. El usuario inicia sesión con código y contraseña y recibe un **token** que dura 8 horas.
2. El token lleva dentro su id, su código y su **rol**. El backend lee el rol del token en cada petición; no vuelve a consultar la base.
3. El token se renueva con `POST /auth/refresh` mientras siga vigente. Vencido, hay que volver a iniciar sesión.

Qué implica:

- **No hay cierre de sesión en el servidor.** "Cerrar sesión" es que el frontend borre el token.
- **Cambiar o resetear una contraseña no cierra las sesiones abiertas.** Un token ya emitido sigue valiendo hasta que expira.
- El video, el WebSocket y las fotos de evidencia reciben el token como `?token=` en la URL, porque el navegador no puede mandar cabeceras desde un `<img>` ni un WebSocket. Las reglas de rol son las mismas.

### La práctica y la cámara

- Hay **una sola cámara** (la del servidor), así que hay **una sola práctica activa** en todo el sistema, sin importar el docente.
- Cada docente solo ve y controla la suya. Si otro intenta iniciar una, recibe `409` avisando que hay una práctica de otro docente.
- El video y los eventos en vivo son **globales**: cualquier docente, coordinador o admin conectado ve la práctica que esté en curso, aunque no sea suya.
- Para dar de alta alumnos sin práctica activa, docentes y coordinadores pueden encender una vista previa de la cámara, que se apaga sola si nadie la mira.

---

## 7. Casos que conviene tener claros

**Un alumno recién creado sin materias no lo ve nadie, salvo el admin.** Como el alumno no tiene dueño, mientras no esté en ninguna materia no aparece en el listado de ningún docente ni coordinador, y su coordinador no puede editarlo ni resetearle la contraseña.

- **Sí se le puede matricular:** la matrícula busca al alumno por su **código** entre todos los alumnos, sin importar la visibilidad. En cuanto entra a una materia, queda al alcance de ese docente y de su coordinador.
- Lo más cómodo es matricularlo al crearlo, indicando las materias en el mismo formulario.

**Quitar a un alumno de su última materia lo vuelve a dejar fuera de alcance.** Sus asistencias pasadas siguen visibles en los reportes de la materia; lo que se pierde es poder editarlo o resetearle la contraseña.

**Un alumno en materias de dos coordinadores está al alcance de ambos.** Cualquiera de los dos puede editar sus datos académicos y resetearle la contraseña.

**Un coordinador no puede dar una práctica.** Si una persona coordina y además da clases, necesita dos usuarios (uno de cada rol), o que el admin inicie la práctica.

**Las asistencias no se pueden editar ni borrar.** Ningún rol tiene esa acción; tampoco existe borrar usuarios, materias ni prácticas.

---

## 8. Limitaciones conocidas de los permisos

Huecos que existen hoy en el código. No rompen el uso normal, pero conviene conocerlos:

| Qué pasa | Efecto |
|---|---|
| `GET /materias/{id}/alumnos` no aplica "solo lo mío" | Cualquier docente o coordinador que conozca el id de una materia ajena puede listar sus alumnos (código, nombre, carrera y facultad) |
| El video y los eventos en vivo no se filtran por dueño | Docentes y coordinadores ven la práctica en curso aunque sea de otro |
| El rol viaja en el token | Si a futuro se permitiera cambiar el rol de un usuario, el cambio no se notaría hasta que renueve su token |
| No hay cómo desactivar o borrar un usuario | Un alumno o docente que se va conserva su acceso; solo se le puede cambiar la contraseña |
