
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry
from app.repositories.customer_repository import CustomerRepository
from app.repositories.ledger_repository import LedgerRepository


class LedgerService:
    def __init__(self, db: Session):
        self.customers = CustomerRepository(db)
        self.repository = LedgerRepository(db)

    def list_entries(
        self, limit: int = 100, offset: int = 0, customer_id: int | None = None
    ) -> list[LedgerEntry]:
        return self.repository.list_all(
            limit=limit, offset=offset, customer_id=customer_id
        )

    def get_customer_entries(
        self, customer_id: int, limit: int = 100, offset: int = 0
    ) -> list[LedgerEntry]:
        if self.customers.get_by_id(customer_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )
        entries = self.repository.list_by_customer(
            customer_id, limit=limit, offset=offset
        )

        if not entries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No ledger entries found for this customer",
            )

        return entries
