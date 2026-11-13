from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import settings
from app.models import User

router = APIRouter(prefix="/limits", tags=["limits"])


class LimitsOut(BaseModel):
    max_upload_bytes: int


@router.get("", response_model=LimitsOut)
def get_limits(_user: User = Depends(get_current_user)):
    """What the server will accept, so the UI can say so before a big upload."""
    return LimitsOut(max_upload_bytes=settings.max_upload_bytes)
