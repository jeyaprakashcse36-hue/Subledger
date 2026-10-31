
from fastapi import FastAPI

from app.api.routes import customers, invoices, ledger, payments, plans, subscriptions
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A modular SaaS billing backend.",
)

app.include_router(plans.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(ledger.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"application": settings.app_name, "status": "running"}


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
