# SubLedger — Low-Level Design

## 1. Objective

SubLedger is a modular SaaS billing backend for managing plans,
customers, subscriptions, invoices, payment attempts, and ledger entries.

## 2. Technology

- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- PostgreSQL
- Alembic
- Pytest

## 3. Architecture

Request -> Route -> Service -> Repository -> SQLAlchemy Model -> Database

- Routes: HTTP handling, dependency injection and response mapping.
- Schemas: request validation and response serialization.
- Services: business rules and multi-step billing workflows.
- Repositories: database reads and writes.
- Models: persistent entities, relationships and database constraints.
- Database: connection configuration, sessions and transactions.
- Core: application settings and shared exceptions.

## 4. Domain entities

### Customer
- id
- name
- email (unique)
- created_at

### Plan
- id
- name
- description
- price (positive NUMERIC)
- currency
- billing_interval
- is_active
- created_at

### Subscription
- id
- customer_id
- plan_id
- status
- current_period_start
- current_period_end
- created_at

### Invoice
- id
- subscription_id
- customer_id
- amount_due
- amount_paid
- currency
- status
- period_start
- period_end
- due_date
- created_at

### PaymentAttempt
- id
- invoice_id
- amount
- currency
- status
- provider_reference
- idempotency_key
- failure_reason
- created_at

### LedgerEntry
- id
- customer_id
- invoice_id (nullable for non-invoice events)
- entry_type
- amount
- currency
- reference_id
- created_at

## 5. Relationships

- Customer has many subscriptions.
- Customer has many ledger entries.
- Plan has many subscriptions.
- Subscription has many invoices.
- Invoice has many payment attempts.
- Invoice has many ledger entries.

## 6. Business-rule ownership

- PlanService: plan price must be greater than zero.
- CustomerService: customer email must be unique.
- SubscriptionService: plan must be active; prevent duplicate active
  subscriptions for the same customer and plan.
- InvoiceService: invoice price is snapshotted from the plan at
  invoice generation time.
- PaymentService: validate positive amounts, currency and remaining
  balance; update invoice totals only for successful payments.
- LedgerService: create traceable append-only ledger events.

Database constraints provide a second line of defence for uniqueness
and other invariants. Concurrent billing operations use transactions
and row locks where appropriate.

## 7. Invoice generation flow

1. Route receives subscription_id and an optional billing period.
2. InvoiceService loads the subscription and plan.
3. Validate that the subscription is active.
4. Snapshot the plan price and determine the billing period.
5. Create the invoice.
6. Append an invoice_created ledger event.
7. Commit both changes in one transaction.
8. Return the invoice response.

## 8. Payment recording flow

1. Route receives amount, currency, status and provider reference.
2. PaymentService loads and locks the invoice.
3. Validate the amount, currency and remaining balance.
4. Create a payment attempt.
5. If successful, update amount_paid and invoice status.
6. If failed, leave amount_paid unchanged.
7. Append the corresponding traceable ledger event.
8. Commit related changes in one transaction.
9. Return the payment attempt and invoice status.

## 9. Design patterns

- Repository pattern separates persistence from business logic.
- Service layer centralizes business rules.
- Dependency injection supplies database sessions and services.
- Transaction boundary / Unit of Work keeps related writes consistent.

## 10. Assumptions and limitations

- Payment processing is simulated; no real payment gateway is integrated.
- Billing periods are explicit and validated.
- Invoice amounts use decimal arithmetic, never floating-point arithmetic.
- Ledger entries are append-only through the application API.
- Authentication, authorization, taxes, refunds, retries and scheduled
  recurring billing are outside the initial scope unless required.
- Production use would require authentication, authorization, stronger
  operational controls, monitoring and payment-provider reconciliation.
