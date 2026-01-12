"""
评价API路由

实现评价提交和查询接口

Requirements:
- 9.1: 评价提交验证（订单已完成且未评价）
- 9.2: 保存评价（评分、内容、图片）
- 9.4: 分页获取评价列表
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_foodie
from app.models.user import User
from app.services.review_service import ReviewService, ReviewServiceError
from app.schemas.common import success_response, error_response, paginated_response


router = APIRouter(tags=["评价"])


# ==================== 请求模型 ====================

class ReviewCreate(BaseModel):
    """创建评价请求"""
    rating: int = Field(..., ge=1, le=5, description="评分 (1-5)")
    content: Optional[str] = Field(None, max_length=500, description="评价内容")
    images: Optional[List[str]] = Field(None, max_length=9, description="评价图片列表")


# ==================== 响应模型 ====================

class ReviewerInfo(BaseModel):
    """评价者信息"""
    id: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class ReviewResponse(BaseModel):
    """评价响应"""
    id: str
    order_id: str
    dish_id: str
    rating: int
    content: Optional[str] = None
    images: List[str] = []
    created_at: Optional[str] = None
    foodie: Optional[ReviewerInfo] = None


# ==================== API接口 ====================

@router.post("/orders/{order_id}/review")
async def create_review(
    order_id: str,
    request: ReviewCreate,
    current_user: User = Depends(require_foodie),
    db: Session = Depends(get_db)
):
    """
    提交订单评价（吃货端）
    
    为已完成的订单提交评价，评价会应用到订单中的所有菜品。
    
    Requirements: 9.1, 9.2
    """
    review_service = ReviewService(db)
    
    try:
        reviews = review_service.create_review(
            order_id=order_id,
            foodie_id=current_user.id,
            rating=request.rating,
            content=request.content,
            images=request.images
        )
        
        # 构建响应数据
        reviews_data = review_service.build_review_list_response(reviews)
        
        return success_response(
            data=reviews_data,
            message="评价提交成功"
        )
        
    except ReviewServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.get("/dishes/{dish_id}/reviews")
async def get_dish_reviews(
    dish_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    db: Session = Depends(get_db)
):
    """
    获取菜品评价列表
    
    获取指定菜品的所有评价，按时间倒序排列。
    
    Requirements: 9.4
    """
    review_service = ReviewService(db)
    
    reviews, total = review_service.get_dish_reviews(
        dish_id=dish_id,
        page=page,
        page_size=page_size
    )
    
    # 构建响应数据
    reviews_data = review_service.build_review_list_response(reviews)
    
    return paginated_response(
        data=reviews_data,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/orders/{order_id}/reviews")
async def get_order_reviews(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取订单的评价
    
    获取指定订单的所有评价记录。
    """
    review_service = ReviewService(db)
    
    reviews = review_service.get_order_reviews(order_id)
    
    # 构建响应数据
    reviews_data = review_service.build_review_list_response(reviews)
    
    return success_response(data=reviews_data)
