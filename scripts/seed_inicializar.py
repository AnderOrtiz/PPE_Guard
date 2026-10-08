import asyncio
import sys

from pymongo import AsyncMongoClient

from app.core.config import settings
from app.core.security import hash_password

# Lo mínimo para usar el sistema sobre una base vacía:
#   1. Un admin. No hay endpoint que lo cree; el resto de usuarios los crea él desde la API.
#   2. El catálogo de PPE por área. Tampoco tiene endpoint, y sin él no se puede iniciar una práctica.
ADMIN_CODIGO = "ADMIN001"
ADMIN_PASSWORD = "cambiar123"
ADMIN_NOMBRE = "Administrador"

CATALOGO_PPE = [
    {"area": "civil", "nombre": "Ingeniería Civil", "ppe_requerido": ["Hardhat", "Safety Vest"]},
    {"area": "medicina", "nombre": "Medicina", "ppe_requerido": ["Mask", "Gloves", "Gorro"]},
]


async def inicializar(codigo: str, password: str, nombre: str):
    client = AsyncMongoClient(
        host=settings.MONGO_HOST,
        port=settings.MONGO_DB_PORT,
        username=settings.MONGO_USERNAME,
        password=settings.MONGO_PASSWORD,
    )
    db = client[settings.MONGO_DB_NAME]

    if await db["usuarios"].count_documents({"rol": "admin"}) > 0:
        print("Ya existe un admin. No se creó otro.")
    elif await db["usuarios"].find_one({"codigo": codigo}) is not None:
        print(f"El código {codigo} ya está en uso por otro usuario. No se creó el admin.")
    else:
        await db["usuarios"].insert_one({
            "codigo": codigo,
            "password_hash": hash_password(password),
            "rol": "admin",
            "nombre": nombre,
        })
        print(f"Admin creado: {codigo} (contraseña: {password}). Cámbiala al entrar: POST /api/v1/auth/me/password")

    if await db["practices"].count_documents({}) > 0:
        print("El catálogo de PPE ya existe. No se insertó nada.")
    else:
        await db["practices"].insert_many([dict(area) for area in CATALOGO_PPE])
        print("Catálogo de PPE insertado: civil y medicina.")

    await client.close()


if __name__ == "__main__":
    # Los argumentos que falten toman el valor por defecto
    dados = sys.argv[1:4]
    codigo, password, nombre = dados + [ADMIN_CODIGO, ADMIN_PASSWORD, ADMIN_NOMBRE][len(dados):]
    asyncio.run(inicializar(codigo, password, nombre))


# python -m scripts.seed_inicializar
# python -m scripts.seed_inicializar <codigo> <contraseña> "<nombre>"
