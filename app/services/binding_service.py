"""
Binding service for managing foodie-chef binding relationships.

Requirements:
- 12.1: Validate binding code belongs to a chef
- 12.2: Create binding relationship
- 12.3: Notify both parties on binding success
- 12.4: Ensure each foodie can only bind to one chef
- 12.5: Return error if foodie is already bound
- 12.6: Remove binding relationship on unbind
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.binding import Binding
from app.models.user import User
from app.models.notification import Notification


class BindingServiceError(Exception):
    """绑定服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def get_binding_by_foodie_id(db: Session, foodie_id: str) -> Optional[Binding]:
    """
    根据吃货ID获取绑定关系。
    
    Args:
        db: 数据库会话
        foodie_id: 吃货用户ID
        
    Returns:
        绑定关系对象，如果不存在则返回None
        
    Requirements: 12.4
    """
    return db.query(Binding).filter(
        Binding.foodie_id == foodie_id
    ).first()


def get_chef_by_binding_code(db: Session, binding_code: str) -> Optional[User]:
    """
    根据绑定码获取大厨信息。
    
    Args:
        db: 数据库会话
        binding_code: 绑定码
        
    Returns:
        大厨用户对象，如果不存在或不是大厨则返回None
        
    Requirements: 12.1
    """
    return db.query(User).filter(
        User.binding_code == binding_code,
        User.role == "chef",
        User.is_deleted == False
    ).first()


def create_binding(
    db: Session,
    foodie: User,
    binding_code: str
) -> Binding:
    """
    创建吃货与大厨的绑定关系。
    
    Args:
        db: 数据库会话
        foodie: 吃货用户对象
        binding_code: 大厨的绑定码
        
    Returns:
        创建的绑定关系对象
        
    Raises:
        BindingServiceError: 如果验证失败
        
    Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
    """
    # 验证用户是吃货角色
    if foodie.role != "foodie":
        raise BindingServiceError("只有吃货可以绑定大厨", code=403)
    
    # 检查是否已经绑定了大厨 (Requirements: 12.4, 12.5)
    existing_binding = get_binding_by_foodie_id(db, foodie.id)
    if existing_binding:
        raise BindingServiceError("您已绑定大厨，请先解除绑定", code=400)
    
    # 验证绑定码是否属于大厨 (Requirements: 12.1)
    chef = get_chef_by_binding_code(db, binding_code)
    if not chef:
        raise BindingServiceError("绑定码无效或该用户不是大厨", code=404)
    
    # 不能绑定自己
    if chef.id == foodie.id:
        raise BindingServiceError("不能绑定自己", code=400)
    
    # 创建绑定关系 (Requirements: 12.2)
    binding = Binding(
        foodie_id=foodie.id,
        chef_id=chef.id,
        binding_code=binding_code
    )
    db.add(binding)
    
    # 创建通知给双方 (Requirements: 12.3)
    # 通知大厨
    chef_notification = Notification(
        user_id=chef.id,
        type="binding",
        title="新的吃货绑定",
        content=f"吃货 {foodie.nickname or '用户'} 已绑定您",
        data={"foodie_id": foodie.id, "foodie_nickname": foodie.nickname}
    )
    db.add(chef_notification)
    
    # 通知吃货
    foodie_notification = Notification(
        user_id=foodie.id,
        type="binding",
        title="绑定成功",
        content=f"您已成功绑定大厨 {chef.nickname or '大厨'}",
        data={"chef_id": chef.id, "chef_nickname": chef.nickname}
    )
    db.add(foodie_notification)
    
    db.commit()
    db.refresh(binding)
    
    return binding


def remove_binding(db: Session, foodie: User) -> bool:
    """
    解除吃货与大厨的绑定关系。
    
    Args:
        db: 数据库会话
        foodie: 吃货用户对象
        
    Returns:
        是否成功解除绑定
        
    Raises:
        BindingServiceError: 如果验证失败
        
    Requirements: 12.6
    """
    # 验证用户是吃货角色
    if foodie.role != "foodie":
        raise BindingServiceError("只有吃货可以解除绑定", code=403)
    
    # 获取现有绑定关系
    binding = get_binding_by_foodie_id(db, foodie.id)
    if not binding:
        raise BindingServiceError("您尚未绑定任何大厨", code=404)
    
    # 获取大厨信息用于通知
    chef = db.query(User).filter(User.id == binding.chef_id).first()
    
    # 删除绑定关系
    db.delete(binding)
    
    # 创建通知给双方
    if chef:
        chef_notification = Notification(
            user_id=chef.id,
            type="binding",
            title="吃货解除绑定",
            content=f"吃货 {foodie.nickname or '用户'} 已解除与您的绑定",
            data={"foodie_id": foodie.id, "foodie_nickname": foodie.nickname}
        )
        db.add(chef_notification)
    
    foodie_notification = Notification(
        user_id=foodie.id,
        type="binding",
        title="解除绑定成功",
        content=f"您已成功解除与大厨 {chef.nickname if chef else '大厨'} 的绑定",
        data={"chef_id": binding.chef_id, "chef_nickname": chef.nickname if chef else None}
    )
    db.add(foodie_notification)
    
    db.commit()
    
    return True


def get_binding_info(db: Session, foodie: User) -> Optional[dict]:
    """
    获取吃货的绑定信息。
    
    Args:
        db: 数据库会话
        foodie: 吃货用户对象
        
    Returns:
        绑定信息字典，如果未绑定则返回None
        
    Requirements: 12.4
    """
    binding = get_binding_by_foodie_id(db, foodie.id)
    if not binding:
        return None
    
    # 获取大厨详细信息
    chef = db.query(User).filter(
        User.id == binding.chef_id,
        User.is_deleted == False
    ).first()
    
    if not chef:
        return None
    
    return {
        "binding_id": binding.id,
        "binding_code": binding.binding_code,
        "created_at": binding.created_at.isoformat() if binding.created_at else None,
        "chef": {
            "id": chef.id,
            "nickname": chef.nickname,
            "avatar": chef.avatar,
            "introduction": chef.introduction,
            "specialties": chef.specialties,
            "rating": float(chef.rating) if chef.rating else 5.0,
            "total_orders": chef.total_orders
        }
    }


def get_bound_foodies(db: Session, chef_id: str) -> list:
    """
    获取绑定到指定大厨的所有吃货列表。
    
    Args:
        db: 数据库会话
        chef_id: 大厨用户ID
        
    Returns:
        绑定的吃货信息列表
    """
    bindings = db.query(Binding).filter(
        Binding.chef_id == chef_id
    ).all()
    
    result = []
    for binding in bindings:
        foodie = db.query(User).filter(
            User.id == binding.foodie_id,
            User.is_deleted == False
        ).first()
        
        if foodie:
            result.append({
                "binding_id": binding.id,
                "created_at": binding.created_at.isoformat() if binding.created_at else None,
                "foodie": {
                    "id": foodie.id,
                    "nickname": foodie.nickname,
                    "avatar": foodie.avatar,
                    "phone": foodie.phone
                }
            })
    
    return result
