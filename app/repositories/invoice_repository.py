
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice


class InvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, invoice: Invoice) -> Invoice:
        self.db.add(invoice)
        self.db.flush()
        self.db.refresh(invoice)
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        return self.db.get(Invoice, invoice_id)

    def get_for_subscription_period(
        self,
        subscription_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> Invoice | None:
        statement = select(Invoice).where(
            Invoice.subscription_id == subscription_id,
            Invoice.period_start == period_start,
            Invoice.period_end == period_end,
        )
        return self.db.scalar(statement)

    def get_for_update(self, invoice_id: int) -> Invoice | None:
        statement = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        customer_id: int | None = None,
        subscription_id: int | None = None,
        status: str | None = None,
    ) -> list[Invoice]:
        statement = select(Invoice).order_by(Invoice.id)
        if customer_id is not None:
            statement = statement.where(Invoice.customer_id == customer_id)
        if subscription_id is not None:
            statement = statement.where(Invoice.subscription_id == subscription_id)
        if status is not None:
            statement = statement.where(Invoice.status == status)
        statement = statement.limit(limit).offset(offset)
        return list(self.db.scalars(statement).all())

    def get_by_subscription(self, subscription_id: int) -> list[Invoice]:
        statement = (
            select(Invoice)
            .where(Invoice.subscription_id == subscription_id)
            .order_by(Invoice.id)
        )
        return list(self.db.scalars(statement).all())
