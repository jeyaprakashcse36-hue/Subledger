from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import Subscription


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, subscription: Subscription) -> Subscription:
        self.db.add(subscription)
        self.db.flush()
        self.db.refresh(subscription)
        return subscription

    def get_by_id(self, subscription_id: int) -> Subscription | None:
        return self.db.get(Subscription, subscription_id)

    def get_active_for_customer_and_plan(
        self, customer_id: int, plan_id: int
    ) -> Subscription | None:
        statement = select(Subscription).where(
            Subscription.customer_id == customer_id,
            Subscription.plan_id == plan_id,
            Subscription.status == "active",
        )
        return self.db.scalars(statement).first()

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Subscription]:
        statement = (
            select(Subscription).order_by(Subscription.id).limit(limit).offset(offset)
        )
        return list(self.db.scalars(statement).all())