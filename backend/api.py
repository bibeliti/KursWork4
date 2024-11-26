from fastapi import FastAPI, Depends, HTTPException
from fastapi_users import FastAPIUsers, BaseUserManager
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.schemas import CreateUpdateDictModel
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, Boolean
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from pydantic import BaseModel, EmailStr, constr, ConfigDict
from typing import Optional
import uuid
import subprocess
from dotenv import load_dotenv
import os

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка базы данных
DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine = create_async_engine(DATABASE_URL, future=True, echo=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base: DeclarativeMeta = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

class UserTable(Base):
    __tablename__ = "user"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

def get_session_local() -> AsyncSession:
    yield SessionLocal()

async def get_user_db(session: AsyncSession = Depends(get_session_local)):
    yield SQLAlchemyUserDatabase(session, UserTable)

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

class UserManager(BaseUserManager[UserTable, str]):
    user_db_model = UserTable

    async def on_after_register(self, user: UserTable, request=None):
        print(f"User {user.email} registered.")

    async def create_user(
        self,
        user: UserCreate,
        safe: bool = False,
        request=None,
    ) -> UserTable:
        hashed_password = get_password_hash(user.password)
        user_data = user.create_update_dict()
        user_data["hashed_password"] = hashed_password
        user_data["is_active"] = True
        db_user = UserTable(**user_data)
        await self.user_db.create(db_user)
        await self.on_after_register(db_user)
        return db_user

    def parse_id(self, user_id: str) -> str:
        return user_id

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

SECRET = os.getenv("SECRET", "SECRET")
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[UserTable, str](
    get_user_manager,
    [auth_backend],
)

app = FastAPI()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Получение режима работы из переменной окружения
MODE = os.getenv("MODE", "development")

def run_ansible_playbook(playbook_name, auditorium_number):
    if MODE == "production":
        result = subprocess.run(
            ["ansible-playbook", playbook_name, "-e", f"auditorium_number={auditorium_number}"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Ansible playbook failed: {result.stderr}")
        return result.stdout
    else:
        # В режиме разработки просто возвращаем фиктивный ответ
        return f"Simulated running playbook {playbook_name} for auditorium {auditorium_number}"

class Auditorium(BaseModel):
    number: int

@app.post("/turn_off_network/")
async def turn_off_network(auditorium: Auditorium, user: UserTable = Depends(fastapi_users.current_user())):
    try:
        output = run_ansible_playbook("playbooks/turn_off_network.yml", auditorium.number)
        return {"message": "Network turned off", "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/turn_on_network/")
async def turn_on_network(auditorium: Auditorium, user: UserTable = Depends(fastapi_users.current_user())):
    try:
        output = run_ansible_playbook("playbooks/turn_on_network.yml", auditorium.number)
        return {"message": "Network turned on", "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check_network/")
async def check_network(auditorium: Auditorium, user: UserTable = Depends(fastapi_users.current_user())):
    try:
        output = run_ansible_playbook("playbooks/check_network.yml", auditorium.number)
        return {"message": "Network status checked", "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
