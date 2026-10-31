# SubLedger — SaaS Billing Backend

SubLedger is a modular FastAPI service for plans, customers, subscriptions,
invoices, simulated payment attempts, and an append-only financial ledger.
It uses SQLAlchemy 2.x and PostgreSQL for runtime persistence, Pydantic v2 for
request/response validation, and Alembic for schema migrations.

## Features

- Layered routes → services → repositories → SQLAlchemy models.
- Decimal/Numeric monetary values and invoice price/currency snapshots.
- Database-enforced unique customer emails, active customer-plan
  subscriptions, invoice periods, idempotency keys, and ledger references.
- Atomic payment processing with PostgreSQL invoice row locks and
  idempotent request replay.
- Ledger updates only for successful payments; no public mutation endpoints.
- Paginated list endpoints and filters for plans, invoices, payments, and
  ledger entries.
- Isolated SQLite API tests and an opt-in PostgreSQL concurrency test.

## Technology

- Python 3.14
- FastAPI, Pydantic v2, SQLAlchemy 2.x
- PostgreSQL 16, psycopg 3, Alembic
- Pytest and HTTPX
- Docker and Docker Compose

## Architecture and project layout

```text
app/
  api/routes/       HTTP endpoints and dependency wiring
  core/             Environment-based settings
  db/               SQLAlchemy base, engine, and session dependency
  models/           Persistence entities and database constraints
  repositories/     Database queries and writes (no commits)
  schemas/          Pydantic request/response models
  services/         Business rules and transaction ownership
migrations/         Alembic revisions
tests/              Isolated API and optional PostgreSQL integration tests
```

See [DESIGN.md](./DESIGN.md) for the ER diagram, transaction flows, and
business-rule ownership.

## Prerequisites

- Python 3.14
- PostgreSQL 16 for a local non-Docker run
- Docker Desktop with Docker Compose for containerized setup

## Local installation

In PowerShell, from the project directory:

```powershell
py -3.14 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create `.env` from the template only if one does not already exist. Do not
overwrite an existing `.env`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Set `DATABASE_URL` to a PostgreSQL connection URL. URL-encode special
characters in the username or password for a local run. For Docker Compose,
`POSTGRES_PASSWORD` is interpolated into the container URL and must be URL-safe.
Never commit `.env`; the example contains placeholders only.

## PostgreSQL setup

Create a PostgreSQL database and user, then set the credentials in `.env`.
The default template targets a local database named `subledger_db` on port
5432. Run migrations before starting the API:

```powershell
.\venv\Scripts\alembic.exe upgrade head
.\venv\Scripts\uvicorn.exe app.main:app --reload
```

The application is available at `http://127.0.0.1:8000`.

## Docker setup

Configure `.env` with the PostgreSQL settings before starting. The Compose
configuration uses the persistent named volume `subledger_data`; it waits for
the database health check, runs Alembic migrations, and then starts the API.

```powershell
docker compose build
docker compose up -d
docker compose logs -f app
```

Open `http://localhost:8000/docs`. To stop containers while retaining the
database volume:

```powershell
docker compose stop
```

Do not use `docker compose down -v` if the database data must be retained.

## Database migrations

```powershell
.\venv\Scripts\alembic.exe current
.\venv\Scripts\alembic.exe upgrade head
```

The new integrity migration adds normalized-email and invoice-period unique
indexes and a PostgreSQL trigger preventing ledger row updates/deletes. The
migration does not delete or rewrite application records. If existing data
contains case-variant duplicate emails or duplicate subscription periods, the
unique-index migration fails rather than silently discarding data; resolve
those records deliberately before retrying.

## Running tests

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

The main API test suite uses an in-memory SQLite database and dependency
overrides. This is for functional test isolation only: SQLite does **not**
provide PostgreSQL-equivalent row-locking or concurrency guarantees.

To run the PostgreSQL concurrent-payment integration test, provide a dedicated
test database URL whose database name ends in `_test`. The test writes unique,
marked test records and must not point at the development or production
database:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/subledger_test"
.\venv\Scripts\python.exe -m pytest tests\test_postgres_concurrency.py -q
Remove-Item Env:\TEST_DATABASE_URL
```

## API reference

All domain routes are under `/api/v1`. Interactive API documentation is
available at `/docs`; the OpenAPI document is at `/openapi.json`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Application name and running status |
| GET | `/health` | Health check |
| POST, GET | `/api/v1/plans` | Create/list plans (`active_only`, `limit`, `offset`) |
| GET | `/api/v1/plans/{plan_id}` | Retrieve a plan |
| POST, GET | `/api/v1/customers` | Create/list customers (`limit`, `offset`) |
| GET | `/api/v1/customers/{customer_id}` | Retrieve a customer |
| POST, GET | `/api/v1/subscriptions` | Create/list subscriptions |
| GET | `/api/v1/subscriptions/{subscription_id}` | Retrieve a subscription |
| POST, GET | `/api/v1/invoices` | Create/list invoices; list filters: `customer_id`, `subscription_id`, `status` |
| GET | `/api/v1/invoices/{invoice_id}` | Retrieve an invoice |
| POST, GET | `/api/v1/payments` | Record/list payment attempts; list filters: `invoice_id`, `status` |
| GET | `/api/v1/payments/{payment_id}` | Retrieve a payment attempt |
| GET | `/api/v1/ledger` | List ledger entries (`customer_id`, `limit`, `offset`) |
| GET | `/api/v1/ledger/customer/{customer_id}` | List one customer's ledger |

List endpoints accept `limit` (1–500; default 100) and `offset` (default 0).
The ledger intentionally has no update or delete API.

### Example requests

Create a plan:

```json
{
  "name": "Standard",
  "price": "49.99",
  "currency": "USD",
  "billing_interval": "monthly",
  "is_active": true
}
```

Create a customer:

```json
{
  "name": "Ada Lovelace",
  "email": "ada@example.com"
}
```

Create a subscription (timestamps must include timezone information):

```json
{
  "customer_id": 1,
  "plan_id": 1,
  "current_period_start": "2026-01-01T00:00:00Z",
  "current_period_end": "2026-02-01T00:00:00Z"
}
```

Create an invoice:

```json
{
  "subscription_id": 1,
  "period_start": "2026-01-01",
  "period_end": "2026-02-01",
  "due_date": "2026-01-15"
}
```

Record a simulated payment:

```json
{
  "invoice_id": 1,
  "amount": "49.99",
  "currency": "USD",
  "status": "succeeded",
  "idempotency_key": "client-generated-unique-key",
  "provider_reference": "example-reference"
}
```

## Business rules and error handling

- Plan prices and payment amounts must be positive values with at most two
  fractional digits. Monetary columns use `NUMERIC(12, 2)` and Python
  `Decimal`.
- Email values are trimmed/lowercased; case-insensitive duplicates return
  `409 Conflict`.
- An active subscription requires an existing customer and active plan.
  Active duplicate customer/plan pairs are prevented by a partial unique
  database index.
- Invoice amount and currency are copied from the plan when the invoice is
  created. Invoice amounts are never recalculated from later plan changes.
  Duplicate subscription periods are rejected.
- A successful payment must fit the current invoice balance and use the same
  currency. Partial/full payments update invoice status and create one
  payment-received ledger entry in the same transaction.
- Failed payment attempts do not change invoice balances or create ledger
  entries.
- An identical idempotency replay returns the original payment result; a
  changed request using the same key returns `409 Conflict`.
- Invalid payloads return `422`, missing resources return `404`, and business
  or uniqueness conflicts return `409`. Database exception details are not
  returned to clients.

## Design decisions and limitations

Payment status is accepted from the API client to simulate provider outcomes
for this assignment. This is **not a production payment verification
mechanism**. A production integration must verify success using a trusted
payment gateway callback/webhook, authenticate and validate the event, and
reconcile provider references.

PostgreSQL `SELECT ... FOR UPDATE` serializes payments for an invoice. A
unique idempotency-key constraint plus savepoint handling covers concurrent
key collisions. SQLite test execution does not validate this PostgreSQL
locking behavior; use the optional PostgreSQL test for that guarantee.

Authentication/authorization, recurring invoice scheduling, refunds, taxes,
provider reconciliation, and operational observability are outside the
assignment scope.
