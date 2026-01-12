"""
评价服务模块

实现评价的创建、查询和评分更新功能。

Requirements:
- 9.1: 评价提交验证（订单已完成且未评价）
- 9.2: 保存评价（评分、内容、图片）
- 9.3: 更新菜品平均评分
- 9.4: 分页获取评价列表
"""
from typing import Optional, List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.review import Review
from app.models.order import Order, OrderItem
from app.models.dish import Dish
from app.models.user import User


class ReviewServiceError(Exception):
    """评价服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


class ReviewService:
    """评价服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== 评价创建 ====================
    
    def create_review(
        self,
        order_id: str,
        foodie_id: str,
        rating: int,
        content: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> List[Review]:
        """
        创建订单评价
        
        为订单中的每个菜品创建评价记录。
        
        Args:
            order_id: 订单ID
            foodie_id: 吃货用户ID
            rating: 评分 (1-5)
            content: 评价内容
            images: 评价图片列表
            
        Returns:
            创建的评价列表
            
        Requirements: 9.1, 9.2
        """
        # 验证评分范围
        if rating < 1 or rating > 5:
            raise ReviewServiceError("评分必须在1-5之间", code=400)
        
        # 获取订单
        order = self.db.query(Order).filter(
            Order.id == order_id,
            Order.is_deleted == False
        ).first()
        
        if not order:
            raise ReviewServiceError("订单不存在", code=404)
        
        # 验证订单归属 (Requirements: 9.1)
        if order.foodie_id != foodie_id:
            raise ReviewServiceError("无权评价此订单", code=403)
        
        # 验证订单状态 (Requirements: 9.1)
        if order.status != "completed":
            raise ReviewServiceError("只能评价已完成的订单", code=400)
        
        # 验证是否已评价 (Requirements: 9.1)
        if order.is_reviewed:
            raise ReviewServiceError("该订单已评价", code=400)
        
        # 为订单中的每个菜品创建评价
        reviews = []
        for item in order.items:
            review = Review(
                order_id=order_id,
                foodie_id=foodie_id,
                chef_id=order.chef_id,
                dish_id=item.dish_id,
                rating=rating,
                content=content,
                images=images
            )
            self.db.add(review)
            reviews.append(review)
            
            # 更新菜品评分 (Requirements: 9.3)
            self._update_dish_rating(item.dish_id)
        
        # 标记订单已评价
        order.is_reviewed = True
        
        # 更新大厨评分
        self._update_chef_rating(order.chef_id)
        
        self.db.commit()
        
        # 刷新评价对象
        for review in reviews:
            self.db.refresh(review)
        
        return reviews
    
    # ==================== 评价查询 ====================
    
    def get_dish_reviews(
        self,
        dish_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[Review], int]:
        """
        获取菜品评价列表
        
        Args:
            dish_id: 菜品ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            Tuple[List[Review], int]: (评价列表, 总数)
            
        Requirements: 9.4
        """
        query = self.db.query(Review).filter(
            Review.dish_id == dish_id,
            Review.is_deleted == False
        )
        
        total = query.count()
        
        reviews = query.order_by(Review.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return reviews, total
    
    def get_chef_reviews(
        self,
        chef_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[Review], int]:
        """
        获取大厨收到的评价列表
        
        Args:
            chef_id: 大厨ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            Tuple[List[Review], int]: (评价列表, 总数)
        """
        query = self.db.query(Review).filter(
            Review.chef_id == chef_id,
            Review.is_deleted == False
        )
        
        total = query.count()
        
        reviews = query.order_by(Review.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return reviews, total
    
    def get_review_by_id(self, review_id: str) -> Optional[Review]:
        """根据ID获取评价"""
        return self.db.query(Review).filter(
            Review.id == review_id,
            Review.is_deleted == False
        ).first()
    
    def get_order_reviews(self, order_id: str) -> List[Review]:
        """获取订单的所有评价"""
        return self.db.query(Review).filter(
            Review.order_id == order_id,
            Review.is_deleted == False
        ).all()
    
    # ==================== 评分更新 ====================
    
    def _update_dish_rating(self, dish_id: str) -> None:
        """
        更新菜品平均评分
        
        Requirements: 9.3
        """
        # 计算平均评分
        result = self.db.query(
            func.avg(Review.rating).label('avg_rating'),
            func.count(Review.id).label('review_count')
        ).filter(
            Review.dish_id == dish_id,
            Review.is_deleted == False
        ).first()
        
        avg_rating = result.avg_rating if result.avg_rating else Decimal("5.0")
        review_count = result.review_count if result.review_count else 0
        
        # 更新菜品
        dish = self.db.query(Dish).filter(Dish.id == dish_id).first()
        if dish:
            dish.rating = round(float(avg_rating), 1)
            dish.review_count = review_count
    
    def _update_chef_rating(self, chef_id: str) -> None:
        """
        更新大厨平均评分
        
        基于所有收到的评价计算平均分。
        """
        # 计算平均评分
        result = self.db.query(
            func.avg(Review.rating).label('avg_rating')
        ).filter(
            Review.chef_id == chef_id,
            Review.is_deleted == False
        ).first()
        
        avg_rating = result.avg_rating if result.avg_rating else Decimal("5.0")
        
        # 更新大厨
        chef = self.db.query(User).filter(User.id == chef_id).first()
        if chef:
            chef.rating = round(float(avg_rating), 1)
    
    # ==================== 响应构建 ====================
    
    def build_review_response(self, review: Review) -> dict:
        """
        构建评价响应数据
        """
        # 获取评价者信息
        foodie = self.db.query(User).filter(User.id == review.foodie_id).first()
        
        return {
            "id": review.id,
            "order_id": review.order_id,
            "dish_id": review.dish_id,
            "rating": review.rating,
            "content": review.content,
            "images": review.images or [],
            "created_at": review.created_at.isoformat() if review.created_at else None,
            "foodie": {
                "id": foodie.id,
                "nickname": foodie.nickname,
                "avatar": foodie.avatar
            } if foodie else None
        }
    
    def build_review_list_response(self, reviews: List[Review]) -> List[dict]:
        """
        构建评价列表响应数据
        """
        return [self.build_review_response(review) for review in reviews]
