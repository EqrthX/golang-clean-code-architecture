from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.entities.user import User
from app.domain.errors import ResourceNotFoundError
from app.domain.user_repository import UserRepository
from app.interface.http.dependencies import get_current_user, get_user_repository
from app.usecases.data import describe_resource, get_data, list_data

router = APIRouter(prefix="/data", tags=["Data"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Repository = Annotated[UserRepository, Depends(get_user_repository)]


@router.get("/{resource}/describe")
async def describe(resource: str, user: CurrentUser) -> dict:
    try:
        return describe_resource(resource)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="ไม่พบชุดข้อมูลนี้") from None


@router.get("/{resource}/")
async def list_records(
    resource: str,
    user: CurrentUser,
    repository: Repository,
    page: Annotated[int, Query(alias="_page", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="_pageSize", ge=1, le=100)] = 10,
) -> dict:
    try:
        return await list_data(repository, resource, user.id, page, page_size)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="ไม่พบชุดข้อมูลนี้") from None


@router.get("/{resource}/{record_id}")
async def retrieve(
    resource: str, record_id: str, user: CurrentUser, repository: Repository
) -> dict:
    try:
        return await get_data(repository, resource, record_id, user.id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลนี้") from None
