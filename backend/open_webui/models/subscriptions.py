import calendar
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, JSON, Text, UniqueConstraint, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


SUBSCRIPTION_STATUS_ACTIVE = 'active'
USAGE_EVENT_CHAT_COMPLETION = 'chat_completion'
PAYMENT_PROVIDER_EPAY = 'epay'
PAYMENT_STATUS_PENDING = 'pending'
PAYMENT_STATUS_PAID = 'paid'


class SubscriptionPlan(Base):
    __tablename__ = 'subscription_plan'

    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    price_cents = Column(Integer, nullable=False, default=0)
    currency = Column(Text, nullable=False, default='CNY')
    interval = Column(Text, nullable=False, default='month')
    token_limit = Column(BigInteger, nullable=True)
    request_limit = Column(BigInteger, nullable=True)
    model_ids = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class UserSubscription(Base):
    __tablename__ = 'user_subscription'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = Column(Text, ForeignKey('subscription_plan.id', ondelete='SET NULL'), nullable=True, index=True)
    status = Column(Text, nullable=False, default=SUBSCRIPTION_STATUS_ACTIVE)
    current_period_start = Column(BigInteger, nullable=False)
    current_period_end = Column(BigInteger, nullable=False)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class UsageLedger(Base):
    __tablename__ = 'usage_ledger'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    subscription_id = Column(Text, nullable=True, index=True)
    plan_id = Column(Text, nullable=True, index=True)
    model_id = Column(Text, nullable=True, index=True)
    chat_id = Column(Text, nullable=True, index=True)
    message_id = Column(Text, nullable=True)
    event_type = Column(Text, nullable=False, default=USAGE_EVENT_CHAT_COMPLETION)
    input_tokens = Column(BigInteger, nullable=False, default=0)
    output_tokens = Column(BigInteger, nullable=False, default=0)
    total_tokens = Column(BigInteger, nullable=False, default=0)
    request_count = Column(BigInteger, nullable=False, default=1)
    estimated = Column(Boolean, nullable=False, default=False)
    data = Column(JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint('chat_id', 'message_id', 'event_type', name='uq_usage_ledger_message_event'),
    )


class PaymentOrder(Base):
    __tablename__ = 'payment_order'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = Column(Text, ForeignKey('subscription_plan.id', ondelete='SET NULL'), nullable=True, index=True)
    provider = Column(Text, nullable=False, default=PAYMENT_PROVIDER_EPAY)
    out_trade_no = Column(Text, nullable=False, unique=True, index=True)
    trade_no = Column(Text, nullable=True, index=True)
    status = Column(Text, nullable=False, default=PAYMENT_STATUS_PENDING)
    amount_cents = Column(Integer, nullable=False, default=0)
    currency = Column(Text, nullable=False, default='CNY')
    client_ip = Column(Text, nullable=True)
    raw_notify = Column(JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    paid_at = Column(BigInteger, nullable=True)


class SubscriptionPlanModel(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price_cents: int = 0
    currency: str = 'CNY'
    interval: str = 'month'
    token_limit: Optional[int] = None
    request_limit: Optional[int] = None
    model_ids: Optional[list[str]] = None
    is_active: bool = True
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class UserSubscriptionModel(BaseModel):
    id: str
    user_id: str
    plan_id: Optional[str] = None
    status: str = SUBSCRIPTION_STATUS_ACTIVE
    current_period_start: int
    current_period_end: int
    cancel_at_period_end: bool = False
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class UsageLedgerModel(BaseModel):
    id: str
    user_id: str
    subscription_id: Optional[str] = None
    plan_id: Optional[str] = None
    model_id: Optional[str] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    event_type: str = USAGE_EVENT_CHAT_COMPLETION
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 1
    estimated: bool = False
    data: Optional[dict] = None
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class PaymentOrderModel(BaseModel):
    id: str
    user_id: str
    plan_id: Optional[str] = None
    provider: str = PAYMENT_PROVIDER_EPAY
    out_trade_no: str
    trade_no: Optional[str] = None
    status: str = PAYMENT_STATUS_PENDING
    amount_cents: int = 0
    currency: str = 'CNY'
    client_ip: Optional[str] = None
    raw_notify: Optional[dict] = None
    created_at: int
    updated_at: int
    paid_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


def _now() -> int:
    return int(time.time())


def current_month_period(now: Optional[int] = None) -> tuple[int, int]:
    dt = datetime.fromtimestamp(now or _now(), tz=timezone.utc)
    start = datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)
    if dt.month == 12:
        end = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def add_months(timestamp: int, months: int = 1) -> int:
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return int(dt.replace(year=year, month=month, day=day).timestamp())


def add_interval(timestamp: int, interval: Optional[str] = 'month') -> int:
    interval = (interval or 'month').lower()
    if interval == 'year':
        return add_months(timestamp, 12)
    if interval == 'quarter':
        return add_months(timestamp, 3)
    if interval == 'week':
        return timestamp + 7 * 24 * 60 * 60
    if interval == 'day':
        return timestamp + 24 * 60 * 60
    return add_months(timestamp, 1)


class SubscriptionTable:
    async def create_plan(self, data: dict, db: Optional[AsyncSession] = None) -> SubscriptionPlanModel:
        async with get_async_db_context(db) as db:
            now = _now()
            plan = SubscriptionPlan(
                id=data.get('id') or str(uuid.uuid4()),
                name=data['name'],
                description=data.get('description'),
                price_cents=int(data.get('price_cents') or 0),
                currency=(data.get('currency') or 'CNY').upper(),
                interval=data.get('interval') or 'month',
                token_limit=data.get('token_limit'),
                request_limit=data.get('request_limit'),
                model_ids=data.get('model_ids') or None,
                is_active=data.get('is_active', True),
                created_at=now,
                updated_at=now,
            )
            db.add(plan)
            await db.commit()
            await db.refresh(plan)
            return SubscriptionPlanModel.model_validate(plan)

    async def update_plan(self, plan_id: str, data: dict, db: Optional[AsyncSession] = None) -> Optional[SubscriptionPlanModel]:
        async with get_async_db_context(db) as db:
            plan = await db.get(SubscriptionPlan, plan_id)
            if not plan:
                return None
            for key, value in data.items():
                if value is not None or key in {'description', 'token_limit', 'request_limit', 'model_ids'}:
                    setattr(plan, key, value)
            plan.updated_at = _now()
            await db.commit()
            await db.refresh(plan)
            return SubscriptionPlanModel.model_validate(plan)

    async def get_plan_by_id(self, plan_id: str, db: Optional[AsyncSession] = None) -> Optional[SubscriptionPlanModel]:
        async with get_async_db_context(db) as db:
            plan = await db.get(SubscriptionPlan, plan_id)
            return SubscriptionPlanModel.model_validate(plan) if plan else None

    async def get_plans(self, include_inactive: bool = True, db: Optional[AsyncSession] = None) -> list[SubscriptionPlanModel]:
        async with get_async_db_context(db) as db:
            stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.created_at.desc())
            if not include_inactive:
                stmt = stmt.filter(SubscriptionPlan.is_active == True)
            result = await db.execute(stmt)
            return [SubscriptionPlanModel.model_validate(plan) for plan in result.scalars().all()]

    async def assign_subscription(
        self,
        user_id: str,
        plan_id: str,
        status: str = SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start: Optional[int] = None,
        current_period_end: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[UserSubscriptionModel]:
        async with get_async_db_context(db) as db:
            plan = await db.get(SubscriptionPlan, plan_id)
            if not plan:
                return None

            now = _now()
            start = current_period_start or now
            end = current_period_end or add_interval(start, plan.interval)

            result = await db.execute(
                select(UserSubscription).filter(
                    UserSubscription.user_id == user_id,
                    UserSubscription.status == SUBSCRIPTION_STATUS_ACTIVE,
                )
            )
            existing = result.scalars().first()
            if existing:
                existing.plan_id = plan_id
                existing.status = status
                existing.current_period_start = start
                existing.current_period_end = end
                existing.cancel_at_period_end = False
                existing.updated_at = now
                subscription = existing
            else:
                subscription = UserSubscription(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    plan_id=plan_id,
                    status=status,
                    current_period_start=start,
                    current_period_end=end,
                    cancel_at_period_end=False,
                    created_at=now,
                    updated_at=now,
                )
                db.add(subscription)

            await db.commit()
            await db.refresh(subscription)
            return UserSubscriptionModel.model_validate(subscription)

    async def create_payment_order(
        self,
        user_id: str,
        plan_id: str,
        amount_cents: int,
        currency: str = 'CNY',
        provider: str = PAYMENT_PROVIDER_EPAY,
        client_ip: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[PaymentOrderModel]:
        async with get_async_db_context(db) as db:
            plan = await db.get(SubscriptionPlan, plan_id)
            if not plan or not plan.is_active:
                return None

            now = _now()
            order = PaymentOrder(
                id=str(uuid.uuid4()),
                user_id=user_id,
                plan_id=plan_id,
                provider=provider,
                out_trade_no=f'sub{now}{uuid.uuid4().hex[:10]}',
                status=PAYMENT_STATUS_PENDING,
                amount_cents=max(0, int(amount_cents or 0)),
                currency=(currency or plan.currency or 'CNY').upper(),
                client_ip=client_ip,
                created_at=now,
                updated_at=now,
            )
            db.add(order)
            await db.commit()
            await db.refresh(order)
            return PaymentOrderModel.model_validate(order)

    async def get_payment_order_by_out_trade_no(
        self, out_trade_no: str, db: Optional[AsyncSession] = None
    ) -> Optional[PaymentOrderModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(PaymentOrder).filter(PaymentOrder.out_trade_no == out_trade_no).limit(1))
            order = result.scalars().first()
            return PaymentOrderModel.model_validate(order) if order else None

    async def activate_payment_order(
        self,
        out_trade_no: str,
        trade_no: Optional[str] = None,
        raw_notify: Optional[dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[tuple[PaymentOrderModel, bool, Optional[UserSubscriptionModel]]]:
        async with get_async_db_context(db) as db:
            now = _now()
            paid_result = await db.execute(
                update(PaymentOrder)
                .filter(PaymentOrder.out_trade_no == out_trade_no, PaymentOrder.status != PAYMENT_STATUS_PAID)
                .values(
                    status=PAYMENT_STATUS_PAID,
                    trade_no=trade_no,
                    raw_notify=raw_notify,
                    paid_at=now,
                    updated_at=now,
                )
            )
            created = bool(paid_result.rowcount)

            result = await db.execute(select(PaymentOrder).filter(PaymentOrder.out_trade_no == out_trade_no).limit(1))
            order = result.scalars().first()
            if not order:
                return None

            subscription_model = None
            if created:
                plan = await db.get(SubscriptionPlan, order.plan_id)
                if plan:
                    active_result = await db.execute(
                        select(UserSubscription)
                        .filter(
                            UserSubscription.user_id == order.user_id,
                            UserSubscription.status == SUBSCRIPTION_STATUS_ACTIVE,
                        )
                        .order_by(UserSubscription.updated_at.desc())
                        .limit(1)
                    )
                    existing = active_result.scalars().first()
                    if existing:
                        period_start = existing.current_period_start if existing.current_period_end > now else now
                        period_end = add_interval(max(now, existing.current_period_end), plan.interval)
                        existing.plan_id = order.plan_id
                        existing.current_period_start = period_start
                        existing.current_period_end = period_end
                        existing.cancel_at_period_end = False
                        existing.updated_at = now
                        subscription = existing
                    else:
                        period_start = now
                        period_end = add_interval(period_start, plan.interval)
                        subscription = UserSubscription(
                            id=str(uuid.uuid4()),
                            user_id=order.user_id,
                            plan_id=order.plan_id,
                            status=SUBSCRIPTION_STATUS_ACTIVE,
                            current_period_start=period_start,
                            current_period_end=period_end,
                            cancel_at_period_end=False,
                            created_at=now,
                            updated_at=now,
                        )
                        db.add(subscription)
                    subscription_model = subscription

            await db.commit()
            await db.refresh(order)
            if subscription_model:
                await db.refresh(subscription_model)
            return (
                PaymentOrderModel.model_validate(order),
                created,
                UserSubscriptionModel.model_validate(subscription_model) if subscription_model else None,
            )

    async def cancel_subscription(self, user_id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                update(UserSubscription)
                .filter(UserSubscription.user_id == user_id, UserSubscription.status == SUBSCRIPTION_STATUS_ACTIVE)
                .values(status='canceled', updated_at=_now())
            )
            await db.commit()
            return bool(result.rowcount)

    async def get_active_subscription(
        self, user_id: str, db: Optional[AsyncSession] = None
    ) -> Optional[UserSubscriptionModel]:
        async with get_async_db_context(db) as db:
            now = _now()
            result = await db.execute(
                select(UserSubscription)
                .filter(
                    UserSubscription.user_id == user_id,
                    UserSubscription.status == SUBSCRIPTION_STATUS_ACTIVE,
                    UserSubscription.current_period_start <= now,
                    UserSubscription.current_period_end > now,
                )
                .order_by(UserSubscription.updated_at.desc())
                .limit(1)
            )
            subscription = result.scalars().first()
            return UserSubscriptionModel.model_validate(subscription) if subscription else None

    async def get_latest_subscription(
        self, user_id: str, db: Optional[AsyncSession] = None
    ) -> Optional[UserSubscriptionModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(UserSubscription)
                .filter(UserSubscription.user_id == user_id)
                .order_by(UserSubscription.updated_at.desc())
                .limit(1)
            )
            subscription = result.scalars().first()
            return UserSubscriptionModel.model_validate(subscription) if subscription else None

    async def get_usage_totals(
        self,
        user_id: str,
        start: int,
        end: int,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(
                    func.coalesce(func.sum(UsageLedger.input_tokens), 0),
                    func.coalesce(func.sum(UsageLedger.output_tokens), 0),
                    func.coalesce(func.sum(UsageLedger.total_tokens), 0),
                    func.coalesce(func.sum(UsageLedger.request_count), 0),
                ).filter(
                    UsageLedger.user_id == user_id,
                    UsageLedger.created_at >= start,
                    UsageLedger.created_at < end,
                )
            )
            input_tokens, output_tokens, total_tokens, request_count = result.one()
            return {
                'input_tokens': int(input_tokens or 0),
                'output_tokens': int(output_tokens or 0),
                'total_tokens': int(total_tokens or 0),
                'request_count': int(request_count or 0),
            }

    async def get_user_summary(self, user_id: str, db: Optional[AsyncSession] = None) -> dict:
        subscription = await self.get_active_subscription(user_id, db=db)
        plan = await self.get_plan_by_id(subscription.plan_id, db=db) if subscription and subscription.plan_id else None
        if subscription:
            period_start = subscription.current_period_start
            period_end = subscription.current_period_end
        else:
            period_start, period_end = current_month_period()
        usage = await self.get_usage_totals(user_id, period_start, period_end, db=db)
        return {
            'subscription': subscription.model_dump() if subscription else None,
            'plan': plan.model_dump() if plan else None,
            'period_start': period_start,
            'period_end': period_end,
            'usage': usage,
        }

    async def assert_can_use(
        self,
        user_id: str,
        user_role: str,
        model_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> None:
        if user_role == 'admin':
            return

        summary = await self.get_user_summary(user_id, db=db)
        subscription = summary.get('subscription')
        plan = summary.get('plan')
        if not subscription:
            latest = await self.get_latest_subscription(user_id, db=db)
            if latest and latest.status == SUBSCRIPTION_STATUS_ACTIVE and latest.current_period_end <= _now():
                from fastapi import HTTPException, status

                raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail='订阅已过期，请续费后继续使用。')
            return
        if not plan or not plan.get('is_active', True):
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail='订阅不可用，请联系管理员。')

        model_ids = plan.get('model_ids') or []
        if model_ids and model_id and model_id not in model_ids:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='当前套餐不能使用该模型。')

        usage = summary['usage']
        token_limit = plan.get('token_limit')
        request_limit = plan.get('request_limit')
        if token_limit and usage['total_tokens'] >= token_limit:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail='本周期 token 额度已用完。')
        if request_limit and usage['request_count'] >= request_limit:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail='本周期调用次数已用完。')

    async def record_usage(
        self,
        user_id: str,
        model_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        message_id: Optional[str] = None,
        usage: Optional[dict] = None,
        estimated: bool = False,
        data: Optional[dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> UsageLedgerModel:
        async with get_async_db_context(db) as db:
            now = _now()
            usage = usage or {}
            input_tokens = int(usage.get('input_tokens') or usage.get('prompt_tokens') or 0)
            output_tokens = int(usage.get('output_tokens') or usage.get('completion_tokens') or 0)
            total_tokens = int(usage.get('total_tokens') or input_tokens + output_tokens)
            subscription = await self.get_active_subscription(user_id, db=db)

            existing = None
            if chat_id and message_id:
                result = await db.execute(
                    select(UsageLedger).filter(
                        UsageLedger.chat_id == chat_id,
                        UsageLedger.message_id == message_id,
                        UsageLedger.event_type == USAGE_EVENT_CHAT_COMPLETION,
                    )
                )
                existing = result.scalars().first()

            if existing:
                existing.user_id = user_id
                existing.subscription_id = subscription.id if subscription else None
                existing.plan_id = subscription.plan_id if subscription else None
                existing.model_id = model_id
                existing.input_tokens = input_tokens
                existing.output_tokens = output_tokens
                existing.total_tokens = total_tokens
                existing.request_count = 1
                existing.estimated = estimated
                existing.data = data or usage or None
                existing.updated_at = now
                ledger = existing
            else:
                ledger = UsageLedger(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    subscription_id=subscription.id if subscription else None,
                    plan_id=subscription.plan_id if subscription else None,
                    model_id=model_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    event_type=USAGE_EVENT_CHAT_COMPLETION,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    request_count=1,
                    estimated=estimated,
                    data=data or usage or None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(ledger)

            await db.commit()
            await db.refresh(ledger)
            return UsageLedgerModel.model_validate(ledger)


Subscriptions = SubscriptionTable()
