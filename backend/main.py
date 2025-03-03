from fastapi import FastAPI
from database import engine, Base
from routers import router
from auth import fastapi_users, auth_backend
from schemas import UserRead, UserCreate, UserUpdate
from utils import initialize_auditoriums
import asyncio
import signal
import sys

async def shutdown():
    print('Завершение работы сервера...')
    await asyncio.sleep(0.1)
    asyncio.get_event_loop().stop()

def signal_handler(sig, frame):
    asyncio.create_task(shutdown())

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

app = FastAPI()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await initialize_auditoriums(conn)

@app.on_event("shutdown")
async def shutdown():
    await asyncio.sleep(0.1)
    asyncio.get_event_loop().stop()

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])
app.include_router(router)
