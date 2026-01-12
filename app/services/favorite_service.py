"""
收藏服务模块 - 处理用户菜品收藏的操作。

Requirements:
- 15.1: 收藏菜品时创建收藏记录
- 15.2: 取消收藏时删除收藏记录
- 15.3: 返回分页的收藏列表
- 15.4: 返回菜品信息时包含isFavorited标志
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.favorite import Favorite
from app.models.dish import Dish


class FavoriteServiceError(Exception):
    """收藏服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def get_favorite(db: Session, user_id: str, dish_id: str) -> Optional[Favorite]:
    """
    获取用户对某菜品的收藏记录。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        dish_id: 菜品ID
        
    Returns:
        收藏记录，如果不存在则返回None
    """
    return db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.dish_id == dish_id
    ).first()


def is_dish_favorited(db: Session, user_id: str, dish_id: str) -> bool:
    """
    检查用户是否已收藏某菜品。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        dish_id: 菜品ID
        
    Returns:
        是否已收藏
        
    Requirements: 15.4
    """
    return get_favorite(db, user_id, dish_id) is not None


def add_favorite(db: Session, user_id: str, dish_id: str) -> Favorite:
    """
    添加收藏。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        dish_id: 菜品ID
        
    Returns:
        创建的收藏记录
        
    Raises:
        FavoriteServiceError: 如果菜品不存在或已收藏
        
    Requirements: 15.1
    """
    # 检查菜品是否存在且未删除
    dish = db.query(Dish).filter(
        Dish.id == dish_id,
        Dish.is_deleted == False
    ).first()
    
    if not dish:
        raise FavoriteServiceError("菜品不存在", code=404)
    
    # 检查是否已收藏
    existing = get_favorite(db, user_id, dish_id)
    if existing:
        raise FavoriteServiceError("已收藏该菜品", code=400)
    
    # 创建收藏记录
    favorite = Favorite(
        user_id=user_id,
        dish_id=dish_id
    )
    
    try:
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        return favorite
    except IntegrityError:
        db.rollback()
        raise FavoriteServiceError("收藏失败，请重试", code=400)


def remove_favorite(db: Session, user_id: str, dish_id: str) -> bool:
    """
    取消收藏。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        dish_id: 菜品ID
        
    Returns:
        是否成功取消
        
    Raises:
        FavoriteServiceError: 如果未收藏该菜品
        
    Requirements: 15.2
    """
    favorite = get_favorite(db, user_id, dish_id)
    
    if not favorite:
        raise FavoriteServiceError("未收藏该菜品", code=404)
    
    db.delete(favorite)
    db.commit()
    
    return True


def get_user_favorites(
    db: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 10
) -> Tuple[List[Dish], int]:
    """
    获取用户的收藏列表（分页）。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        page: 页码（从1开始）
        page_size: 每页数量
        
    Returns:
        (菜品列表, 总数)
        
    Requirements: 15.3
    """
    # 构建查询：获取用户收藏的菜品
    query = db.query(Dish).join(
        Favorite, Favorite.dish_id == Dish.id
    ).filter(
        Favorite.user_id == user_id,
        Dish.is_deleted == False
    ).order_by(Favorite.created_at.desc())
    
    # 获取总数
    total = query.count()
    
    # 分页
    offset = (page - 1) * page_size
    dishes = query.offset(offset).limit(page_size).all()
    
    return dishes, total


def get_user_favorite_dish_ids(db: Session, user_id: str) -> List[str]:
    """
    获取用户收藏的所有菜品ID列表。
    
    用于批量检查菜品是否被收藏。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        收藏的菜品ID列表
        
    Requirements: 15.4
    """
    favorites = db.query(Favorite.dish_id).filter(
        Favorite.user_id == user_id
    ).all()
    
    return [f.dish_id for f in favorites]


def dish_to_favorite_dict(dish: Dish, chef_info: dict = None) -> dict:
    """
    将菜品对象转换为收藏列表中的字典格式。
    
    Args:
        dish: 菜品对象
        chef_info: 大厨信息（可选）
        
    Returns:
        菜品信息字典
    """
    result = {
        "id": dish.id,
        "name": dish.name,
        "price": float(dish.price),
        "images": dish.images or [],
        "description": dish.description,
        "tags": dish.tags or [],
        "category": dish.category,
        "rating": float(dish.rating) if dish.rating else 5.0,
        "review_count": dish.review_count or 0,
        "is_on_shelf": dish.is_on_shelf,
        "is_favorited": True,  # 在收藏列表中，肯定是已收藏
        "created_at": dish.created_at.isoformat() if dish.created_at else None
    }
    
    # 添加大厨信息
    if chef_info:
        result["chef"] = chef_info
    elif dish.chef:
        result["chef"] = {
            "id": dish.chef.id,
            "nickname": dish.chef.nickname,
            "avatar": dish.chef.avatar,
            "rating": float(dish.chef.rating) if dish.chef.rating else 5.0
        }
    
    return result
