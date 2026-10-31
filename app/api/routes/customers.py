
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.customer import CustomerCreate, CustomerRead
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    return CustomerService(db).create_customer(data)


@router.get("", response_model=list[CustomerRead])
def list_customers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return CustomerService(db).list_customers(limit=limit, offset=offset)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int = Path(gt=0), db: Session = Depends(get_db)
):
    return CustomerService(db).get_customer(customer_id)
