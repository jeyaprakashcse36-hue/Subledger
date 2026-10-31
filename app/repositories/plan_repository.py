
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, plan: Plan) -> Plan:
        self.db.add(plan)
        self.db.flush()
        self.db.refresh(plan)
        return plan

    def get_by_id(self, plan_id: int) -> Plan | None:
        return self.db.get(Plan, plan_id)

    def list_all(
        self, active_only: bool = False, limit: int = 100, offset: int = 0
    ) -> list[Plan]:
        statement = select(Plan).order_by(Plan.id)

        if active_only:
            statement = statement.where(Plan.is_active.is_(True))

        statement = statement.limit(limit).offset(offset)
        return list(self.db.scalars(statement).all())
