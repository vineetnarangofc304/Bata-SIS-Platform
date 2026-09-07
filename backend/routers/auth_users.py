import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional
from core.db import db
from core.auth import (hash_password, verify_password, create_access_token, get_current_user, admin_only, public_user, ROLES, ROLE_LABELS)
from core.utils import now_iso, new_id, paginate
from core.audit import log_audit

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str
    email: str
    name: str
    role: str
    password: Optional[str] = None
    active: bool = True


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    ident = body.username.strip().lower()
    user = await db.users.find_one({"$or": [{"username": ident}, {"email": ident}]})
    key = f"{request.client.host if request.client else 'x'}:{ident}"
    attempt = await db.login_attempts.find_one({"identifier": key})
    if attempt and attempt.get("count", 0) >= 5 and attempt.get("locked_until", "") > now_iso():
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    if not user or not verify_password(body.password, user["password_hash"]):
        from datetime import datetime, timezone, timedelta
        await db.login_attempts.update_one({"identifier": key}, {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}}, upsert=True)
        await log_audit(ident, "auth.login_failed", "user", None, {"ip": key.split(":")[0]}, category="security")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")
    await db.login_attempts.delete_one({"identifier": key})
    token = create_access_token(user["id"], user["username"], user["role"])
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": now_iso()}})
    await log_audit(user["username"], "auth.login", "user", user["id"], {}, category="security")
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    return {"token": token, "user": public_user(user), "role_label": ROLE_LABELS[user["role"]]}


@router.post("/auth/logout")
async def logout(response: Response, user=Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    await log_audit(user["username"], "auth.logout", "user", user["id"], {}, category="security")
    return {"ok": True}


@router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return {**user, "role_label": ROLE_LABELS[user["role"]]}


@router.post("/auth/change-password")
async def change_password(body: PasswordIn, user=Depends(get_current_user)):
    doc = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.current_password, doc["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password), "updated_at": now_iso()}})
    await log_audit(user["username"], "user.password_changed", "user", user["id"], {}, category="security")
    return {"ok": True}


@router.get("/users")
async def list_users(page: int = 1, page_size: int = 50, user=Depends(admin_only)):
    return await paginate(db.users, {}, page, page_size, ("username", 1), {"password_hash": 0})


@router.get("/users/roles")
async def roles(user=Depends(get_current_user)):
    return [{"key": r, "label": ROLE_LABELS[r]} for r in ROLES]


@router.post("/users")
async def create_user(body: UserIn, user=Depends(admin_only)):
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if not body.password or len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password of at least 8 characters required")
    uname = body.username.strip().lower()
    if await db.users.find_one({"$or": [{"username": uname}, {"email": body.email.lower()}]}):
        raise HTTPException(status_code=409, detail="Username or email already exists")
    doc = {"id": new_id(), "username": uname, "email": body.email.lower(), "name": body.name, "role": body.role, "active": body.active,
           "password_hash": hash_password(body.password), "created_at": now_iso(), "created_by": user["username"]}
    await db.users.insert_one(dict(doc))
    await log_audit(user["username"], "user.created", "user", doc["id"], {"username": uname, "role": body.role}, category="users")
    return public_user(doc)


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: UserIn, user=Depends(admin_only)):
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    upd = {"email": body.email.lower(), "name": body.name, "role": body.role, "active": body.active, "updated_at": now_iso()}
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        upd["password_hash"] = hash_password(body.password)
    res = await db.users.update_one({"id": user_id}, {"$set": upd})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="User not found")
    await log_audit(user["username"], "user.updated", "user", user_id, {k: v for k, v in upd.items() if k != "password_hash"}, category="users")
    return public_user(await db.users.find_one({"id": user_id}))
