"""
菜品API路由

实现吃货端和大厨端的菜品相关接口

Requirements:
- 4.1-4.6: 菜品管理接口（大厨端）
- 5.1-5.5: 菜品查询接口（吃货端）
"""
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_chef, require_foodie
from app.models.user import User
from app.services.dish_service import DishService
from app.schemas.dish import (
    DishCreateRequest,
    DishUpdateRequest,
    DishStatusRequest,
    DishResponse
)
from app.schemas.common import success_response, error_response, paginated_response


router = APIRouter(tags=["菜品"])


# ==================== 吃货端接口 ====================

@router.get("/dishes")
async def get_dishes(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    category: Optional[str] = Query(None, description="分类筛选"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    date_str: Optional[str] = Query(None, alias="date", description="预订日期 YYYY-MM-DD"),
    min_price: Optional[float] = Query(None, ge=0, description="最低价格"),
    max_price: Optional[float] = Query(None, ge=0, description="最高价格"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取菜品列表（吃货端）
    
    仅返回绑定大厨的上架菜品
    
    Requirements: 5.1, 5.2, 5.4
    """
    # 解析日期
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return error_response(400, "日期格式错误，请使用 YYYY-MM-DD 格式")
    
    # 转换价格
    min_price_decimal = Decimal(str(min_price)) if min_price is not None else None
    max_price_decimal = Decimal(str(max_price)) if max_price is not None else None
    
    dish_service = DishService(db)
    dishes, total = dish_service.get_dishes_for_foodie(
        foodie_id=current_user.id,
        page=page,
        page_size=page_size,
        category=category,
        keyword=keyword,
        target_date=target_date,
        min_price=min_price_decimal,
        max_price=max_price_decimal
    )
    
    return paginated_response(
        data=dishes,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/dishes/{dish_id}")
async def get_dish_detail(
    dish_id: str,
    date_str: Optional[str] = Query(None, alias="date", description="预订日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取菜品详情
    
    返回菜品完整信息，包含大厨信息、可用数量、收藏状态
    
    Requirements: 5.3, 5.4, 5.5
    """
    # 解析日期
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return error_response(400, "日期格式错误，请使用 YYYY-MM-DD 格式")
    
    dish_service = DishService(db)
    dish_data = dish_service.get_dish_detail(
        dish_id=dish_id,
        user_id=current_user.id,
        target_date=target_date
    )
    
    if not dish_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="菜品不存在"
        )
    
    return success_response(data=dish_data)


# ==================== 大厨端接口 ====================

@router.post("/chef/dishes")
async def create_dish(
    request: DishCreateRequest,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    创建菜品（大厨端）
    
    Requirements: 4.1, 4.2
    """
    dish_service = DishService(db)
    dish = dish_service.create_dish(
        chef_id=current_user.id,
        name=request.name,
        price=request.price,
        images=request.images,
        description=request.description,
        ingredients=request.ingredients,
        tags=request.tags,
        category=request.category,
        available_dates=request.available_dates,
        max_quantity=request.max_quantity
    )
    
    # 构建响应数据
    dish_data = {
        "id": dish.id,
        "name": dish.name,
        "price": float(dish.price),
        "images": dish.images or [],
        "description": dish.description,
        "ingredients": dish.ingredients or [],
        "tags": dish.tags or [],
        "category": dish.category,
        "available_dates": dish.available_dates or [],
        "max_quantity": dish.max_quantity,
        "rating": float(dish.rating) if dish.rating else 5.0,
        "review_count": dish.review_count or 0,
        "is_on_shelf": dish.is_on_shelf,
        "created_at": dish.created_at.isoformat() if dish.created_at else None
    }
    
    return success_response(data=dish_data, message="菜品创建成功")


@router.put("/chef/dishes/{dish_id}")
async def update_dish(
    dish_id: str,
    request: DishUpdateRequest,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    更新菜品（大厨端）
    
    Requirements: 4.3
    """
    dish_service = DishService(db)
    dish, error = dish_service.update_dish(
        dish_id=dish_id,
        chef_id=current_user.id,
        name=request.name,
        price=request.price,
        images=request.images,
        description=request.description,
        ingredients=request.ingredients,
        tags=request.tags,
        category=request.category,
        available_dates=request.available_dates,
        max_quantity=request.max_quantity
    )
    
    if error:
        if error == "菜品不存在":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error
            )
        elif error == "无权操作此菜品":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error
            )
        return error_response(400, error)
    
    # 构建响应数据
    dish_data = {
        "id": dish.id,
        "name": dish.name,
        "price": float(dish.price),
        "images": dish.images or [],
        "description": dish.description,
        "ingredients": dish.ingredients or [],
        "tags": dish.tags or [],
        "category": dish.category,
        "available_dates": dish.available_dates or [],
        "max_quantity": dish.max_quantity,
        "rating": float(dish.rating) if dish.rating else 5.0,
        "review_count": dish.review_count or 0,
        "is_on_shelf": dish.is_on_shelf,
        "created_at": dish.created_at.isoformat() if dish.created_at else None
    }
    
    return success_response(data=dish_data, message="菜品更新成功")


@router.delete("/chef/dishes/{dish_id}")
async def delete_dish(
    dish_id: str,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    删除菜品（大厨端）
    
    软删除，不会真正删除数据
    
    Requirements: 4.4
    """
    dish_service = DishService(db)
    success, error = dish_service.delete_dish(
        dish_id=dish_id,
        chef_id=current_user.id
    )
    
    if not success:
        if error == "菜品不存在":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error
            )
        elif error == "无权操作此菜品":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error
            )
        return error_response(400, error)
    
    return success_response(message="菜品删除成功")


@router.put("/chef/dishes/{dish_id}/status")
async def toggle_dish_status(
    dish_id: str,
    request: DishStatusRequest,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    切换菜品上下架状态（大厨端）
    
    Requirements: 4.5
    """
    dish_service = DishService(db)
    dish, error = dish_service.toggle_dish_status(
        dish_id=dish_id,
        chef_id=current_user.id,
        is_on_shelf=request.is_on_shelf
    )
    
    if error:
        if error == "菜品不存在":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error
            )
        elif error == "无权操作此菜品":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error
            )
        return error_response(400, error)
    
    status_text = "上架" if request.is_on_shelf else "下架"
    return success_response(
        data={"is_on_shelf": dish.is_on_shelf},
        message=f"菜品已{status_text}"
    )


@router.get("/chef/dishes")
async def get_chef_dishes(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    category: Optional[str] = Query(None, description="分类筛选"),
    is_on_shelf: Optional[bool] = Query(None, description="上架状态筛选"),
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    获取大厨自己的菜品列表（大厨端）
    
    Requirements: 4.6
    """
    dish_service = DishService(db)
    dishes, total = dish_service.get_chef_dishes(
        chef_id=current_user.id,
        page=page,
        page_size=page_size,
        category=category,
        is_on_shelf=is_on_shelf
    )
    
    # 构建响应数据
    dishes_data = []
    for dish in dishes:
        dish_data = {
            "id": dish.id,
            "name": dish.name,
            "price": float(dish.price),
            "images": dish.images or [],
            "description": dish.description,
            "ingredients": dish.ingredients or [],
            "tags": dish.tags or [],
            "category": dish.category,
            "available_dates": dish.available_dates or [],
            "max_quantity": dish.max_quantity,
            "rating": float(dish.rating) if dish.rating else 5.0,
            "review_count": dish.review_count or 0,
            "is_on_shelf": dish.is_on_shelf,
            "created_at": dish.created_at.isoformat() if dish.created_at else None
        }
        dishes_data.append(dish_data)
    
    return paginated_response(
        data=dishes_data,
        page=page,
        page_size=page_size,
        total=total
    )
