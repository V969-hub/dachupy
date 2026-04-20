"""
Service layer for the couple memo MVP.
"""
import calendar
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
)
from app.models.order import Order
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import create_notification
from app.utils.security import generate_binding_code


MEMO_CATEGORIES = {"日常", "约会", "纪念日", "礼物", "其他"}
ANNIVERSARY_TYPES = {"恋爱纪念日", "生日", "节日", "自定义"}
DATE_PLAN_STATUSES = {"planned", "completed", "cancelled"}
MAX_RESTAURANT_IMAGES = 9


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


def _normalize_images(images: list[str]) -> list[str]:
    normalized_images = [image.strip() for image in images if isinstance(image, str) and image.strip()]
    if not normalized_images:
        raise CoupleServiceError("请至少上传一张图片")
    if len(normalized_images) > MAX_RESTAURANT_IMAGES:
        raise CoupleServiceError(f"最多上传 {MAX_RESTAURANT_IMAGES} 张图片")
    return normalized_images


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
        "description": item.description,
        "created_by": item.created_by,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


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
    return memo


def update_memo(
    db: Session,
    relationship: CoupleRelationship,
    memo_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
    remind_at: Optional[datetime] = None,
    is_pinned: Optional[bool] = None,
    remind_at_provided: bool = False,
) -> CoupleMemo:
    memo = _get_memo_or_raise(db, relationship.id, memo_id)

    if title is not None:
        memo.title = _normalize_title(title, "备忘录")
    if content is not None:
        memo.content = content
    if category is not None:
        if category not in MEMO_CATEGORIES:
            raise CoupleServiceError("无效的备忘录分类")
        memo.category = category
    if remind_at_provided:
        memo.remind_at = remind_at
    if is_pinned is not None:
        memo.is_pinned = is_pinned

    db.commit()
    db.refresh(memo)
    return memo


def update_memo_status(
    db: Session,
    relationship: CoupleRelationship,
    memo_id: str,
    is_completed: bool
) -> CoupleMemo:
    memo = _get_memo_or_raise(db, relationship.id, memo_id)
    memo.is_completed = is_completed
    db.commit()
    db.refresh(memo)
    return memo


def delete_memo(db: Session, relationship: CoupleRelationship, memo_id: str) -> None:
    memo = _get_memo_or_raise(db, relationship.id, memo_id)
    db.delete(memo)
    db.commit()


def get_memo_detail(db: Session, relationship: CoupleRelationship, memo_id: str) -> CoupleMemo:
    return _get_memo_or_raise(db, relationship.id, memo_id)


def list_anniversaries(db: Session, relationship: CoupleRelationship) -> list[CoupleAnniversary]:
    return db.query(CoupleAnniversary).filter(
        CoupleAnniversary.relationship_id == relationship.id
    ).order_by(asc(CoupleAnniversary.date)).all()


def create_anniversary(
    db: Session,
    relationship: CoupleRelationship,
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
    return anniversary


def update_anniversary(
    db: Session,
    relationship: CoupleRelationship,
    anniversary_id: str,
    title: Optional[str] = None,
    target_date: Optional[date] = None,
    anniversary_type: Optional[str] = None,
    remind_days_before: Optional[int] = None,
    note: Optional[str] = None,
    note_provided: bool = False,
) -> CoupleAnniversary:
    anniversary = _get_anniversary_or_raise(db, relationship.id, anniversary_id)

    if title is not None:
        anniversary.title = _normalize_title(title, "纪念日")
    if target_date is not None:
        anniversary.date = target_date
    if anniversary_type is not None:
        if anniversary_type not in ANNIVERSARY_TYPES:
            raise CoupleServiceError("无效的纪念日类型")
        anniversary.type = anniversary_type
    if remind_days_before is not None:
        anniversary.remind_days_before = remind_days_before
    if note_provided:
        anniversary.note = note

    db.commit()
    db.refresh(anniversary)
    return anniversary


def delete_anniversary(db: Session, relationship: CoupleRelationship, anniversary_id: str) -> None:
    anniversary = _get_anniversary_or_raise(db, relationship.id, anniversary_id)
    db.delete(anniversary)
    db.commit()


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
) -> CoupleDatePlan:
    normalized_title = _normalize_title(title, "约饭计划")
    _validate_anniversary_link(db, relationship, anniversary_id)
    _validate_order_link(db, relationship, order_id)

    plan = CoupleDatePlan(
        relationship_id=relationship.id,
        title=normalized_title,
        plan_at=plan_at,
        location=location,
        note=note,
        anniversary_id=anniversary_id,
        order_id=order_id,
        created_by=current_user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_date_plan(
    db: Session,
    relationship: CoupleRelationship,
    plan_id: str,
    title: Optional[str] = None,
    plan_at: Optional[datetime] = None,
    location: Optional[str] = None,
    note: Optional[str] = None,
    anniversary_id: Optional[str] = None,
    order_id: Optional[str] = None,
    location_provided: bool = False,
    note_provided: bool = False,
    anniversary_id_provided: bool = False,
    order_id_provided: bool = False,
) -> CoupleDatePlan:
    plan = _get_date_plan_or_raise(db, relationship.id, plan_id)

    if title is not None:
        plan.title = _normalize_title(title, "约饭计划")
    if plan_at is not None:
        plan.plan_at = plan_at
    if location_provided:
        plan.location = location
    if note_provided:
        plan.note = note
    if anniversary_id_provided:
        _validate_anniversary_link(db, relationship, anniversary_id)
        plan.anniversary_id = anniversary_id
    if order_id_provided:
        _validate_order_link(db, relationship, order_id)
        plan.order_id = order_id

    db.commit()
    db.refresh(plan)
    return plan


def update_date_plan_status(
    db: Session,
    relationship: CoupleRelationship,
    plan_id: str,
    status: str,
) -> CoupleDatePlan:
    if status not in DATE_PLAN_STATUSES:
        raise CoupleServiceError("无效的约饭计划状态")

    plan = _get_date_plan_or_raise(db, relationship.id, plan_id)
    plan.status = status
    db.commit()
    db.refresh(plan)
    return plan


def delete_date_plan(db: Session, relationship: CoupleRelationship, plan_id: str) -> None:
    plan = _get_date_plan_or_raise(db, relationship.id, plan_id)
    db.delete(plan)
    db.commit()


def get_date_plan_detail(db: Session, relationship: CoupleRelationship, plan_id: str) -> CoupleDatePlan:
    return _get_date_plan_or_raise(db, relationship.id, plan_id)


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

    if keyword:
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            query = query.filter(
                or_(
                    CoupleRestaurantItem.name.ilike(keyword_pattern),
                    CoupleRestaurantItem.description.ilike(keyword_pattern),
                )
            )

    return query.order_by(
        asc(CoupleRestaurantItem.created_at),
        desc(CoupleRestaurantItem.updated_at)
    ).all()


def create_restaurant_item(
    db: Session,
    relationship: CoupleRelationship,
    current_user: User,
    category_id: str,
    name: str,
    price: float,
    images: list[str],
    description: Optional[str],
) -> CoupleRestaurantItem:
    _get_category_or_raise(db, relationship.id, category_id)
    normalized_name = _normalize_title(name, "菜单")
    normalized_images = _normalize_images(images)
    normalized_description = _normalize_optional_text(description)
    normalized_price = _normalize_price(price)

    item = CoupleRestaurantItem(
        relationship_id=relationship.id,
        category_id=category_id,
        name=normalized_name,
        price=normalized_price,
        images=normalized_images,
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
    description: Optional[str] = None,
    description_provided: bool = False,
    images_provided: bool = False,
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
    return {
        "categories": [restaurant_category_to_dict(db, category) for category in categories],
        "items": [restaurant_item_to_dict(item) for item in items],
        "total_items": len(items),
    }


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
        data = {"kind": "couple_memo", "memo_id": memo.id}
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
            data = {"kind": "couple_anniversary", "anniversary_id": anniversary.id}
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
        data = {"kind": "couple_date_plan", "plan_id": plan.id}
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
            "date_plans": []
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
        "date_plans": [date_plan_to_dict(plan) for plan in list_date_plans(db, relationship)[:3]]
    }
