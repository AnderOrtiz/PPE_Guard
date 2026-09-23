from fastapi import APIRouter

from app.core.database import get_database
from app.models.practice import PracticeInDB

router = APIRouter()


@router.get("/practices", response_model=list[PracticeInDB], tags=["practices"])
async def list_practices():
    database = get_database()
    cursor = database["practices"].find()
    return [PracticeInDB(**doc) async for doc in cursor]