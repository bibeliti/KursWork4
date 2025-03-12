from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi_users import FastAPIUsers, BaseUserManager, schemas
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.schemas import CreateUpdateDictModel
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, Boolean, Integer, DateTime
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from pydantic import BaseModel, constr, ConfigDict, EmailStr
from typing import Optional, List
import uuid
from datetime import datetime, timedelta
import asyncio
import subprocess
from dotenv import load_dotenv
import os
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv()

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

class AuditoriumState(Base):
    __tablename__ = "auditorium_state"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auditorium_number = Column(Integer, unique=True, index=True, nullable=False)
    is_network_on = Column(Boolean, default=True, nullable=False)
    unlock_time = Column(DateTime, nullable=True)

class AuditoriumStateRead(BaseModel):
    auditorium_number: int
    is_network_on: bool
    unlock_time: Optional[datetime]

    class Config:
        orm_mode = True

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
        # Устанавливаем начальное состояние аудиторий
        await initialize_auditoriums(conn)

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

class Auditorium(BaseModel):
    number: int
    duration: Optional[int] = 60  # Время блокировки в минутах, по умолчанию 60

async def run_ansible_playbook(playbook_name, auditorium_number):
    if os.getenv("MODE", "development") == "production":
        result = subprocess.run(
            ["ansible-playbook", playbook_name, "-e", f"auditorium_number={auditorium_number}"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Ansible playbook failed: {result.stderr}")
        return result.stdout
    else:
        return f"Simulated running playbook {playbook_name} for auditorium {auditorium_number}"

async def auto_unlock_network(auditorium: Auditorium):
    async with SessionLocal() as session:
        try:
            # Получаем состояние аудитории
            print('auditorium_number', auditorium.number)
            result = await session.execute(
                select(AuditoriumState)
                .where(AuditoriumState.auditorium_number == auditorium.number)
                .execution_options(populate_existing=True)
            )
            auditorium_state = result.scalar_one_or_none()
            if not auditorium_state:
                raise ValueError(f"Аудитория {auditorium.number} не найдена.")

            # Проверяем время разблокировки
            current_time = datetime.utcnow()
            print(f"[DEBUG] Current time: {current_time}, Unlock time: {auditorium_state.unlock_time}")
            print(f"[DEBUG] Auditorium network: {auditorium_state.is_network_on}")

            if auditorium_state.unlock_time:
                delay = (auditorium_state.unlock_time - current_time).total_seconds()
                print(f"[DEBUG] Calculated delay: {delay} seconds")

                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    print(f"[DEBUG] Unlock time is already in the past. Immediate unlock.")

            # Разблокируем аудиторию
            await run_ansible_playbook("network_on.yaml", auditorium.number)
            auditorium_state.is_network_on = True
            auditorium_state.unlock_time = None
            await session.commit()
            print(f"Аудитория {auditorium.number} успешно разблокирована.")
        except Exception as e:
            print(f"Ошибка разблокировки аудитории {auditorium.number}: {e}")


@app.post("/auditoriums/lock")
async def lock_auditorium(auditorium: Auditorium, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session_local)):
    await run_ansible_playbook("network_off.yaml", auditorium.number)
    print('datetime.utcnow()', datetime.utcnow(), '\n')
    print('timedelta(minutes=auditorium.duration)', timedelta(minutes=auditorium.duration), '\n')
    unlock_time = datetime.utcnow() + timedelta(minutes=auditorium.duration)
    print('unlock_time', unlock_time, '\n')

    async with session.begin():
        # Проверяем, существует ли запись для данной аудитории
        result = await session.execute(
            select(AuditoriumState)
            .where(AuditoriumState.auditorium_number == auditorium.number)
            .execution_options(populate_existing=True)
        )
        existing_state = result.scalar_one_or_none()

        if existing_state:
            # Обновляем существующую запись
            existing_state.is_network_on = False
            existing_state.unlock_time = unlock_time
        else:
            # Создаем новую запись
            new_state = AuditoriumState(
                auditorium_number=auditorium.number,
                is_network_on=False,
                unlock_time=unlock_time,
            )
            session.add(new_state)

        await session.commit()
        print(f"Аудитория номер {auditorium.number} заблокирована до {unlock_time}")

    background_tasks.add_task(auto_unlock_network, auditorium)
    return {"message": f"Аудитория номер {auditorium.number} заблокирована до {unlock_time}"}


@app.post("/auditoriums/unlock")
async def unlock_auditorium(auditorium: Auditorium, session: AsyncSession = Depends(get_session_local)):
    await run_ansible_playbook("network_on.yaml", auditorium.number)

    async with session.begin():
        await session.execute(
            AuditoriumState.__table__.update()
            .where(AuditoriumState.auditorium_number == auditorium.number)
            .values(is_network_on=True, unlock_time=None)
        )
        await session.commit()
        print(f"Аудитория номер {auditorium.number} успешно разблокирована")

    return {"message": f"Аудитория номер {auditorium.number} успешно разблокирована"}


@app.get("/auditoriums/status", response_model=List[AuditoriumStateRead])
async def get_auditoriums_status(session: AsyncSession = Depends(get_session_local)):
    """
    Получает состояние всех аудиторий.
    """
    result = await session.execute(select(AuditoriumState))
    auditoriums = result.scalars().all()
    return auditoriums

async def initialize_auditoriums(conn):
    """
    Инициализирует состояние аудиторий в базе данных.
    """
    auditoriums = [11, 14, 15, 17, 19, 20, 23, 24, 103, 113, 262]  # Список номеров аудиторий
    async with SessionLocal() as session:
        for number in auditoriums:
            auditorium_state = AuditoriumState(
                auditorium_number=number,
                is_network_on=True,
                unlock_time=None
            )
            session.add(auditorium_state)
        await session.commit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
