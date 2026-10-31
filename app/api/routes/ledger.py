
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ledger import LedgerRead
from app.services.ledger_service import LedgerService

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.get("", response_model=list[LedgerRead])
def list_ledger_entries(
    customer_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return LedgerService(db).list_entries(
        limit=limit, offset=offset, customer_id=customer_id
    )


@router.get("/customer/{customer_id}", response_model=list[LedgerRead])
def get_customer_ledger(
    customer_id: int = Path(gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return LedgerService(db).get_customer_entries(
        customer_id, limit=limit, offset=offset
    )
