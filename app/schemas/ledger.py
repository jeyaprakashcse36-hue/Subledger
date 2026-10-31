
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LedgerRead(BaseModel):
    id: int
    customer_id: int
    invoice_id: int | None
    entry_type: str
    amount: Decimal
    currency: str
    reference_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
