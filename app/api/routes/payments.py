
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
):
    return PaymentService(db).create_payment(data)


@router.get("", response_model=list[PaymentRead])
def list_payments(
    invoice_id: int | None = Query(default=None, gt=0),
    payment_status: str | None = Query(
        default=None, alias="status", pattern="^(succeeded|failed)$"
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return PaymentService(db).list_payments(
        limit=limit,
        offset=offset,
        invoice_id=invoice_id,
        payment_status=payment_status,
    )


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return PaymentService(db).get_payment(payment_id)
