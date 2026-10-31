
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.invoice import InvoiceCreate, InvoiceRead
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post(
    "",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice(
    data: InvoiceCreate,
    db: Session = Depends(get_db),
):
    return InvoiceService(db).create_invoice(data)


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    customer_id: int | None = Query(default=None, gt=0),
    subscription_id: int | None = Query(default=None, gt=0),
    invoice_status: str | None = Query(
        default=None, alias="status", pattern="^(issued|partially_paid|paid)$"
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return InvoiceService(db).list_invoices(
        limit=limit,
        offset=offset,
        customer_id=customer_id,
        subscription_id=subscription_id,
        invoice_status=invoice_status,
    )


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return InvoiceService(db).get_invoice(invoice_id)
