"""
打赏服务模块

实现打赏创建和查询功能。

Requirements:
- 10.1: 创建打赏并完成餐币结算
- 10.2: 打赏成功后保存记录并通知大厨
- 10.3: 查询打赏记录
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
import logging

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.tip import Tip
from app.models.notification import Notification
from app.models.user import User
from app.models.order import Order
from app.services.wallet_service import WalletService, WalletServiceError, normalize_decimal_amount


logger = logging.getLogger(__name__)


class TipServiceError(Exception):
    """打赏服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


class TipService:
    """打赏服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_tip(
        self,
        foodie_id: str,
        chef_id: str,
        amount: Decimal,
        message: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> Tip:
        """
        创建打赏记录
        
        Args:
            foodie_id: 吃货ID
            chef_id: 大厨ID
            amount: 打赏金额
            message: 留言
            order_id: 关联订单ID（可选）
            
        Returns:
            创建的打赏记录
            
        Requirements: 10.1
        """
        # 验证吃货存在
        foodie = self.db.query(User).filter(
            User.id == foodie_id,
            User.is_deleted == False
        ).first()
        
        if not foodie:
            raise TipServiceError("用户不存在", code=404)
        
        # 验证大厨存在且角色正确
        chef = self.db.query(User).filter(
            User.id == chef_id,
            User.role == "chef",
            User.is_deleted == False
        ).first()
        
        if not chef:
            raise TipServiceError("大厨不存在", code=404)
        
        # 验证金额
        if amount <= 0:
            raise TipServiceError("打赏金额必须大于0", code=400)
        
        # 如果指定了订单，验证订单存在且属于该吃货和大厨
        if order_id:
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.foodie_id == foodie_id,
                Order.chef_id == chef_id,
                Order.is_deleted == False
            ).first()
            
            if not order:
                raise TipServiceError("订单不存在或不属于当前用户", code=404)
        
        # 创建打赏记录
        tip = Tip(
            foodie_id=foodie_id,
            chef_id=chef_id,
            amount=amount,
            message=message,
            order_id=order_id,
            status="pending"
        )
        
        self.db.add(tip)
        self.db.commit()
        self.db.refresh(tip)
        
        logger.info(f"创建打赏记录: tip_id={tip.id}, amount={amount}")
        
        return tip

    def create_tip_with_virtual_coin_payment(
        self,
        foodie_id: str,
        chef_id: str,
        amount: Decimal,
        message: Optional[str] = None,
        order_id: Optional[str] = None,
    ) -> Tip:
        """Create a paid tip using the virtual coin wallet."""
        foodie = self.db.query(User).filter(
            User.id == foodie_id,
            User.is_deleted == False
        ).first()
        if not foodie:
            raise TipServiceError("用户不存在", code=404)

        chef = self.db.query(User).filter(
            User.id == chef_id,
            User.role == "chef",
            User.is_deleted == False
        ).first()
        if not chef:
            raise TipServiceError("大厨不存在", code=404)

        normalized_amount = normalize_decimal_amount(amount)
        if normalized_amount <= Decimal("0.00"):
            raise TipServiceError("打赏金额必须大于0", code=400)

        if order_id:
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.foodie_id == foodie_id,
                Order.chef_id == chef_id,
                Order.is_deleted == False
            ).first()
            if not order:
                raise TipServiceError("订单不存在或不属于当前用户", code=404)

        wallet_service = WalletService(self.db)

        try:
            wallet_service.ensure_sufficient_balance(foodie, normalized_amount)

            tip = Tip(
                foodie_id=foodie_id,
                chef_id=chef_id,
                amount=normalized_amount,
                message=message,
                order_id=order_id,
                status="paid",
            )
            self.db.add(tip)
            self.db.flush()

            wallet_service.deduct_balance(
                user=foodie,
                amount=normalized_amount,
                transaction_type="tip_payment",
                note=f"打赏大厨 {chef.nickname or chef.id}：{message or '感谢支持'}",
                related_order_id=order_id,
            )

            self.db.add(Notification(
                user_id=chef.id,
                type="tip",
                title="收到打赏",
                content=f"您收到一笔 {normalized_amount:.2f} 餐币打赏",
                data={
                    "tip_id": tip.id,
                    "amount": float(normalized_amount),
                    "message": message,
                },
            ))
            self.db.commit()
            self.db.refresh(tip)
            self.db.refresh(foodie)
            return tip
        except WalletServiceError as exc:
            self.db.rollback()
            raise TipServiceError(exc.message, code=exc.code) from exc
        except Exception:
            self.db.rollback()
            raise
    
    def get_tip_by_id(self, tip_id: str) -> Optional[Tip]:
        """
        根据ID获取打赏记录
        
        Args:
            tip_id: 打赏ID
            
        Returns:
            打赏记录或None
        """
        return self.db.query(Tip).filter(Tip.id == tip_id).first()
    
    def get_tips_by_foodie(
        self,
        foodie_id: str,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None
    ) -> tuple[List[Tip], int]:
        """
        获取吃货的打赏记录
        
        Args:
            foodie_id: 吃货ID
            page: 页码
            page_size: 每页数量
            status: 状态筛选
            
        Returns:
            (打赏列表, 总数)
            
        Requirements: 10.3
        """
        query = self.db.query(Tip).filter(Tip.foodie_id == foodie_id)
        
        # 状态筛选
        if status:
            query = query.filter(Tip.status == status)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        tips = query.order_by(desc(Tip.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return tips, total
    
    def get_tips_by_chef(
        self,
        chef_id: str,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None
    ) -> tuple[List[Tip], int]:
        """
        获取大厨收到的打赏记录
        
        Args:
            chef_id: 大厨ID
            page: 页码
            page_size: 每页数量
            status: 状态筛选
            
        Returns:
            (打赏列表, 总数)
            
        Requirements: 10.3
        """
        query = self.db.query(Tip).filter(Tip.chef_id == chef_id)
        
        # 状态筛选
        if status:
            query = query.filter(Tip.status == status)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        tips = query.order_by(desc(Tip.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return tips, total
    
    def update_tip_status(
        self,
        tip_id: str,
        status: str,
        payment_id: Optional[str] = None
    ) -> Optional[Tip]:
        """
        更新打赏状态
        
        Args:
            tip_id: 打赏ID
            status: 新状态
            payment_id: 支付订单号
            
        Returns:
            更新后的打赏记录
        """
        tip = self.db.query(Tip).filter(Tip.id == tip_id).first()
        
        if not tip:
            return None
        
        tip.status = status
        if payment_id:
            tip.payment_id = payment_id
        
        self.db.commit()
        self.db.refresh(tip)
        
        return tip
    
    def get_chef_tip_statistics(self, chef_id: str) -> Dict[str, Any]:
        """
        获取大厨打赏统计
        
        Args:
            chef_id: 大厨ID
            
        Returns:
            统计数据
        """
        from sqlalchemy import func
        
        # 查询已支付的打赏
        result = self.db.query(
            func.count(Tip.id).label("total_count"),
            func.sum(Tip.amount).label("total_amount")
        ).filter(
            Tip.chef_id == chef_id,
            Tip.status == "paid"
        ).first()
        
        return {
            "total_count": result.total_count or 0,
            "total_amount": float(result.total_amount or 0)
        }
