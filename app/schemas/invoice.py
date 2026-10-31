
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceCreate(BaseModel):
    subscription_id: int = Field(gt=0)
    period_start: date
    period_end: date
    due_date: date | None = None


class InvoiceRead(BaseModel):
    id: int
    subscription_id: int
    customer_id: int
    amount_due: Decimal
    amount_paid: Decimal
    currency: str
    status: str
    period_start: date
    period_end: date
    due_date: date | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
