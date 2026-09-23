import asyncio
from pymongo import AsyncMongoClient

from app.core.config import settings


async def seed():
    client = AsyncMongoClient(
        host=settings.MONGO_HOST,
        port=settings.MONGO_DB_PORT,
        username=settings.MONGO_USERNAME,
        password=settings.MONGO_PASSWORD,
    )
    db = client[settings.MONGO_DB_NAME]

    existentes = await db["practices"].count_documents({})
    if existentes > 0:
        print(f"Ya hay {existentes} prácticas en la colección. No se insertó nada.")
        await client.close()
        return

    await db["practices"].insert_many([
        {
            "area": "civil",
            "nombre": "Ingeniería Civil",
            "ppe_requerido": ["Hardhat", "Safety Vest"],
        },
        {
            "area": "medicina",
            "nombre": "Medicina",
            "ppe_requerido": ["Mask", "Gloves", "Gorro"],
        },
    ])

    print("Prácticas insertadas: civil y medicina.")
    await client.close()


if __name__ == "__main__":
    asyncio.run(seed())
    
    
# python -m scripts.seed_practices