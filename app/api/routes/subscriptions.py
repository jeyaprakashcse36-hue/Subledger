from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.subscription import SubscriptionCreate, SubscriptionRead
from app.services.subscription_service import SubscriptionService


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).create_subscription(data)


@router.get("", response_model=list[SubscriptionRead])
def list_subscriptions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).list_subscriptions(limit=limit, offset=offset)


@router.get("/{subscription_id}", response_model=SubscriptionRead)
def get_subscription(
    subscription_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).get_subscription(subscription_id)