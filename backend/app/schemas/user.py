from pydantic import BaseModel, EmailStr, ConfigDict

from app.models.user import UserRole

class UserRead(BaseModel):
    id: int
    email: EmailStr
    role: UserRole

    model_config = ConfigDict(from_attributes=True, extra='allow') # it allows pydantic to convert a SQLAlchemy model object lie `user.email` to JSON like `{"id": 1, "email": "aman@example.com"}`