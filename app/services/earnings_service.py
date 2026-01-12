"""
收益服务模块

实现大厨收益统计、图表数据聚合和收益明细查询功能。

Requirements:
- 14.1: 收益汇总（总收益、订单收益、打赏收益）
- 14.2: 收益图表（周/月聚合数据）
- 14.3: 收益明细（分页交易列表）
- 14.4: 收益计算（已完成订单 + 已支付打赏）
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case

from app.models.order import Order
from app.models.tip import Tip
from app.models.user import User


logger = logging.getLogger(__name__)


class EarningsServiceError(Exception):
    """收益服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


class EarningsService:
    """收益服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_earnings_summary(self, chef_id: str) -> Dict[str, Any]:
        """
        获取收益汇总
        
        计算大厨的总收益，包括：
        - 总收益 = 订单收益 + 打赏收益
        - 订单收益 = 所有已完成订单的总价之和
        - 打赏收益 = 所有已支付打赏的金额之和
        - 本月收益
        - 本周收益
        
        Args:
            chef_id: 大厨ID
            
        Returns:
            收益汇总数据
            
        Requirements: 14.1, 14.4
        """
        # 验证大厨存在
        chef = self.db.query(User).filter(
            User.id == chef_id,
            User.role == "chef",
            User.is_deleted == False
        ).first()
        
        if not chef:
            raise EarningsServiceError("大厨不存在", code=404)
        
        # 计算订单收益（已完成订单）
        order_earnings = self._calculate_order_earnings(chef_id)
        
        # 计算打赏收益（已支付打赏）
        tip_earnings = self._calculate_tip_earnings(chef_id)
        
        # 总收益
        total_earnings = order_earnings + tip_earnings
        
        # 计算本月收益
        this_month_earnings = self._calculate_period_earnings(
            chef_id,
            self._get_month_start(),
            datetime.now()
        )
        
        # 计算本周收益
        this_week_earnings = self._calculate_period_earnings(
            chef_id,
            self._get_week_start(),
            datetime.now()
        )
        
        return {
            "total_earnings": float(total_earnings),
            "order_earnings": float(order_earnings),
            "tip_earnings": float(tip_earnings),
            "this_month": float(this_month_earnings),
            "this_week": float(this_week_earnings)
        }

    
    def get_earnings_chart(
        self,
        chef_id: str,
        chart_type: str = "weekly"
    ) -> Dict[str, Any]:
        """
        获取收益图表数据
        
        按周或月聚合收益数据，用于前端图表展示。
        
        Args:
            chef_id: 大厨ID
            chart_type: 图表类型 ("weekly" 或 "monthly")
            
        Returns:
            图表数据，包含日期标签和对应的收益值
            
        Requirements: 14.2
        """
        # 验证大厨存在
        chef = self.db.query(User).filter(
            User.id == chef_id,
            User.role == "chef",
            User.is_deleted == False
        ).first()
        
        if not chef:
            raise EarningsServiceError("大厨不存在", code=404)
        
        if chart_type == "weekly":
            return self._get_weekly_chart_data(chef_id)
        elif chart_type == "monthly":
            return self._get_monthly_chart_data(chef_id)
        else:
            raise EarningsServiceError("无效的图表类型，请使用 weekly 或 monthly", code=400)
    
    def get_earnings_detail(
        self,
        chef_id: str,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取收益明细
        
        返回分页的交易列表，包括订单收入和打赏收入。
        
        Args:
            chef_id: 大厨ID
            page: 页码
            page_size: 每页数量
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            transaction_type: 交易类型筛选 ("order" 或 "tip"，可选）
            
        Returns:
            (交易列表, 总数)
            
        Requirements: 14.3
        """
        # 验证大厨存在
        chef = self.db.query(User).filter(
            User.id == chef_id,
            User.role == "chef",
            User.is_deleted == False
        ).first()
        
        if not chef:
            raise EarningsServiceError("大厨不存在", code=404)
        
        # 获取订单收入记录
        order_records = []
        if transaction_type is None or transaction_type == "order":
            order_records = self._get_order_earnings_records(
                chef_id, start_date, end_date
            )
        
        # 获取打赏收入记录
        tip_records = []
        if transaction_type is None or transaction_type == "tip":
            tip_records = self._get_tip_earnings_records(
                chef_id, start_date, end_date
            )
        
        # 合并并按时间排序
        all_records = order_records + tip_records
        all_records.sort(key=lambda x: x["created_at"], reverse=True)
        
        # 计算总数
        total = len(all_records)
        
        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_records = all_records[start_idx:end_idx]
        
        return paginated_records, total

    
    # ==================== 私有辅助方法 ====================
    
    def _calculate_order_earnings(self, chef_id: str) -> Decimal:
        """
        计算订单收益
        
        统计所有已完成订单的总价之和。
        
        Requirements: 14.4
        """
        result = self.db.query(
            func.coalesce(func.sum(Order.total_price), 0)
        ).filter(
            Order.chef_id == chef_id,
            Order.status == "completed",
            Order.is_deleted == False
        ).scalar()
        
        return Decimal(str(result)) if result else Decimal("0.00")
    
    def _calculate_tip_earnings(self, chef_id: str) -> Decimal:
        """
        计算打赏收益
        
        统计所有已支付打赏的金额之和。
        
        Requirements: 14.4
        """
        result = self.db.query(
            func.coalesce(func.sum(Tip.amount), 0)
        ).filter(
            Tip.chef_id == chef_id,
            Tip.status == "paid"
        ).scalar()
        
        return Decimal(str(result)) if result else Decimal("0.00")
    
    def _calculate_period_earnings(
        self,
        chef_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Decimal:
        """
        计算指定时间段内的收益
        
        包括订单收益和打赏收益。
        """
        # 订单收益
        order_earnings = self.db.query(
            func.coalesce(func.sum(Order.total_price), 0)
        ).filter(
            Order.chef_id == chef_id,
            Order.status == "completed",
            Order.is_deleted == False,
            Order.completed_at >= start_time,
            Order.completed_at <= end_time
        ).scalar()
        
        # 打赏收益
        tip_earnings = self.db.query(
            func.coalesce(func.sum(Tip.amount), 0)
        ).filter(
            Tip.chef_id == chef_id,
            Tip.status == "paid",
            Tip.created_at >= start_time,
            Tip.created_at <= end_time
        ).scalar()
        
        order_total = Decimal(str(order_earnings)) if order_earnings else Decimal("0.00")
        tip_total = Decimal(str(tip_earnings)) if tip_earnings else Decimal("0.00")
        
        return order_total + tip_total
    
    def _get_week_start(self) -> datetime:
        """获取本周开始时间（周一）"""
        today = date.today()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        return datetime.combine(monday, datetime.min.time())
    
    def _get_month_start(self) -> datetime:
        """获取本月开始时间"""
        today = date.today()
        first_day = today.replace(day=1)
        return datetime.combine(first_day, datetime.min.time())

    
    def _get_weekly_chart_data(self, chef_id: str) -> Dict[str, Any]:
        """
        获取最近7天的收益数据
        
        Requirements: 14.2
        """
        labels = []
        order_data = []
        tip_data = []
        total_data = []
        
        today = date.today()
        
        for i in range(6, -1, -1):
            target_date = today - timedelta(days=i)
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())
            
            # 当天订单收益
            day_order_earnings = self.db.query(
                func.coalesce(func.sum(Order.total_price), 0)
            ).filter(
                Order.chef_id == chef_id,
                Order.status == "completed",
                Order.is_deleted == False,
                Order.completed_at >= start_time,
                Order.completed_at <= end_time
            ).scalar()
            
            # 当天打赏收益
            day_tip_earnings = self.db.query(
                func.coalesce(func.sum(Tip.amount), 0)
            ).filter(
                Tip.chef_id == chef_id,
                Tip.status == "paid",
                Tip.created_at >= start_time,
                Tip.created_at <= end_time
            ).scalar()
            
            order_amount = float(day_order_earnings) if day_order_earnings else 0.0
            tip_amount = float(day_tip_earnings) if day_tip_earnings else 0.0
            
            labels.append(target_date.strftime("%m-%d"))
            order_data.append(order_amount)
            tip_data.append(tip_amount)
            total_data.append(order_amount + tip_amount)
        
        return {
            "type": "weekly",
            "labels": labels,
            "datasets": {
                "order": order_data,
                "tip": tip_data,
                "total": total_data
            }
        }
    
    def _get_monthly_chart_data(self, chef_id: str) -> Dict[str, Any]:
        """
        获取最近30天的收益数据
        
        Requirements: 14.2
        """
        labels = []
        order_data = []
        tip_data = []
        total_data = []
        
        today = date.today()
        
        for i in range(29, -1, -1):
            target_date = today - timedelta(days=i)
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())
            
            # 当天订单收益
            day_order_earnings = self.db.query(
                func.coalesce(func.sum(Order.total_price), 0)
            ).filter(
                Order.chef_id == chef_id,
                Order.status == "completed",
                Order.is_deleted == False,
                Order.completed_at >= start_time,
                Order.completed_at <= end_time
            ).scalar()
            
            # 当天打赏收益
            day_tip_earnings = self.db.query(
                func.coalesce(func.sum(Tip.amount), 0)
            ).filter(
                Tip.chef_id == chef_id,
                Tip.status == "paid",
                Tip.created_at >= start_time,
                Tip.created_at <= end_time
            ).scalar()
            
            order_amount = float(day_order_earnings) if day_order_earnings else 0.0
            tip_amount = float(day_tip_earnings) if day_tip_earnings else 0.0
            
            labels.append(target_date.strftime("%m-%d"))
            order_data.append(order_amount)
            tip_data.append(tip_amount)
            total_data.append(order_amount + tip_amount)
        
        return {
            "type": "monthly",
            "labels": labels,
            "datasets": {
                "order": order_data,
                "tip": tip_data,
                "total": total_data
            }
        }

    
    def _get_order_earnings_records(
        self,
        chef_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        获取订单收入记录
        
        Requirements: 14.3
        """
        query = self.db.query(Order).filter(
            Order.chef_id == chef_id,
            Order.status == "completed",
            Order.is_deleted == False
        )
        
        if start_date:
            start_time = datetime.combine(start_date, datetime.min.time())
            query = query.filter(Order.completed_at >= start_time)
        
        if end_date:
            end_time = datetime.combine(end_date, datetime.max.time())
            query = query.filter(Order.completed_at <= end_time)
        
        orders = query.all()
        
        records = []
        for order in orders:
            # 获取吃货信息
            foodie = self.db.query(User).filter(User.id == order.foodie_id).first()
            
            records.append({
                "id": order.id,
                "type": "order",
                "amount": float(order.total_price),
                "order_no": order.order_no,
                "description": f"订单收入 - {order.order_no}",
                "created_at": order.completed_at.isoformat() if order.completed_at else order.created_at.isoformat(),
                "foodie": {
                    "id": foodie.id,
                    "nickname": foodie.nickname,
                    "avatar": foodie.avatar
                } if foodie else None
            })
        
        return records
    
    def _get_tip_earnings_records(
        self,
        chef_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        获取打赏收入记录
        
        Requirements: 14.3
        """
        query = self.db.query(Tip).filter(
            Tip.chef_id == chef_id,
            Tip.status == "paid"
        )
        
        if start_date:
            start_time = datetime.combine(start_date, datetime.min.time())
            query = query.filter(Tip.created_at >= start_time)
        
        if end_date:
            end_time = datetime.combine(end_date, datetime.max.time())
            query = query.filter(Tip.created_at <= end_time)
        
        tips = query.all()
        
        records = []
        for tip in tips:
            # 获取吃货信息
            foodie = self.db.query(User).filter(User.id == tip.foodie_id).first()
            
            records.append({
                "id": tip.id,
                "type": "tip",
                "amount": float(tip.amount),
                "message": tip.message,
                "description": f"打赏收入{' - ' + tip.message if tip.message else ''}",
                "created_at": tip.created_at.isoformat() if tip.created_at else None,
                "order_id": tip.order_id,
                "foodie": {
                    "id": foodie.id,
                    "nickname": foodie.nickname,
                    "avatar": foodie.avatar
                } if foodie else None
            })
        
        return records
