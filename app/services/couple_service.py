"""
Service layer for the couple memo MVP.
"""
import calendar
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session

from app.models.couple import CoupleRelationship, CoupleMemo, CoupleAnniversary
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import create_notification
from app.utils.security import generate_binding_code


MEMO_CATEGORIES = {"日常", "约会", "纪念日", "礼物", "其他"}
ANNIVERSARY_TYPES = {"恋爱纪念日", "生日", "节日", "自定义"}


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
    is_pinned: Optional[bool] = None
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
    if remind_at is not None:
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
    note: Optional[str] = None
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
    if note is not None:
        anniversary.note = note

    db.commit()
    db.refresh(anniversary)
    return anniversary


def delete_anniversary(db: Session, relationship: CoupleRelationship, anniversary_id: str) -> None:
    anniversary = _get_anniversary_or_raise(db, relationship.id, anniversary_id)
    db.delete(anniversary)
    db.commit()


def _notification_exists_today(db: Session, user_id: str, title: str) -> bool:
    start = datetime.combine(_today(), datetime.min.time())
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.title == title,
        Notification.created_at >= start
    ).first() is not None


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
        for user_id in users:
            if not _notification_exists_today(db, user_id, title):
                create_notification(
                    db=db,
                    user_id=user_id,
                    notification_type="couple_memo",
                    title=title,
                    content="今天有一条情侣备忘录待处理",
                    data={"kind": "couple_memo", "memo_id": memo.id}
                )

    for anniversary in list_anniversaries(db, relationship):
        anniversary_data = anniversary_to_dict(anniversary)
        if anniversary_data["days_left"] <= anniversary.remind_days_before:
            title = f"纪念日提醒：{anniversary.title}"
            for user_id in users:
                if not _notification_exists_today(db, user_id, title):
                    create_notification(
                        db=db,
                        user_id=user_id,
                        notification_type="couple_anniversary",
                        title=title,
                        content=f"{anniversary_data['days_left']} 天后就是重要纪念日",
                        data={"kind": "couple_anniversary", "anniversary_id": anniversary.id}
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
            "memos": []
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

    return {
        "profile": profile,
        "today_reminders": reminders,
        "upcoming_anniversaries": upcoming_anniversaries,
        "memos": [memo_to_dict(memo) for memo in list_memos(db, relationship)]
    }
