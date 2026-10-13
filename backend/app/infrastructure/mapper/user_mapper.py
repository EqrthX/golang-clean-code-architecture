from app.domain.entities.user import User
from app.infrastructure.database.models.user_model import UserSQLModel


class UserMapper:
    @staticmethod
    def to_entity(sql_model: UserSQLModel) -> User:
        return User(
            id=sql_model.id,
            name=sql_model.name,
            email=sql_model.email,
            created_at=sql_model.created_at,
            updated_at=sql_model.updated_at,
        )

    @staticmethod
    def to_sql_model(entity: User) -> UserSQLModel:
        return UserSQLModel(
            id=entity.id,
            name=entity.name,
            email=entity.email,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
