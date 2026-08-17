import uuid
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr

    class Config:
        from_attributes = True


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str

    class Config:
        from_attributes = True