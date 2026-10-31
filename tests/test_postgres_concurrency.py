from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    Customer,
    Invoice,
    LedgerEntry,
    PaymentAttempt,
    Plan,
    Subscription,
)
from app.schemas.payment import PaymentCreate
from app.services.payment_service import PaymentService


def test_concurrent_payments_cannot_overpay_postgres(postgres_test_engine):
    engine = postgres_test_engine
    test_sessions = sessionmaker(bind=engine, expire_on_commit=False)
    marker = uuid4().hex

    with test_sessions() as session:
        customer = Customer(name="Concurrency Test", email=f"{marker}@example.test")
        plan = Plan(
            name=f"Concurrency-{marker[:8]}",
            price=Decimal("100.00"),
            currency="INR",
            billing_interval="monthly",
            is_active=True,
        )
        session.add_all((customer, plan))
        session.flush()
        now = datetime.now(timezone.utc)
        subscription = Subscription(
            customer_id=customer.id,
            plan_id=plan.id,
            status="active",
            current_period_start=now,
            current_period_end=now.replace(year=now.year + 1),
        )
        session.add(subscription)
        session.flush()
        invoice = Invoice(
            subscription_id=subscription.id,
            customer_id=customer.id,
            amount_due=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
            currency="INR",
            status="issued",
            period_start=now,
            period_end=now.replace(year=now.year + 1),
        )
        session.add(invoice)
        session.commit()
        invoice_id = invoice.id

    def attempt(key: str) -> str:
        with test_sessions() as session:
            try:
                PaymentService(session).create_payment(
                    PaymentCreate(
                        invoice_id=invoice_id,
                        amount=Decimal("60.00"),
                        currency="INR",
                        status="succeeded",
                        idempotency_key=key,
                    )
                )
                return "succeeded"
            except HTTPException as error:
                return f"rejected:{error.status_code}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                attempt,
                (f"{marker}-first", f"{marker}-second"),
            )
        )

    assert sorted(outcomes) == ["rejected:422", "succeeded"]
    with test_sessions() as session:
        saved_invoice = session.get(Invoice, invoice_id)
        assert saved_invoice is not None
        assert saved_invoice.amount_paid == Decimal("60.00")
        assert (
            session.scalar(
                select(func.count(PaymentAttempt.id)).where(
                    PaymentAttempt.invoice_id == invoice_id
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(LedgerEntry.id)).where(
                    LedgerEntry.invoice_id == invoice_id
                )
            )
            == 1
        )
