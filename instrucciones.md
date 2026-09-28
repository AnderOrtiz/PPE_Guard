# Propuesta de Arquitectura: Roles, Flujos y Reportes de Asistencia

---

## 1. Modelo de Roles y Permisos (RBAC)

El acceso al sistema estará estrictamente limitado según el rol del usuario autenticado:

* **Alumno**
* Accede solo a las **materias** en las que está inscrito.
* Al seleccionar una materia, solo puede consultar su propio historial de asistencias.


* **Docente**
* Puede iniciar una **Práctica** (sesión en tiempo real donde el sistema reconoce el rostro del alumno y valida su indumentaria).
* Puede consultar los reportes de asistencia de las materias que imparte.
* Puede **añadir alumnos** a las materias que tiene asignadas.


* **Coordinador**
* Puede **crear materias** en el sistema.
* Puede **crear y asignar Alumnos, Docentes** a sus respectivas materias.
* Puede consultar las asistencias de cualquier materia (filtrando primero por docente y luego por materia).


* **Administrador (Admin)**
* Posee todos los permisos del Coordinador.
* Es el único rol con la facultad exclusiva de **crear nuevos Coordinadores**.



---

## 2. Gestión de Materias

El **Coordinador** o **Admin** serán los unicos que pueden crear las materias en la plataforma.

* **Campos del Formulario de Materia:**
* **Nombre de la Materia**
* **Docente asignado**
* **Coordinador a cargo**
* **Carrera**
* **Facultad**



> **Estructura:** Todas las **Prácticas** (sesiones en vivo de pase de lista y validación facial) ejecutadas por los docentes se irán guardando dinámicamente dentro de la materia correspondiente.

---

## 3. Flujo e Interfaz de Registro de Usuarios

### A. Registro de Alumnos (Registro Único Centralizado)

Para garantizar la calidad de la biometría y evitar redundancias, **el alumno se registra una sola vez en el sistema** (asociando su rostro a su perfil global). Luego, simplemente se le asigna o enrola a las materias requeridas sin repetir el proceso facial.

1. **Paso 1 - Datos Generales:** Formulario con Código, Nombre completo y Contraseña.
> *Nota:* El docente y la facultad se asignan automáticamente según el contexto de la materia donde el coordinador o docente esté matriculando al alumno.


2. **Indicaciones:** Se muestran instrucciones claras en pantalla (*"Mira a la cámara"*, *"Permanece quieto"*, *"Quítate los lentes"*).
3. **Paso 3 - Captura Biométrica y Generación de Vector:** Al confirmar, el sistema procesa y guarda el **vector del rostro** asociado al perfil del alumno para usarse en todas sus materias.

### B. Registro de Docentes

* **Campos:** Nombre completo, Código, Facultad y Contraseña.
* **Asignación Dinámica de Materias:** Campo dinámico donde, al asignar una materia, se despliega automáticamente un nuevo *input* vacante para agregar otra materia si es necesario.

### C. Registro de Coordinadores

* **Campos:** Nombre completo, Código, Facultad y Contraseña.

---

## 4. Módulo de Reportes de Asistencia

Para cada práctica ejecutada, el sistema desplegará la información organizada de la siguiente manera:

* **Cabecera de Sesión:**
* Datos generales: Materia, Docente asignado, Fecha y Hora de ejecución.
* Resumen de métricas: Total de alumnos presentes, ausentes, con indumentaria correcta e incorrecta.


* **Tabla Detallada de Asistencia e Indumentaria:**

| Nombre | Código | Hora de Entrada | Estatus / Indumentaria (Detalle Visual) |
| --- | --- | --- | --- |
| Juan Pérez | 2024001 | 08:02 AM | **Cumplió** (Verde completo) |
| María Gómez | 2024002 | 08:05 AM | **Casco** / **Chaleco** *(Tooltip/Detalle)* |
| Carlos López | 2024003 | --:-- | **Inasistencia** |

> **Lógica del campo Estatus / Indumentaria:**
> * Muestra de manera dinámica cada elemento de la indumentaria requerida.
> * Cada componente se evalúa individualmente: en **verde** si cumple y en **rojo** si no cumple (ejemplo: si le falta el casco pero lleva chaleco, el badge/tooltip dirá **Casco** en rojo y **Chaleco** en verde).
> 
> 

---

## 5. Reglas de Negocio Clave

1. **Diferenciación de Roles:** `Admin` = `Coordinador` + `Crear Coordinadores`.
2. **Jerarquía Institucional:** La facultad o área académica queda definida dentro de la **materia** (cada materia pertenece a una carrera y facultad fija).
3. **Perfil Único de Alumno:** El vector facial del alumno pertenece a su perfil general. No es necesario recapturar el rostro cada vez que se inscribe a una nueva materia.
4. **Persistencia de Prácticas:** Cada práctica iniciada por un docente se almacena históricamente dentro de la materia a la que pertenece.

---

está bien fusiona usuarios y estudiantes en una sola colección y manten un el campo  de área (civil/medicina) en la materia.

con respecto a:
"El docente y la facultad se asignan automáticamente según el contexto de la materia donde el coordinador o docente esté matriculando al alumno."
si un alumno tiene un perfíl único global y  puede tener varios docentes, pero no estar en varias carreras ni en varias facultades,
un alumno tiene una carrera y una facultad, si tienene varios docentes

un docente solo puede tener una facultad, pero puede inpartir varias materias, y un coordinador puede tener varios docentes en su cargo 

dame una propuesta para que estas relaciones: