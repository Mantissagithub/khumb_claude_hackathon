"""Auth router: staff login + identity. Mounted at /api/auth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from shared.db import get_conn
from shared.security import create_token, get_current_user, verify_password

router = APIRouter()


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


class MeOut(BaseModel):
    username: str
    role: str
    name: str


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends()):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT username, password_hash, role, name FROM staff WHERE username = ?",
            (form.username,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not verify_password(form.password, row["password_hash"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password",
            {"WWW-Authenticate": "Bearer"},
        )
    token = create_token(row["username"], row["role"])
    return TokenOut(access_token=token, role=row["role"], name=row["name"])


@router.get("/me", response_model=MeOut)
def me(user: dict = Depends(get_current_user)):
    return MeOut(username=user["username"], role=user["role"], name=user["name"])
