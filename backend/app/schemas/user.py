from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserMinRead(BaseModel):
    id: int
    full_name: str | None = None
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    full_name: str | None = None
    avatar_key: str | None = None
    is_active: bool
    is_email_verified: bool

    model_config = ConfigDict(from_attributes=True)


class UserUpdateProfile(BaseModel):
    full_name: str | None = Field(None, max_length=255)


class UserRoleUpdate(BaseModel):
    role: UserRole
