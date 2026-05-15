"""
Admin console APIs.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.database import get_db
from app.middleware.admin_auth import require_admin
from app.models.admin import AdminBroadcast, AdminOperationLog
from app.models.binding import Binding
from app.models.couple import (
    CoupleAnniversary,
    CoupleDatePlan,
    CoupleDateDraw,
    CoupleMemo,
    CoupleRelationship,
    CoupleRestaurantCategory,
    CoupleRestaurantItem,
    CoupleRestaurantWish,
)
from app.models.dish import Dish
from app.models.notification import Notification
from app.models.order import Order, OrderRefund
from app.models.review import Review
from app.models.tip import Tip
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.schemas.admin import (
    AdminBroadcastCreateRequest,
    AdminCoupleBindRequest,
    AdminDishUpdateRequest,
    AdminLoginRequest,
    AdminOperationLogCreateRequest,
    AdminOrderStatusUpdateRequest,
    AdminRefundCreateRequest,
    AdminUserCreateRequest,
    AdminUserWalletTopUpRequest,
    AdminUserUpdateRequest,
)
from app.schemas.couple import (
    CoupleRestaurantCategoryCreateRequest,
    CoupleRestaurantCategoryUpdateRequest,
    CoupleRestaurantItemCreateRequest,
    CoupleRestaurantItemUpdateRequest,
)
from app.schemas.common import error_response, paginated_response, success_response
from app.services.couple_service import (
    CoupleServiceError,
    create_restaurant_category,
    create_restaurant_item,
    delete_restaurant_category,
    delete_restaurant_item,
    ensure_couple_code,
    get_active_relationship,
    get_partner_from_relationship,
    get_restaurant_dashboard,
    restaurant_category_to_dict,
    restaurant_item_to_dict,
    update_restaurant_category,
    update_restaurant_item,
)
from app.services.order_service import OrderService, OrderServiceError
from app.services.wallet_service import WalletService, WalletServiceError
from app.utils.security import create_admin_token, generate_binding_code


router = APIRouter(prefix="/admin", tags=["后台管理"])

ORDER_STATUSES = {
    "unpaid",
    "pending",
    "accepted",
    "cooking",
    "delivering",
    "completed",
    "cancelled",
}

VALID_USER_ROLES = {"foodie", "chef"}


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _serialize_decimal(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _serialize_optional_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    return _serialize_decimal(value)


def _coerce_optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_broadcast_filters(filters: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not filters:
        return None

    normalized = dict(filters)
    normalized["user_ids"] = [item for item in normalized.get("user_ids") or [] if item]

    min_value = _coerce_optional_float(normalized.get("min_wallet_balance"))
    max_value = _coerce_optional_float(normalized.get("max_wallet_balance"))
    reward_amount = _coerce_optional_float(normalized.get("reward_amount"))
    has_min_flag = normalized.get("has_min_wallet_balance")
    has_max_flag = normalized.get("has_max_wallet_balance")

    if has_min_flag is True:
        normalized["min_wallet_balance"] = 0.0 if min_value is None else min_value
    elif has_min_flag is False:
        normalized["min_wallet_balance"] = None
    else:
        normalized["min_wallet_balance"] = min_value if min_value and min_value > 0 else None

    if has_max_flag is True:
        normalized["max_wallet_balance"] = 0.0 if max_value is None else max_value
    elif has_max_flag is False:
        normalized["max_wallet_balance"] = None
    else:
        normalized["max_wallet_balance"] = max_value if max_value and max_value > 0 else None

    normalized["reward_amount"] = reward_amount if reward_amount and reward_amount > 0 else None
    normalized["has_min_wallet_balance"] = has_min_flag if has_min_flag is not None else None
    normalized["has_max_wallet_balance"] = has_max_flag if has_max_flag is not None else None

    return normalized


def _generate_unique_binding_code(db: Session) -> str:
    code = generate_binding_code()
    while db.query(User).filter(User.binding_code == code).first():
        code = generate_binding_code()
    return code


def _normalize_specialties(values: Optional[list[str]]) -> Optional[list[str]]:
    if not values:
        return None
    normalized = [item.strip() for item in values if item and item.strip()]
    return normalized or None


def _serialize_refund(refund: OrderRefund) -> dict:
    return {
        "id": refund.id,
        "amount": _serialize_decimal(refund.amount),
        "status": refund.status,
        "method": refund.method,
        "reason": refund.reason,
        "note": refund.note,
        "operator_name": refund.operator_name,
        "created_at": _serialize_datetime(refund.created_at),
        "updated_at": _serialize_datetime(refund.updated_at),
    }


def _serialize_wallet_transaction(transaction: WalletTransaction) -> dict:
    return {
        "id": transaction.id,
        "transaction_type": transaction.transaction_type,
        "change_amount": _serialize_decimal(transaction.change_amount),
        "balance_after": _serialize_decimal(transaction.balance_after),
        "related_order_id": transaction.related_order_id,
        "note": transaction.note,
        "created_at": _serialize_datetime(transaction.created_at),
    }


def _get_couple_relationship_or_none(db: Session, relationship_id: str) -> Optional[CoupleRelationship]:
    return db.query(CoupleRelationship).filter(CoupleRelationship.id == relationship_id).first()


def _get_couple_actor_user(relationship: CoupleRelationship) -> Optional[User]:
    return relationship.user_a or relationship.user_b


def _serialize_admin_couple_relationship(relationship: CoupleRelationship) -> dict:
    user_a = relationship.user_a
    user_b = relationship.user_b
    return {
        "id": relationship.id,
        "status": relationship.status,
        "anniversary_date": relationship.anniversary_date.isoformat() if relationship.anniversary_date else None,
        "created_at": _serialize_datetime(relationship.created_at),
        "updated_at": _serialize_datetime(relationship.updated_at),
        "user_a": {
            "id": relationship.user_a_id,
            "nickname": user_a.nickname if user_a else None,
            "phone": user_a.phone if user_a else None,
        },
        "user_b": {
            "id": relationship.user_b_id,
            "nickname": user_b.nickname if user_b else None,
            "phone": user_b.phone if user_b else None,
        },
    }


def _serialize_admin_couple_candidate(user: User, relationship: Optional[CoupleRelationship]) -> dict:
    partner = get_partner_from_relationship(relationship, user.id) if relationship else None
    return {
        "id": user.id,
        "nickname": user.nickname,
        "phone": user.phone,
        "role": user.role,
        "couple_code": user.couple_code,
        "created_at": _serialize_datetime(user.created_at),
        "has_active_couple": relationship is not None,
        "active_couple_relationship_id": relationship.id if relationship else None,
        "active_partner": {
            "id": partner.id,
            "nickname": partner.nickname,
            "phone": partner.phone,
        } if partner else None,
    }


def _create_admin_operation_log(
    db: Session,
    admin: dict,
    action_type: str,
    target_type: str,
    summary: str,
    *,
    target_id: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
) -> AdminOperationLog:
    log = AdminOperationLog(
        operator_username=str(admin.get("username") or "admin"),
        operator_name=str(admin.get("display_name") or admin.get("username") or "系统管理员"),
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        detail=detail,
    )
    db.add(log)
    return log


def _recalculate_order_refund_summary(order: Order) -> None:
    refunded_total = Decimal("0.00")
    latest_reason = None
    latest_refunded_at = None

    for refund in order.refunds:
        if refund.status != "refunded":
            continue
        refunded_total += Decimal(str(refund.amount or 0))
        if latest_refunded_at is None or (
            refund.created_at and refund.created_at >= latest_refunded_at
        ):
            latest_refunded_at = refund.created_at
            latest_reason = refund.reason

    order_total = Decimal(str(order.total_price or 0))
    order.refund_amount = refunded_total
    if refunded_total <= Decimal("0.00"):
        order.refund_status = "none"
    elif refunded_total < order_total:
        order.refund_status = "partial"
    else:
        order.refund_status = "refunded"
    order.refund_reason = latest_reason
    order.refunded_at = latest_refunded_at


def _build_admin_refund_notice(order: Order, refund_amount: Decimal, refund_method: str) -> tuple[str, str]:
    if order.payment_method == "virtual_coin":
        return (
            "订单退款已处理",
            f"订单 {order.order_no} 已退回 {refund_amount:.2f} 餐币",
        )

    if refund_method == "wechat_manual":
        return (
            "订单退款已登记",
            f"订单 {order.order_no} 已登记线下退款 {refund_amount:.2f} 元，请以实际到账为准",
        )

    return (
        "订单退款已处理",
        f"订单 {order.order_no} 已退款 {refund_amount:.2f} 元",
    )


def _build_day_labels(days: int) -> list[date]:
    today = datetime.now().date()
    start = today - timedelta(days=days - 1)
    return [start + timedelta(days=index) for index in range(days)]


def _map_daily_rows(rows: list[tuple[Any, Any]], labels: list[date]) -> list[float]:
    lookup: dict[str, float] = {}
    for raw_day, value in rows:
        if raw_day is None:
            continue
        lookup[str(raw_day)] = float(value or 0)
    return [lookup.get(item.isoformat(), 0.0) for item in labels]


@router.post("/auth/login")
async def admin_login(request: AdminLoginRequest):
    """
    Admin console login with environment-configured credentials.
    """
    if (
        request.username.strip() != settings.ADMIN_USERNAME
        or request.password != settings.ADMIN_PASSWORD
    ):
        return error_response(401, "后台账号或密码错误")

    token = create_admin_token(settings.ADMIN_USERNAME)
    return success_response(
        data={
            "token": token,
            "profile": {
                "username": settings.ADMIN_USERNAME,
                "display_name": settings.ADMIN_DISPLAY_NAME
            }
        },
        message="登录成功"
    )


@router.get("/auth/me")
async def admin_me(admin: dict = Depends(require_admin)):
    """
    Return the current admin profile.
    """
    return success_response(data=admin)


@router.post("/users")
async def admin_create_user(
    request: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Create a local/account-login compatible user from the admin console.
    """
    account = request.account.strip()
    role = request.role.strip()

    if role not in VALID_USER_ROLES:
        return error_response(400, "角色必须是 foodie 或 chef")

    if db.query(User).filter(User.open_id == account).first():
        return error_response(409, "账号已存在")

    nickname = request.nickname.strip()
    specialties = _normalize_specialties(request.specialties) if role == "chef" else None
    introduction = ((request.introduction or "").strip() or None) if role == "chef" else None

    user = User(
        open_id=account,
        role=role,
        binding_code=_generate_unique_binding_code(db),
        nickname=nickname,
        avatar=(request.avatar or "").strip(),
        phone=(request.phone or "").strip() or None,
        introduction=introduction,
        specialties=specialties,
        is_open=request.is_open if role == "chef" else True,
    )
    db.add(user)
    db.flush()
    _create_admin_operation_log(
        db,
        admin,
        action_type="create_user",
        target_type="user",
        target_id=user.id,
        summary=f"创建{role}账号 {account}",
        detail={
            "account": account,
            "role": role,
            "nickname": nickname,
            "phone": user.phone,
        },
    )
    db.commit()
    db.refresh(user)

    return success_response(
        data={
            "id": user.id,
            "account": user.open_id,
            "nickname": user.nickname,
            "phone": user.phone,
            "role": user.role,
            "binding_code": user.binding_code,
            "wallet_balance": _serialize_decimal(user.virtual_coin_balance),
            "login_hint": {
                "endpoint": "/api/auth/login/account",
                "account": user.open_id,
                "password_rule": "当前后端 account 登录接口仍允许任意密码"
            },
            "created_at": _serialize_datetime(user.created_at),
        },
        message="用户已创建"
    )


@router.get("/dashboard/overview")
async def admin_dashboard_overview(
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Get headline statistics and recent activity for the admin dashboard.
    """
    del admin

    today_start = datetime.combine(datetime.now().date(), time.min)
    active_order_statuses = ("pending", "accepted", "cooking", "delivering", "completed")

    total_users = db.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0
    total_chefs = db.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.role == "chef"
    ).scalar() or 0
    total_orders = db.query(func.count(Order.id)).filter(Order.is_deleted == False).scalar() or 0
    active_dishes = db.query(func.count(Dish.id)).filter(
        Dish.is_deleted == False,
        Dish.is_on_shelf == True
    ).scalar() or 0
    active_couples = db.query(func.count(CoupleRelationship.id)).filter(
        CoupleRelationship.status == "active"
    ).scalar() or 0
    pending_orders = db.query(func.count(Order.id)).filter(
        Order.is_deleted == False,
        Order.status.in_(("pending", "accepted", "cooking", "delivering"))
    ).scalar() or 0
    unread_notifications = db.query(func.count(Notification.id)).filter(
        Notification.is_read == False
    ).scalar() or 0
    refunded_orders = db.query(func.count(Order.id)).filter(
        Order.is_deleted == False,
        Order.refund_status.in_(("partial", "refunded"))
    ).scalar() or 0
    total_gmv = db.query(func.coalesce(func.sum(Order.total_price), 0)).filter(
        Order.is_deleted == False,
        Order.status.in_(active_order_statuses)
    ).scalar() or 0
    today_orders = db.query(func.count(Order.id)).filter(
        Order.is_deleted == False,
        Order.created_at >= today_start
    ).scalar() or 0
    today_gmv = db.query(func.coalesce(func.sum(Order.total_price), 0)).filter(
        Order.is_deleted == False,
        Order.created_at >= today_start,
        Order.status.in_(active_order_statuses)
    ).scalar() or 0
    total_tips = db.query(func.coalesce(func.sum(Tip.amount), 0)).filter(
        Tip.status == "paid"
    ).scalar() or 0
    total_refunded_amount = db.query(func.coalesce(func.sum(OrderRefund.amount), 0)).filter(
        OrderRefund.status == "refunded"
    ).scalar() or 0
    broadcast_count = db.query(func.count(AdminBroadcast.id)).scalar() or 0
    total_wallet_balance = db.query(func.coalesce(func.sum(User.virtual_coin_balance), 0)).filter(
        User.is_deleted == False
    ).scalar() or 0
    total_wallet_topup = db.query(func.coalesce(func.sum(WalletTransaction.change_amount), 0)).filter(
        WalletTransaction.transaction_type.in_(("topup", "admin_topup")),
        WalletTransaction.change_amount > Decimal("0.00"),
    ).scalar() or 0
    today_wallet_topup = db.query(func.coalesce(func.sum(WalletTransaction.change_amount), 0)).filter(
        WalletTransaction.transaction_type.in_(("topup", "admin_topup")),
        WalletTransaction.change_amount > Decimal("0.00"),
        WalletTransaction.created_at >= today_start,
    ).scalar() or 0
    virtual_coin_order_count = db.query(func.count(Order.id)).filter(
        Order.is_deleted == False,
        Order.payment_method == "virtual_coin",
    ).scalar() or 0
    total_wallet_payment = db.query(
        func.coalesce(func.sum(func.abs(WalletTransaction.change_amount)), 0)
    ).filter(
        WalletTransaction.transaction_type == "order_payment"
    ).scalar() or 0

    role_distribution_rows = db.query(
        User.role,
        func.count(User.id)
    ).filter(
        User.is_deleted == False
    ).group_by(User.role).all()

    order_status_rows = db.query(
        Order.status,
        func.count(Order.id)
    ).filter(
        Order.is_deleted == False
    ).group_by(Order.status).all()

    payment_method_rows = db.query(
        Order.payment_method,
        func.count(Order.id)
    ).filter(
        Order.is_deleted == False
    ).group_by(Order.payment_method).all()

    foodie_alias = aliased(User)
    chef_alias = aliased(User)
    recent_orders = db.query(
        Order,
        foodie_alias.nickname.label("foodie_nickname"),
        chef_alias.nickname.label("chef_nickname"),
    ).join(
        foodie_alias, Order.foodie_id == foodie_alias.id
    ).join(
        chef_alias, Order.chef_id == chef_alias.id
    ).filter(
        Order.is_deleted == False
    ).order_by(
        Order.created_at.desc()
    ).limit(8).all()

    recent_reviews = db.query(
        Review,
        User.nickname.label("foodie_nickname"),
        Dish.name.label("dish_name")
    ).join(
        User, Review.foodie_id == User.id
    ).join(
        Dish, Review.dish_id == Dish.id
    ).filter(
        Review.is_deleted == False
    ).order_by(
        Review.created_at.desc()
    ).limit(6).all()

    recent_wallet_transactions = db.query(
        WalletTransaction,
        User.nickname.label("nickname"),
        User.role.label("role"),
    ).outerjoin(
        User, WalletTransaction.user_id == User.id
    ).order_by(
        WalletTransaction.created_at.desc()
    ).limit(6).all()

    recent_operation_logs = db.query(
        AdminOperationLog
    ).order_by(
        AdminOperationLog.created_at.desc()
    ).limit(6).all()

    return success_response(
        data={
            "headline": {
                "total_users": total_users,
                "total_chefs": total_chefs,
                "total_orders": total_orders,
                "active_dishes": active_dishes,
                "active_couples": active_couples,
                "pending_orders": pending_orders,
                "unread_notifications": unread_notifications,
                "refunded_orders": refunded_orders,
                "total_gmv": _serialize_decimal(total_gmv),
                "today_orders": today_orders,
                "today_gmv": _serialize_decimal(today_gmv),
                "paid_tips": _serialize_decimal(total_tips),
                "total_refunded_amount": _serialize_decimal(total_refunded_amount),
                "broadcast_count": broadcast_count,
                "total_wallet_balance": _serialize_decimal(total_wallet_balance),
                "total_wallet_topup": _serialize_decimal(total_wallet_topup),
                "today_wallet_topup": _serialize_decimal(today_wallet_topup),
                "virtual_coin_order_count": virtual_coin_order_count,
                "total_wallet_payment": _serialize_decimal(total_wallet_payment),
            },
            "role_distribution": [
                {"role": role, "count": count}
                for role, count in role_distribution_rows
            ],
            "order_status_distribution": [
                {"status": status, "count": count}
                for status, count in order_status_rows
            ],
            "payment_method_distribution": [
                {"payment_method": payment_method or "unknown", "count": count}
                for payment_method, count in payment_method_rows
            ],
            "recent_orders": [
                {
                    "id": order.id,
                    "order_no": order.order_no,
                    "status": order.status,
                    "total_price": _serialize_decimal(order.total_price),
                    "payment_method": order.payment_method,
                    "wallet_paid_amount": _serialize_decimal(order.wallet_paid_amount),
                    "foodie_nickname": foodie_nickname or "未命名吃货",
                    "chef_nickname": chef_nickname or "未命名大厨",
                    "delivery_time": _serialize_datetime(order.delivery_time),
                    "created_at": _serialize_datetime(order.created_at),
                }
                for order, foodie_nickname, chef_nickname in recent_orders
            ],
            "recent_reviews": [
                {
                    "id": review.id,
                    "rating": review.rating,
                    "content": review.content,
                    "foodie_nickname": foodie_nickname or "匿名用户",
                    "dish_name": dish_name or "未知菜品",
                    "created_at": _serialize_datetime(review.created_at),
                }
                for review, foodie_nickname, dish_name in recent_reviews
            ],
            "recent_wallet_transactions": [
                {
                    "id": transaction.id,
                    "transaction_type": transaction.transaction_type,
                    "change_amount": _serialize_decimal(transaction.change_amount),
                    "balance_after": _serialize_decimal(transaction.balance_after),
                    "nickname": nickname or "未命名用户",
                    "role": role or "foodie",
                    "note": transaction.note,
                    "created_at": _serialize_datetime(transaction.created_at),
                }
                for transaction, nickname, role in recent_wallet_transactions
            ],
            "recent_operation_logs": [
                {
                    "id": item.id,
                    "operator_username": item.operator_username,
                    "operator_name": item.operator_name,
                    "action_type": item.action_type,
                    "target_type": item.target_type,
                    "target_id": item.target_id,
                    "summary": item.summary,
                    "detail": item.detail,
                    "created_at": _serialize_datetime(item.created_at),
                }
                for item in recent_operation_logs
            ],
        }
    )


@router.get("/dashboard/trends")
async def admin_dashboard_trends(
    days: int = Query(14, ge=7, le=30, description="趋势天数"),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Return daily trend series for chart widgets in the admin dashboard.
    """
    del admin

    labels = _build_day_labels(days)
    start_time = datetime.combine(labels[0], time.min)
    active_order_statuses = ("pending", "accepted", "cooking", "delivering", "completed")

    order_rows = db.query(
        func.date(Order.created_at),
        func.count(Order.id)
    ).filter(
        Order.is_deleted == False,
        Order.created_at >= start_time
    ).group_by(func.date(Order.created_at)).all()

    gmv_rows = db.query(
        func.date(Order.created_at),
        func.coalesce(func.sum(Order.total_price), 0)
    ).filter(
        Order.is_deleted == False,
        Order.created_at >= start_time,
        Order.status.in_(active_order_statuses)
    ).group_by(func.date(Order.created_at)).all()

    user_rows = db.query(
        func.date(User.created_at),
        func.count(User.id)
    ).filter(
        User.is_deleted == False,
        User.created_at >= start_time
    ).group_by(func.date(User.created_at)).all()

    review_rows = db.query(
        func.date(Review.created_at),
        func.count(Review.id)
    ).filter(
        Review.is_deleted == False,
        Review.created_at >= start_time
    ).group_by(func.date(Review.created_at)).all()

    refund_count_rows = db.query(
        func.date(OrderRefund.created_at),
        func.count(OrderRefund.id)
    ).filter(
        OrderRefund.status == "refunded",
        OrderRefund.created_at >= start_time
    ).group_by(func.date(OrderRefund.created_at)).all()

    refund_amount_rows = db.query(
        func.date(OrderRefund.created_at),
        func.coalesce(func.sum(OrderRefund.amount), 0)
    ).filter(
        OrderRefund.status == "refunded",
        OrderRefund.created_at >= start_time
    ).group_by(func.date(OrderRefund.created_at)).all()

    broadcast_rows = db.query(
        func.date(AdminBroadcast.created_at),
        func.count(AdminBroadcast.id)
    ).filter(
        AdminBroadcast.created_at >= start_time
    ).group_by(func.date(AdminBroadcast.created_at)).all()

    wallet_topup_rows = db.query(
        func.date(WalletTransaction.created_at),
        func.coalesce(func.sum(WalletTransaction.change_amount), 0)
    ).filter(
        WalletTransaction.transaction_type.in_(("topup", "admin_topup")),
        WalletTransaction.change_amount > Decimal("0.00"),
        WalletTransaction.created_at >= start_time
    ).group_by(func.date(WalletTransaction.created_at)).all()

    wallet_payment_rows = db.query(
        func.date(WalletTransaction.created_at),
        func.coalesce(func.sum(func.abs(WalletTransaction.change_amount)), 0)
    ).filter(
        WalletTransaction.transaction_type == "order_payment",
        WalletTransaction.created_at >= start_time
    ).group_by(func.date(WalletTransaction.created_at)).all()

    return success_response(
        data={
            "labels": [item.isoformat() for item in labels],
            "series": {
                "order_count": _map_daily_rows(order_rows, labels),
                "gmv": _map_daily_rows(gmv_rows, labels),
                "user_count": _map_daily_rows(user_rows, labels),
                "review_count": _map_daily_rows(review_rows, labels),
                "refund_count": _map_daily_rows(refund_count_rows, labels),
                "refund_amount": _map_daily_rows(refund_amount_rows, labels),
                "broadcast_count": _map_daily_rows(broadcast_rows, labels),
                "wallet_topup_amount": _map_daily_rows(wallet_topup_rows, labels),
                "wallet_payment_amount": _map_daily_rows(wallet_payment_rows, labels),
            }
        }
    )


@router.get("/users")
async def admin_list_users(
    search: Optional[str] = Query(None, description="昵称/手机号/open_id/邀请码搜索"),
    role: Optional[str] = Query(None, description="foodie/chef"),
    is_deleted: Optional[bool] = Query(None, description="是否已禁用"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Paginated user management list.
    """
    del admin

    chef_dish_count_sq = db.query(
        Dish.chef_id.label("user_id"),
        func.count(Dish.id).label("dish_count")
    ).filter(
        Dish.is_deleted == False
    ).group_by(Dish.chef_id).subquery()

    chef_order_count_sq = db.query(
        Order.chef_id.label("user_id"),
        func.count(Order.id).label("chef_order_count")
    ).filter(
        Order.is_deleted == False
    ).group_by(Order.chef_id).subquery()

    foodie_order_count_sq = db.query(
        Order.foodie_id.label("user_id"),
        func.count(Order.id).label("foodie_order_count")
    ).filter(
        Order.is_deleted == False
    ).group_by(Order.foodie_id).subquery()

    binding_count_sq = db.query(
        Binding.chef_id.label("user_id"),
        func.count(Binding.id).label("bound_foodies_count")
    ).group_by(Binding.chef_id).subquery()

    query = db.query(
        User,
        func.coalesce(chef_dish_count_sq.c.dish_count, 0).label("dish_count"),
        func.coalesce(chef_order_count_sq.c.chef_order_count, 0).label("chef_order_count"),
        func.coalesce(foodie_order_count_sq.c.foodie_order_count, 0).label("foodie_order_count"),
        func.coalesce(binding_count_sq.c.bound_foodies_count, 0).label("bound_foodies_count"),
    ).outerjoin(
        chef_dish_count_sq, chef_dish_count_sq.c.user_id == User.id
    ).outerjoin(
        chef_order_count_sq, chef_order_count_sq.c.user_id == User.id
    ).outerjoin(
        foodie_order_count_sq, foodie_order_count_sq.c.user_id == User.id
    ).outerjoin(
        binding_count_sq, binding_count_sq.c.user_id == User.id
    )

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.nickname.like(keyword),
                User.phone.like(keyword),
                User.open_id.like(keyword),
                User.binding_code.like(keyword),
                User.couple_code.like(keyword),
            )
        )
    if role:
        query = query.filter(User.role == role)
    if is_deleted is not None:
        query = query.filter(User.is_deleted == is_deleted)

    total = query.count()
    rows = query.order_by(User.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            {
                "id": user.id,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "phone": user.phone,
                "role": user.role,
                "binding_code": user.binding_code,
                "couple_code": user.couple_code,
                "is_open": user.is_open,
                "is_deleted": user.is_deleted,
                "rest_notice": user.rest_notice,
                "rating": _serialize_decimal(user.rating) if user.rating is not None else None,
                "total_orders": user.total_orders,
                "wallet_balance": _serialize_decimal(user.virtual_coin_balance),
                "metrics": {
                    "dish_count": dish_count,
                    "chef_order_count": chef_order_count,
                    "foodie_order_count": foodie_order_count,
                    "bound_foodies_count": bound_foodies_count,
                },
                "created_at": _serialize_datetime(user.created_at),
                "updated_at": _serialize_datetime(user.updated_at),
            }
            for user, dish_count, chef_order_count, foodie_order_count, bound_foodies_count in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    request: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Update a subset of user management fields.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return error_response(404, "用户不存在")

    payload = request.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(user, field, value)

    _create_admin_operation_log(
        db,
        admin,
        action_type="update_user",
        target_type="user",
        target_id=user.id,
        summary=f"更新用户 {user.nickname or user.id}",
        detail=payload,
    )
    db.commit()
    db.refresh(user)

    return success_response(
        data={
            "id": user.id,
            "nickname": user.nickname,
            "phone": user.phone,
            "role": user.role,
            "is_open": user.is_open,
            "is_deleted": user.is_deleted,
            "rest_notice": user.rest_notice,
            "wallet_balance": _serialize_decimal(user.virtual_coin_balance),
            "updated_at": _serialize_datetime(user.updated_at),
        },
        message="用户信息已更新"
    )


@router.get("/users/{user_id}/wallet/transactions")
async def admin_list_user_wallet_transactions(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    List wallet transactions for a specific user in the admin console.
    """
    del admin

    service = WalletService(db)

    try:
        service.get_user_or_raise(user_id)
        items, total = service.list_transactions(user_id, page=page, page_size=page_size)
    except WalletServiceError as exc:
        return error_response(exc.code, exc.message)

    return paginated_response(
        data=[_serialize_wallet_transaction(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/users/{user_id}/wallet/topup")
async def admin_top_up_user_wallet(
    user_id: str,
    request: AdminUserWalletTopUpRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Add virtual coins to a user account from the admin console.
    """
    service = WalletService(db)
    operator_name = str(admin.get("display_name") or admin.get("username") or "系统管理员")
    normalized_note = (request.note or "").strip()
    transaction_note = f"后台加币，操作人：{operator_name}"
    if normalized_note:
        transaction_note = f"{transaction_note}；备注：{normalized_note}"

    try:
        user = service.get_user_or_raise(user_id)
        transaction = service.add_balance(
            user=user,
            amount=request.amount,
            transaction_type="admin_topup",
            note=transaction_note,
        )
        _create_admin_operation_log(
            db,
            admin,
            action_type="wallet_topup",
            target_type="user_wallet",
            target_id=user.id,
            summary=f"给用户 {user.nickname or user.id} 增加餐币",
            detail={
                "amount": _serialize_decimal(request.amount),
                "note": normalized_note or None,
                "balance_after": _serialize_decimal(user.virtual_coin_balance),
            },
        )
        db.commit()
        db.refresh(user)
        db.refresh(transaction)
    except WalletServiceError as exc:
        db.rollback()
        return error_response(exc.code, exc.message)
    except Exception as exc:
        db.rollback()
        return error_response(500, f"后台加钱失败: {str(exc)}")

    return success_response(
        data={
            "user": {
                "id": user.id,
                "nickname": user.nickname,
                "role": user.role,
                "wallet_balance": _serialize_decimal(user.virtual_coin_balance),
                "updated_at": _serialize_datetime(user.updated_at),
            },
            "transaction": _serialize_wallet_transaction(transaction),
        },
        message="虚拟币余额已增加"
    )


@router.get("/dishes")
async def admin_list_dishes(
    search: Optional[str] = Query(None, description="菜品名/分类/大厨搜索"),
    is_on_shelf: Optional[bool] = Query(None, description="是否上架"),
    is_deleted: Optional[bool] = Query(None, description="是否删除"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Paginated dish management list.
    """
    del admin

    chef_alias = aliased(User)
    query = db.query(
        Dish,
        chef_alias.nickname.label("chef_nickname")
    ).join(
        chef_alias, Dish.chef_id == chef_alias.id
    )

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Dish.name.like(keyword),
                Dish.category.like(keyword),
                chef_alias.nickname.like(keyword),
            )
        )
    if is_on_shelf is not None:
        query = query.filter(Dish.is_on_shelf == is_on_shelf)
    if is_deleted is not None:
        query = query.filter(Dish.is_deleted == is_deleted)

    total = query.count()
    rows = query.order_by(Dish.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            {
                "id": dish.id,
                "name": dish.name,
                "chef_id": dish.chef_id,
                "chef_nickname": chef_nickname or "未命名大厨",
                "price": _serialize_decimal(dish.price),
                "category": dish.category,
                "rating": _serialize_decimal(dish.rating) if dish.rating is not None else None,
                "review_count": dish.review_count,
                "max_quantity": dish.max_quantity,
                "is_on_shelf": dish.is_on_shelf,
                "is_deleted": dish.is_deleted,
                "images": dish.images or [],
                "created_at": _serialize_datetime(dish.created_at),
                "updated_at": _serialize_datetime(dish.updated_at),
            }
            for dish, chef_nickname in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.put("/dishes/{dish_id}")
async def admin_update_dish(
    dish_id: str,
    request: AdminDishUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Update dish availability fields.
    """
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        return error_response(404, "菜品不存在")

    payload = request.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(dish, field, value)

    _create_admin_operation_log(
        db,
        admin,
        action_type="update_dish",
        target_type="dish",
        target_id=dish.id,
        summary=f"更新菜品 {dish.name}",
        detail=payload,
    )
    db.commit()
    db.refresh(dish)

    return success_response(
        data={
            "id": dish.id,
            "is_on_shelf": dish.is_on_shelf,
            "is_deleted": dish.is_deleted,
            "category": dish.category,
            "max_quantity": dish.max_quantity,
            "updated_at": _serialize_datetime(dish.updated_at),
        },
        message="菜品信息已更新"
    )


@router.get("/orders")
async def admin_list_orders(
    search: Optional[str] = Query(None, description="订单号/买家/大厨搜索"),
    status: Optional[str] = Query(None, description="订单状态"),
    payment_method: Optional[str] = Query(None, description="支付方式"),
    refund_status: Optional[str] = Query(None, description="退款状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Paginated order management list.
    """
    del admin

    foodie_alias = aliased(User)
    chef_alias = aliased(User)
    query = db.query(
        Order,
        foodie_alias.nickname.label("foodie_nickname"),
        chef_alias.nickname.label("chef_nickname"),
    ).join(
        foodie_alias, Order.foodie_id == foodie_alias.id
    ).join(
        chef_alias, Order.chef_id == chef_alias.id
    ).filter(
        Order.is_deleted == False
    )

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Order.order_no.like(keyword),
                foodie_alias.nickname.like(keyword),
                chef_alias.nickname.like(keyword),
                Order.remarks.like(keyword),
            )
        )
    if status:
        query = query.filter(Order.status == status)
    if payment_method:
        query = query.filter(Order.payment_method == payment_method)
    if refund_status:
        query = query.filter(Order.refund_status == refund_status)

    total = query.count()
    rows = query.order_by(Order.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            {
                "id": order.id,
                "order_no": order.order_no,
                "foodie_id": order.foodie_id,
                "foodie_nickname": foodie_nickname or "未命名吃货",
                "chef_id": order.chef_id,
                "chef_nickname": chef_nickname or "未命名大厨",
                "status": order.status,
                "payment_method": order.payment_method,
                "wallet_paid_amount": _serialize_decimal(order.wallet_paid_amount),
                "refund_status": order.refund_status,
                "refund_amount": _serialize_decimal(order.refund_amount),
                "total_price": _serialize_decimal(order.total_price),
                "delivery_time": _serialize_datetime(order.delivery_time),
                "is_reviewed": order.is_reviewed,
                "remarks": order.remarks,
                "created_at": _serialize_datetime(order.created_at),
                "updated_at": _serialize_datetime(order.updated_at),
            }
            for order, foodie_nickname, chef_nickname in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/orders/{order_id}")
async def admin_get_order_detail(
    order_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Get full detail for one order.
    """
    del admin

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.is_deleted == False
    ).first()
    if not order:
        return error_response(404, "订单不存在")

    foodie = db.query(User).filter(User.id == order.foodie_id).first()
    chef = db.query(User).filter(User.id == order.chef_id).first()

    return success_response(
        data={
            "id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "payment_method": order.payment_method,
            "wallet_paid_amount": _serialize_decimal(order.wallet_paid_amount),
            "refund_status": order.refund_status,
            "refund_amount": _serialize_decimal(order.refund_amount),
            "refund_reason": order.refund_reason,
            "foodie": {
                "id": foodie.id if foodie else order.foodie_id,
                "nickname": foodie.nickname if foodie else None,
                "phone": foodie.phone if foodie else None,
            },
            "chef": {
                "id": chef.id if chef else order.chef_id,
                "nickname": chef.nickname if chef else None,
                "phone": chef.phone if chef else None,
            },
            "total_price": _serialize_decimal(order.total_price),
            "delivery_time": _serialize_datetime(order.delivery_time),
            "address_snapshot": order.address_snapshot,
            "remarks": order.remarks,
            "cancel_reason": order.cancel_reason,
            "is_reviewed": order.is_reviewed,
            "payment_id": order.payment_id,
            "refunded_at": _serialize_datetime(order.refunded_at),
            "created_at": _serialize_datetime(order.created_at),
            "updated_at": _serialize_datetime(order.updated_at),
            "completed_at": _serialize_datetime(order.completed_at),
            "items": [
                {
                    "id": item.id,
                    "dish_id": item.dish_id,
                    "dish_name": item.dish_name,
                    "dish_image": item.dish_image,
                    "price": _serialize_decimal(item.price),
                    "quantity": item.quantity,
                }
                for item in order.items
            ],
            "refunds": [_serialize_refund(refund) for refund in order.refunds],
        }
    )


@router.put("/orders/{order_id}/status")
async def admin_update_order_status(
    order_id: str,
    request: AdminOrderStatusUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Update order status from the admin console.
    """
    if request.status not in ORDER_STATUSES:
        return error_response(400, "不支持的订单状态")

    order_service = OrderService(db)
    try:
        order = order_service.admin_update_status(
            order_id=order_id,
            target_status=request.status,
            cancel_reason=request.cancel_reason,
        )
    except OrderServiceError as exc:
        return error_response(exc.code, exc.message)

    _create_admin_operation_log(
        db,
        admin,
        action_type="update_order_status",
        target_type="order",
        target_id=order.id,
        summary=f"更新订单 {order.order_no} 状态为 {order.status}",
        detail={
            "status": order.status,
            "cancel_reason": order.cancel_reason,
            "completed_at": _serialize_datetime(order.completed_at),
        },
    )
    db.commit()
    db.refresh(order)

    return success_response(
        data={
            "id": order.id,
            "status": order.status,
            "cancel_reason": order.cancel_reason,
            "completed_at": _serialize_datetime(order.completed_at),
            "updated_at": _serialize_datetime(order.updated_at),
        },
        message="订单状态已更新"
    )


@router.post("/orders/{order_id}/refund")
async def admin_create_order_refund(
    order_id: str,
    request: AdminRefundCreateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Create a manual refund record and update the order refund summary.
    """
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.is_deleted == False
    ).first()
    if not order:
        return error_response(404, "订单不存在")

    if Decimal(str(order.total_price or 0)) <= Decimal("0.00"):
        return error_response(400, "零金额订单无需退款")

    refunded_total = Decimal(str(order.refund_amount or 0))
    remaining_refundable = Decimal(str(order.total_price or 0)) - refunded_total
    if remaining_refundable <= Decimal("0.00"):
        return error_response(400, "该订单已完成全额退款")

    if order.payment_method == "wechat" and order.status == "unpaid":
        return error_response(400, "微信未支付订单不能创建退款记录，请先确认支付状态或直接取消订单")

    if order.payment_method == "wechat" and not request.mark_manual_processed:
        return error_response(
            400,
            "暂未接入微信原路退款，请先在线下或微信商户后台完成退款后，再勾选“已线下处理”登记退款记录",
        )

    refund_amount = Decimal(str(request.amount or remaining_refundable)).quantize(Decimal("0.01"))
    if refund_amount > remaining_refundable:
        return error_response(400, "退款金额不能超过剩余可退金额")

    if order.payment_method == "virtual_coin":
        refund_method = "virtual_coin"
    elif order.payment_method == "wechat":
        refund_method = "wechat_manual"
    else:
        refund_method = "manual"
    refund_created_at = datetime.now()
    refund = OrderRefund(
        order=order,
        amount=refund_amount,
        status="refunded",
        method=refund_method,
        reason=request.reason.strip(),
        note=(request.note or "").strip() or None,
        operator_name=str(admin.get("display_name") or admin.get("username") or "admin"),
        created_at=refund_created_at,
    )
    db.add(refund)
    db.flush()

    if order.payment_method == "virtual_coin":
        foodie = db.query(User).filter(User.id == order.foodie_id).first()
        if not foodie:
            db.rollback()
            return error_response(404, "订单对应的用户不存在，无法退回餐币")

        WalletService(db).add_balance(
            user=foodie,
            amount=refund_amount,
            transaction_type="order_refund",
            note=f"后台退款：订单 {order.order_no} 退回 {refund_amount:.2f} 餐币",
            related_order_id=order.id,
        )

    _recalculate_order_refund_summary(order)
    if order.refund_status == "refunded" and order.status in {"unpaid", "pending", "accepted", "cooking", "delivering"}:
        order.status = "cancelled"
        order.cancel_reason = order.cancel_reason or "后台退款"
        OrderService(db)._restore_order_inventory(order)

    refund_title, refund_content = _build_admin_refund_notice(order, refund_amount, refund_method)
    db.add(Notification(
        id=str(uuid.uuid4()),
        user_id=order.foodie_id,
        type="system",
        title=refund_title,
        content=refund_content,
        data={"source": "admin_refund", "order_id": order.id, "refund_id": refund.id}
    ))
    db.add(Notification(
        id=str(uuid.uuid4()),
        user_id=order.chef_id,
        type="system",
        title=refund_title,
        content=refund_content,
        data={"source": "admin_refund", "order_id": order.id, "refund_id": refund.id}
    ))

    _create_admin_operation_log(
        db,
        admin,
        action_type="create_order_refund",
        target_type="order",
        target_id=order.id,
        summary=f"为订单 {order.order_no} 创建退款记录",
        detail={
            "refund_amount": _serialize_decimal(refund_amount),
            "refund_method": refund_method,
            "reason": request.reason.strip(),
            "mark_manual_processed": request.mark_manual_processed,
        },
    )
    db.commit()
    db.refresh(order)
    db.refresh(refund)

    return success_response(
        data={
            "order_id": order.id,
            "refund_status": order.refund_status,
            "refund_amount": _serialize_decimal(order.refund_amount),
            "refunded_at": _serialize_datetime(order.refunded_at),
            "refund": _serialize_refund(refund),
        },
        message="线下退款记录已登记" if refund_method == "wechat_manual" else "退款记录已创建"
    )


@router.post("/notifications/broadcast")
async def admin_create_broadcast(
    request: AdminBroadcastCreateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Broadcast a system notification to all or selected users.
    """
    target_role = (request.target_role or "").strip() or None
    if target_role and target_role not in VALID_USER_ROLES:
        return error_response(400, "目标角色必须是 foodie 或 chef")

    min_wallet_balance = (
        Decimal(str(request.min_wallet_balance)).quantize(Decimal("0.01"))
        if request.min_wallet_balance is not None
        else None
    )
    max_wallet_balance = (
        Decimal(str(request.max_wallet_balance)).quantize(Decimal("0.01"))
        if request.max_wallet_balance is not None
        else None
    )

    if (
        min_wallet_balance is not None
        and max_wallet_balance is not None
        and min_wallet_balance > max_wallet_balance
    ):
        return error_response(400, "最小余额不能大于最大余额")

    reward_amount = (
        Decimal(str(request.reward_amount)).quantize(Decimal("0.01"))
        if request.reward_amount is not None
        else Decimal("0.00")
    )
    user_ids = request.user_ids or []
    recipients_query = db.query(User).filter(User.is_deleted == False)
    if target_role:
        recipients_query = recipients_query.filter(User.role == target_role)
    if user_ids:
        recipients_query = recipients_query.filter(User.id.in_(user_ids))
    if min_wallet_balance is not None:
        recipients_query = recipients_query.filter(User.virtual_coin_balance >= min_wallet_balance)
    if max_wallet_balance is not None:
        recipients_query = recipients_query.filter(User.virtual_coin_balance <= max_wallet_balance)

    recipients = recipients_query.all()

    created_by = str(admin.get("display_name") or admin.get("username") or "admin")
    broadcast = AdminBroadcast(
        title=request.title.strip(),
        content=request.content.strip(),
        target_role=target_role,
        recipient_count=len(recipients),
        created_by=created_by,
        filters={
            "target_role": target_role,
            "user_ids": user_ids,
            "has_min_wallet_balance": min_wallet_balance is not None,
            "has_max_wallet_balance": max_wallet_balance is not None,
            "min_wallet_balance": _serialize_optional_decimal(min_wallet_balance),
            "max_wallet_balance": _serialize_optional_decimal(max_wallet_balance),
            "reward_amount": _serialize_optional_decimal(reward_amount if reward_amount > Decimal("0.00") else None),
        },
        note=(request.note or "").strip() or None,
    )
    db.add(broadcast)
    db.flush()

    wallet_service = WalletService(db)
    notifications = [
        Notification(
            id=str(uuid.uuid4()),
            user_id=user.id,
            type="system",
            title=broadcast.title,
            content=broadcast.content,
            data={
                "source": "admin_broadcast",
                "broadcast_id": broadcast.id,
                "target_role": target_role,
                "reward_amount": _serialize_decimal(reward_amount),
            }
        )
        for user in recipients
    ]
    db.add_all(notifications)

    if reward_amount > Decimal("0.00"):
        for user in recipients:
            wallet_service.add_balance(
                user=user,
                amount=reward_amount,
                transaction_type="campaign_reward",
                note=f"广播活动奖励：{broadcast.title}，操作人：{created_by}",
            )

    _create_admin_operation_log(
        db,
        admin,
        action_type="create_broadcast",
        target_type="broadcast",
        target_id=broadcast.id,
        summary=f"发送广播 {broadcast.title}",
        detail={
            "target_role": target_role,
            "recipient_count": len(recipients),
            "reward_amount": _serialize_decimal(reward_amount),
            "filters": _normalize_broadcast_filters(broadcast.filters),
        },
    )
    db.commit()
    db.refresh(broadcast)

    return success_response(
        data={
            "id": broadcast.id,
            "title": broadcast.title,
            "content": broadcast.content,
            "target_role": broadcast.target_role,
            "recipient_count": broadcast.recipient_count,
            "reward_amount": _serialize_decimal(reward_amount),
            "filters": _normalize_broadcast_filters(broadcast.filters),
            "created_by": broadcast.created_by,
            "created_at": _serialize_datetime(broadcast.created_at),
        },
        message=(
            "系统通知已创建，当前没有命中用户"
            if not recipients
            else "系统通知已群发"
            if reward_amount <= Decimal("0.00")
            else "系统通知已群发，餐币奖励已发放"
        )
    )


@router.get("/notifications/broadcasts")
async def admin_list_broadcasts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Paginated broadcast history.
    """
    del admin

    query = db.query(AdminBroadcast)
    total = query.count()
    rows = query.order_by(AdminBroadcast.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "target_role": item.target_role,
                "recipient_count": item.recipient_count,
                "created_by": item.created_by,
                "filters": _normalize_broadcast_filters(item.filters),
                "note": item.note,
                "created_at": _serialize_datetime(item.created_at),
            }
            for item in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/operation-logs")
async def admin_create_operation_log(
    request: AdminOperationLogCreateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Create an explicit admin operation log entry.
    """
    log = _create_admin_operation_log(
        db,
        admin,
        action_type=request.action_type.strip(),
        target_type=request.target_type.strip(),
        target_id=(request.target_id or "").strip() or None,
        summary=request.summary.strip(),
        detail=request.detail,
    )
    db.commit()
    db.refresh(log)

    return success_response(
        data={
            "id": log.id,
            "action_type": log.action_type,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "summary": log.summary,
            "created_at": _serialize_datetime(log.created_at),
        },
        message="操作日志已记录"
    )


@router.get("/operation-logs")
async def admin_list_operation_logs(
    search: Optional[str] = Query(None, description="按操作摘要、操作账号搜索"),
    action_type: Optional[str] = Query(None, description="按操作类型筛选"),
    target_type: Optional[str] = Query(None, description="按目标类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Paginated admin operation audit log.
    """
    del admin

    query = db.query(AdminOperationLog)

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AdminOperationLog.summary.like(keyword),
                AdminOperationLog.operator_username.like(keyword),
                AdminOperationLog.operator_name.like(keyword),
            )
        )
    if action_type:
        query = query.filter(AdminOperationLog.action_type == action_type)
    if target_type:
        query = query.filter(AdminOperationLog.target_type == target_type)

    total = query.count()
    rows = query.order_by(AdminOperationLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            {
                "id": item.id,
                "operator_username": item.operator_username,
                "operator_name": item.operator_name,
                "action_type": item.action_type,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "summary": item.summary,
                "detail": item.detail,
                "created_at": _serialize_datetime(item.created_at),
            }
            for item in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/reviews")
async def admin_list_reviews(
    search: Optional[str] = Query(None, description="评价内容/菜品/用户搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Paginated review list for admin inspection.
    """
    del admin

    foodie_alias = aliased(User)
    chef_alias = aliased(User)
    query = db.query(
        Review,
        foodie_alias.nickname.label("foodie_nickname"),
        chef_alias.nickname.label("chef_nickname"),
        Dish.name.label("dish_name"),
    ).join(
        foodie_alias, Review.foodie_id == foodie_alias.id
    ).join(
        chef_alias, Review.chef_id == chef_alias.id
    ).join(
        Dish, Review.dish_id == Dish.id
    ).filter(
        Review.is_deleted == False
    )

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Review.content.like(keyword),
                foodie_alias.nickname.like(keyword),
                chef_alias.nickname.like(keyword),
                Dish.name.like(keyword),
            )
        )

    total = query.count()
    rows = query.order_by(Review.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            {
                "id": review.id,
                "order_id": review.order_id,
                "rating": review.rating,
                "content": review.content,
                "images": review.images or [],
                "dish_name": dish_name,
                "foodie_nickname": foodie_nickname,
                "chef_nickname": chef_nickname,
                "created_at": _serialize_datetime(review.created_at),
            }
            for review, foodie_nickname, chef_nickname, dish_name in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/couples")
async def admin_list_couples(
    search: Optional[str] = Query(None, description="情侣用户昵称或手机号搜索"),
    status: Optional[str] = Query(None, description="active/inactive"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Paginated couple relationship overview.
    """
    del admin

    user_a = aliased(User)
    user_b = aliased(User)

    memo_count_sq = db.query(
        CoupleMemo.relationship_id.label("relationship_id"),
        func.count(CoupleMemo.id).label("memo_count")
    ).group_by(CoupleMemo.relationship_id).subquery()

    anniversary_count_sq = db.query(
        CoupleAnniversary.relationship_id.label("relationship_id"),
        func.count(CoupleAnniversary.id).label("anniversary_count")
    ).group_by(CoupleAnniversary.relationship_id).subquery()

    date_plan_count_sq = db.query(
        CoupleDatePlan.relationship_id.label("relationship_id"),
        func.count(CoupleDatePlan.id).label("date_plan_count")
    ).group_by(CoupleDatePlan.relationship_id).subquery()

    restaurant_wish_count_sq = db.query(
        CoupleRestaurantWish.relationship_id.label("relationship_id"),
        func.count(CoupleRestaurantWish.id).label("restaurant_wish_count")
    ).group_by(CoupleRestaurantWish.relationship_id).subquery()

    restaurant_item_count_sq = db.query(
        CoupleRestaurantItem.relationship_id.label("relationship_id"),
        func.count(CoupleRestaurantItem.id).label("restaurant_item_count")
    ).group_by(CoupleRestaurantItem.relationship_id).subquery()

    date_draw_count_sq = db.query(
        CoupleDateDraw.relationship_id.label("relationship_id"),
        func.count(CoupleDateDraw.id).label("date_draw_count")
    ).group_by(CoupleDateDraw.relationship_id).subquery()

    query = db.query(
        CoupleRelationship,
        user_a.nickname.label("user_a_nickname"),
        user_a.phone.label("user_a_phone"),
        user_b.nickname.label("user_b_nickname"),
        user_b.phone.label("user_b_phone"),
        func.coalesce(memo_count_sq.c.memo_count, 0).label("memo_count"),
        func.coalesce(anniversary_count_sq.c.anniversary_count, 0).label("anniversary_count"),
        func.coalesce(date_plan_count_sq.c.date_plan_count, 0).label("date_plan_count"),
        func.coalesce(restaurant_wish_count_sq.c.restaurant_wish_count, 0).label("restaurant_wish_count"),
        func.coalesce(restaurant_item_count_sq.c.restaurant_item_count, 0).label("restaurant_item_count"),
        func.coalesce(date_draw_count_sq.c.date_draw_count, 0).label("date_draw_count"),
    ).join(
        user_a, CoupleRelationship.user_a_id == user_a.id
    ).join(
        user_b, CoupleRelationship.user_b_id == user_b.id
    ).outerjoin(
        memo_count_sq, memo_count_sq.c.relationship_id == CoupleRelationship.id
    ).outerjoin(
        anniversary_count_sq, anniversary_count_sq.c.relationship_id == CoupleRelationship.id
    ).outerjoin(
        date_plan_count_sq, date_plan_count_sq.c.relationship_id == CoupleRelationship.id
    ).outerjoin(
        restaurant_wish_count_sq, restaurant_wish_count_sq.c.relationship_id == CoupleRelationship.id
    ).outerjoin(
        restaurant_item_count_sq, restaurant_item_count_sq.c.relationship_id == CoupleRelationship.id
    ).outerjoin(
        date_draw_count_sq, date_draw_count_sq.c.relationship_id == CoupleRelationship.id
    )

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                user_a.nickname.like(keyword),
                user_a.phone.like(keyword),
                user_b.nickname.like(keyword),
                user_b.phone.like(keyword),
            )
        )
    if status:
        query = query.filter(CoupleRelationship.status == status)

    total = query.count()
    rows = query.order_by(CoupleRelationship.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            {
                "id": relationship.id,
                "status": relationship.status,
                "anniversary_date": relationship.anniversary_date.isoformat() if relationship.anniversary_date else None,
                "created_at": _serialize_datetime(relationship.created_at),
                "updated_at": _serialize_datetime(relationship.updated_at),
                "user_a": {
                    "id": relationship.user_a_id,
                    "nickname": user_a_nickname,
                    "phone": user_a_phone,
                },
                "user_b": {
                    "id": relationship.user_b_id,
                    "nickname": user_b_nickname,
                    "phone": user_b_phone,
                },
                "metrics": {
                    "memo_count": memo_count,
                    "anniversary_count": anniversary_count,
                    "date_plan_count": date_plan_count,
                    "restaurant_wish_count": restaurant_wish_count,
                    "restaurant_item_count": restaurant_item_count,
                    "date_draw_count": date_draw_count,
                }
            }
            for (
                relationship,
                user_a_nickname,
                user_a_phone,
                user_b_nickname,
                user_b_phone,
                memo_count,
                anniversary_count,
                date_plan_count,
                restaurant_wish_count,
                restaurant_item_count,
                date_draw_count,
            ) in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/couples/candidates")
async def admin_list_couple_candidates(
    search: Optional[str] = Query(None, description="昵称/手机号/open_id/情侣码搜索"),
    exclude_user_id: Optional[str] = Query(None, description="需要排除的用户ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Search users that can be selected for a manual couple bind action.
    """
    del admin

    query = db.query(User).filter(User.is_deleted == False)

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.nickname.like(keyword),
                User.phone.like(keyword),
                User.open_id.like(keyword),
                User.couple_code.like(keyword),
            )
        )
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)

    total = query.count()
    rows = query.order_by(User.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return paginated_response(
        data=[
            _serialize_admin_couple_candidate(user, get_active_relationship(db, user.id))
            for user in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/couples/bind")
async def admin_bind_couple(
    request: AdminCoupleBindRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Manually create a couple relationship from the admin console.
    """
    user_a_id = request.user_a_id.strip()
    user_b_id = request.user_b_id.strip()

    if user_a_id == user_b_id:
        return error_response(400, "不能把同一个用户绑定成情侣")

    user_a = db.query(User).filter(
        User.id == user_a_id,
        User.is_deleted == False,
    ).first()
    if not user_a:
        return error_response(404, "用户A不存在")

    user_b = db.query(User).filter(
        User.id == user_b_id,
        User.is_deleted == False,
    ).first()
    if not user_b:
        return error_response(404, "用户B不存在")

    relationship_a = get_active_relationship(db, user_a.id)
    if relationship_a:
        partner = get_partner_from_relationship(relationship_a, user_a.id)
        return error_response(
            400,
            f"{user_a.nickname or '用户A'} 已绑定 {partner.nickname or '其他用户'}，请先解绑",
        )

    relationship_b = get_active_relationship(db, user_b.id)
    if relationship_b:
        partner = get_partner_from_relationship(relationship_b, user_b.id)
        return error_response(
            400,
            f"{user_b.nickname or '用户B'} 已绑定 {partner.nickname or '其他用户'}，请先解绑",
        )

    ensure_couple_code(db, user_a)
    ensure_couple_code(db, user_b)

    relationship = CoupleRelationship(
        user_a_id=user_a.id,
        user_b_id=user_b.id,
        anniversary_date=request.anniversary_date or date.today(),
        status="active",
    )
    db.add(relationship)
    db.flush()

    notice_data = {
        "kind": "couple_bind",
        "source": "admin",
        "relationship_id": relationship.id,
    }
    partner_a_name = user_b.nickname or "对方"
    partner_b_name = user_a.nickname or "对方"
    db.add(Notification(
        id=str(uuid.uuid4()),
        user_id=user_a.id,
        type="couple_bind",
        title="情侣关系已建立",
        content=f"后台已为你和 {partner_a_name} 建立情侣关系，如有疑问请联系平台客服",
        data=notice_data,
    ))
    db.add(Notification(
        id=str(uuid.uuid4()),
        user_id=user_b.id,
        type="couple_bind",
        title="情侣关系已建立",
        content=f"后台已为你和 {partner_b_name} 建立情侣关系，如有疑问请联系平台客服",
        data=notice_data,
    ))

    _create_admin_operation_log(
        db,
        admin,
        action_type="bind_couple",
        target_type="couple_relationship",
        target_id=relationship.id,
        summary=f"手动绑定情侣关系 {user_a.nickname or user_a.id} / {user_b.nickname or user_b.id}",
        detail={
            "relationship_id": relationship.id,
            "user_a_id": user_a.id,
            "user_b_id": user_b.id,
            "anniversary_date": relationship.anniversary_date.isoformat() if relationship.anniversary_date else None,
        },
    )
    db.commit()
    db.refresh(relationship)

    return success_response(
        data=_serialize_admin_couple_relationship(relationship),
        message="情侣关系已手动绑定",
    )


@router.post("/couples/{relationship_id}/unbind")
async def admin_unbind_couple(
    relationship_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Manually deactivate an active couple relationship from the admin console.
    """
    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    if relationship.status != "active":
        return error_response(400, "该情侣关系已经解绑")

    operator_name = str(admin.get("display_name") or admin.get("username") or "系统管理员")
    relationship.status = "inactive"

    notice_data = {
        "kind": "couple_unbind",
        "source": "admin",
        "relationship_id": relationship.id,
    }
    db.add(Notification(
        id=str(uuid.uuid4()),
        user_id=relationship.user_a_id,
        type="couple_bind",
        title="情侣关系已解绑",
        content="后台已手动解除你当前的情侣关系，如有疑问请联系平台客服",
        data=notice_data,
    ))
    db.add(Notification(
        id=str(uuid.uuid4()),
        user_id=relationship.user_b_id,
        type="couple_bind",
        title="情侣关系已解绑",
        content="后台已手动解除你当前的情侣关系，如有疑问请联系平台客服",
        data=notice_data,
    ))

    user_a_name = relationship.user_a.nickname if relationship.user_a else relationship.user_a_id
    user_b_name = relationship.user_b.nickname if relationship.user_b else relationship.user_b_id
    _create_admin_operation_log(
        db,
        admin,
        action_type="unbind_couple",
        target_type="couple_relationship",
        target_id=relationship.id,
        summary=f"手动解绑情侣关系 {user_a_name} / {user_b_name}",
        detail={
            "relationship_id": relationship.id,
            "user_a_id": relationship.user_a_id,
            "user_b_id": relationship.user_b_id,
            "operator_name": operator_name,
        },
    )
    db.commit()
    db.refresh(relationship)

    return success_response(
        data={
            "id": relationship.id,
            "status": relationship.status,
            "updated_at": _serialize_datetime(relationship.updated_at),
        },
        message="情侣关系已手动解绑",
    )


@router.get("/couples/{relationship_id}/restaurant")
async def admin_get_couple_restaurant_dashboard(
    relationship_id: str,
    keyword: Optional[str] = Query(None, description="按菜单名/描述/标签搜索"),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Load the shared restaurant menu workspace for one couple relationship.
    """
    del admin

    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    try:
        payload = get_restaurant_dashboard(db, relationship, keyword=keyword)
    except CoupleServiceError as exc:
        return error_response(exc.code, exc.message)

    return success_response(
        data={
            "relationship": _serialize_admin_couple_relationship(relationship),
            "categories": payload["categories"],
            "items": payload["items"],
            "total_categories": len(payload["categories"]),
            "total_items": payload["total_items"],
            "wish_count": payload["wish_count"],
        }
    )


@router.post("/couples/{relationship_id}/restaurant/categories")
async def admin_create_couple_restaurant_category(
    relationship_id: str,
    request: CoupleRestaurantCategoryCreateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Create a couple menu category from the admin console.
    """
    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    actor = _get_couple_actor_user(relationship)
    if not actor:
        return error_response(404, "情侣关系对应用户不存在")

    try:
        category = create_restaurant_category(
            db,
            relationship,
            actor,
            request.name,
            request.image,
            request.sort_order,
        )
    except CoupleServiceError as exc:
        return error_response(exc.code, exc.message)

    _create_admin_operation_log(
        db,
        admin,
        action_type="create_couple_menu_category",
        target_type="couple_menu_category",
        target_id=category.id,
        summary=f"新增情侣菜单分类 {category.name}",
        detail={
            "relationship_id": relationship.id,
            "name": category.name,
            "sort_order": category.sort_order,
        },
    )
    db.commit()

    return success_response(
        data=restaurant_category_to_dict(db, category),
        message="菜单分类已创建",
    )


@router.put("/couples/{relationship_id}/restaurant/categories/{category_id}")
async def admin_update_couple_restaurant_category(
    relationship_id: str,
    category_id: str,
    request: CoupleRestaurantCategoryUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Update a couple menu category from the admin console.
    """
    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    try:
        category = update_restaurant_category(
            db,
            relationship,
            category_id,
            name=request.name,
            image=request.image,
            sort_order=request.sort_order,
            image_provided="image" in request.model_fields_set,
        )
    except CoupleServiceError as exc:
        return error_response(exc.code, exc.message)

    _create_admin_operation_log(
        db,
        admin,
        action_type="update_couple_menu_category",
        target_type="couple_menu_category",
        target_id=category.id,
        summary=f"更新情侣菜单分类 {category.name}",
        detail={
            "relationship_id": relationship.id,
            "name": category.name,
            "image": category.image,
            "sort_order": category.sort_order,
        },
    )
    db.commit()

    return success_response(
        data=restaurant_category_to_dict(db, category),
        message="菜单分类已更新",
    )


@router.delete("/couples/{relationship_id}/restaurant/categories/{category_id}")
async def admin_delete_couple_restaurant_category(
    relationship_id: str,
    category_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Delete a couple menu category from the admin console.
    """
    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    category = db.query(CoupleRestaurantCategory).filter(
        CoupleRestaurantCategory.id == category_id,
        CoupleRestaurantCategory.relationship_id == relationship.id,
    ).first()
    if not category:
        return error_response(404, "菜单分类不存在")

    snapshot = {
        "id": category.id,
        "name": category.name,
        "sort_order": category.sort_order,
    }

    try:
        delete_restaurant_category(db, relationship, category_id)
    except CoupleServiceError as exc:
        return error_response(exc.code, exc.message)

    _create_admin_operation_log(
        db,
        admin,
        action_type="delete_couple_menu_category",
        target_type="couple_menu_category",
        target_id=snapshot["id"],
        summary=f"删除情侣菜单分类 {snapshot['name']}",
        detail={
            "relationship_id": relationship.id,
            "name": snapshot["name"],
            "sort_order": snapshot["sort_order"],
        },
    )
    db.commit()

    return success_response(message="菜单分类已删除")


@router.post("/couples/{relationship_id}/restaurant/items")
async def admin_create_couple_restaurant_item(
    relationship_id: str,
    request: CoupleRestaurantItemCreateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Create a couple menu item from the admin console.
    """
    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    actor = _get_couple_actor_user(relationship)
    if not actor:
        return error_response(404, "情侣关系对应用户不存在")

    try:
        item = create_restaurant_item(
            db,
            relationship,
            actor,
            request.category_id,
            request.name,
            request.price,
            request.images,
            request.tags,
            request.description,
        )
    except CoupleServiceError as exc:
        return error_response(exc.code, exc.message)

    _create_admin_operation_log(
        db,
        admin,
        action_type="create_couple_menu_item",
        target_type="couple_menu_item",
        target_id=item.id,
        summary=f"新增情侣菜单 {item.name}",
        detail={
            "relationship_id": relationship.id,
            "category_id": item.category_id,
            "name": item.name,
            "price": _serialize_decimal(item.price),
        },
    )
    db.commit()

    return success_response(
        data=restaurant_item_to_dict(item),
        message="菜单已创建",
    )


@router.put("/couples/{relationship_id}/restaurant/items/{item_id}")
async def admin_update_couple_restaurant_item(
    relationship_id: str,
    item_id: str,
    request: CoupleRestaurantItemUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Update a couple menu item from the admin console.
    """
    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    try:
        item = update_restaurant_item(
            db,
            relationship,
            item_id,
            category_id=request.category_id,
            name=request.name,
            price=request.price,
            images=request.images,
            tags=request.tags,
            description=request.description,
            description_provided="description" in request.model_fields_set,
            images_provided="images" in request.model_fields_set,
            tags_provided="tags" in request.model_fields_set,
        )
    except CoupleServiceError as exc:
        return error_response(exc.code, exc.message)

    _create_admin_operation_log(
        db,
        admin,
        action_type="update_couple_menu_item",
        target_type="couple_menu_item",
        target_id=item.id,
        summary=f"更新情侣菜单 {item.name}",
        detail={
            "relationship_id": relationship.id,
            "category_id": item.category_id,
            "name": item.name,
            "price": _serialize_decimal(item.price),
            "images_count": len(item.images or []),
            "tags": item.tags or [],
        },
    )
    db.commit()

    return success_response(
        data=restaurant_item_to_dict(item),
        message="菜单已更新",
    )


@router.delete("/couples/{relationship_id}/restaurant/items/{item_id}")
async def admin_delete_couple_restaurant_item(
    relationship_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """
    Delete a couple menu item from the admin console.
    """
    relationship = _get_couple_relationship_or_none(db, relationship_id)
    if not relationship:
        return error_response(404, "情侣关系不存在")

    item = db.query(CoupleRestaurantItem).filter(
        CoupleRestaurantItem.id == item_id,
        CoupleRestaurantItem.relationship_id == relationship.id,
    ).first()
    if not item:
        return error_response(404, "菜单不存在")

    snapshot = {
        "id": item.id,
        "category_id": item.category_id,
        "name": item.name,
        "price": _serialize_decimal(item.price),
    }

    try:
        delete_restaurant_item(db, relationship, item_id)
    except CoupleServiceError as exc:
        return error_response(exc.code, exc.message)

    _create_admin_operation_log(
        db,
        admin,
        action_type="delete_couple_menu_item",
        target_type="couple_menu_item",
        target_id=snapshot["id"],
        summary=f"删除情侣菜单 {snapshot['name']}",
        detail={
            "relationship_id": relationship.id,
            "category_id": snapshot["category_id"],
            "price": snapshot["price"],
        },
    )
    db.commit()

    return success_response(message="菜单已删除")
