from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubscriptionCreate(BaseModel):
    customer_id: int = Field(gt=0)
    plan_id: int = Field(gt=0)
    current_period_start: datetime
    current_period_end: datetime

    @model_validator(mode="after")
    def validate_period(self):
        start = self.current_period_start
        end = self.current_period_end
        if start.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("Subscription period timestamps must include time zones")
        if end <= start:
            raise ValueError("The subscription period end must be after its start")
        return self


class SubscriptionRead(BaseModel):
    id: int
    customer_id: int
    plan_id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)