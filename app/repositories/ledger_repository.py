
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry


class LedgerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, entry: LedgerEntry) -> LedgerEntry:
        self.db.add(entry)
        self.db.flush()
        self.db.refresh(entry)
        return entry

    def get_by_id(self, entry_id: int) -> LedgerEntry | None:
        return self.db.get(LedgerEntry, entry_id)

    def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        customer_id: int | None = None,
    ) -> list[LedgerEntry]:
        statement = select(LedgerEntry).order_by(LedgerEntry.id)
        if customer_id is not None:
            statement = statement.where(LedgerEntry.customer_id == customer_id)
        statement = statement.limit(limit).offset(offset)
        return list(self.db.scalars(statement).all())

    def list_by_customer(
        self, customer_id: int, limit: int = 100, offset: int = 0
    ) -> list[LedgerEntry]:
        statement = (
            select(LedgerEntry)
            .where(LedgerEntry.customer_id == customer_id)
            .order_by(LedgerEntry.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())
