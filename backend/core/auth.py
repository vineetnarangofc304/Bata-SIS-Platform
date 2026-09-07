import os
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from core.db import db

JWT_ALGORITHM = "HS256"
ROLES = ("admin", "ops", "management")
ROLE_LABELS = {"admin": "Administrator", "ops": "Data Operations User", "management": "Management User"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, username: str, role: str, hours: int = 12) -> str:
    payload = {"sub": user_id, "username": username, "role": role, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=hours)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def public_user(user: dict) -> dict:
    return {k: v for k, v in user.items() if k not in ("_id", "password_hash")}


async def get_current_user(request: Request) -> dict:
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"id": payload["sub"]})
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return public_user(user)


def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions for this action")
        return user
    return checker


admin_only = require_roles("admin")
ops_or_admin = require_roles("admin", "ops")
any_user = get_current_user
