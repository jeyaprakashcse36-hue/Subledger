from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.invoice import Invoice
from app.models.ledger_entry import LedgerEntry
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.ledger_repository import LedgerRepository


def create_plan(client: TestClient, **overrides) -> dict:
    payload = {
        "name": "Starter",
        "price": "25.50",
        "currency": "INR",
        "billing_interval": "monthly",
    }
    payload.update(overrides)
    return client.post("/api/v1/plans", json=payload)


def create_customer(client: TestClient, **overrides) -> dict:
    payload = {"name": "Grace Hopper", "email": "grace@example.com"}
    payload.update(overrides)
    return client.post("/api/v1/customers", json=payload)


def create_subscription(
    client: TestClient, customer_id: int, plan_id: int, **overrides
):
    payload = {
        "customer_id": customer_id,
        "plan_id": plan_id,
        "current_period_start": "2026-01-01T00:00:00Z",
        "current_period_end": "2026-02-01T00:00:00Z",
    }
    payload.update(overrides)
    return client.post("/api/v1/subscriptions", json=payload)


def create_invoice(client: TestClient, subscription_id: int, **overrides):
    payload = {
        "subscription_id": subscription_id,
        "period_start": "2026-01-01",
        "period_end": "2026-02-01",
    }
    payload.update(overrides)
    return client.post("/api/v1/invoices", json=payload)


def create_payment(invoice: dict, **overrides):
    payload = {
        "invoice_id": invoice["id"],
        "amount": "40.00",
        "currency": invoice["currency"],
        "status": "succeeded",
        "idempotency_key": "payment-key-1",
    }
    payload.update(overrides)
    return payload


def test_plan_create_and_currency_normalization(client):
    response = create_plan(client, currency="inr")
    assert response.status_code == 201
    assert response.json()["price"] == "25.50"
    assert response.json()["currency"] == "INR"


@pytest.mark.parametrize("price", ["0", "-1.00"])
def test_plan_rejects_nonpositive_price(client, price):
    assert create_plan(client, price=price).status_code == 422


def test_plan_rejects_invalid_name(client):
    assert create_plan(client, name=" ").status_code == 422


def test_plan_list_pagination_and_detail(client, plan):
    second = create_plan(client, name="Premium")
    assert second.status_code == 201
    page = client.get("/api/v1/plans?limit=1&offset=1")
    assert page.status_code == 200
    assert len(page.json()) == 1
    assert page.json()[0]["name"] == "Premium"
    assert client.get(f"/api/v1/plans/{plan['id']}").json()["id"] == plan["id"]


def test_plan_active_filter(client, plan):
    inactive = create_plan(client, name="Archived", is_active=False)
    assert inactive.status_code == 201
    active = client.get("/api/v1/plans?active_only=true")
    assert [item["name"] for item in active.json()] == ["Standard"]


def test_customer_create_normalizes_email(client):
    response = create_customer(client)
    assert response.status_code == 201
    assert response.json()["email"] == "grace@example.com"


def test_customer_duplicate_email_is_case_insensitive(client, customer):
    response = create_customer(client, email="ADA@EXAMPLE.COM")
    assert response.status_code == 409


def test_customer_rejects_invalid_email(client):
    assert create_customer(client, email="not-an-email").status_code == 422


def test_customer_listing_and_detail(client, customer):
    assert client.get("/api/v1/customers?limit=1").json()[0]["id"] == customer["id"]
    assert client.get(f"/api/v1/customers/{customer['id']}").status_code == 200
    assert client.get("/api/v1/customers/9999").status_code == 404


def test_subscription_creation_and_listing(client, subscription):
    assert subscription["status"] == "active"
    assert len(client.get("/api/v1/subscriptions?limit=1").json()) == 1
    assert (
        client.get(f"/api/v1/subscriptions/{subscription['id']}").status_code == 200
    )


def test_subscription_rejects_inactive_plan(client, customer):
    inactive = create_plan(client, is_active=False).json()
    response = create_subscription(client, customer["id"], inactive["id"])
    assert response.status_code == 409


def test_subscription_rejects_unknown_customer(client, plan):
    response = create_subscription(client, 9999, plan["id"])
    assert response.status_code == 404


def test_subscription_rejects_unknown_plan(client, customer):
    response = create_subscription(client, customer["id"], 9999)
    assert response.status_code == 404


def test_subscription_prevents_duplicate_active_plan(client, subscription):
    response = create_subscription(
        client, subscription["customer_id"], subscription["plan_id"]
    )
    assert response.status_code == 409


def test_subscription_rejects_invalid_period(client, customer, plan):
    response = create_subscription(
        client,
        customer["id"],
        plan["id"],
        current_period_end="2025-12-31T00:00:00Z",
    )
    assert response.status_code == 422


def test_invoice_uses_plan_price_snapshot(client, invoice, db_session):
    plan = db_session.query(Plan).first()
    assert plan is not None
    plan.price = Decimal("200.00")
    db_session.commit()
    saved = client.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert saved["amount_due"] == "100.00"
    assert saved["amount_paid"] == "0.00"
    assert saved["status"] == "issued"


def test_invoice_rejects_duplicate_billing_period(client, invoice):
    response = create_invoice(client, invoice["subscription_id"])
    assert response.status_code == 409


def test_invoice_rejects_inactive_subscription(client, subscription, db_session):
    row = db_session.get(Subscription, subscription["id"])
    row.status = "canceled"
    db_session.commit()
    assert create_invoice(client, subscription["id"]).status_code == 409


def test_invoice_rejects_invalid_period(client, subscription):
    response = create_invoice(
        client,
        subscription["id"],
        period_start="2026-02-01",
        period_end="2026-01-01",
    )
    assert response.status_code == 422


def test_invoice_filters_and_pagination(client, invoice):
    response = client.get(
        f"/api/v1/invoices?customer_id={invoice['customer_id']}&limit=1"
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert client.get("/api/v1/invoices?status=paid").json() == []


def test_payment_success_updates_balance_and_ledger(client, invoice, customer):
    response = client.post("/api/v1/payments", json=create_payment(invoice))
    assert response.status_code == 201
    saved_invoice = client.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert saved_invoice["amount_paid"] == "40.00"
    assert saved_invoice["status"] == "partially_paid"
    ledger = client.get(f"/api/v1/ledger/customer/{customer['id']}").json()
    assert len(ledger) == 1
    assert ledger[0]["entry_type"] == "payment_received"


def test_payment_full_balance_marks_invoice_paid(client, invoice):
    response = client.post(
        "/api/v1/payments",
        json=create_payment(invoice, amount="100.00"),
    )
    assert response.status_code == 201
    saved = client.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert saved["status"] == "paid"
    assert saved["amount_paid"] == "100.00"


def test_failed_payment_does_not_change_invoice_or_ledger(
    client, invoice, customer
):
    payload = create_payment(
        invoice, status="failed", failure_reason="declined", amount="1000.00"
    )
    assert client.post("/api/v1/payments", json=payload).status_code == 201
    saved = client.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert saved["amount_paid"] == "0.00"
    assert saved["status"] == "issued"
    assert client.get(f"/api/v1/ledger/customer/{customer['id']}").status_code == 404


def test_payment_rejects_overpayment(client, invoice):
    response = client.post(
        "/api/v1/payments",
        json=create_payment(invoice, amount="100.01"),
    )
    assert response.status_code == 422


def test_payment_rejects_currency_mismatch(client, invoice):
    response = client.post(
        "/api/v1/payments",
        json=create_payment(invoice, currency="USD"),
    )
    assert response.status_code == 422


def test_payment_idempotency_replays_original_result(client, invoice):
    payload = create_payment(invoice, amount="100.00")
    first = client.post("/api/v1/payments", json=payload)
    replay = client.post("/api/v1/payments", json=payload)
    assert first.status_code == replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert len(client.get("/api/v1/ledger").json()) == 1


def test_payment_idempotency_conflict_for_changed_request(client, invoice):
    first_payload = create_payment(invoice)
    assert client.post("/api/v1/payments", json=first_payload).status_code == 201
    conflict = client.post(
        "/api/v1/payments",
        json={**first_payload, "amount": "41.00"},
    )
    assert conflict.status_code == 409


def test_payment_idempotency_compares_provider_details(client, invoice):
    payload = create_payment(invoice, status="failed")
    assert client.post("/api/v1/payments", json=payload).status_code == 201
    conflict = client.post(
        "/api/v1/payments",
        json={**payload, "failure_reason": "different"},
    )
    assert conflict.status_code == 409


def test_payment_list_filters_and_detail(client, invoice):
    created = client.post(
        "/api/v1/payments", json=create_payment(invoice, status="failed")
    ).json()
    filtered = client.get(
        f"/api/v1/payments?invoice_id={invoice['id']}&status=failed&limit=1"
    )
    assert len(filtered.json()) == 1
    assert client.get(f"/api/v1/payments/{created['id']}").status_code == 200


def test_payment_rolls_back_if_ledger_insert_fails(
    client, invoice, monkeypatch
):
    def fail_create(self, entry):
        raise RuntimeError("simulated ledger storage failure")

    monkeypatch.setattr(LedgerRepository, "create", fail_create)
    with pytest.raises(RuntimeError, match="simulated ledger storage failure"):
        client.post("/api/v1/payments", json=create_payment(invoice))

    saved = client.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert saved["amount_paid"] == "0.00"
    assert client.get("/api/v1/payments").json() == []
    assert client.get("/api/v1/ledger").json() == []


def test_ledger_customer_filter_and_pagination(client, invoice, customer):
    client.post("/api/v1/payments", json=create_payment(invoice))
    response = client.get(
        f"/api/v1/ledger?customer_id={customer['id']}&limit=1"
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_ledger_has_no_public_update_or_delete_routes(client):
    assert client.put("/api/v1/ledger/1", json={}).status_code == 404
    assert client.delete("/api/v1/ledger/1").status_code == 404


def test_ledger_orm_mutation_is_rejected(db_session, client, invoice):
    client.post(
        "/api/v1/payments",
        json=create_payment(invoice, amount="10.00"),
    )
    entry = db_session.query(LedgerEntry).one()
    entry.entry_type = "changed"
    with pytest.raises(ValueError, match="append-only"):
        db_session.flush()


def test_ledger_reference_id_is_unique(db_session, client, invoice):
    client.post(
        "/api/v1/payments",
        json=create_payment(invoice, amount="10.00"),
    )
    existing = db_session.query(LedgerEntry).one()
    duplicate = LedgerEntry(
        customer_id=existing.customer_id,
        invoice_id=existing.invoice_id,
        entry_type="payment_received",
        amount=Decimal("10.00"),
        currency=existing.currency,
        reference_id=existing.reference_id,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_pagination_is_rejected(client):
    assert client.get("/api/v1/plans?limit=0").status_code == 422
    assert client.get("/api/v1/customers?offset=-1").status_code == 422


def test_invoice_creation_for_unknown_subscription(client):
    assert create_invoice(client, 9999).status_code == 404


def test_payment_creation_for_unknown_invoice(client):
    payload = {
        "invoice_id": 9999,
        "amount": "1.00",
        "currency": "INR",
        "status": "succeeded",
        "idempotency_key": "missing-invoice",
    }
    assert client.post("/api/v1/payments", json=payload).status_code == 404
