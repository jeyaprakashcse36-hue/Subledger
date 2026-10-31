
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate


class CustomerService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CustomerRepository(db)

    def create_customer(self, data: CustomerCreate) -> Customer:
        email = str(data.email).strip().lower()

        if self.repository.get_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this email already exists",
            )

        customer = Customer(name=data.name.strip(), email=email)

        try:
            result = self.repository.create(customer)
            self.db.commit()
            self.db.refresh(result)
            return result
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this email already exists",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def get_customer(self, customer_id: int) -> Customer:
        customer = self.repository.get_by_id(customer_id)

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        return customer

    def list_customers(self, limit: int = 100, offset: int = 0) -> list[Customer]:
        return self.repository.list_all(limit=limit, offset=offset)
