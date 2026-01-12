"""
地址服务模块 - 处理用户配送地址的CRUD操作。

Requirements:
- 11.1: 添加地址时保存用户ID
- 11.2: 更新地址时验证所有权
- 11.3: 软删除地址
- 11.4: 设置默认地址时更新标志
- 11.5: 返回地址列表时默认地址排在前面
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.address import Address


class AddressServiceError(Exception):
    """地址服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def get_address_by_id(db: Session, address_id: str) -> Optional[Address]:
    """
    根据ID获取地址。
    
    Args:
        db: 数据库会话
        address_id: 地址ID
        
    Returns:
        地址对象，如果不存在或已删除则返回None
    """
    return db.query(Address).filter(
        Address.id == address_id,
        Address.is_deleted == False
    ).first()


def get_user_addresses(db: Session, user_id: str) -> List[Address]:
    """
    获取用户的所有地址，默认地址排在前面。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        地址列表，按默认地址优先、创建时间倒序排列
        
    Requirements: 11.5
    """
    return db.query(Address).filter(
        Address.user_id == user_id,
        Address.is_deleted == False
    ).order_by(
        Address.is_default.desc(),
        Address.created_at.desc()
    ).all()


def create_address(
    db: Session,
    user_id: str,
    name: str,
    phone: str,
    province: str,
    city: str,
    district: str,
    detail: str,
    is_default: bool = False
) -> Address:
    """
    创建新地址。
    
    如果设置为默认地址，会先取消用户其他地址的默认状态。
    如果是用户的第一个地址，自动设为默认。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        name: 联系人姓名
        phone: 联系电话
        province: 省
        city: 市
        district: 区
        detail: 详细地址
        is_default: 是否设为默认地址
        
    Returns:
        创建的地址对象
        
    Raises:
        AddressServiceError: 如果验证失败
        
    Requirements: 11.1, 11.4
    """
    # 验证必填字段
    _validate_address_fields(name, phone, province, city, district, detail)
    
    # 检查是否是用户的第一个地址
    existing_count = db.query(Address).filter(
        Address.user_id == user_id,
        Address.is_deleted == False
    ).count()
    
    # 如果是第一个地址，自动设为默认
    if existing_count == 0:
        is_default = True
    
    # 如果设置为默认，先取消其他地址的默认状态
    if is_default:
        _clear_default_address(db, user_id)
    
    # 创建新地址
    address = Address(
        user_id=user_id,
        name=name,
        phone=phone,
        province=province,
        city=city,
        district=district,
        detail=detail,
        is_default=is_default
    )
    
    db.add(address)
    db.commit()
    db.refresh(address)
    
    return address


def update_address(
    db: Session,
    address: Address,
    user_id: str,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    detail: Optional[str] = None,
    is_default: Optional[bool] = None
) -> Address:
    """
    更新地址信息。
    
    Args:
        db: 数据库会话
        address: 地址对象
        user_id: 当前用户ID（用于验证所有权）
        name: 联系人姓名（可选）
        phone: 联系电话（可选）
        province: 省（可选）
        city: 市（可选）
        district: 区（可选）
        detail: 详细地址（可选）
        is_default: 是否设为默认地址（可选）
        
    Returns:
        更新后的地址对象
        
    Raises:
        AddressServiceError: 如果验证失败或无权限
        
    Requirements: 11.2, 11.4
    """
    # 验证所有权
    if address.user_id != user_id:
        raise AddressServiceError("无权操作此地址", code=403)
    
    # 更新字段
    if name is not None:
        _validate_name(name)
        address.name = name
    
    if phone is not None:
        _validate_phone(phone)
        address.phone = phone
    
    if province is not None:
        _validate_province(province)
        address.province = province
    
    if city is not None:
        _validate_city(city)
        address.city = city
    
    if district is not None:
        _validate_district(district)
        address.district = district
    
    if detail is not None:
        _validate_detail(detail)
        address.detail = detail
    
    # 处理默认地址设置
    if is_default is not None and is_default and not address.is_default:
        _clear_default_address(db, user_id)
        address.is_default = True
    
    db.commit()
    db.refresh(address)
    
    return address


def delete_address(db: Session, address: Address, user_id: str) -> bool:
    """
    软删除地址。
    
    如果删除的是默认地址，会自动将最新的地址设为默认。
    
    Args:
        db: 数据库会话
        address: 地址对象
        user_id: 当前用户ID（用于验证所有权）
        
    Returns:
        是否删除成功
        
    Raises:
        AddressServiceError: 如果无权限
        
    Requirements: 11.3
    """
    # 验证所有权
    if address.user_id != user_id:
        raise AddressServiceError("无权操作此地址", code=403)
    
    was_default = address.is_default
    
    # 软删除
    address.is_deleted = True
    address.is_default = False
    
    db.commit()
    
    # 如果删除的是默认地址，设置新的默认地址
    if was_default:
        _set_new_default_address(db, user_id)
    
    return True


def set_default_address(db: Session, address: Address, user_id: str) -> Address:
    """
    设置地址为默认地址。
    
    Args:
        db: 数据库会话
        address: 地址对象
        user_id: 当前用户ID（用于验证所有权）
        
    Returns:
        更新后的地址对象
        
    Raises:
        AddressServiceError: 如果无权限
        
    Requirements: 11.4
    """
    # 验证所有权
    if address.user_id != user_id:
        raise AddressServiceError("无权操作此地址", code=403)
    
    # 如果已经是默认地址，直接返回
    if address.is_default:
        return address
    
    # 取消其他地址的默认状态
    _clear_default_address(db, user_id)
    
    # 设置当前地址为默认
    address.is_default = True
    
    db.commit()
    db.refresh(address)
    
    return address


def address_to_dict(address: Address) -> dict:
    """
    将地址对象转换为字典。
    
    Args:
        address: 地址对象
        
    Returns:
        地址信息字典
    """
    return {
        "id": address.id,
        "name": address.name,
        "phone": address.phone,
        "province": address.province,
        "city": address.city,
        "district": address.district,
        "detail": address.detail,
        "full_address": f"{address.province}{address.city}{address.district}{address.detail}",
        "is_default": address.is_default,
        "created_at": address.created_at.isoformat() if address.created_at else None,
        "updated_at": address.updated_at.isoformat() if address.updated_at else None
    }


# ============ 私有辅助函数 ============

def _clear_default_address(db: Session, user_id: str) -> None:
    """取消用户所有地址的默认状态。"""
    db.query(Address).filter(
        Address.user_id == user_id,
        Address.is_deleted == False,
        Address.is_default == True
    ).update({"is_default": False})


def _set_new_default_address(db: Session, user_id: str) -> None:
    """设置用户最新的地址为默认地址。"""
    newest_address = db.query(Address).filter(
        Address.user_id == user_id,
        Address.is_deleted == False
    ).order_by(Address.created_at.desc()).first()
    
    if newest_address:
        newest_address.is_default = True
        db.commit()


def _validate_address_fields(
    name: str,
    phone: str,
    province: str,
    city: str,
    district: str,
    detail: str
) -> None:
    """验证地址所有必填字段。"""
    _validate_name(name)
    _validate_phone(phone)
    _validate_province(province)
    _validate_city(city)
    _validate_district(district)
    _validate_detail(detail)


def _validate_name(name: str) -> None:
    """验证联系人姓名。"""
    if not name or not name.strip():
        raise AddressServiceError("联系人姓名不能为空")
    if len(name) > 32:
        raise AddressServiceError("联系人姓名不能超过32个字符")


def _validate_phone(phone: str) -> None:
    """验证联系电话。"""
    if not phone or not phone.strip():
        raise AddressServiceError("联系电话不能为空")
    if len(phone) > 20:
        raise AddressServiceError("联系电话不能超过20个字符")


def _validate_province(province: str) -> None:
    """验证省份。"""
    if not province or not province.strip():
        raise AddressServiceError("省份不能为空")
    if len(province) > 32:
        raise AddressServiceError("省份不能超过32个字符")


def _validate_city(city: str) -> None:
    """验证城市。"""
    if not city or not city.strip():
        raise AddressServiceError("城市不能为空")
    if len(city) > 32:
        raise AddressServiceError("城市不能超过32个字符")


def _validate_district(district: str) -> None:
    """验证区县。"""
    if not district or not district.strip():
        raise AddressServiceError("区县不能为空")
    if len(district) > 32:
        raise AddressServiceError("区县不能超过32个字符")


def _validate_detail(detail: str) -> None:
    """验证详细地址。"""
    if not detail or not detail.strip():
        raise AddressServiceError("详细地址不能为空")
    if len(detail) > 256:
        raise AddressServiceError("详细地址不能超过256个字符")
