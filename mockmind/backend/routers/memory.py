from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.memory_store import delete_memory

router = APIRouter()


class ForgetMeRequest(BaseModel):
    email: str


@router.delete("/api/candidate-memory", status_code=204)
async def forget_me(req: ForgetMeRequest):
    email = req.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    await delete_memory(email)
