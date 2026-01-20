from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.security import create_access_token, verify_credentials


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(request: LoginRequest):
    if not verify_credentials(request.username, request.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(request.username)
    return {"access_token": token, "token_type": "bearer"}
