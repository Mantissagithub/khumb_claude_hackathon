"""Auth core: password hashing, JWT issuance, and FastAPI dependencies.

`get_current_user` validates the Bearer token and loads the staff row.
`require_role(*roles)` builds a dependency that 403s on insufficient role.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SANGAM_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 8

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(plain: str) -> str:
    return pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd.verify(plain, hashed)


def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2)) -> dict:
    # Imported lazily to avoid a circular import (db imports hash_password).
    from .db import get_conn

    exc = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Invalid credentials",
        {"WWW-Authenticate": "Bearer"},
    )
    try:
        username = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
    except Exception:
        raise exc
    if not username:
        raise exc
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, role, name FROM staff WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise exc
    return {"id": row["id"], "username": row["username"], "role": row["role"], "name": row["name"]}


def require_role(*allowed: str):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return checker
