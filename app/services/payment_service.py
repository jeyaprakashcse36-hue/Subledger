from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.ledger_entry import LedgerEntry
from app.models.payment_attempt import PaymentAttempt
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.ledger_repository import LedgerRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import PaymentCreate


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.invoices = InvoiceRepository(db)
        self.payments = PaymentRepository(db)
        self.ledger = LedgerRepository(db)

    @staticmethod
    def _same_request(
        existing: PaymentAttempt, data: PaymentCreate
    ) -> bool:
        return (
            existing.invoice_id == data.invoice_id
            and existing.amount == data.amount
            and existing.currency == data.currency
            and existing.status == data.status
            and existing.provider_reference == data.provider_reference
            and existing.failure_reason == data.failure_reason
        )

    def _existing_result(self, data: PaymentCreate) -> PaymentAttempt | None:
        existing = self.payments.get_by_idempotency_key(data.idempotency_key)
        if existing is None:
            return None
        if not self._same_request(existing, data):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already used for another request",
            )
        return existing

    def create_payment(self, data: PaymentCreate) -> PaymentAttempt:
        try:
            existing = self._existing_result(data)
            if existing is not None:
                self.db.commit()
                return existing

            invoice = self.invoices.get_for_update(data.invoice_id)
            if invoice is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invoice not found",
                )

            # Recheck after locking so a concurrent identical request can replay.
            existing = self._existing_result(data)
            if existing is not None:
                self.db.commit()
                return existing

            if data.currency != invoice.currency:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Payment currency does not match invoice currency",
                )

            if invoice.status == "paid":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invoice is already fully paid",
                )

            if data.status == "succeeded":
                outstanding = invoice.amount_due - invoice.amount_paid
                if data.amount > outstanding:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Payment exceeds outstanding balance: {outstanding}",
                    )

            payment = PaymentAttempt(
                invoice_id=invoice.id,
                amount=data.amount,
                currency=data.currency,
                status=data.status,
                provider_reference=data.provider_reference,
                idempotency_key=data.idempotency_key,
                failure_reason=data.failure_reason,
            )

            try:
                # The savepoint lets a unique-key race be handled without losing
                # the surrounding transaction and invoice lock.
                with self.db.begin_nested():
                    self.payments.create(payment)
            except IntegrityError:
                replay = self._existing_result(data)
                if replay is not None:
                    self.db.commit()
                    return replay
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Payment conflicts with an existing record",
                )

            if data.status == "succeeded":
                self._apply_successful_payment(invoice, payment)

            self.db.commit()
            self.db.refresh(payment)
            return payment
        except HTTPException:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment conflicts with an existing record",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def _apply_successful_payment(
        self, invoice: Invoice, payment: PaymentAttempt
    ) -> None:
        invoice.amount_paid += payment.amount
        invoice.status = (
            "paid" if invoice.amount_paid == invoice.amount_due else "partially_paid"
        )
        self.ledger.create(
            LedgerEntry(
                customer_id=invoice.customer_id,
                invoice_id=invoice.id,
                entry_type="payment_received",
                amount=payment.amount,
                currency=payment.currency,
                reference_id=f"payment:{payment.id}",
            )
        )

    def list_payments(
        self,
        limit: int = 100,
        offset: int = 0,
        invoice_id: int | None = None,
        payment_status: str | None = None,
    ) -> list[PaymentAttempt]:
        return self.payments.list_all(
            limit=limit,
            offset=offset,
            invoice_id=invoice_id,
            status=payment_status,
        )

    def get_payment(self, payment_id: int) -> PaymentAttempt:
        payment = self.payments.get_by_id(payment_id)
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )
        return payment
