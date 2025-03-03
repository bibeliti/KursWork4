from pydantic import BaseModel, constr, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime
from fastapi_users.schemas import CreateUpdateDictModel

class UserRead(BaseModel):
    id: str
    email: EmailStr
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class UserCreate(CreateUpdateDictModel):
    email: EmailStr
    password: constr(min_length=8, max_length=128)

class UserUpdate(CreateUpdateDictModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None

class AuditoriumStateRead(BaseModel):
    auditorium_number: int
    is_network_on: bool
    unlock_time: Optional[datetime]

    class Config:
        from_attributes = True

class Auditorium(BaseModel):
    number: int
    duration: Optional[int] = 60
