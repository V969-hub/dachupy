"""
订单服务模块

实现订单的创建、查询、状态管理等功能。

Requirements:
- 6.1-6.6: 订单管理接口
- 7.1-7.6: 订单状态管理接口
"""
from typing import Optional, List, Tuple
from datetime import datetime, date
from decimal import Decimal
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.order import Order, OrderItem
from app.models.dish import Dish, DailyDishQuantity
from app.models.binding import Binding
from app.models.address import Address
from app.models.notification import Notification
from app.models.user import User


class OrderServiceError(Exception):
    """订单服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


# 订单状态转换规则 (Requirements: 7.6)
# 定义每个状态可以转换到的目标状态
ORDER_STATUS_TRANSITIONS = {
    "unpaid": ["pending", "cancelled"],  # 未支付 -> 待接单/已取消
    "pending": ["accepted", "cancelled"],  # 待接单 -> 已接单/已取消
    "accepted": ["cooking", "cancelled"],  # 已接单 -> 烹饪中/已取消
    "cooking": ["delivering"],  # 烹饪中 -> 配送中
    "delivering": ["completed"],  # 配送中 -> 已完成
    "completed": [],  # 已完成 -> 无
    "cancelled": []  # 已取消 -> 无
}

# 可取消的状态 (Requirements: 7.1)
CANCELLABLE_STATUSES = ["unpaid", "pending", "accepted"]


def generate_order_no() -> str:
    """
    生成唯一订单号
    
    格式: 年月日时分秒 + 微秒(6位) + 8位随机数
    例如: 20240115123045123456 + 12345678
    
    使用微秒级时间戳 + 8位随机数确保唯一性
    
    Requirements: 6.2
    """
    now = datetime.now()
    # 使用秒级时间戳(14位) + 微秒(6位) + 8位随机数 = 28位
    date_part = now.strftime("%Y%m%d%H%M%S") + f"{now.microsecond:06d}"
    # 使用uuid的hex表示，取8位确保足够的随机性
    random_part = uuid.uuid4().hex[:8]
    return f"{date_part}{random_part}"


def calculate_total_price(items: List[dict], db: Session) -> Tuple[Decimal, List[dict]]:
    """
    计算订单总价并验证菜品信息
    
    Args:
        items: 订单项列表 [{"dish_id": str, "quantity": int}, ...]
        db: 数据库会话
        
    Returns:
        Tuple[Decimal, List[dict]]: (总价, 订单项详情列表)
        
    Requirements: 6.3
    """
    total = Decimal("0.00")
    item_details = []
    
    for item in items:
        dish = db.query(Dish).filter(
            Dish.id == item["dish_id"],
            Dish.is_deleted == False
        ).first()
        
        if not dish:
            raise OrderServiceError(f"菜品不存在: {item['dish_id']}", code=404)
        
        if not dish.is_on_shelf:
            raise OrderServiceError(f"菜品已下架: {dish.name}", code=400)
        
        quantity = item.get("quantity", 1)
        item_total = dish.price * quantity
        total += item_total
        
        item_details.append({
            "dish_id": dish.id,
            "dish_name": dish.name,
            "dish_image": dish.images[0] if dish.images else None,
            "price": dish.price,
            "quantity": quantity,
            "chef_id": dish.chef_id
        })
    
    return total, item_details


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """
    验证订单状态转换是否合法
    
    Requirements: 7.6
    """
    allowed_transitions = ORDER_STATUS_TRANSITIONS.get(current_status, [])
    return new_status in allowed_transitions


class OrderService:
    """订单服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== 订单创建 ====================
    
    def create_order(
        self,
        foodie_id: str,
        items: List[dict],
        delivery_time: datetime,
        address_id: str,
        remarks: Optional[str] = None
    ) -> Order:
        """
        创建订单
        
        Args:
            foodie_id: 吃货用户ID
            items: 订单项列表 [{"dish_id": str, "quantity": int}, ...]
            delivery_time: 配送时间
            address_id: 地址ID
            remarks: 备注
            
        Returns:
            创建的订单对象
            
        Requirements: 6.1, 6.2, 6.3, 6.4
        """
        # 验证吃货身份
        foodie = self.db.query(User).filter(
            User.id == foodie_id,
            User.is_deleted == False
        ).first()
        
        if not foodie:
            raise OrderServiceError("用户不存在", code=404)
        
        if foodie.role != "foodie":
            raise OrderServiceError("只有吃货可以创建订单", code=403)
        
        # 获取绑定的大厨
        binding = self.db.query(Binding).filter(
            Binding.foodie_id == foodie_id
        ).first()
        
        if not binding:
            raise OrderServiceError("请先绑定大厨", code=400)
        
        chef_id = binding.chef_id
        
        # 验证地址
        address = self.db.query(Address).filter(
            Address.id == address_id,
            Address.user_id == foodie_id,
            Address.is_deleted == False
        ).first()
        
        if not address:
            raise OrderServiceError("地址不存在或无权使用", code=404)
        
        # 计算总价并获取菜品详情 (Requirements: 6.3)
        total_price, item_details = calculate_total_price(items, self.db)
        
        # 验证所有菜品属于绑定的大厨
        for item_detail in item_details:
            if item_detail["chef_id"] != chef_id:
                raise OrderServiceError(
                    f"菜品 {item_detail['dish_name']} 不属于您绑定的大厨",
                    code=400
                )
        
        # 验证菜品可用数量 (Requirements: 6.1)
        delivery_date = delivery_time.date()
        for item in items:
            available = self._check_dish_availability(
                item["dish_id"],
                delivery_date,
                item.get("quantity", 1)
            )
            if not available[0]:
                raise OrderServiceError(available[1], code=400)
        
        # 生成订单号 (Requirements: 6.2)
        order_no = generate_order_no()
        
        # 确保订单号唯一
        while self.db.query(Order).filter(Order.order_no == order_no).first():
            order_no = generate_order_no()
        
        # 创建地址快照
        address_snapshot = {
            "name": address.name,
            "phone": address.phone,
            "province": address.province,
            "city": address.city,
            "district": address.district,
            "detail": address.detail
        }
        
        # 创建订单
        order = Order(
            order_no=order_no,
            foodie_id=foodie_id,
            chef_id=chef_id,
            status="unpaid",
            total_price=total_price,
            delivery_time=delivery_time,
            address_snapshot=address_snapshot,
            remarks=remarks
        )
        self.db.add(order)
        self.db.flush()  # 获取order.id
        
        # 创建订单项
        for item_detail in item_details:
            order_item = OrderItem(
                order_id=order.id,
                dish_id=item_detail["dish_id"],
                dish_name=item_detail["dish_name"],
                dish_image=item_detail["dish_image"],
                price=item_detail["price"],
                quantity=item_detail["quantity"]
            )
            self.db.add(order_item)
        
        # 更新菜品预订数量
        for item in items:
            self._update_booked_quantity(
                item["dish_id"],
                delivery_date,
                item.get("quantity", 1)
            )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order

    
    def confirm_payment(self, order_id: str, payment_id: str) -> Order:
        """
        确认支付成功，更新订单状态
        
        Args:
            order_id: 订单ID
            payment_id: 微信支付订单号
            
        Returns:
            更新后的订单对象
            
        Requirements: 8.3
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderServiceError("订单不存在", code=404)
        
        if order.status != "unpaid":
            raise OrderServiceError("订单状态不正确", code=400)
        
        order.status = "pending"
        order.payment_id = payment_id
        
        # 创建通知给大厨 (Requirements: 6.4)
        self._create_order_notification(
            order,
            "new_order",
            "新订单",
            f"您有一个新订单，订单号: {order.order_no}"
        )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    # ==================== 订单查询 ====================
    
    def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """根据ID获取订单"""
        return self.db.query(Order).filter(
            Order.id == order_id,
            Order.is_deleted == False
        ).first()
    
    def get_order_by_order_no(self, order_no: str) -> Optional[Order]:
        """根据订单号获取订单"""
        return self.db.query(Order).filter(
            Order.order_no == order_no,
            Order.is_deleted == False
        ).first()
    
    def get_foodie_orders(
        self,
        foodie_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[Order], int]:
        """
        获取吃货的订单列表
        
        Requirements: 6.5
        
        Returns:
            Tuple[List[Order], int]: (订单列表, 总数)
        """
        query = self.db.query(Order).filter(
            Order.foodie_id == foodie_id,
            Order.is_deleted == False
        )
        
        if status and status != "all":
            query = query.filter(Order.status == status)
        
        total = query.count()
        
        orders = query.order_by(Order.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return orders, total
    
    def get_chef_orders(
        self,
        chef_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[Order], int]:
        """
        获取大厨的订单列表
        
        Returns:
            Tuple[List[Order], int]: (订单列表, 总数)
        """
        query = self.db.query(Order).filter(
            Order.chef_id == chef_id,
            Order.is_deleted == False
        )
        
        if status and status != "all":
            query = query.filter(Order.status == status)
        
        total = query.count()
        
        orders = query.order_by(Order.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return orders, total
    
    def get_order_detail(self, order_id: str, user_id: str) -> Optional[dict]:
        """
        获取订单详情
        
        Requirements: 6.6
        
        Returns:
            Optional[dict]: 订单详情
        """
        order = self.get_order_by_id(order_id)
        if not order:
            return None
        
        # 验证权限：只有订单的吃货或大厨可以查看
        if order.foodie_id != user_id and order.chef_id != user_id:
            return None
        
        return self._build_order_response(order)
    
    # ==================== 订单状态管理 ====================
    
    def cancel_order(
        self,
        order_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Order:
        """
        取消订单
        
        Requirements: 7.1
        
        Args:
            order_id: 订单ID
            user_id: 操作用户ID
            reason: 取消原因
            
        Returns:
            更新后的订单对象
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderServiceError("订单不存在", code=404)
        
        # 验证权限
        if order.foodie_id != user_id and order.chef_id != user_id:
            raise OrderServiceError("无权操作此订单", code=403)
        
        # 验证状态是否可取消 (Requirements: 7.1)
        if order.status not in CANCELLABLE_STATUSES:
            raise OrderServiceError(
                f"当前状态({order.status})不可取消",
                code=400
            )
        
        # 更新状态
        order.status = "cancelled"
        order.cancel_reason = reason
        
        # 恢复菜品预订数量
        delivery_date = order.delivery_time.date()
        for item in order.items:
            self._update_booked_quantity(
                item.dish_id,
                delivery_date,
                -item.quantity  # 负数表示减少
            )
        
        # 创建通知
        if order.foodie_id == user_id:
            # 吃货取消，通知大厨
            self._create_order_notification(
                order,
                "order_status",
                "订单已取消",
                f"订单 {order.order_no} 已被吃货取消",
                notify_chef=True
            )
        else:
            # 大厨取消，通知吃货
            self._create_order_notification(
                order,
                "order_status",
                "订单已取消",
                f"订单 {order.order_no} 已被大厨取消，原因: {reason or '无'}",
                notify_foodie=True
            )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def accept_order(self, order_id: str, chef_id: str) -> Order:
        """
        大厨接受订单
        
        Requirements: 7.2
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderServiceError("订单不存在", code=404)
        
        if order.chef_id != chef_id:
            raise OrderServiceError("无权操作此订单", code=403)
        
        if not validate_status_transition(order.status, "accepted"):
            raise OrderServiceError(
                f"当前状态({order.status})不能接受订单",
                code=400
            )
        
        order.status = "accepted"
        
        # 通知吃货
        self._create_order_notification(
            order,
            "order_status",
            "订单已接受",
            f"大厨已接受您的订单 {order.order_no}",
            notify_foodie=True
        )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def reject_order(
        self,
        order_id: str,
        chef_id: str,
        reason: str
    ) -> Order:
        """
        大厨拒绝订单
        
        Requirements: 7.3
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderServiceError("订单不存在", code=404)
        
        if order.chef_id != chef_id:
            raise OrderServiceError("无权操作此订单", code=403)
        
        if order.status != "pending":
            raise OrderServiceError(
                f"当前状态({order.status})不能拒绝订单",
                code=400
            )
        
        order.status = "cancelled"
        order.cancel_reason = reason
        
        # 恢复菜品预订数量
        delivery_date = order.delivery_time.date()
        for item in order.items:
            self._update_booked_quantity(
                item.dish_id,
                delivery_date,
                -item.quantity
            )
        
        # 通知吃货
        self._create_order_notification(
            order,
            "order_status",
            "订单已拒绝",
            f"大厨拒绝了您的订单 {order.order_no}，原因: {reason}",
            notify_foodie=True
        )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order

    
    def start_cooking(self, order_id: str, chef_id: str) -> Order:
        """
        大厨开始烹饪
        
        Requirements: 7.4
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderServiceError("订单不存在", code=404)
        
        if order.chef_id != chef_id:
            raise OrderServiceError("无权操作此订单", code=403)
        
        if not validate_status_transition(order.status, "cooking"):
            raise OrderServiceError(
                f"当前状态({order.status})不能开始烹饪",
                code=400
            )
        
        order.status = "cooking"
        
        # 通知吃货
        self._create_order_notification(
            order,
            "order_status",
            "开始烹饪",
            f"大厨已开始为您的订单 {order.order_no} 烹饪",
            notify_foodie=True
        )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def cooking_done(self, order_id: str, chef_id: str) -> Order:
        """
        大厨烹饪完成，开始配送
        
        Requirements: 7.4
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderServiceError("订单不存在", code=404)
        
        if order.chef_id != chef_id:
            raise OrderServiceError("无权操作此订单", code=403)
        
        if not validate_status_transition(order.status, "delivering"):
            raise OrderServiceError(
                f"当前状态({order.status})不能标记配送",
                code=400
            )
        
        order.status = "delivering"
        
        # 通知吃货
        self._create_order_notification(
            order,
            "order_status",
            "配送中",
            f"您的订单 {order.order_no} 已开始配送",
            notify_foodie=True
        )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def start_delivering(self, order_id: str, chef_id: str) -> Order:
        """
        大厨开始配送（从cooking状态）
        
        Requirements: 7.4
        """
        return self.cooking_done(order_id, chef_id)
    
    def confirm_receipt(self, order_id: str, foodie_id: str) -> Order:
        """
        吃货确认收货
        
        Requirements: 7.5
        """
        order = self.get_order_by_id(order_id)
        if not order:
            raise OrderServiceError("订单不存在", code=404)
        
        if order.foodie_id != foodie_id:
            raise OrderServiceError("无权操作此订单", code=403)
        
        if not validate_status_transition(order.status, "completed"):
            raise OrderServiceError(
                f"当前状态({order.status})不能确认收货",
                code=400
            )
        
        order.status = "completed"
        order.completed_at = datetime.now()
        
        # 更新大厨订单数
        chef = self.db.query(User).filter(User.id == order.chef_id).first()
        if chef:
            chef.total_orders = (chef.total_orders or 0) + 1
        
        # 通知大厨
        self._create_order_notification(
            order,
            "order_status",
            "订单已完成",
            f"订单 {order.order_no} 已完成，吃货已确认收货",
            notify_chef=True
        )
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    # ==================== 辅助方法 ====================
    
    def _check_dish_availability(
        self,
        dish_id: str,
        target_date: date,
        quantity: int
    ) -> Tuple[bool, str]:
        """
        检查菜品是否可预订
        
        Requirements: 6.1
        """
        dish = self.db.query(Dish).filter(
            Dish.id == dish_id,
            Dish.is_deleted == False
        ).first()
        
        if not dish:
            return False, "菜品不存在"
        
        if not dish.is_on_shelf:
            return False, f"菜品 {dish.name} 已下架"
        
        # 获取当日已预订数量
        daily_quantity = self.db.query(DailyDishQuantity).filter(
            DailyDishQuantity.dish_id == dish_id,
            DailyDishQuantity.date == target_date
        ).first()
        
        booked = daily_quantity.booked_quantity if daily_quantity else 0
        available = dish.max_quantity - booked
        
        if available < quantity:
            return False, f"菜品 {dish.name} 库存不足，当前可用: {available}"
        
        return True, ""
    
    def _update_booked_quantity(
        self,
        dish_id: str,
        target_date: date,
        quantity: int
    ) -> None:
        """
        更新菜品预订数量
        
        Args:
            dish_id: 菜品ID
            target_date: 日期
            quantity: 增加的数量（可为负数表示取消）
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
    
    def _create_order_notification(
        self,
        order: Order,
        notification_type: str,
        title: str,
        content: str,
        notify_foodie: bool = False,
        notify_chef: bool = False
    ) -> None:
        """
        创建订单相关通知
        
        Requirements: 6.4, 13.1, 13.2
        """
        data = {
            "order_id": order.id,
            "order_no": order.order_no,
            "status": order.status
        }
        
        if notify_foodie:
            notification = Notification(
                user_id=order.foodie_id,
                type=notification_type,
                title=title,
                content=content,
                data=data
            )
            self.db.add(notification)
        
        if notify_chef:
            notification = Notification(
                user_id=order.chef_id,
                type=notification_type,
                title=title,
                content=content,
                data=data
            )
            self.db.add(notification)
        
        # 如果都没指定，默认通知大厨（新订单场景）
        if not notify_foodie and not notify_chef:
            notification = Notification(
                user_id=order.chef_id,
                type=notification_type,
                title=title,
                content=content,
                data=data
            )
            self.db.add(notification)
    
    def _build_order_response(self, order: Order) -> dict:
        """
        构建订单响应数据
        
        Requirements: 6.6
        """
        # 获取吃货信息
        foodie = self.db.query(User).filter(User.id == order.foodie_id).first()
        
        # 获取大厨信息
        chef = self.db.query(User).filter(User.id == order.chef_id).first()
        
        # 构建订单项列表
        items = []
        for item in order.items:
            items.append({
                "id": item.id,
                "dish_id": item.dish_id,
                "dish_name": item.dish_name,
                "dish_image": item.dish_image,
                "price": float(item.price),
                "quantity": item.quantity,
                "subtotal": float(item.price * item.quantity)
            })
        
        return {
            "id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "total_price": float(order.total_price),
            "delivery_time": order.delivery_time.isoformat() if order.delivery_time else None,
            "address": order.address_snapshot,
            "remarks": order.remarks,
            "cancel_reason": order.cancel_reason,
            "is_reviewed": order.is_reviewed,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "completed_at": order.completed_at.isoformat() if order.completed_at else None,
            "items": items,
            "foodie": {
                "id": foodie.id,
                "nickname": foodie.nickname,
                "avatar": foodie.avatar,
                "phone": foodie.phone
            } if foodie else None,
            "chef": {
                "id": chef.id,
                "nickname": chef.nickname,
                "avatar": chef.avatar,
                "phone": chef.phone,
                "rating": float(chef.rating) if chef.rating else 5.0
            } if chef else None
        }
    
    def build_order_list_item(self, order: Order) -> dict:
        """
        构建订单列表项响应数据（简化版）
        """
        # 获取第一个订单项的图片作为封面
        cover_image = None
        if order.items:
            cover_image = order.items[0].dish_image
        
        # 获取大厨信息
        chef = self.db.query(User).filter(User.id == order.chef_id).first()
        
        return {
            "id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "total_price": float(order.total_price),
            "delivery_time": order.delivery_time.isoformat() if order.delivery_time else None,
            "cover_image": cover_image,
            "item_count": len(order.items),
            "is_reviewed": order.is_reviewed,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "chef": {
                "id": chef.id,
                "nickname": chef.nickname,
                "avatar": chef.avatar
            } if chef else None
        }
