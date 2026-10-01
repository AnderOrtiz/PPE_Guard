# PPE_Guard — Guía de integración para el frontend (actualizada)

Este documento reemplaza por completo la guía anterior — el sistema cambió bastante desde entonces (roles, materias, prácticas, identificación facial). Si tienes la versión vieja pegada en algún lado, bórrala; varias cosas de ahí ya no existen.

---

## 1. Los cuatro roles

| Rol | Puede hacer |
|---|---|
| **Alumno** | Ver solo su propio historial de asistencia, solo en las materias donde está inscrito |
| **Docente** | Iniciar/finalizar prácticas, matricular alumnos, ver reportes de sus propias materias |
| **Coordinador** | Crear materias, crear docentes y alumnos, ver reportes de los docentes a su cargo |
| **Admin** | Todo lo de coordinador + todo lo de docente (puede iniciar prácticas), y es el único que crea coordinadores |

Estos permisos los aplica el **backend**, no el frontend — ocultar un botón no es seguridad, el servidor siempre vuelve a validar. El frontend oculta/muestra según el rol solo para que la interfaz tenga sentido, no como mecanismo de control de acceso.

---

## 2. Autenticación

**Login:** `POST /api/v1/auth/login`
```json
{ "codigo": "DOC001", "password": "cambiar123" }
```

Respuesta:
```json
{ "access_token": "eyJ...", "token_type": "bearer", "rol": "docente", "nombre": "Docente Demo" }
```

Guarda `access_token` y mándalo en cada petición protegida: