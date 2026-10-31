
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanCreate


class PlanService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PlanRepository(db)

    def create_plan(self, data: PlanCreate) -> Plan:
        plan = Plan(
            name=data.name.strip(),
            description=data.description,
            price=data.price,
            currency=data.currency.upper(),
            billing_interval=data.billing_interval.lower(),
            is_active=data.is_active,
        )

        try:
            result = self.repository.create(plan)
            self.db.commit()
            self.db.refresh(result)
            return result
        except Exception:
            self.db.rollback()
            raise

    def get_plan(self, plan_id: int) -> Plan:
        plan = self.repository.get_by_id(plan_id)

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found",
            )

        return plan

    def list_plans(
        self, active_only: bool = False, limit: int = 100, offset: int = 0
    ) -> list[Plan]:
        return self.repository.list_all(active_only, limit=limit, offset=offset)

    def get_plan(self, plan_id: int) -> Plan:
        plan = self.repository.get_by_id(plan_id)
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found",
            )
        return plan
