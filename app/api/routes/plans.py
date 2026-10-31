
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.plan import PlanCreate, PlanRead
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.post("", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def create_plan(data: PlanCreate, db: Session = Depends(get_db)):
    return PlanService(db).create_plan(data)


@router.get("", response_model=list[PlanRead])
def list_plans(
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return PlanService(db).list_plans(active_only, limit=limit, offset=offset)


@router.get("/{plan_id}", response_model=PlanRead)
def get_plan(
    plan_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return PlanService(db).get_plan(plan_id)
