from math import ceil

from app.domain.errors import ResourceNotFoundError
from app.domain.user_repository import UserRepository

PUBLIC_FIELDS = {
    "users": {
        "id": "integer",
        "name": "string",
        "email": "string",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "user_tokens": {
        "id": "uuid",
        "user_id": "integer",
        "expires_at": "datetime",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "user_permissions": {
        "id": "integer",
        "user_id": "integer",
        "permission": "string",
        "updated_at": "datetime",
    },
}


def describe_resource(resource: str) -> dict:
    if resource not in PUBLIC_FIELDS:
        raise ResourceNotFoundError()
    return {"name": resource, "datasource": "postgresql", "fields": PUBLIC_FIELDS[resource]}


async def list_data(
    repository: UserRepository, resource: str, user_id: int, page: int, page_size: int
) -> dict:
    schema = describe_resource(resource)
    admin = await repository.get_permission(user_id) == "admin"
    rows, total = await repository.list_records(resource, user_id, admin, page, page_size)
    return {
        "data": rows,
        "page": page,
        "page_size": page_size,
        "total_data": total,
        "total_page": ceil(total / page_size),
        "data_schema": schema,
    }


async def get_data(repository: UserRepository, resource: str, record_id: str, user_id: int) -> dict:
    schema = describe_resource(resource)
    admin = await repository.get_permission(user_id) == "admin"
    record = await repository.get_record(resource, record_id, user_id, admin)
    if record is None:
        raise ResourceNotFoundError()
    return {"data": record, "data_schema": schema}
