
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment_attempt import PaymentAttempt


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payment: PaymentAttempt) -> PaymentAttempt:
        self.db.add(payment)
        self.db.flush()
        self.db.refresh(payment)
        return payment

    def get_by_id(self, payment_id: int) -> PaymentAttempt | None:
        return self.db.get(PaymentAttempt, payment_id)

    def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> PaymentAttempt | None:
        statement = select(PaymentAttempt).where(
            PaymentAttempt.idempotency_key == idempotency_key
        )
        return self.db.scalar(statement)

    def list_by_invoice(self, invoice_id: int) -> list[PaymentAttempt]:
        statement = (
            select(PaymentAttempt)
            .where(PaymentAttempt.invoice_id == invoice_id)
            .order_by(PaymentAttempt.id)
        )
        return list(self.db.scalars(statement).all())

    def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        invoice_id: int | None = None,
        status: str | None = None,
    ) -> list[PaymentAttempt]:
        statement = select(PaymentAttempt).order_by(PaymentAttempt.id)
        if invoice_id is not None:
            statement = statement.where(PaymentAttempt.invoice_id == invoice_id)
        if status is not None:
            statement = statement.where(PaymentAttempt.status == status)
        statement = statement.limit(limit).offset(offset)
        return list(self.db.scalars(statement).all())
