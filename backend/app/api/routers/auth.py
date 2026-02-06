"""Auth: signup, login, refresh (cookie-based), logout."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.services.auth_service import AuthService
from app.schemas import UserCreate, UserResponse, Token, LoginRequest
from app.api.deps import rate_limit_stub

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * settings.refresh_token_expire_days


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_SECONDS,
        httponly=True,
        samesite=settings.cookie_same_site,
        secure=settings.cookie_secure,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.cookie_name, path="/", samesite=settings.cookie_same_site)


@router.post("/signup", response_model=UserResponse)
async def signup(
    request: Request,
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    rate_limit_stub(request)
    service = AuthService(db)
    try:
        return await service.signup(data)
    except ValueError as e:
        if "already registered" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    rate_limit_stub(request)
    user_agent = request.headers.get("user-agent")
    client = request.client
    ip = str(client.host) if client else None
    service = AuthService(db)
    try:
        token = await service.login(data, user_agent=user_agent, ip=ip)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    _set_refresh_cookie(response, token.refresh_token or "")
    return Token(
        access_token=token.access_token,
        refresh_token=None,
        expires_in=token.expires_in,
    )


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Token:
    rate_limit_stub(request)
    refresh_token = request.cookies.get(settings.cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    service = AuthService(db)
    try:
        token = await service.refresh_tokens(refresh_token)
    except ValueError as e:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    _set_refresh_cookie(response, token.refresh_token or "")
    return Token(
        access_token=token.access_token,
        refresh_token=None,
        expires_in=token.expires_in,
    )


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    rate_limit_stub(request)
    refresh_token = request.cookies.get(settings.cookie_name)
    service = AuthService(db)
    await service.logout(refresh_token)
    _clear_refresh_cookie(response)
    return {"message": "Logged out"}
