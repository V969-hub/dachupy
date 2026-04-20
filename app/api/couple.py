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
    CoupleDatePlanCreateRequest,
    CoupleDatePlanUpdateRequest,
    CoupleDatePlanStatusRequest,
    CoupleRestaurantCategoryCreateRequest,
    CoupleRestaurantCategorySortRequest,
    CoupleRestaurantCategoryUpdateRequest,
    CoupleRestaurantItemCreateRequest,
    CoupleRestaurantItemUpdateRequest,
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
    list_date_plans,
    create_date_plan,
    update_date_plan,
    update_date_plan_status,
    delete_date_plan,
    get_date_plan_detail,
    date_plan_to_dict,
    list_restaurant_categories,
    create_restaurant_category,
    update_restaurant_category,
    sort_restaurant_categories,
    delete_restaurant_category,
    restaurant_category_to_dict,
    list_restaurant_items,
    create_restaurant_item,
    update_restaurant_item,
    delete_restaurant_item,
    get_restaurant_item_detail,
    restaurant_item_to_dict,
    get_restaurant_dashboard,
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
            is_pinned=request.is_pinned,
            remind_at_provided="remind_at" in request.model_fields_set,
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
            note=request.note,
            note_provided="note" in request.model_fields_set
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


@router.get("/date-plans")
async def date_plans(
    status: str = Query("all", description="筛选：all/planned/completed/cancelled"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        data = [date_plan_to_dict(item) for item in list_date_plans(db, relationship, status)]
        return success_response(data=data)
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取约饭计划失败: {str(e)}")


@router.post("/date-plans")
async def create_couple_date_plan(
    request: CoupleDatePlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        plan = create_date_plan(
            db,
            relationship,
            current_user,
            request.title,
            request.plan_at,
            request.location,
            request.note,
            request.anniversary_id,
            request.order_id
        )
        return success_response(data=date_plan_to_dict(plan), message="创建成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"创建约饭计划失败: {str(e)}")


@router.get("/date-plans/{plan_id}")
async def date_plan_detail(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        return success_response(data=date_plan_to_dict(get_date_plan_detail(db, relationship, plan_id)))
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取约饭计划详情失败: {str(e)}")


@router.put("/date-plans/{plan_id}")
async def update_couple_date_plan(
    plan_id: str,
    request: CoupleDatePlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        plan = update_date_plan(
            db,
            relationship,
            plan_id,
            title=request.title,
            plan_at=request.plan_at,
            location=request.location,
            note=request.note,
            anniversary_id=request.anniversary_id,
            order_id=request.order_id,
            location_provided="location" in request.model_fields_set,
            note_provided="note" in request.model_fields_set,
            anniversary_id_provided="anniversary_id" in request.model_fields_set,
            order_id_provided="order_id" in request.model_fields_set,
        )
        return success_response(data=date_plan_to_dict(plan), message="更新成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新约饭计划失败: {str(e)}")


@router.put("/date-plans/{plan_id}/status")
async def update_couple_date_plan_status(
    plan_id: str,
    request: CoupleDatePlanStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        plan = update_date_plan_status(db, relationship, plan_id, request.status)
        return success_response(data=date_plan_to_dict(plan), message="状态已更新")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新约饭计划状态失败: {str(e)}")


@router.delete("/date-plans/{plan_id}")
async def remove_couple_date_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        delete_date_plan(db, relationship, plan_id)
        return success_response(message="删除成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"删除约饭计划失败: {str(e)}")


@router.get("/restaurant/dashboard")
async def couple_restaurant_dashboard(
    keyword: str | None = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        return success_response(data=get_restaurant_dashboard(db, relationship, keyword))
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取小餐厅数据失败: {str(e)}")


@router.get("/restaurant/categories")
async def couple_restaurant_categories(
    keyword: str | None = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        data = [restaurant_category_to_dict(db, item) for item in list_restaurant_categories(db, relationship, keyword)]
        return success_response(data=data)
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取菜单分类失败: {str(e)}")


@router.post("/restaurant/categories")
async def create_couple_restaurant_category(
    request: CoupleRestaurantCategoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        category = create_restaurant_category(
            db,
            relationship,
            current_user,
            request.name,
            request.image,
            request.sort_order
        )
        return success_response(data=restaurant_category_to_dict(db, category), message="分类创建成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"创建菜单分类失败: {str(e)}")


@router.put("/restaurant/categories/sort")
async def sort_couple_restaurant_categories(
    request: CoupleRestaurantCategorySortRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        categories = sort_restaurant_categories(
            db,
            relationship,
            [{"id": item.id, "sort_order": item.sort_order} for item in request.categories]
        )
        return success_response(
            data=[restaurant_category_to_dict(db, item) for item in categories],
            message="分类排序已更新"
        )
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新分类排序失败: {str(e)}")


@router.put("/restaurant/categories/{category_id}")
async def update_couple_restaurant_category(
    category_id: str,
    request: CoupleRestaurantCategoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        category = update_restaurant_category(
            db,
            relationship,
            category_id,
            name=request.name,
            image=request.image,
            sort_order=request.sort_order,
            image_provided="image" in request.model_fields_set,
        )
        return success_response(data=restaurant_category_to_dict(db, category), message="分类更新成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新菜单分类失败: {str(e)}")


@router.delete("/restaurant/categories/{category_id}")
async def remove_couple_restaurant_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        delete_restaurant_category(db, relationship, category_id)
        return success_response(message="分类删除成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"删除菜单分类失败: {str(e)}")


@router.get("/restaurant/items")
async def couple_restaurant_items(
    category_id: str | None = Query(None, description="分类ID"),
    keyword: str | None = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        data = [restaurant_item_to_dict(item) for item in list_restaurant_items(db, relationship, category_id, keyword)]
        return success_response(data=data)
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取菜单列表失败: {str(e)}")


@router.get("/restaurant/items/{item_id}")
async def couple_restaurant_item_detail(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        item = get_restaurant_item_detail(db, relationship, item_id)
        return success_response(data=restaurant_item_to_dict(item))
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取菜单详情失败: {str(e)}")


@router.post("/restaurant/items")
async def create_couple_restaurant_item(
    request: CoupleRestaurantItemCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        item = create_restaurant_item(
            db,
            relationship,
            current_user,
            request.category_id,
            request.name,
            request.price,
            request.images,
            request.description
        )
        return success_response(data=restaurant_item_to_dict(item), message="菜单创建成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"创建菜单失败: {str(e)}")


@router.put("/restaurant/items/{item_id}")
async def update_couple_restaurant_item(
    item_id: str,
    request: CoupleRestaurantItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        item = update_restaurant_item(
            db,
            relationship,
            item_id,
            category_id=request.category_id,
            name=request.name,
            price=request.price,
            images=request.images,
            description=request.description,
            description_provided="description" in request.model_fields_set,
            images_provided="images" in request.model_fields_set,
        )
        return success_response(data=restaurant_item_to_dict(item), message="菜单更新成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新菜单失败: {str(e)}")


@router.delete("/restaurant/items/{item_id}")
async def remove_couple_restaurant_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        relationship = require_relationship(db, current_user)
        delete_restaurant_item(db, relationship, item_id)
        return success_response(message="菜单删除成功")
    except CoupleServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"删除菜单失败: {str(e)}")
