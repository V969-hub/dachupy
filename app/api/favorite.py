"""
收藏管理API接口。

Requirements:
- 15.1: 收藏菜品时创建收藏记录
- 15.2: 取消收藏时删除收藏记录
- 15.3: 返回分页的收藏列表
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.common import success_response, error_response, paginated_response
from app.middleware.auth import get_current_user
from app.services.favorite_service import (
    add_favorite,
    remove_favorite,
    get_user_favorites,
    dish_to_favorite_dict,
    FavoriteServiceError
)


router = APIRouter(prefix="/favorites", tags=["收藏"])


@router.post("/{dish_id}")
async def favorite_dish(
    dish_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    收藏菜品。
    
    将指定菜品添加到用户的收藏列表中。
    
    Args:
        dish_id: 菜品ID
        
    Returns:
        收藏成功的响应
        
    Requirements: 15.1
    """
    try:
        favorite = add_favorite(db, current_user.id, dish_id)
        return success_response(
            data={"dish_id": dish_id, "favorited_at": favorite.created_at.isoformat()},
            message="收藏成功"
        )
    except FavoriteServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"收藏失败: {str(e)}")


@router.delete("/{dish_id}")
async def unfavorite_dish(
    dish_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    取消收藏菜品。
    
    从用户的收藏列表中移除指定菜品。
    
    Args:
        dish_id: 菜品ID
        
    Returns:
        取消收藏成功的响应
        
    Requirements: 15.2
    """
    try:
        remove_favorite(db, current_user.id, dish_id)
        return success_response(
            data={"dish_id": dish_id},
            message="已取消收藏"
        )
    except FavoriteServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"取消收藏失败: {str(e)}")


@router.get("")
async def list_favorites(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取收藏列表。
    
    返回用户收藏的菜品列表，按收藏时间倒序排列。
    
    Args:
        page: 页码（从1开始）
        page_size: 每页数量（1-50）
        
    Returns:
        分页的收藏菜品列表
        
    Requirements: 15.3
    """
    try:
        dishes, total = get_user_favorites(db, current_user.id, page, page_size)
        
        # 转换为字典格式
        dish_list = [dish_to_favorite_dict(dish) for dish in dishes]
        
        return paginated_response(
            data=dish_list,
            page=page,
            page_size=page_size,
            total=total
        )
    except Exception as e:
        return error_response(500, f"获取收藏列表失败: {str(e)}")
