import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#6B7280", max_length=7)

    @field_validator("color")
    @classmethod
    def must_be_hex_color(cls, v: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("color must be a valid hex color like #FF5733")
        return v.upper()


class LabelRead(BaseModel):
    id: int
    project_id: int
    name: str
    color: str

    model_config = ConfigDict(from_attributes=True)
