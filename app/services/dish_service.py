"""
菜品服务模块

实现菜品的CRUD操作、搜索筛选和可用数量计算。

Requirements:
- 4.1-4.6: 菜品管理接口
- 5.1-5.5: 菜品查询接口
"""
from typing import Optional, List, Tuple
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.dish import Dish, DailyDishQuantity
from app.models.binding import Binding
from app.models.favorite import Favorite
from app.models.user import User


class DishService:
    """菜品服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== 大厨端操作 ====================
    
    def create_dish(
        self,
        chef_id: str,
        name: str,
        price: Decimal,
        images: List[str],
        description: Optional[str] = None,
        ingredients: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        available_dates: Optional[List[str]] = None,
        max_quantity: int = 10
    ) -> Dish:
        """
        创建菜品
        
        Requirements: 4.1, 4.2
        """
        dish = Dish(
            chef_id=chef_id,
            name=name,
            price=price,
            images=images,
            description=description,
            ingredients=ingredients,
            tags=tags,
            category=category,
            available_dates=available_dates,
            max_quantity=max_quantity,
            is_on_shelf=True,
            is_deleted=False
        )
        self.db.add(dish)
        self.db.commit()
        self.db.refresh(dish)
        return dish

    
    def update_dish(
        self,
        dish_id: str,
        chef_id: str,
        name: Optional[str] = None,
        price: Optional[Decimal] = None,
        images: Optional[List[str]] = None,
        description: Optional[str] = None,
        ingredients: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        available_dates: Optional[List[str]] = None,
        max_quantity: Optional[int] = None
    ) -> Tuple[Optional[Dish], str]:
        """
        更新菜品
        
        Requirements: 4.3
        
        Returns:
            Tuple[Optional[Dish], str]: (菜品对象, 错误信息)
        """
        dish = self.get_dish_by_id(dish_id)
        if not dish:
            return None, "菜品不存在"
        
        # 验证所有权
        if dish.chef_id != chef_id:
            return None, "无权操作此菜品"
        
        # 更新字段
        if name is not None:
            dish.name = name
        if price is not None:
            dish.price = price
        if images is not None:
            dish.images = images
        if description is not None:
            dish.description = description
        if ingredients is not None:
            dish.ingredients = ingredients
        if tags is not None:
            dish.tags = tags
        if category is not None:
            dish.category = category
        if available_dates is not None:
            dish.available_dates = available_dates
        if max_quantity is not None:
            dish.max_quantity = max_quantity
        
        self.db.commit()
        self.db.refresh(dish)
        return dish, ""
    
    def delete_dish(self, dish_id: str, chef_id: str) -> Tuple[bool, str]:
        """
        软删除菜品
        
        Requirements: 4.4
        
        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        dish = self.get_dish_by_id(dish_id)
        if not dish:
            return False, "菜品不存在"
        
        # 验证所有权
        if dish.chef_id != chef_id:
            return False, "无权操作此菜品"
        
        dish.is_deleted = True
        self.db.commit()
        return True, ""
    
    def toggle_dish_status(
        self,
        dish_id: str,
        chef_id: str,
        is_on_shelf: bool
    ) -> Tuple[Optional[Dish], str]:
        """
        切换菜品上下架状态
        
        Requirements: 4.5
        
        Returns:
            Tuple[Optional[Dish], str]: (菜品对象, 错误信息)
        """
        dish = self.get_dish_by_id(dish_id)
        if not dish:
            return None, "菜品不存在"
        
        # 验证所有权
        if dish.chef_id != chef_id:
            return None, "无权操作此菜品"
        
        dish.is_on_shelf = is_on_shelf
        self.db.commit()
        self.db.refresh(dish)
        return dish, ""

    
    # ==================== 查询操作 ====================
    
    def get_dish_by_id(self, dish_id: str) -> Optional[Dish]:
        """根据ID获取菜品"""
        return self.db.query(Dish).filter(
            Dish.id == dish_id,
            Dish.is_deleted == False
        ).first()
    
    def get_chef_dishes(
        self,
        chef_id: str,
        page: int = 1,
        page_size: int = 10,
        category: Optional[str] = None,
        is_on_shelf: Optional[bool] = None
    ) -> Tuple[List[Dish], int]:
        """
        获取大厨的菜品列表
        
        Requirements: 4.6
        
        Returns:
            Tuple[List[Dish], int]: (菜品列表, 总数)
        """
        query = self.db.query(Dish).filter(
            Dish.chef_id == chef_id,
            Dish.is_deleted == False
        )
        
        if category:
            query = query.filter(Dish.category == category)
        
        if is_on_shelf is not None:
            query = query.filter(Dish.is_on_shelf == is_on_shelf)
        
        total = query.count()
        
        dishes = query.order_by(Dish.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return dishes, total
    
    def get_dishes_for_foodie(
        self,
        foodie_id: str,
        page: int = 1,
        page_size: int = 10,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        target_date: Optional[date] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None
    ) -> Tuple[List[dict], int]:
        """
        获取吃货可见的菜品列表（仅绑定大厨的菜品）
        
        Requirements: 5.1, 5.2, 5.4
        
        Returns:
            Tuple[List[dict], int]: (菜品列表(含额外信息), 总数)
        """
        # 获取绑定的大厨
        binding = self.db.query(Binding).filter(
            Binding.foodie_id == foodie_id
        ).first()
        
        if not binding:
            return [], 0
        
        chef_id = binding.chef_id
        
        # 构建查询
        query = self.db.query(Dish).filter(
            Dish.chef_id == chef_id,
            Dish.is_deleted == False,
            Dish.is_on_shelf == True
        )
        
        # 分类筛选
        if category:
            query = query.filter(Dish.category == category)
        
        # 关键词搜索（名称或食材）
        if keyword:
            keyword_pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    Dish.name.like(keyword_pattern),
                    Dish.description.like(keyword_pattern)
                )
            )
        
        # 价格范围筛选
        if min_price is not None:
            query = query.filter(Dish.price >= min_price)
        if max_price is not None:
            query = query.filter(Dish.price <= max_price)
        
        total = query.count()
        
        dishes = query.order_by(Dish.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        # 构建返回数据，包含额外信息
        result = []
        for dish in dishes:
            dish_data = self._build_dish_response(dish, foodie_id, target_date)
            result.append(dish_data)
        
        return result, total

    
    def get_dish_detail(
        self,
        dish_id: str,
        user_id: Optional[str] = None,
        target_date: Optional[date] = None
    ) -> Optional[dict]:
        """
        获取菜品详情
        
        Requirements: 5.3
        
        Returns:
            Optional[dict]: 菜品详情（含大厨信息、可用数量、收藏状态）
        """
        dish = self.get_dish_by_id(dish_id)
        if not dish:
            return None
        
        return self._build_dish_response(dish, user_id, target_date, include_chef=True)
    
    def _build_dish_response(
        self,
        dish: Dish,
        user_id: Optional[str] = None,
        target_date: Optional[date] = None,
        include_chef: bool = False
    ) -> dict:
        """
        构建菜品响应数据
        
        Requirements: 5.4, 5.5
        """
        # 计算可用数量
        available_quantity = self.get_available_quantity(dish.id, target_date)
        
        # 检查是否收藏
        is_favorited = False
        if user_id:
            favorite = self.db.query(Favorite).filter(
                Favorite.user_id == user_id,
                Favorite.dish_id == dish.id
            ).first()
            is_favorited = favorite is not None
        
        result = {
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
            "available_quantity": available_quantity,
            "is_favorited": is_favorited,
            "created_at": dish.created_at.isoformat() if dish.created_at else None
        }
        
        # 包含大厨信息
        if include_chef and dish.chef:
            result["chef"] = {
                "id": dish.chef.id,
                "nickname": dish.chef.nickname,
                "avatar": dish.chef.avatar,
                "rating": float(dish.chef.rating) if dish.chef.rating else 5.0,
                "introduction": dish.chef.introduction,
                "specialties": dish.chef.specialties or []
            }
        
        return result
    
    # ==================== 数量计算 ====================
    
    def get_available_quantity(
        self,
        dish_id: str,
        target_date: Optional[date] = None
    ) -> int:
        """
        计算菜品在指定日期的可用数量
        
        Requirements: 5.4
        
        Returns:
            int: 可用数量
        """
        dish = self.db.query(Dish).filter(Dish.id == dish_id).first()
        if not dish:
            return 0
        
        if target_date is None:
            target_date = date.today()
        
        # 获取当日已预订数量
        daily_quantity = self.db.query(DailyDishQuantity).filter(
            DailyDishQuantity.dish_id == dish_id,
            DailyDishQuantity.date == target_date
        ).first()
        
        booked = daily_quantity.booked_quantity if daily_quantity else 0
        available = dish.max_quantity - booked
        
        return max(0, available)
    
    def update_booked_quantity(
        self,
        dish_id: str,
        target_date: date,
        quantity: int
    ) -> bool:
        """
        更新菜品预订数量
        
        Args:
            dish_id: 菜品ID
            target_date: 日期
            quantity: 增加的数量（可为负数表示取消）
            
        Returns:
            bool: 是否成功
        """
        daily_quantity = self.db.query(DailyDishQuantity).filter(
            DailyDishQuantity.dish_id == dish_id,
            DailyDishQuantity.date == target_date
        ).first()
        
        if daily_quantity:
            daily_quantity.booked_quantity += quantity
            if daily_quantity.booked_quantity < 0:
                daily_quantity.booked_quantity = 0
        else:
            if quantity > 0:
                daily_quantity = DailyDishQuantity(
                    dish_id=dish_id,
                    date=target_date,
                    booked_quantity=quantity
                )
                self.db.add(daily_quantity)
        
        self.db.commit()
        return True
    
    def check_dish_availability(
        self,
        dish_id: str,
        target_date: date,
        quantity: int
    ) -> Tuple[bool, str]:
        """
        检查菜品是否可预订
        
        Returns:
            Tuple[bool, str]: (是否可用, 错误信息)
        """
        dish = self.get_dish_by_id(dish_id)
        if not dish:
            return False, "菜品不存在"
        
        if not dish.is_on_shelf:
            return False, "菜品已下架"
        
        available = self.get_available_quantity(dish_id, target_date)
        if available < quantity:
            return False, f"库存不足，当前可用数量: {available}"
        
        return True, ""
