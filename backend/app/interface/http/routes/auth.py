from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.domain.entities.user import User
from app.domain.errors import DuplicateEmailError, InvalidTokenError, PasswordVerifyError
from app.domain.user_repository import UserRepository
from app.interface.http.dependencies import get_current_user, get_user_repository, unauthorized
from app.interface.http.schemas.auth import (
    RefreshTokenRequest,
    RegisterResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
)
from app.usecases.usecease_auth import login_user, logout_user, refresh_user_token, register_user

router = APIRouter(tags=["Auth"])
Repository = Annotated[UserRepository, Depends(get_user_repository)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(form_data: UserCreate, repository: Repository) -> RegisterResponse:
    try:
        user = await register_user(
            repository, name=form_data.name, email=str(form_data.email), password=form_data.password
        )
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="มีผู้ใช้งานอีเมลนี้แล้ว") from None
    return RegisterResponse(Data=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(form_data: UserLogin, repository: Repository) -> TokenResponse:
    try:
        tokens = await login_user(repository, str(form_data.email), form_data.password)
    except PasswordVerifyError:
        raise unauthorized("อีเมลหรือรหัสผ่านไม่ถูกต้อง") from None
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh-token", response_model=TokenResponse)
async def refresh_token(form_data: RefreshTokenRequest, repository: Repository) -> TokenResponse:
    try:
        tokens = await refresh_user_token(repository, form_data.refresh_token)
    except InvalidTokenError:
        raise unauthorized() from None
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", status_code=204)
async def logout(form_data: RefreshTokenRequest, repository: Repository) -> Response:
    try:
        await logout_user(repository, form_data.refresh_token)
    except InvalidTokenError:
        raise unauthorized() from None
    return Response(status_code=204)


@router.get("/protected")
async def protected(user: CurrentUser) -> dict:
    return {"message": "ยืนยันตัวตนสำเร็จ", "user_id": str(user.id)}


@router.post("/profile", response_model=UserRead, include_in_schema=False)
@router.get("/profile", response_model=UserRead)
async def profile(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
