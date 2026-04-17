"""
情侣备忘录 MVP 接口。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.common import success_response, error_response
from app.schemas.couple import (
    BindCoupleRequest,
    CoupleMemoCreateRequest,
    CoupleMemoUpdateRequest,
    CoupleMemoStatusRequest,
    CoupleAnniversaryCreateRequest,
    CoupleAnniversaryUpdateRequest,
)
from app.services.couple_service import (
    CoupleServiceError,
    get_couple_profile,
    refresh_couple_code,
    bind_couple,
    unbind_couple,
    require_relationship,
    get_dashboard,
    list_memos,
    create_memo,
    update_memo,
    update_memo_status,
    delete_memo,
    get_memo_detail,
    memo_to_dict,
    list_anniversaries,
    create_anniversary,
    update_anniversary,
    delete_anniversary,
    anniversary_to_dict,
)


router = APIRouter(prefix="/couple", tags=["情侣"])


@router.get("/profile")
async def couple_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return success_response(data=get_couple_profile(db, current_user))
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取情侣资料失败: {str(e)}")


@router.post("/bind")
async def bind_partner(
    request: BindCoupleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        bind_couple(db, current_user, request.partner_code, request.anniversary_date)
        return success_response(data=get_couple_profile(db, current_user), message="绑定成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"绑定失败: {str(e)}")


@router.delete("/bind")
async def unbind_partner(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        unbind_couple(db, current_user)
        return success_response(data=get_couple_profile(db, current_user), message="解绑成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"解绑失败: {str(e)}")


@router.post("/code/refresh")
async def refresh_code(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        code = refresh_couple_code(db, current_user)
        return success_response(data={"couple_code": code}, message="邀请码已刷新")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"刷新邀请码失败: {str(e)}")


@router.get("/dashboard")
async def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return success_response(data=get_dashboard(db, current_user))
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取情侣首页失败: {str(e)}")


@router.get("/memos")
async def couple_memos(
    status: str = Query("all", description="筛选：all/completed/pending/pinned"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        memos = [memo_to_dict(item) for item in list_memos(db, relationship, status if status != "all" else None)]
        return success_response(data=memos)
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取备忘录失败: {str(e)}")


@router.post("/memos")
async def create_couple_memo(
    request: CoupleMemoCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        memo = create_memo(
            db,
            relationship,
            current_user,
            request.title,
            request.content,
            request.category,
            request.remind_at,
            request.is_pinned
        )
        return success_response(data=memo_to_dict(memo), message="创建成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"创建备忘录失败: {str(e)}")


@router.get("/memos/{memo_id}")
async def memo_detail(
    memo_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        return success_response(data=memo_to_dict(get_memo_detail(db, relationship, memo_id)))
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取备忘录详情失败: {str(e)}")


@router.put("/memos/{memo_id}")
async def update_couple_memo(
    memo_id: str,
    request: CoupleMemoUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        memo = update_memo(
            db,
            relationship,
            memo_id,
            title=request.title,
            content=request.content,
            category=request.category,
            remind_at=request.remind_at,
            is_pinned=request.is_pinned
        )
        return success_response(data=memo_to_dict(memo), message="更新成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新备忘录失败: {str(e)}")


@router.put("/memos/{memo_id}/status")
async def update_couple_memo_status(
    memo_id: str,
    request: CoupleMemoStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        memo = update_memo_status(db, relationship, memo_id, request.is_completed)
        return success_response(data=memo_to_dict(memo), message="状态已更新")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新备忘录状态失败: {str(e)}")


@router.delete("/memos/{memo_id}")
async def remove_couple_memo(
    memo_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        delete_memo(db, relationship, memo_id)
        return success_response(message="删除成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"删除备忘录失败: {str(e)}")


@router.get("/anniversaries")
async def anniversaries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        data = [anniversary_to_dict(item) for item in list_anniversaries(db, relationship)]
        return success_response(data=data)
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取纪念日失败: {str(e)}")


@router.post("/anniversaries")
async def create_couple_anniversary(
    request: CoupleAnniversaryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        anniversary = create_anniversary(
            db,
            relationship,
            request.title,
            request.date,
            request.type,
            request.remind_days_before,
            request.note
        )
        return success_response(data=anniversary_to_dict(anniversary), message="创建成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"创建纪念日失败: {str(e)}")


@router.put("/anniversaries/{anniversary_id}")
async def update_couple_anniversary(
    anniversary_id: str,
    request: CoupleAnniversaryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        anniversary = update_anniversary(
            db,
            relationship,
            anniversary_id,
            title=request.title,
            target_date=request.date,
            anniversary_type=request.type,
            remind_days_before=request.remind_days_before,
            note=request.note
        )
        return success_response(data=anniversary_to_dict(anniversary), message="更新成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新纪念日失败: {str(e)}")


@router.delete("/anniversaries/{anniversary_id}")
async def remove_couple_anniversary(
    anniversary_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        delete_anniversary(db, relationship, anniversary_id)
        return success_response(message="删除成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"删除纪念日失败: {str(e)}")
