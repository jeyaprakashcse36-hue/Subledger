
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentCreate(BaseModel):
    invoice_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(
        default="INR", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$"
    )
    status: Literal["succeeded", "failed"]
    provider_reference: str | None = Field(default=None, max_length=255)
    idempotency_key: str = Field(min_length=1, max_length=100)
    failure_reason: str | None = Field(default=None, max_length=500)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Idempotency key cannot be blank")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PaymentRead(BaseModel):
    id: int
    invoice_id: int
    amount: Decimal
    currency: str
    status: str
    provider_reference: str | None
    idempotency_key: str | None
    failure_reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
