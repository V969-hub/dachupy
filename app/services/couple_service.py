"""
Service layer for the couple memo MVP.
"""
import calendar
import random
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session

from app.models.couple import (
    CoupleRelationship,
    CoupleMemo,
    CoupleAnniversary,
    CoupleDatePlan,
    CoupleRestaurantCategory,
    CoupleRestaurantItem,
    CoupleRestaurantCartItem,
    CoupleRestaurantWish,
    CoupleDateDraw,
)
from app.models.order import Order
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import create_notification
from app.utils.security import generate_binding_code


MEMO_CATEGORIES = {"日常", "约会", "纪念日", "礼物", "其他"}
ANNIVERSARY_TYPES = {"恋爱纪念日", "生日", "节日", "自定义"}
DATE_PLAN_STATUSES = {"planned", "completed", "cancelled"}
WISH_STATUSES = {"active", "done", "archived"}
DATE_DRAW_STATUSES = {"drawn", "accepted", "completed", "cancelled"}
DATE_DRAW_SOURCES = {"mixed", "wishes", "restaurant", "anniversaries"}
RESTAURANT_RECOMMENDATION_SOURCES = {"mixed", "restaurant", "wishes"}
MAX_RESTAURANT_IMAGES = 9
MAX_RESTAURANT_TAGS = 8


class CoupleServiceError(Exception):
    """情侣模块业务异常。"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def _today() -> date:
    return date.today()


def _current_time() -> datetime:
    return datetime.now()


def _generate_unique_couple_code(db: Session) -> str:
    code = generate_binding_code()
    while db.query(User).filter(User.couple_code == code).first():
        code = generate_binding_code()
    return code


def ensure_couple_code(db: Session, user: User) -> str:
    """Ensure a user always has a couple code before rendering the feature."""
    if user.couple_code:
        return user.couple_code

    user.couple_code = _generate_unique_couple_code(db)
    db.commit()
    db.refresh(user)
    return user.couple_code


def get_active_relationship(db: Session, user_id: str) -> Optional[CoupleRelationship]:
    return db.query(CoupleRelationship).filter(
        CoupleRelationship.status == "active",
        or_(
            CoupleRelationship.user_a_id == user_id,
            CoupleRelationship.user_b_id == user_id
        )
    ).first()


def list_active_relationships(db: Session) -> list[CoupleRelationship]:
    return db.query(CoupleRelationship).filter(
        CoupleRelationship.status == "active"
    ).all()


def get_partner_from_relationship(relationship: CoupleRelationship, user_id: str) -> Optional[User]:
    if relationship.user_a_id == user_id:
        return relationship.user_b
    if relationship.user_b_id == user_id:
        return relationship.user_a
    return None


def _partner_to_dict(user: Optional[User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar": user.avatar
    }


def _calculate_love_days(anniversary_date: Optional[date]) -> int:
    if not anniversary_date:
        return 0
    delta = _today() - anniversary_date
    return max(delta.days + 1, 0)


def _format_short_datetime(value: Optional[datetime]) -> str:
    if not value:
        return "暂未设置时间"
    return value.strftime("%m月%d日 %H:%M")


def _format_short_date(value: Optional[date]) -> str:
    if not value:
        return "暂未设置日期"
    return value.strftime("%Y年%m月%d日")


def _normalize_title(title: str, title_type: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise CoupleServiceError(f"请输入{title_type}标题")
    return normalized_title


def _date_with_safe_year(source_date: date, year: int) -> date:
    last_day = calendar.monthrange(year, source_date.month)[1]
    return source_date.replace(year=year, day=min(source_date.day, last_day))


def _next_anniversary_occurrence(source_date: date) -> date:
    today = _today()
    this_year = _date_with_safe_year(source_date, today.year)
    if this_year >= today:
        return this_year
    return _date_with_safe_year(source_date, today.year + 1)


def anniversary_to_dict(anniversary: CoupleAnniversary) -> dict:
    next_occurrence = _next_anniversary_occurrence(anniversary.date)
    days_left = (next_occurrence - _today()).days
    return {
        "id": anniversary.id,
        "relationship_id": anniversary.relationship_id,
        "title": anniversary.title,
        "date": anniversary.date.isoformat(),
        "type": anniversary.type,
        "remind_days_before": anniversary.remind_days_before,
        "note": anniversary.note,
        "days_left": days_left,
        "created_at": anniversary.created_at.isoformat() if anniversary.created_at else None,
        "updated_at": anniversary.updated_at.isoformat() if anniversary.updated_at else None,
    }


def memo_to_dict(memo: CoupleMemo) -> dict:
    return {
        "id": memo.id,
        "relationship_id": memo.relationship_id,
        "title": memo.title,
        "content": memo.content,
        "category": memo.category,
        "remind_at": memo.remind_at.isoformat() if memo.remind_at else None,
        "is_completed": memo.is_completed,
        "is_pinned": memo.is_pinned,
        "created_by": memo.created_by,
        "created_at": memo.created_at.isoformat() if memo.created_at else None,
        "updated_at": memo.updated_at.isoformat() if memo.updated_at else None,
    }


def date_plan_to_dict(plan: CoupleDatePlan) -> dict:
    return {
        "id": plan.id,
        "relationship_id": plan.relationship_id,
        "title": plan.title,
        "plan_at": plan.plan_at.isoformat() if plan.plan_at else None,
        "location": plan.location,
        "note": plan.note,
        "anniversary_id": plan.anniversary_id,
        "order_id": plan.order_id,
        "menu_items": plan.menu_items or [],
        "menu_total": float(plan.menu_total or 0),
        "status": plan.status,
        "created_by": plan.created_by,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "anniversary_title": plan.anniversary.title if plan.anniversary else None,
        "order_no": plan.order.order_no if plan.order else None,
    }


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_price(price: float | Decimal) -> Decimal:
    normalized = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized < 0:
        raise CoupleServiceError("金额不能小于 0")
    return normalized


def _normalize_date_plan_menu_items(menu_items: Optional[list[dict]]) -> tuple[list[dict], Decimal]:
    if not menu_items:
        return [], Decimal("0.00")

    normalized_items: list[dict] = []
    total = Decimal("0.00")
    for raw_item in menu_items:
        item_id = str(raw_item.get("item_id") or raw_item.get("id") or "").strip()
        name = str(raw_item.get("name") or "").strip()
        if not item_id or not name:
            raise CoupleServiceError("约饭菜单信息不完整")

        price = _normalize_price(raw_item.get("price", 0))
        quantity = int(raw_item.get("quantity") or 1)
        if quantity <= 0 or quantity > 99:
            raise CoupleServiceError("菜单数量必须在 1 到 99 之间")

        subtotal = (price * Decimal(quantity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        normalized_items.append({
            "item_id": item_id,
            "name": name[:100],
            "price": float(price),
            "quantity": quantity,
            "subtotal": float(subtotal),
            "cover_image": _normalize_optional_text(raw_item.get("cover_image")),
            "category_name": _normalize_optional_text(raw_item.get("category_name")),
        })
        total += subtotal

    return normalized_items, total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_images(images: list[str]) -> list[str]:
    normalized_images = [image.strip() for image in images if isinstance(image, str) and image.strip()]
    if not normalized_images:
        raise CoupleServiceError("请至少上传一张图片")
    if len(normalized_images) > MAX_RESTAURANT_IMAGES:
        raise CoupleServiceError(f"最多上传 {MAX_RESTAURANT_IMAGES} 张图片")
    return normalized_images


def _normalize_tags(tags: Optional[list[str]]) -> list[str]:
    if not tags:
        return []

    normalized_tags: list[str] = []
    seen_tags = set()
    for raw_tag in tags:
        if not isinstance(raw_tag, str):
            continue
        tag = raw_tag.strip()
        if not tag or tag in seen_tags:
            continue
        normalized_tags.append(tag[:16])
        seen_tags.add(tag)
        if len(normalized_tags) >= MAX_RESTAURANT_TAGS:
            break

    return normalized_tags


def _get_category_or_raise(db: Session, relationship_id: str, category_id: str) -> CoupleRestaurantCategory:
    category = db.query(CoupleRestaurantCategory).filter(
        CoupleRestaurantCategory.id == category_id,
        CoupleRestaurantCategory.relationship_id == relationship_id
    ).first()
    if not category:
        raise CoupleServiceError("菜单分类不存在", code=404)
    return category


def _get_restaurant_item_or_raise(db: Session, relationship_id: str, item_id: str) -> CoupleRestaurantItem:
    item = db.query(CoupleRestaurantItem).filter(
        CoupleRestaurantItem.id == item_id,
        CoupleRestaurantItem.relationship_id == relationship_id
    ).first()
    if not item:
        raise CoupleServiceError("菜单不存在", code=404)
    return item


def _get_restaurant_wish_or_raise(db: Session, relationship_id: str, wish_id: str) -> CoupleRestaurantWish:
    wish = db.query(CoupleRestaurantWish).filter(
        CoupleRestaurantWish.id == wish_id,
        CoupleRestaurantWish.relationship_id == relationship_id
    ).first()
    if not wish:
        raise CoupleServiceError("想吃清单记录不存在", code=404)
    return wish


def _get_restaurant_wish_by_item(
    db: Session,
    relationship_id: str,
    item_id: str
) -> Optional[CoupleRestaurantWish]:
    return db.query(CoupleRestaurantWish).filter(
        CoupleRestaurantWish.relationship_id == relationship_id,
        CoupleRestaurantWish.item_id == item_id
    ).first()


def _get_date_draw_or_raise(db: Session, relationship_id: str, draw_id: str) -> CoupleDateDraw:
    draw = db.query(CoupleDateDraw).filter(
        CoupleDateDraw.id == draw_id,
        CoupleDateDraw.relationship_id == relationship_id
    ).first()
    if not draw:
        raise CoupleServiceError("抽卡记录不存在", code=404)
    return draw


def restaurant_category_to_dict(db: Session, category: CoupleRestaurantCategory) -> dict:
    item_count = db.query(CoupleRestaurantItem).filter(
        CoupleRestaurantItem.relationship_id == category.relationship_id,
        CoupleRestaurantItem.category_id == category.id
    ).count()
    return {
        "id": category.id,
        "relationship_id": category.relationship_id,
        "name": category.name,
        "image": category.image,
        "sort_order": category.sort_order,
        "item_count": item_count,
        "created_by": category.created_by,
        "created_at": category.created_at.isoformat() if category.created_at else None,
        "updated_at": category.updated_at.isoformat() if category.updated_at else None,
    }


def restaurant_item_to_dict(item: CoupleRestaurantItem) -> dict:
    images = item.images or []
    return {
        "id": item.id,
        "relationship_id": item.relationship_id,
        "category_id": item.category_id,
        "category_name": item.category.name if item.category else None,
        "name": item.name,
        "price": float(item.price or 0),
        "images": images,
        "cover_image": images[0] if images else None,
        "tags": item.tags or [],
        "description": item.description,
        "created_by": item.created_by,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def restaurant_cart_item_to_dict(cart_item: CoupleRestaurantCartItem) -> dict:
    item_data = restaurant_item_to_dict(cart_item.item)
    subtotal = _normalize_price(item_data["price"]) * Decimal(cart_item.quantity)
    return {
        "id": cart_item.id,
        "relationship_id": cart_item.relationship_id,
        "item_id": cart_item.item_id,
        "quantity": cart_item.quantity,
        "item": item_data,
        "subtotal": float(subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "created_by": cart_item.created_by,
        "created_at": cart_item.created_at.isoformat() if cart_item.created_at else None,
        "updated_at": cart_item.updated_at.isoformat() if cart_item.updated_at else None,
    }


def restaurant_wish_to_dict(wish: CoupleRestaurantWish) -> dict:
    item_data = restaurant_item_to_dict(wish.item) if wish.item else None
    return {
        "id": wish.id,
        "relationship_id": wish.relationship_id,
        "item_id": wish.item_id,
        "note": wish.note,
        "priority": wish.priority,
        "status": wish.status,
        "created_by": wish.created_by,
        "created_at": wish.created_at.isoformat() if wish.created_at else None,
        "updated_at": wish.updated_at.isoformat() if wish.updated_at else None,
        "item": item_data,
    }


def date_draw_to_dict(draw: CoupleDateDraw) -> dict:
    return {
        "id": draw.id,
        "relationship_id": draw.relationship_id,
        "title": draw.title,
        "subtitle": draw.subtitle,
        "card_type": draw.card_type,
        "source_item_id": draw.source_item_id,
        "source_item_type": draw.source_item_type,
        "content": draw.content,
        "payload": draw.payload or {},
        "plan_id": draw.plan_id,
        "status": draw.status,
        "created_by": draw.created_by,
        "created_at": draw.created_at.isoformat() if draw.created_at else None,
        "updated_at": draw.updated_at.isoformat() if draw.updated_at else None,
    }


def _notify_partner_date_draw_event(
    db: Session,
    relationship: CoupleRelationship,
    actor: User,
    draw: CoupleDateDraw,
    action: str,
) -> None:
    partner = get_partner_from_relationship(relationship, actor.id)
    if not partner:
        return

    actor_name = actor.nickname or "对方"
    title = "约会抽卡有更新"
    content = f"{actor_name} 更新了“{draw.title}”"

    if action == "drawn":
        title = "抽到一张约会卡"
        content = f"{actor_name} 抽到了“{draw.title}”"
        if draw.subtitle:
            content = f"{content}，{draw.subtitle}"
    elif action == "accepted":
        title = "约会卡已接受"
        content = f"{actor_name} 接受了“{draw.title}”"
        if draw.plan_id:
            content = f"{content}，并生成了新的约饭计划"
    elif action == "completed":
        title = "约会卡已完成"
        content = f"{actor_name} 已完成“{draw.title}”"
    elif action == "cancelled":
        title = "约会卡先放一放"
        content = f"{actor_name} 暂时取消了“{draw.title}”"
    elif action == "restored":
        title = "约会卡重新开启"
        content = f"{actor_name} 重新开启了“{draw.title}”"

    create_notification(
        db=db,
        user_id=partner.id,
        notification_type="couple_date_draw",
        title=title,
        content=content,
        data={
            "kind": "couple_date_draw",
            "action": action,
            "draw_id": draw.id,
            "draw_title": draw.title,
            "draw_status": draw.status,
            "card_type": draw.card_type,
            "plan_id": draw.plan_id,
            "actor_id": actor.id,
            "actor_name": actor_name,
        }
    )


def get_couple_profile(db: Session, user: User) -> dict:
    couple_code = ensure_couple_code(db, user)
    relationship = get_active_relationship(db, user.id)
    partner = get_partner_from_relationship(relationship, user.id) if relationship else None

    return {
        "couple_code": couple_code,
        "is_bound": relationship is not None,
        "relationship_id": relationship.id if relationship else None,
        "anniversary_date": relationship.anniversary_date.isoformat() if relationship and relationship.anniversary_date else None,
        "love_days": _calculate_love_days(relationship.anniversary_date if relationship else None),
        "partner": _partner_to_dict(partner),
    }


def refresh_couple_code(db: Session, user: User) -> str:
    user.couple_code = _generate_unique_couple_code(db)
    db.commit()
    db.refresh(user)
    return user.couple_code


def bind_couple(
    db: Session,
    current_user: User,
    partner_code: str,
    anniversary_date: Optional[date]
) -> CoupleRelationship:
    ensure_couple_code(db, current_user)

    normalized_code = partner_code.strip().upper()
    if not normalized_code:
        raise CoupleServiceError("请输入邀请码")

    partner = db.query(User).filter(
        User.couple_code == normalized_code,
        User.is_deleted == False
    ).first()
    if not partner:
        raise CoupleServiceError("情侣邀请码不存在", code=404)
    if partner.id == current_user.id:
        raise CoupleServiceError("不能绑定自己")
    if get_active_relationship(db, current_user.id):
        raise CoupleServiceError("你已经绑定了情侣")
    if get_active_relationship(db, partner.id):
        raise CoupleServiceError("对方已经绑定了情侣")

    relationship = CoupleRelationship(
        user_a_id=current_user.id,
        user_b_id=partner.id,
        anniversary_date=anniversary_date or _today(),
        status="active"
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)

    create_notification(
        db=db,
        user_id=current_user.id,
        notification_type="couple_bind",
        title="情侣绑定成功",
        content=f"你已与 {partner.nickname or '对方'} 建立情侣关系",
        data={"kind": "couple_bind", "relationship_id": relationship.id}
    )
    create_notification(
        db=db,
        user_id=partner.id,
        notification_type="couple_bind",
        title="新的情侣绑定",
        content=f"{current_user.nickname or '对方'} 已与你建立情侣关系",
        data={"kind": "couple_bind", "relationship_id": relationship.id}
    )

    return relationship


def unbind_couple(db: Session, current_user: User) -> None:
    relationship = get_active_relationship(db, current_user.id)
    if not relationship:
        raise CoupleServiceError("当前没有已绑定的情侣关系", code=404)

    partner = get_partner_from_relationship(relationship, current_user.id)
    relationship.status = "inactive"
    db.commit()

    create_notification(
        db=db,
        user_id=current_user.id,
        notification_type="couple_bind",
        title="情侣关系已解绑",
        content="你已结束当前情侣关系",
        data={"kind": "couple_unbind"}
    )
    if partner:
        create_notification(
            db=db,
            user_id=partner.id,
            notification_type="couple_bind",
            title="情侣关系已解绑",
            content=f"{current_user.nickname or '对方'} 已结束当前情侣关系",
            data={"kind": "couple_unbind"}
        )


def require_relationship(db: Session, user: User) -> CoupleRelationship:
    relationship = get_active_relationship(db, user.id)
    if not relationship:
        raise CoupleServiceError("请先绑定情侣")
    return relationship


def _get_memo_or_raise(db: Session, relationship_id: str, memo_id: str) -> CoupleMemo:
    memo = db.query(CoupleMemo).filter(
        CoupleMemo.id == memo_id,
        CoupleMemo.relationship_id == relationship_id
    ).first()
    if not memo:
        raise CoupleServiceError("备忘录不存在", code=404)
    return memo


def _get_anniversary_or_raise(db: Session, relationship_id: str, anniversary_id: str) -> CoupleAnniversary:
    anniversary = db.query(CoupleAnniversary).filter(
        CoupleAnniversary.id == anniversary_id,
        CoupleAnniversary.relationship_id == relationship_id
    ).first()
    if not anniversary:
        raise CoupleServiceError("纪念日不存在", code=404)
    return anniversary


def _get_date_plan_or_raise(db: Session, relationship_id: str, plan_id: str) -> CoupleDatePlan:
    plan = db.query(CoupleDatePlan).filter(
        CoupleDatePlan.id == plan_id,
        CoupleDatePlan.relationship_id == relationship_id
    ).first()
    if not plan:
        raise CoupleServiceError("约饭计划不存在", code=404)
    return plan


def _validate_anniversary_link(db: Session, relationship: CoupleRelationship, anniversary_id: Optional[str]) -> None:
    if not anniversary_id:
        return
    _get_anniversary_or_raise(db, relationship.id, anniversary_id)


def _validate_order_link(db: Session, relationship: CoupleRelationship, order_id: Optional[str]) -> None:
    if not order_id:
        return

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise CoupleServiceError("关联订单不存在", code=404)
    if order.foodie_id not in {relationship.user_a_id, relationship.user_b_id}:
        raise CoupleServiceError("只能关联情侣双方创建的订单", code=403)


def list_memos(db: Session, relationship: CoupleRelationship, status_filter: Optional[str] = None) -> list[CoupleMemo]:
    query = db.query(CoupleMemo).filter(CoupleMemo.relationship_id == relationship.id)

    if status_filter == "completed":
        query = query.filter(CoupleMemo.is_completed == True)
    elif status_filter == "pending":
        query = query.filter(CoupleMemo.is_completed == False)
    elif status_filter == "pinned":
        query = query.filter(CoupleMemo.is_pinned == True)

    return query.order_by(
        desc(CoupleMemo.is_pinned),
        asc(CoupleMemo.is_completed),
        asc(CoupleMemo.remind_at),
        desc(CoupleMemo.updated_at)
    ).all()


def _notify_partner_memo_event(
    db: Session,
    relationship: CoupleRelationship,
    actor: User,
    memo: CoupleMemo,
    action: str,
) -> None:
    partner = get_partner_from_relationship(relationship, actor.id)
    if not partner:
        return

    actor_name = actor.nickname or "对方"
    title = "情侣备忘录更新"
    content = f"{actor_name} 更新了“{memo.title}”"

    if action == "created":
        title = "新的情侣备忘录"
        content = f"{actor_name} 新建了“{memo.title}”"
        if memo.remind_at:
            content = f"{content}，提醒时间是 {_format_short_datetime(memo.remind_at)}"
    elif action == "updated":
        title = "情侣备忘录有更新"
        content = f"{actor_name} 更新了“{memo.title}”"
    elif action == "completed":
        title = "情侣备忘录已完成"
        content = f"{actor_name} 已完成“{memo.title}”"
    elif action == "restored":
        title = "情侣备忘录重新开启"
        content = f"{actor_name} 重新把“{memo.title}”设为待处理"
    elif action == "deleted":
        title = "情侣备忘录已删除"
        content = f"{actor_name} 删除了“{memo.title}”"

    create_notification(
        db=db,
        user_id=partner.id,
        notification_type="couple_memo",
        title=title,
        content=content,
        data={
            "kind": "couple_memo",
            "action": action,
            "memo_id": memo.id,
            "memo_title": memo.title,
            "category": memo.category,
            "is_completed": memo.is_completed,
            "actor_id": actor.id,
            "actor_name": actor_name,
        }
    )


def create_memo(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    title: str,
    content: Optional[str],
    category: str,
    remind_at: Optional[datetime],
    is_pinned: bool
) -> CoupleMemo:
    if category not in MEMO_CATEGORIES:
        raise CoupleServiceError("无效的备忘录分类")
    normalized_title = _normalize_title(title, "备忘录")

    memo = CoupleMemo(
        relationship_id=relationship.id,
        title=normalized_title,
        content=content,
        category=category,
        remind_at=remind_at,
        is_pinned=is_pinned,
        created_by=current_user.id
    )
    db.add(memo)
    db.commit()
    db.refresh(memo)
    _notify_partner_memo_event(db, relationship, current_user, memo, "created")
    return memo


def update_memo(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    memo_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
    remind_at: Optional[datetime] = None,
    is_pinned: Optional[bool] = None,
    remind_at_provided: bool = False,
) -> CoupleMemo:
    memo = _get_memo_or_raise(db, relationship.id, memo_id)
    has_changes = False

    if title is not None:
        normalized_title = _normalize_title(title, "备忘录")
        if memo.title != normalized_title:
            memo.title = normalized_title
            has_changes = True
    if content is not None:
        if memo.content != content:
            memo.content = content
            has_changes = True
    if category is not None:
        if category not in MEMO_CATEGORIES:
            raise CoupleServiceError("无效的备忘录分类")
        if memo.category != category:
            memo.category = category
            has_changes = True
    if remind_at_provided:
        if memo.remind_at != remind_at:
            memo.remind_at = remind_at
            has_changes = True
    if is_pinned is not None:
        if memo.is_pinned != is_pinned:
            memo.is_pinned = is_pinned
            has_changes = True

    db.commit()
    db.refresh(memo)
    if has_changes:
        _notify_partner_memo_event(db, relationship, current_user, memo, "updated")
    return memo


def update_memo_status(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    memo_id: str,
    is_completed: bool
) -> CoupleMemo:
    memo = _get_memo_or_raise(db, relationship.id, memo_id)
    if memo.is_completed == is_completed:
        return memo
    memo.is_completed = is_completed
    db.commit()
    db.refresh(memo)
    _notify_partner_memo_event(
        db,
        relationship,
        current_user,
        memo,
        "completed" if is_completed else "restored",
    )
    return memo


def delete_memo(db: Session, relationship: CoupleRelationship, current_user: User, memo_id: str) -> None:
    memo = _get_memo_or_raise(db, relationship.id, memo_id)
    memo_snapshot = CoupleMemo(
        id=memo.id,
        title=memo.title,
        category=memo.category,
        is_completed=memo.is_completed,
    )
    db.delete(memo)
    db.commit()
    _notify_partner_memo_event(db, relationship, current_user, memo_snapshot, "deleted")


def get_memo_detail(db: Session, relationship: CoupleRelationship, memo_id: str) -> CoupleMemo:
    return _get_memo_or_raise(db, relationship.id, memo_id)


def list_anniversaries(db: Session, relationship: CoupleRelationship) -> list[CoupleAnniversary]:
    return db.query(CoupleAnniversary).filter(
        CoupleAnniversary.relationship_id == relationship.id
    ).order_by(asc(CoupleAnniversary.date)).all()


def _notify_partner_anniversary_event(
    db: Session,
    relationship: CoupleRelationship,
    actor: User,
    anniversary: CoupleAnniversary,
    action: str,
) -> None:
    partner = get_partner_from_relationship(relationship, actor.id)
    if not partner:
        return

    actor_name = actor.nickname or "对方"
    title = "纪念日有更新"
    content = f"{actor_name} 更新了“{anniversary.title}”"

    if action == "created":
        title = "新的纪念日"
        content = f"{actor_name} 新增了“{anniversary.title}”，日期是 {_format_short_date(anniversary.date)}"
    elif action == "updated":
        title = "纪念日安排已更新"
        content = f"{actor_name} 更新了“{anniversary.title}”，当前日期是 {_format_short_date(anniversary.date)}"
    elif action == "deleted":
        title = "纪念日已删除"
        content = f"{actor_name} 删除了“{anniversary.title}”"

    create_notification(
        db=db,
        user_id=partner.id,
        notification_type="couple_anniversary",
        title=title,
        content=content,
        data={
            "kind": "couple_anniversary",
            "action": action,
            "anniversary_id": anniversary.id,
            "anniversary_title": anniversary.title,
            "anniversary_type": anniversary.type,
            "actor_id": actor.id,
            "actor_name": actor_name,
        }
    )


def create_anniversary(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    title: str,
    target_date: date,
    anniversary_type: str,
    remind_days_before: int,
    note: Optional[str]
) -> CoupleAnniversary:
    if anniversary_type not in ANNIVERSARY_TYPES:
        raise CoupleServiceError("无效的纪念日类型")
    normalized_title = _normalize_title(title, "纪念日")

    anniversary = CoupleAnniversary(
        relationship_id=relationship.id,
        title=normalized_title,
        date=target_date,
        type=anniversary_type,
        remind_days_before=remind_days_before,
        note=note
    )
    db.add(anniversary)
    db.commit()
    db.refresh(anniversary)
    _notify_partner_anniversary_event(db, relationship, current_user, anniversary, "created")
    return anniversary


def update_anniversary(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    anniversary_id: str,
    title: Optional[str] = None,
    target_date: Optional[date] = None,
    anniversary_type: Optional[str] = None,
    remind_days_before: Optional[int] = None,
    note: Optional[str] = None,
    note_provided: bool = False,
) -> CoupleAnniversary:
    anniversary = _get_anniversary_or_raise(db, relationship.id, anniversary_id)
    has_changes = False

    if title is not None:
        normalized_title = _normalize_title(title, "纪念日")
        if anniversary.title != normalized_title:
            anniversary.title = normalized_title
            has_changes = True
    if target_date is not None:
        if anniversary.date != target_date:
            anniversary.date = target_date
            has_changes = True
    if anniversary_type is not None:
        if anniversary_type not in ANNIVERSARY_TYPES:
            raise CoupleServiceError("无效的纪念日类型")
        if anniversary.type != anniversary_type:
            anniversary.type = anniversary_type
            has_changes = True
    if remind_days_before is not None:
        if anniversary.remind_days_before != remind_days_before:
            anniversary.remind_days_before = remind_days_before
            has_changes = True
    if note_provided:
        if anniversary.note != note:
            anniversary.note = note
            has_changes = True

    db.commit()
    db.refresh(anniversary)
    if has_changes:
        _notify_partner_anniversary_event(db, relationship, current_user, anniversary, "updated")
    return anniversary


def delete_anniversary(db: Session, relationship: CoupleRelationship, current_user: User, anniversary_id: str) -> None:
    anniversary = _get_anniversary_or_raise(db, relationship.id, anniversary_id)
    anniversary_snapshot = CoupleAnniversary(
        id=anniversary.id,
        title=anniversary.title,
        date=anniversary.date,
        type=anniversary.type,
    )
    db.delete(anniversary)
    db.commit()
    _notify_partner_anniversary_event(db, relationship, current_user, anniversary_snapshot, "deleted")


def list_date_plans(
    db: Session,
    relationship: CoupleRelationship,
    status_filter: Optional[str] = None
) -> list[CoupleDatePlan]:
    query = db.query(CoupleDatePlan).filter(CoupleDatePlan.relationship_id == relationship.id)

    if status_filter and status_filter != "all":
        if status_filter not in DATE_PLAN_STATUSES:
            raise CoupleServiceError("无效的约饭计划状态")
        query = query.filter(CoupleDatePlan.status == status_filter)

    return query.order_by(
        asc(CoupleDatePlan.plan_at),
        desc(CoupleDatePlan.updated_at)
    ).all()


def _format_date_plan_schedule(plan_at: datetime, location: Optional[str]) -> str:
    schedule = plan_at.strftime("%m月%d日 %H:%M")
    if location:
        return f"{schedule} · {location}"
    return schedule


def _notify_partner_date_plan_event(
    db: Session,
    relationship: CoupleRelationship,
    actor: User,
    plan_id: str,
    plan_title: str,
    plan_at: datetime,
    location: Optional[str],
    status: str,
    action: str,
) -> None:
    partner = get_partner_from_relationship(relationship, actor.id)
    if not partner:
        return

    actor_name = actor.nickname or "对方"
    schedule = _format_date_plan_schedule(plan_at, location)

    title = "约饭计划更新"
    content = f"{actor_name} 更新了“{plan_title}”"

    if action == "created":
        title = "新的约饭计划"
        content = f"{actor_name} 新建了“{plan_title}”，安排在 {schedule}"
    elif action == "updated":
        title = "约饭计划有新变动"
        content = f"{actor_name} 更新了“{plan_title}”，当前安排在 {schedule}"
    elif action == "completed":
        title = "约饭计划已完成"
        content = f"{actor_name} 已将“{plan_title}”标记为已完成"
    elif action == "restored":
        title = "约饭计划已恢复"
        content = f"{actor_name} 重新开启了“{plan_title}”，当前安排在 {schedule}"
    elif action == "cancelled":
        title = "约饭计划已取消"
        content = f"{actor_name} 取消了“{plan_title}”"
    elif action == "deleted":
        title = "约饭计划已删除"
        content = f"{actor_name} 删除了“{plan_title}”"

    create_notification(
        db=db,
        user_id=partner.id,
        notification_type="couple_date_plan",
        title=title,
        content=content,
        data={
            "kind": "couple_date_plan",
            "action": action,
            "plan_id": plan_id,
            "plan_title": plan_title,
            "status": status,
            "actor_id": actor.id,
            "actor_name": actor_name,
        }
    )


def create_date_plan(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    title: str,
    plan_at: datetime,
    location: Optional[str],
    note: Optional[str],
    anniversary_id: Optional[str],
    order_id: Optional[str],
    menu_items: Optional[list[dict]] = None,
    notify_partner: bool = True,
) -> CoupleDatePlan:
    normalized_title = _normalize_title(title, "约饭计划")
    _validate_anniversary_link(db, relationship, anniversary_id)
    _validate_order_link(db, relationship, order_id)
    normalized_menu_items, menu_total = _normalize_date_plan_menu_items(menu_items)

    plan = CoupleDatePlan(
        relationship_id=relationship.id,
        title=normalized_title,
        plan_at=plan_at,
        location=location,
        note=note,
        anniversary_id=anniversary_id,
        order_id=order_id,
        menu_items=normalized_menu_items,
        menu_total=menu_total,
        created_by=current_user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    if notify_partner:
        _notify_partner_date_plan_event(
            db,
            relationship,
            current_user,
            plan.id,
            plan.title,
            plan.plan_at,
            plan.location,
            plan.status,
            "created",
        )
    return plan


def update_date_plan(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    plan_id: str,
    title: Optional[str] = None,
    plan_at: Optional[datetime] = None,
    location: Optional[str] = None,
    note: Optional[str] = None,
    anniversary_id: Optional[str] = None,
    order_id: Optional[str] = None,
    menu_items: Optional[list[dict]] = None,
    location_provided: bool = False,
    note_provided: bool = False,
    anniversary_id_provided: bool = False,
    order_id_provided: bool = False,
    menu_items_provided: bool = False,
) -> CoupleDatePlan:
    plan = _get_date_plan_or_raise(db, relationship.id, plan_id)
    has_changes = False

    if title is not None:
        normalized_title = _normalize_title(title, "约饭计划")
        if plan.title != normalized_title:
            plan.title = normalized_title
            has_changes = True
    if plan_at is not None:
        if plan.plan_at != plan_at:
            plan.plan_at = plan_at
            has_changes = True
    if location_provided:
        if plan.location != location:
            plan.location = location
            has_changes = True
    if note_provided:
        if plan.note != note:
            plan.note = note
            has_changes = True
    if anniversary_id_provided:
        _validate_anniversary_link(db, relationship, anniversary_id)
        if plan.anniversary_id != anniversary_id:
            plan.anniversary_id = anniversary_id
            has_changes = True
    if order_id_provided:
        _validate_order_link(db, relationship, order_id)
        if plan.order_id != order_id:
            plan.order_id = order_id
            has_changes = True
    if menu_items_provided:
        normalized_menu_items, menu_total = _normalize_date_plan_menu_items(menu_items)
        if plan.menu_items != normalized_menu_items:
            plan.menu_items = normalized_menu_items
            has_changes = True
        if plan.menu_total != menu_total:
            plan.menu_total = menu_total
            has_changes = True

    db.commit()
    db.refresh(plan)
    if has_changes:
        _notify_partner_date_plan_event(
            db,
            relationship,
            current_user,
            plan.id,
            plan.title,
            plan.plan_at,
            plan.location,
            plan.status,
            "updated",
        )
    return plan


def update_date_plan_status(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    plan_id: str,
    status: str,
) -> CoupleDatePlan:
    if status not in DATE_PLAN_STATUSES:
        raise CoupleServiceError("无效的约饭计划状态")

    plan = _get_date_plan_or_raise(db, relationship.id, plan_id)
    previous_status = plan.status
    if previous_status == status:
        return plan

    plan.status = status
    db.commit()
    db.refresh(plan)

    action = "updated"
    if status == "completed":
        action = "completed"
    elif status == "cancelled":
        action = "cancelled"
    elif status == "planned" and previous_status in {"completed", "cancelled"}:
        action = "restored"

    _notify_partner_date_plan_event(
        db,
        relationship,
        current_user,
        plan.id,
        plan.title,
        plan.plan_at,
        plan.location,
        plan.status,
        action,
    )
    return plan


def delete_date_plan(db: Session, relationship: CoupleRelationship, current_user: User, plan_id: str) -> None:
    plan = _get_date_plan_or_raise(db, relationship.id, plan_id)
    plan_snapshot = {
        "id": plan.id,
        "title": plan.title,
        "plan_at": plan.plan_at,
        "location": plan.location,
        "status": plan.status,
    }
    db.delete(plan)
    db.commit()
    _notify_partner_date_plan_event(
        db,
        relationship,
        current_user,
        plan_snapshot["id"],
        plan_snapshot["title"],
        plan_snapshot["plan_at"],
        plan_snapshot["location"],
        plan_snapshot["status"],
        "deleted",
    )


def get_date_plan_detail(db: Session, relationship: CoupleRelationship, plan_id: str) -> CoupleDatePlan:
    return _get_date_plan_or_raise(db, relationship.id, plan_id)


def list_restaurant_wishes(
    db: Session,
    relationship: CoupleRelationship,
    status_filter: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list[CoupleRestaurantWish]:
    query = db.query(CoupleRestaurantWish).join(
        CoupleRestaurantItem,
        CoupleRestaurantWish.item_id == CoupleRestaurantItem.id
    ).filter(
        CoupleRestaurantWish.relationship_id == relationship.id,
        CoupleRestaurantItem.relationship_id == relationship.id
    )

    if status_filter and status_filter != "all":
        if status_filter not in WISH_STATUSES:
            raise CoupleServiceError("无效的想吃清单状态")
        query = query.filter(CoupleRestaurantWish.status == status_filter)

    if keyword:
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            query = query.filter(
                or_(
                    CoupleRestaurantItem.name.ilike(keyword_pattern),
                    CoupleRestaurantItem.description.ilike(keyword_pattern),
                    CoupleRestaurantWish.note.ilike(keyword_pattern),
                )
            )

    return query.order_by(
        desc(CoupleRestaurantWish.priority),
        asc(CoupleRestaurantWish.created_at)
    ).all()


def create_restaurant_wish(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    item_id: str,
    note: Optional[str],
    priority: int = 0,
) -> CoupleRestaurantWish:
    _get_restaurant_item_or_raise(db, relationship.id, item_id)
    existing = _get_restaurant_wish_by_item(db, relationship.id, item_id)
    normalized_note = _normalize_optional_text(note)

    if existing:
        existing.note = normalized_note
        existing.priority = priority
        existing.status = "active"
        db.commit()
        db.refresh(existing)
        return existing

    wish = CoupleRestaurantWish(
        relationship_id=relationship.id,
        item_id=item_id,
        note=normalized_note,
        priority=priority,
        status="active",
        created_by=current_user.id,
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish


def update_restaurant_wish(
    db: Session,
    relationship: CoupleRelationship,
    wish_id: str,
    note: Optional[str] = None,
    priority: Optional[int] = None,
    status: Optional[str] = None,
    note_provided: bool = False,
) -> CoupleRestaurantWish:
    wish = _get_restaurant_wish_or_raise(db, relationship.id, wish_id)

    if note_provided:
        wish.note = _normalize_optional_text(note)
    if priority is not None:
        wish.priority = priority
    if status is not None:
        if status not in WISH_STATUSES:
            raise CoupleServiceError("无效的想吃清单状态")
        wish.status = status

    db.commit()
    db.refresh(wish)
    return wish


def delete_restaurant_wish(db: Session, relationship: CoupleRelationship, wish_id: str) -> None:
    wish = _get_restaurant_wish_or_raise(db, relationship.id, wish_id)
    db.delete(wish)
    db.commit()


def _build_restaurant_recommendation_payload(
    *,
    title: str,
    subtitle: str,
    seed_value: str,
    anniversary: Optional[CoupleAnniversary],
    recommended_items: list[CoupleRestaurantItem],
    source: str,
) -> dict:
    total_amount = sum(Decimal(item.price or 0) for item in recommended_items).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    ) if recommended_items else Decimal("0.00")

    return {
        "title": title,
        "subtitle": subtitle,
        "seed": seed_value,
        "anniversary_id": anniversary.id if anniversary else None,
        "source": source,
        "items": [restaurant_item_to_dict(item) for item in recommended_items],
        "total_amount": float(total_amount),
    }


def list_restaurant_categories(
    db: Session,
    relationship: CoupleRelationship,
    keyword: Optional[str] = None
) -> list[CoupleRestaurantCategory]:
    query = db.query(CoupleRestaurantCategory).filter(
        CoupleRestaurantCategory.relationship_id == relationship.id
    )

    if keyword:
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            query = query.filter(CoupleRestaurantCategory.name.ilike(f"%{normalized_keyword}%"))

    return query.order_by(
        asc(CoupleRestaurantCategory.sort_order),
        asc(CoupleRestaurantCategory.created_at)
    ).all()


def create_restaurant_category(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    name: str,
    image: Optional[str],
    sort_order: int,
) -> CoupleRestaurantCategory:
    normalized_name = _normalize_title(name, "分类")
    image_value = _normalize_optional_text(image)

    category = CoupleRestaurantCategory(
        relationship_id=relationship.id,
        name=normalized_name,
        image=image_value,
        sort_order=sort_order,
        created_by=current_user.id,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_restaurant_category(
    db: Session,
    relationship: CoupleRelationship,
    category_id: str,
    name: Optional[str] = None,
    image: Optional[str] = None,
    sort_order: Optional[int] = None,
    image_provided: bool = False,
) -> CoupleRestaurantCategory:
    category = _get_category_or_raise(db, relationship.id, category_id)

    if name is not None:
        category.name = _normalize_title(name, "分类")
    if image_provided:
        category.image = _normalize_optional_text(image)
    if sort_order is not None:
        category.sort_order = sort_order

    db.commit()
    db.refresh(category)
    return category


def sort_restaurant_categories(
    db: Session,
    relationship: CoupleRelationship,
    category_orders: list[dict[str, int]]
) -> list[CoupleRestaurantCategory]:
    if not category_orders:
        raise CoupleServiceError("请提供分类排序数据")

    category_ids = [item["id"] for item in category_orders]
    unique_category_ids = set(category_ids)
    if len(unique_category_ids) != len(category_ids):
        raise CoupleServiceError("分类排序数据重复")

    categories = db.query(CoupleRestaurantCategory).filter(
        CoupleRestaurantCategory.relationship_id == relationship.id,
        CoupleRestaurantCategory.id.in_(unique_category_ids)
    ).all()

    if len(categories) != len(unique_category_ids):
        raise CoupleServiceError("存在无效的菜单分类", code=404)

    category_map = {category.id: category for category in categories}
    for item in category_orders:
        category_map[item["id"]].sort_order = item["sort_order"]

    db.commit()
    return list_restaurant_categories(db, relationship)


def delete_restaurant_category(
    db: Session,
    relationship: CoupleRelationship,
    category_id: str
) -> None:
    category = _get_category_or_raise(db, relationship.id, category_id)
    item_count = db.query(CoupleRestaurantItem).filter(
        CoupleRestaurantItem.relationship_id == relationship.id,
        CoupleRestaurantItem.category_id == category_id
    ).count()
    if item_count > 0:
        raise CoupleServiceError("请先删除该分类下的菜单")

    db.delete(category)
    db.commit()


def list_restaurant_items(
    db: Session,
    relationship: CoupleRelationship,
    category_id: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list[CoupleRestaurantItem]:
    query = db.query(CoupleRestaurantItem).filter(
        CoupleRestaurantItem.relationship_id == relationship.id
    )

    if category_id:
        _get_category_or_raise(db, relationship.id, category_id)
        query = query.filter(CoupleRestaurantItem.category_id == category_id)

    items = query.order_by(
        asc(CoupleRestaurantItem.created_at),
        desc(CoupleRestaurantItem.updated_at)
    ).all()

    if keyword:
        normalized_keyword = keyword.strip().lower()
        if normalized_keyword:
            filtered_items: list[CoupleRestaurantItem] = []
            for item in items:
                haystacks = [
                    (item.name or "").lower(),
                    (item.description or "").lower(),
                    *[((tag or "").lower()) for tag in (item.tags or [])],
                ]
                if any(normalized_keyword in text for text in haystacks):
                    filtered_items.append(item)
            return filtered_items

    return items


def create_restaurant_item(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    category_id: str,
    name: str,
    price: float,
    images: list[str],
    tags: Optional[list[str]],
    description: Optional[str],
) -> CoupleRestaurantItem:
    _get_category_or_raise(db, relationship.id, category_id)
    normalized_name = _normalize_title(name, "菜单")
    normalized_images = _normalize_images(images)
    normalized_tags = _normalize_tags(tags)
    normalized_description = _normalize_optional_text(description)
    normalized_price = _normalize_price(price)

    item = CoupleRestaurantItem(
        relationship_id=relationship.id,
        category_id=category_id,
        name=normalized_name,
        price=normalized_price,
        images=normalized_images,
        tags=normalized_tags,
        description=normalized_description,
        created_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_restaurant_item(
    db: Session,
    relationship: CoupleRelationship,
    item_id: str,
    category_id: Optional[str] = None,
    name: Optional[str] = None,
    price: Optional[float] = None,
    images: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    description: Optional[str] = None,
    description_provided: bool = False,
    images_provided: bool = False,
    tags_provided: bool = False,
) -> CoupleRestaurantItem:
    item = _get_restaurant_item_or_raise(db, relationship.id, item_id)

    if category_id is not None:
        _get_category_or_raise(db, relationship.id, category_id)
        item.category_id = category_id
    if name is not None:
        item.name = _normalize_title(name, "菜单")
    if price is not None:
        item.price = _normalize_price(price)
    if images_provided:
        item.images = _normalize_images(images or [])
    if tags_provided:
        item.tags = _normalize_tags(tags)
    if description_provided:
        item.description = _normalize_optional_text(description)

    db.commit()
    db.refresh(item)
    return item


def delete_restaurant_item(
    db: Session,
    relationship: CoupleRelationship,
    item_id: str
) -> None:
    item = _get_restaurant_item_or_raise(db, relationship.id, item_id)
    db.query(CoupleRestaurantWish).filter(
        CoupleRestaurantWish.relationship_id == relationship.id,
        CoupleRestaurantWish.item_id == item_id
    ).delete(synchronize_session=False)
    db.query(CoupleRestaurantCartItem).filter(
        CoupleRestaurantCartItem.relationship_id == relationship.id,
        CoupleRestaurantCartItem.item_id == item_id
    ).delete(synchronize_session=False)
    db.delete(item)
    db.commit()


def get_restaurant_item_detail(
    db: Session,
    relationship: CoupleRelationship,
    item_id: str
) -> CoupleRestaurantItem:
    return _get_restaurant_item_or_raise(db, relationship.id, item_id)


def get_restaurant_dashboard(
    db: Session,
    relationship: CoupleRelationship,
    keyword: Optional[str] = None
) -> dict:
    categories = list_restaurant_categories(db, relationship)
    items = list_restaurant_items(db, relationship, keyword=keyword)
    wishes = list_restaurant_wishes(db, relationship, "active")
    return {
        "categories": [restaurant_category_to_dict(db, category) for category in categories],
        "items": [restaurant_item_to_dict(item) for item in items],
        "total_items": len(items),
        "wish_count": len(wishes),
    }


def get_restaurant_recommendation(
    db: Session,
    relationship: CoupleRelationship,
    seed: Optional[str] = None,
    anniversary_id: Optional[str] = None,
    source: str = "mixed",
    category_id: Optional[str] = None,
) -> dict:
    if source not in RESTAURANT_RECOMMENDATION_SOURCES:
        raise CoupleServiceError("无效的推荐来源")
    anniversary = _get_anniversary_or_raise(db, relationship.id, anniversary_id) if anniversary_id else None
    items = list_restaurant_items(db, relationship, category_id=category_id)
    active_wishes = list_restaurant_wishes(db, relationship, "active")
    wished_item_ids = {wish.item_id for wish in active_wishes}

    seed_value = seed or (
        f"anniversary:{anniversary.id}:{anniversary.title}:{anniversary.type}"
        if anniversary else _today().isoformat()
    )
    if category_id:
        category = _get_category_or_raise(db, relationship.id, category_id)
        seed_value = f"{seed_value}:category:{category.id}"
    else:
        category = None

    title = f"{anniversary.title}推荐菜单" if anniversary else "今天就吃这一组"

    if not items:
        return {
            "title": "先把喜欢的菜放进小餐厅",
            "subtitle": "有了共享菜单后，我就能帮你们为重要日子挑一组。",
            "seed": seed_value,
            "anniversary_id": anniversary.id if anniversary else None,
            "source": source,
            "items": [],
            "total_amount": 0,
        }

    randomizer = random.Random(f"{relationship.id}:{seed_value}")
    if source == "wishes":
        candidate_items = [item for item in items if item.id in wished_item_ids]
    elif source == "restaurant":
        candidate_items = items[:]
    else:
        wished_items = [item for item in items if item.id in wished_item_ids]
        other_items = [item for item in items if item.id not in wished_item_ids]
        candidate_items = wished_items + other_items

    if not candidate_items:
        return {
            "title": "想吃清单还没有内容",
            "subtitle": "先把几道想一起吃的菜加入想吃清单，再来抽今天吃什么。",
            "seed": seed_value,
            "anniversary_id": anniversary.id if anniversary else None,
            "source": source,
            "items": [],
            "total_amount": 0,
        }

    shuffled_items = candidate_items[:]
    randomizer.shuffle(shuffled_items)
    recommended_items = shuffled_items[:min(3, len(shuffled_items))]
    category_names = [item.category.name for item in recommended_items if item.category]
    unique_category_names = list(dict.fromkeys(category_names))
    subtitle_prefix = "、".join(unique_category_names[:2]) or "共享菜单"
    if category:
        subtitle_prefix = category.name
    if anniversary:
        subtitle = f"{anniversary.type} · {subtitle_prefix} · {len(recommended_items)} 道推荐"
    elif source == "wishes":
        subtitle = f"优先从想吃清单里挑了 {len(recommended_items)} 道"
    elif source == "mixed" and wished_item_ids:
        subtitle = f"想吃清单优先 · {subtitle_prefix} · {len(recommended_items)} 道推荐"
    else:
        subtitle = f"{subtitle_prefix} · {len(recommended_items)} 道推荐"

    return _build_restaurant_recommendation_payload(
        title=title,
        subtitle=subtitle,
        seed_value=seed_value,
        anniversary=anniversary,
        recommended_items=recommended_items,
        source=source,
    )


def list_restaurant_cart_items(
    db: Session,
    relationship: CoupleRelationship
) -> list[CoupleRestaurantCartItem]:
    return db.query(CoupleRestaurantCartItem).join(
        CoupleRestaurantItem,
        CoupleRestaurantCartItem.item_id == CoupleRestaurantItem.id
    ).filter(
        CoupleRestaurantCartItem.relationship_id == relationship.id,
        CoupleRestaurantItem.relationship_id == relationship.id
    ).order_by(
        asc(CoupleRestaurantCartItem.created_at),
        asc(CoupleRestaurantCartItem.id)
    ).all()


def get_restaurant_cart(db: Session, relationship: CoupleRelationship) -> dict:
    cart_items = list_restaurant_cart_items(db, relationship)
    cart_data = [restaurant_cart_item_to_dict(item) for item in cart_items]
    total_amount = sum(
        (Decimal(str(item["subtotal"])) for item in cart_data),
        Decimal("0.00")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )
    return {
        "items": cart_data,
        "total_quantity": sum(item["quantity"] for item in cart_data),
        "total_amount": float(total_amount),
    }


def _get_restaurant_cart_item(
    db: Session,
    relationship_id: str,
    item_id: str,
) -> Optional[CoupleRestaurantCartItem]:
    return db.query(CoupleRestaurantCartItem).filter(
        CoupleRestaurantCartItem.relationship_id == relationship_id,
        CoupleRestaurantCartItem.item_id == item_id
    ).first()


def add_restaurant_cart_item(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    item_id: str,
    quantity: int,
) -> dict:
    _get_restaurant_item_or_raise(db, relationship.id, item_id)
    cart_item = _get_restaurant_cart_item(db, relationship.id, item_id)

    if cart_item:
        next_quantity = cart_item.quantity + quantity
        if next_quantity > 99:
            raise CoupleServiceError("单个菜单最多只能加入 99 份")
        cart_item.quantity = next_quantity
    else:
        cart_item = CoupleRestaurantCartItem(
            relationship_id=relationship.id,
            item_id=item_id,
            quantity=quantity,
            created_by=current_user.id,
        )
        db.add(cart_item)

    db.commit()
    return get_restaurant_cart(db, relationship)


def set_restaurant_cart_item_quantity(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    item_id: str,
    quantity: int,
) -> dict:
    _get_restaurant_item_or_raise(db, relationship.id, item_id)
    cart_item = _get_restaurant_cart_item(db, relationship.id, item_id)

    if cart_item:
        cart_item.quantity = quantity
    else:
        cart_item = CoupleRestaurantCartItem(
            relationship_id=relationship.id,
            item_id=item_id,
            quantity=quantity,
            created_by=current_user.id,
        )
        db.add(cart_item)

    db.commit()
    return get_restaurant_cart(db, relationship)


def remove_restaurant_cart_item(
    db: Session,
    relationship: CoupleRelationship,
    item_id: str,
) -> dict:
    db.query(CoupleRestaurantCartItem).filter(
        CoupleRestaurantCartItem.relationship_id == relationship.id,
        CoupleRestaurantCartItem.item_id == item_id
    ).delete(synchronize_session=False)
    db.commit()
    return get_restaurant_cart(db, relationship)


def clear_restaurant_cart(db: Session, relationship: CoupleRelationship) -> dict:
    db.query(CoupleRestaurantCartItem).filter(
        CoupleRestaurantCartItem.relationship_id == relationship.id
    ).delete(synchronize_session=False)
    db.commit()
    return get_restaurant_cart(db, relationship)


def _build_date_draw_candidate_pool(
    db: Session,
    relationship: CoupleRelationship,
    source: str,
    category_id: Optional[str] = None,
    anniversary_id: Optional[str] = None,
) -> list[dict]:
    if source not in DATE_DRAW_SOURCES:
        raise CoupleServiceError("无效的抽卡来源")

    candidates: list[dict] = []

    if source in {"mixed", "wishes"}:
        wishes = list_restaurant_wishes(db, relationship, "active")
        for wish in wishes:
            if not wish.item:
                continue
            if category_id and wish.item.category_id != category_id:
                continue
            candidates.append({
                "card_type": "wish",
                "source_item_id": wish.id,
                "source_item_type": "couple_restaurant_wish",
                "title": f"今晚试试 {wish.item.name}",
                "subtitle": f"想吃清单 · {wish.item.category.name if wish.item.category else '共享菜单'}",
                "content": wish.note or "从你们的想吃清单里抽到了一道值得安排的菜。",
                "payload": {
                    "wish_id": wish.id,
                    "item": restaurant_item_to_dict(wish.item),
                    "note": wish.note,
                    "priority": wish.priority,
                }
            })

    if source in {"mixed", "restaurant"}:
        items = list_restaurant_items(db, relationship, category_id=category_id)
        for item in items:
            candidates.append({
                "card_type": "food",
                "source_item_id": item.id,
                "source_item_type": "couple_restaurant_item",
                "title": f"今天就吃 {item.name}",
                "subtitle": f"共享菜单 · {item.category.name if item.category else '小餐厅'}",
                "content": item.description or "从你们共同维护的小餐厅里抽到的一道菜。",
                "payload": {
                    "item": restaurant_item_to_dict(item),
                }
            })

    if source in {"mixed", "anniversaries"}:
        anniversaries = list_anniversaries(db, relationship)
        for anniversary in anniversaries:
            if anniversary_id and anniversary.id != anniversary_id:
                continue
            anniversary_data = anniversary_to_dict(anniversary)
            candidates.append({
                "card_type": "anniversary",
                "source_item_id": anniversary.id,
                "source_item_type": "couple_anniversary",
                "title": f"{anniversary.title}约会提案",
                "subtitle": f"{anniversary.type} · {anniversary_data['days_left']} 天后",
                "content": anniversary.note or "把这个纪念日变成一次认真准备的约会吧。",
                "payload": {
                    "anniversary": anniversary_data,
                }
            })

    return candidates


def draw_date_card(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    source: str = "mixed",
    category_id: Optional[str] = None,
    anniversary_id: Optional[str] = None,
    seed: Optional[str] = None,
) -> CoupleDateDraw:
    if category_id:
        _get_category_or_raise(db, relationship.id, category_id)
    if anniversary_id:
        _get_anniversary_or_raise(db, relationship.id, anniversary_id)

    candidates = _build_date_draw_candidate_pool(
        db,
        relationship,
        source,
        category_id=category_id,
        anniversary_id=anniversary_id,
    )
    if not candidates:
        raise CoupleServiceError("还没有可抽取的内容，先补充想吃清单或共享菜单吧")

    seed_value = seed or f"{relationship.id}:{source}:{category_id or 'all'}:{anniversary_id or 'none'}:{_current_time().isoformat()}"
    randomizer = random.Random(seed_value)
    selected = randomizer.choice(candidates)

    draw = CoupleDateDraw(
        relationship_id=relationship.id,
        title=selected["title"],
        subtitle=selected.get("subtitle"),
        card_type=selected["card_type"],
        source_item_id=selected.get("source_item_id"),
        source_item_type=selected.get("source_item_type"),
        content=selected.get("content"),
        payload={
            **(selected.get("payload") or {}),
            "source": source,
            "seed": seed_value,
            "category_id": category_id,
            "anniversary_id": anniversary_id,
        },
        status="drawn",
        created_by=current_user.id,
    )
    db.add(draw)
    db.commit()
    db.refresh(draw)
    _notify_partner_date_draw_event(db, relationship, current_user, draw, "drawn")
    return draw


def list_date_draws(
    db: Session,
    relationship: CoupleRelationship,
    status_filter: Optional[str] = None,
) -> list[CoupleDateDraw]:
    query = db.query(CoupleDateDraw).filter(
        CoupleDateDraw.relationship_id == relationship.id
    )

    if status_filter and status_filter != "all":
        if status_filter not in DATE_DRAW_STATUSES:
            raise CoupleServiceError("无效的抽卡状态")
        query = query.filter(CoupleDateDraw.status == status_filter)

    return query.order_by(desc(CoupleDateDraw.created_at)).all()


def accept_date_draw(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    draw_id: str,
    title: Optional[str] = None,
    plan_at: Optional[datetime] = None,
    location: Optional[str] = None,
    note: Optional[str] = None,
) -> CoupleDateDraw:
    draw = _get_date_draw_or_raise(db, relationship.id, draw_id)
    if draw.status not in {"drawn", "accepted"}:
        raise CoupleServiceError("当前抽卡记录不能再生成计划")
    if draw.status == "accepted" and draw.plan_id:
        existing_plan = _get_date_plan_or_raise(db, relationship.id, draw.plan_id)
        if existing_plan:
            db.refresh(draw)
            return draw

    payload = draw.payload or {}
    draw_title = _normalize_title(title or draw.title or "情侣约会", "约会计划")
    final_note = _normalize_optional_text(note) or _normalize_optional_text(draw.content)
    final_plan_at = plan_at or (_current_time() + timedelta(days=1)).replace(second=0, microsecond=0)
    anniversary_payload = payload.get("anniversary") if isinstance(payload, dict) else None
    anniversary_id = None
    menu_items = None

    if isinstance(anniversary_payload, dict):
        anniversary_id = anniversary_payload.get("id")

    item_payload = payload.get("item") if isinstance(payload, dict) else None
    if isinstance(item_payload, dict) and item_payload.get("id"):
        menu_items = [{
            "item_id": item_payload.get("id"),
            "name": item_payload.get("name"),
            "price": item_payload.get("price") or 0,
            "quantity": 1,
            "cover_image": item_payload.get("cover_image"),
            "category_name": item_payload.get("category_name"),
        }]

    plan = create_date_plan(
        db,
        relationship,
        current_user,
        draw_title,
        final_plan_at,
        _normalize_optional_text(location),
        final_note,
        anniversary_id,
        None,
        menu_items,
        notify_partner=False,
    )

    draw.plan_id = plan.id
    draw.status = "accepted"
    db.commit()
    db.refresh(draw)
    _notify_partner_date_draw_event(db, relationship, current_user, draw, "accepted")
    return draw


def update_date_draw_status(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    draw_id: str,
    status: str,
) -> CoupleDateDraw:
    if status not in DATE_DRAW_STATUSES:
        raise CoupleServiceError("无效的抽卡状态")
    draw = _get_date_draw_or_raise(db, relationship.id, draw_id)
    previous_status = draw.status
    if previous_status == status:
        return draw
    draw.status = status
    db.commit()
    db.refresh(draw)
    action = status
    if status == "drawn" and previous_status in {"accepted", "completed", "cancelled"}:
        action = "restored"
    _notify_partner_date_draw_event(db, relationship, current_user, draw, action)
    return draw


def _notification_exists_today(
    db: Session,
    user_id: str,
    notification_type: str,
    data_match: dict[str, str]
) -> bool:
    start = datetime.combine(_today(), datetime.min.time())
    notifications = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.type == notification_type,
        Notification.created_at >= start
    ).all()

    for notification in notifications:
        data = notification.data or {}
        if all(data.get(key) == value for key, value in data_match.items()):
            return True

    return False


def sync_due_notifications(db: Session, relationship: CoupleRelationship) -> None:
    users = [relationship.user_a_id, relationship.user_b_id]
    now = _current_time()
    today_start = datetime.combine(_today(), datetime.min.time())
    tomorrow_start = today_start + timedelta(days=1)

    due_memos = db.query(CoupleMemo).filter(
        CoupleMemo.relationship_id == relationship.id,
        CoupleMemo.is_completed == False,
        CoupleMemo.remind_at.isnot(None),
        CoupleMemo.remind_at >= today_start,
        CoupleMemo.remind_at <= now,
        CoupleMemo.remind_at < tomorrow_start
    ).all()

    for memo in due_memos:
        title = f"情侣备忘录提醒：{memo.title}"
        data = {
            "kind": "couple_memo",
            "action": "reminder",
            "memo_id": memo.id,
            "memo_title": memo.title,
            "category": memo.category,
            "is_completed": memo.is_completed,
        }
        for user_id in users:
            if not _notification_exists_today(db, user_id, "couple_memo", data):
                create_notification(
                    db=db,
                    user_id=user_id,
                    notification_type="couple_memo",
                    title=title,
                    content="今天有一条情侣备忘录待处理",
                    data=data
                )

    for anniversary in list_anniversaries(db, relationship):
        anniversary_data = anniversary_to_dict(anniversary)
        if anniversary_data["days_left"] <= anniversary.remind_days_before:
            title = f"纪念日提醒：{anniversary.title}"
            data = {
                "kind": "couple_anniversary",
                "action": "reminder",
                "anniversary_id": anniversary.id,
                "anniversary_title": anniversary.title,
                "anniversary_type": anniversary.type,
            }
            for user_id in users:
                if not _notification_exists_today(db, user_id, "couple_anniversary", data):
                    create_notification(
                        db=db,
                        user_id=user_id,
                        notification_type="couple_anniversary",
                        title=title,
                        content=f"{anniversary_data['days_left']} 天后就是重要纪念日",
                        data=data
                    )

    due_date_plans = db.query(CoupleDatePlan).filter(
        CoupleDatePlan.relationship_id == relationship.id,
        CoupleDatePlan.status == "planned",
        CoupleDatePlan.plan_at >= today_start,
        CoupleDatePlan.plan_at <= now,
        CoupleDatePlan.plan_at < tomorrow_start
    ).all()

    for plan in due_date_plans:
        title = f"约饭计划提醒：{plan.title}"
        data = {
            "kind": "couple_date_plan",
            "action": "reminder",
            "plan_id": plan.id,
            "plan_title": plan.title,
            "status": plan.status,
        }
        content = "今天有一个约饭计划待确认"
        if plan.location:
            content = f"今天约在 {plan.location}，记得准时赴约"
        for user_id in users:
            if not _notification_exists_today(db, user_id, "couple_date_plan", data):
                create_notification(
                    db=db,
                    user_id=user_id,
                    notification_type="couple_date_plan",
                    title=title,
                    content=content,
                    data=data
                )


def sync_all_due_notifications(db: Session) -> int:
    relationships = list_active_relationships(db)
    for relationship in relationships:
        sync_due_notifications(db, relationship)
    return len(relationships)


def get_dashboard(db: Session, current_user: User) -> dict:
    profile = get_couple_profile(db, current_user)
    if not profile["is_bound"]:
        return {
            "profile": profile,
            "today_reminders": [],
            "upcoming_anniversaries": [],
            "memos": [],
            "date_plans": [],
            "restaurant_wishes": [],
            "date_draws": [],
        }

    relationship = require_relationship(db, current_user)
    sync_due_notifications(db, relationship)

    reminders = []
    today = _today()
    for memo in list_memos(db, relationship, "pending"):
        if memo.remind_at and memo.remind_at.date() == today:
            reminders.append({
                "id": memo.id,
                "kind": "memo",
                "title": memo.title,
                "time": memo.remind_at.isoformat(),
                "category": memo.category
            })

    upcoming_anniversaries = sorted(
        [anniversary_to_dict(item) for item in list_anniversaries(db, relationship)],
        key=lambda item: item["days_left"]
    )[:3]

    for item in upcoming_anniversaries:
        if item["days_left"] == 0:
            reminders.append({
                "id": item["id"],
                "kind": "anniversary",
                "title": item["title"],
                "time": item["date"],
                "category": item["type"]
            })

    for plan in list_date_plans(db, relationship, "planned"):
        if plan.plan_at.date() == today:
            reminders.append({
                "id": plan.id,
                "kind": "date_plan",
                "title": plan.title,
                "time": plan.plan_at.isoformat(),
                "category": "约饭计划"
            })

    return {
        "profile": profile,
        "today_reminders": reminders,
        "upcoming_anniversaries": upcoming_anniversaries,
        "memos": [memo_to_dict(memo) for memo in list_memos(db, relationship)],
        "date_plans": [date_plan_to_dict(plan) for plan in list_date_plans(db, relationship)[:3]],
        "restaurant_wishes": [restaurant_wish_to_dict(wish) for wish in list_restaurant_wishes(db, relationship, "active")[:5]],
        "date_draws": [date_draw_to_dict(draw) for draw in list_date_draws(db, relationship)[:5]],
    }
