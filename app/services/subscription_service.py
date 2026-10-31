from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionCreate


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SubscriptionRepository(db)
        self.customer_repository = CustomerRepository(db)
        self.plan_repository = PlanRepository(db)

    def create_subscription(self, data: SubscriptionCreate) -> Subscription:
        customer = self.customer_repository.get_by_id(data.customer_id)
        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        plan = self.plan_repository.get_by_id(data.plan_id)
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found",
            )

        if not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot subscribe to an inactive plan",
            )

        existing = self.repository.get_active_for_customer_and_plan(
            data.customer_id, data.plan_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer already has an active subscription to this plan",
            )

        subscription = Subscription(
            customer_id=data.customer_id,
            plan_id=data.plan_id,
            status="active",
            current_period_start=data.current_period_start,
            current_period_end=data.current_period_end,
        )

        try:
            result = self.repository.create(subscription)
            self.db.commit()
            self.db.refresh(result)
            return result
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription conflicts with an existing database record",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def list_subscriptions(
        self, limit: int = 100, offset: int = 0
    ) -> list[Subscription]:
        return self.repository.list_all(limit=limit, offset=offset)

    def get_subscription(self, subscription_id: int) -> Subscription:
        subscription = self.repository.get_by_id(subscription_id)
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found",
            )
        return subscription