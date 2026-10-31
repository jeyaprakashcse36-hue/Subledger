
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer


class CustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, customer: Customer) -> Customer:
        self.db.add(customer)
        self.db.flush()
        self.db.refresh(customer)
        return customer

    def get_by_id(self, customer_id: int) -> Customer | None:
        return self.db.get(Customer, customer_id)

    def get_by_email(self, email: str) -> Customer | None:
        statement = select(Customer).where(Customer.email == email)
        return self.db.scalars(statement).first()

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Customer]:
        statement = select(Customer).order_by(Customer.id).limit(limit).offset(offset)
        return list(self.db.scalars(statement).all())
