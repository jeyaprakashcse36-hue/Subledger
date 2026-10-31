
from datetime import datetime, time, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.invoice import InvoiceCreate


class InvoiceService:
    def __init__(self, db: Session):
        self.db = db
        self.invoices = InvoiceRepository(db)
        self.subscriptions = SubscriptionRepository(db)

    def create_invoice(self, data: InvoiceCreate) -> Invoice:
        subscription = self.subscriptions.get_by_id(data.subscription_id)

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Subscription not found"
            )

        if subscription.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot generate invoice for inactive subscription",
            )

        period_start = datetime.combine(
            data.period_start, time.min, tzinfo=timezone.utc
        )
        period_end = datetime.combine(data.period_end, time.min, tzinfo=timezone.utc)
        if period_end <= period_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invoice period end must be after start",
            )

        if self.invoices.get_for_subscription_period(
            data.subscription_id, period_start, period_end
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice already exists for this billing period",
            )

        invoice = Invoice(
            subscription_id=subscription.id,
            customer_id=subscription.customer_id,
            amount_due=subscription.plan.price,
            amount_paid=0,
            currency=subscription.plan.currency,
            status="issued",
            period_start=period_start,
            period_end=period_end,
            due_date=(
                datetime.combine(data.due_date, time.min, tzinfo=timezone.utc)
                if data.due_date is not None
                else None
            ),
        )

        try:
            result = self.invoices.create(invoice)
            self.db.commit()
            self.db.refresh(result)
            return result
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice already exists for this billing period",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def get_invoice(self, invoice_id: int) -> Invoice:
        invoice = self.invoices.get_by_id(invoice_id)

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        return invoice

    def list_invoices(
        self,
        limit: int = 100,
        offset: int = 0,
        customer_id: int | None = None,
        subscription_id: int | None = None,
        invoice_status: str | None = None,
    ) -> list[Invoice]:
        return self.invoices.list_all(
            limit=limit,
            offset=offset,
            customer_id=customer_id,
            subscription_id=subscription_id,
            status=invoice_status,
        )
