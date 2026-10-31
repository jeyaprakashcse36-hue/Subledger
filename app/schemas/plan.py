
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(
        default="INR", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$"
    )
    billing_interval: str = Field(min_length=1, max_length=20, default="monthly")
    is_active: bool = True

    @field_validator("name", "billing_interval")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This value cannot be blank")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class PlanRead(BaseModel):
    id: int
    name: str
    description: str | None
    price: Decimal
    currency: str
    billing_interval: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
