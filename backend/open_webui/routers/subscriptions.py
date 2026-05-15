import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.models.subscriptions import Subscriptions
from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user, get_verified_user


router = APIRouter()


def get_epay_config(request: Request) -> dict:
    app_config = getattr(request.app.state, 'config', None)
    return {
        'api_url': (getattr(app_config, 'EPAY_API_URL', '') if app_config else '').rstrip('/'),
        'pid': getattr(app_config, 'EPAY_PID', '') if app_config else '',
        'key': getattr(app_config, 'EPAY_KEY', '') if app_config else '',
        'payment_type': getattr(app_config, 'EPAY_PAYMENT_TYPE', 'alipay') if app_config else 'alipay',
        'sign_type': getattr(app_config, 'EPAY_SIGN_TYPE', 'MD5') if app_config else 'MD5',
        'notify_url': getattr(app_config, 'EPAY_NOTIFY_URL', '') if app_config else '',
        'return_url': getattr(app_config, 'EPAY_RETURN_URL', '') if app_config else '',
    }


def epay_is_configured(config: dict) -> bool:
    return bool(config['api_url'] and config['pid'] and config['key'])


def epay_sign(params: dict, key: str) -> str:
    filtered = {
        k: str(v)
        for k, v in params.items()
        if k not in {'sign', 'sign_type'} and v is not None and str(v) != ''
    }
    sign_src = '&'.join([f'{k}={filtered[k]}' for k in sorted(filtered.keys())]) + key
    return hashlib.md5(sign_src.encode('utf-8')).hexdigest()


def verify_epay_sign(params: dict, key: str) -> bool:
    sign = str(params.get('sign') or '').lower()
    if not sign:
        return False
    return hmac.compare_digest(sign, epay_sign(params, key))


def cents_to_money(amount_cents: int) -> str:
    return f'{Decimal(max(0, int(amount_cents or 0))) / Decimal(100):.2f}'


def money_to_cents(money: str) -> Optional[int]:
    try:
        return int((Decimal(str(money)).quantize(Decimal('0.01')) * 100).to_integral_value())
    except (InvalidOperation, ValueError, TypeError):
        return None


def get_public_base_url(request: Request) -> str:
    app_config = getattr(request.app.state, 'config', None)
    configured = getattr(app_config, 'WEBUI_URL', '') if app_config else ''
    if configured:
        return configured.rstrip('/')

    proto = request.headers.get('x-forwarded-proto', request.url.scheme).split(',')[0].strip()
    host = request.headers.get('x-forwarded-host') or request.headers.get('host') or request.url.netloc
    return f'{proto}://{host}'.rstrip('/')


def get_callback_url(request: Request, path: str, override: str = '') -> str:
    if override:
        return override.rstrip('/')
    return f'{get_public_base_url(request)}/api/v1/subscriptions{path}'


def epay_submit_url(api_url: str) -> str:
    return api_url if api_url.endswith('.php') else f'{api_url}/submit.php'


async def request_params(request: Request) -> dict:
    params = dict(request.query_params)
    if request.method.upper() == 'POST':
        content_type = request.headers.get('content-type', '')
        if 'application/json' in content_type:
            body = await request.json()
            params.update(body if isinstance(body, dict) else {})
        else:
            form = await request.form()
            params.update({k: str(v) for k, v in form.items()})
    return params


class PlanForm(BaseModel):
    name: str
    description: Optional[str] = None
    price_cents: int = 0
    currency: str = 'CNY'
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


class CheckoutForm(BaseModel):
    plan_id: str
    payment_type: Optional[str] = None


class EPayConfigForm(BaseModel):
    EPAY_API_URL: str = ''
    EPAY_PID: str = ''
    EPAY_KEY: str = ''
    EPAY_PAYMENT_TYPE: str = 'alipay'
    EPAY_SIGN_TYPE: str = 'MD5'
    EPAY_NOTIFY_URL: str = ''
    EPAY_RETURN_URL: str = ''


def epay_config_response(request: Request) -> dict:
    config = get_epay_config(request)
    return {
        'EPAY_API_URL': config['api_url'],
        'EPAY_PID': config['pid'],
        'EPAY_KEY': config['key'],
        'EPAY_PAYMENT_TYPE': config['payment_type'],
        'EPAY_SIGN_TYPE': config['sign_type'],
        'EPAY_NOTIFY_URL': config['notify_url'],
        'EPAY_RETURN_URL': config['return_url'],
        'configured': epay_is_configured(config),
    }


@router.get('/plans')
async def get_plans(
    include_inactive: bool = Query(True),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await Subscriptions.get_plans(include_inactive=include_inactive, db=db)


@router.get('/available-plans')
async def get_available_plans(user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    return await Subscriptions.get_plans(include_inactive=False, db=db)


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


@router.get('/epay/config')
async def get_epay_settings(request: Request, user=Depends(get_admin_user)):
    return epay_config_response(request)


@router.post('/epay/config')
async def update_epay_settings(request: Request, form_data: EPayConfigForm, user=Depends(get_admin_user)):
    request.app.state.config.EPAY_API_URL = form_data.EPAY_API_URL.rstrip('/')
    request.app.state.config.EPAY_PID = form_data.EPAY_PID
    request.app.state.config.EPAY_KEY = form_data.EPAY_KEY
    request.app.state.config.EPAY_PAYMENT_TYPE = form_data.EPAY_PAYMENT_TYPE or 'alipay'
    request.app.state.config.EPAY_SIGN_TYPE = form_data.EPAY_SIGN_TYPE or 'MD5'
    request.app.state.config.EPAY_NOTIFY_URL = form_data.EPAY_NOTIFY_URL.rstrip('/')
    request.app.state.config.EPAY_RETURN_URL = form_data.EPAY_RETURN_URL.rstrip('/')
    return epay_config_response(request)


@router.post('/checkout')
async def create_checkout(
    request: Request,
    form_data: CheckoutForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    plan = await Subscriptions.get_plan_by_id(form_data.plan_id, db=db)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Plan not found')

    if plan.price_cents <= 0:
        subscription = await Subscriptions.assign_subscription(user_id=user.id, plan_id=plan.id, db=db)
        return {'status': 'activated', 'subscription': subscription}
    if plan.currency.upper() != 'CNY':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='易支付仅支持 CNY 套餐')

    config = get_epay_config(request)
    if not epay_is_configured(config):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='EPay is not configured')

    client_ip = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
    client_ip = client_ip or (request.client.host if request.client else None)
    order = await Subscriptions.create_payment_order(
        user_id=user.id,
        plan_id=plan.id,
        amount_cents=plan.price_cents,
        currency=plan.currency,
        client_ip=client_ip,
        db=db,
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Plan not found')

    params = {
        'pid': config['pid'],
        'type': form_data.payment_type or config['payment_type'],
        'out_trade_no': order.out_trade_no,
        'notify_url': get_callback_url(request, '/epay/notify', config['notify_url']),
        'return_url': get_callback_url(request, '/epay/return', config['return_url']),
        'name': plan.name,
        'money': cents_to_money(order.amount_cents),
        'clientip': client_ip,
    }
    params = {k: v for k, v in params.items() if v is not None and str(v) != ''}
    params['sign'] = epay_sign(params, config['key'])
    params['sign_type'] = config['sign_type']

    return {
        'status': 'pending',
        'order': order,
        'payment_url': f'{epay_submit_url(config["api_url"])}?{urlencode(params)}',
        'params': params,
    }


async def handle_epay_paid(request: Request, params: dict, db: AsyncSession) -> Optional[dict]:
    config = get_epay_config(request)
    if not epay_is_configured(config) or not verify_epay_sign(params, config['key']):
        return None
    if params.get('pid') and str(params.get('pid')) != str(config['pid']):
        return None
    if params.get('trade_status') != 'TRADE_SUCCESS':
        return {'status': 'ignored'}

    out_trade_no = params.get('out_trade_no')
    if not out_trade_no:
        return None

    order = await Subscriptions.get_payment_order_by_out_trade_no(out_trade_no, db=db)
    if not order:
        return None

    paid_cents = money_to_cents(params.get('money'))
    if paid_cents is None or paid_cents != order.amount_cents:
        return None

    activated = await Subscriptions.activate_payment_order(
        out_trade_no=out_trade_no,
        trade_no=params.get('trade_no'),
        raw_notify=params,
        db=db,
    )
    if not activated:
        return None

    order, created, subscription = activated
    return {'status': 'paid', 'order': order, 'created': created, 'subscription': subscription}


@router.api_route('/epay/notify', methods=['GET', 'POST'])
async def epay_notify(request: Request, db: AsyncSession = Depends(get_async_session)):
    result = await handle_epay_paid(request, await request_params(request), db=db)
    if not result:
        return PlainTextResponse('FAIL', status_code=status.HTTP_400_BAD_REQUEST)
    return PlainTextResponse('SUCCESS')


@router.api_route('/epay/return', methods=['GET', 'POST'])
async def epay_return(request: Request, db: AsyncSession = Depends(get_async_session)):
    result = await handle_epay_paid(request, await request_params(request), db=db)
    redirect_url = f'{get_public_base_url(request)}/'
    if not result:
        return RedirectResponse(f'{redirect_url}?subscription_payment=failed', status_code=status.HTTP_302_FOUND)
    return RedirectResponse(f'{redirect_url}?subscription_payment=success', status_code=status.HTTP_302_FOUND)


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
