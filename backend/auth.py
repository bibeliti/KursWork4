from fastapi_users import FastAPIUsers, BaseUserManager, schemas
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from passlib.context import CryptContext
from fastapi import Depends
from database import get_session_local
from models import UserTable
from schemas import UserRead, UserCreate, UserUpdate
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def get_user_db(session=Depends(get_session_local)):
    yield SQLAlchemyUserDatabase(session, UserTable)

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
        user_data = user.dict()
        user_data["hashed_password"] = hashed_password
        user_data["is_active"] = True
        db_user = UserTable(**user_data)
        await self.user_db.create(db_user)
        await self.on_after_register(db_user)
        return db_user

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
