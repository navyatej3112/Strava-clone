"""Auth schemas."""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int
    jti: str


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None  # Only in body for legacy; normally sent via HttpOnly cookie
    token_type: str = "bearer"
    expires_in: int  # seconds
