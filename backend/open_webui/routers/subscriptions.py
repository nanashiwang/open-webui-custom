from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.models.subscriptions import Subscriptions
from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user, get_verified_user


router = APIRouter()


class PlanForm(BaseModel):
    name: str
    description: Optional[str] = None
    price_cents: int = 0
    currency: str = 'USD'
    interval: str = 'month'
    token_limit: Optional[int] = None
    request_limit: Optional[int] = None
    model_ids: Optional[list[str]] = None
    is_active: bool = True

    @field_validator('token_limit', 'request_limit')
    @classmethod
    def normalize_limit(cls, value: Optional[int]) -> Optional[int]:
        if value is None or value <= 0:
            return None
        return value


class PlanUpdateForm(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    currency: Optional[str] = None
    interval: Optional[str] = None
    token_limit: Optional[int] = None
    request_limit: Optional[int] = None
    model_ids: Optional[list[str]] = None
    is_active: Optional[bool] = None

    @field_validator('token_limit', 'request_limit')
    @classmethod
    def normalize_limit(cls, value: Optional[int]) -> Optional[int]:
        if value is None or value <= 0:
            return None
        return value


class AssignSubscriptionForm(BaseModel):
    plan_id: str
    current_period_start: Optional[int] = None
    current_period_end: Optional[int] = None


@router.get('/plans')
async def get_plans(
    include_inactive: bool = Query(True),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await Subscriptions.get_plans(include_inactive=include_inactive, db=db)


@router.post('/plans')
async def create_plan(form_data: PlanForm, user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    return await Subscriptions.create_plan(form_data.model_dump(), db=db)


@router.patch('/plans/{plan_id}')
async def update_plan(
    plan_id: str,
    form_data: PlanUpdateForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    plan = await Subscriptions.update_plan(plan_id, form_data.model_dump(exclude_unset=True), db=db)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Plan not found')
    return plan


@router.get('/me')
async def get_my_subscription(user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    return await Subscriptions.get_user_summary(user.id, db=db)


@router.get('/users')
async def get_users_subscription_usage(
    query: Optional[str] = None,
    page: int = 1,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    page = max(1, page)
    result = await Users.get_users(filter={'query': query} if query else {}, skip=(page - 1) * 30, limit=30, db=db)
    rows = []
    for item in result['users']:
        rows.append(
            {
                'user': item.model_dump(),
                **await Subscriptions.get_user_summary(item.id, db=db),
            }
        )
    return {'items': rows, 'total': result['total']}


@router.get('/users/{user_id}')
async def get_user_subscription_usage(
    user_id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    target = await Users.get_user_by_id(user_id, db=db)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return {'user': target.model_dump(), **await Subscriptions.get_user_summary(user_id, db=db)}


@router.post('/users/{user_id}')
async def assign_user_subscription(
    user_id: str,
    form_data: AssignSubscriptionForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    target = await Users.get_user_by_id(user_id, db=db)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    subscription = await Subscriptions.assign_subscription(
        user_id=user_id,
        plan_id=form_data.plan_id,
        current_period_start=form_data.current_period_start,
        current_period_end=form_data.current_period_end,
        db=db,
    )
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Plan not found')
    return {'subscription': subscription, **await Subscriptions.get_user_summary(user_id, db=db)}


@router.delete('/users/{user_id}')
async def cancel_user_subscription(
    user_id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {'status': await Subscriptions.cancel_subscription(user_id, db=db)}
