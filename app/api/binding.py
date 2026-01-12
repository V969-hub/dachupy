"""
Binding API endpoints for managing foodie-chef binding relationships.

Requirements:
- 12.1: Validate binding code belongs to a chef
- 12.2: Create binding relationship
- 12.6: Remove binding relationship on unbind
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.schemas.common import success_response, error_response
from app.middleware.auth import get_current_user, require_foodie
from app.services.binding_service import (
    create_binding,
    remove_binding,
    get_binding_info,
    get_bound_foodies,
    BindingServiceError
)


router = APIRouter(tags=["绑定"])


class BindingCodeRequest(BaseModel):
    """绑定大厨请求模型"""
    binding_code: str = Field(..., min_length=1, max_length=8, description="大厨的绑定码")


@router.post("/bindingcode")
async def bind_chef(
    request: BindingCodeRequest,
    current_user: User = Depends(require_foodie),
    db: Session = Depends(get_db)
):
    """
    绑定大厨。
    
    吃货通过输入大厨的绑定码来建立专属绑定关系。
    每个吃货只能绑定一个大厨，如需更换需先解除绑定。
    
    Args:
        binding_code: 大厨的专属绑定码
        
    Returns:
        绑定成功后的绑定信息，包含大厨详情
        
    Raises:
        400: 已绑定大厨或绑定码无效
        403: 非吃货角色
        404: 绑定码对应的大厨不存在
        
    Requirements: 12.1, 12.2
    """
    try:
        binding = create_binding(
            db=db,
            foodie=current_user,
            binding_code=request.binding_code
        )
        
        # 获取完整的绑定信息返回
        binding_info = get_binding_info(db, current_user)
        
        return success_response(
            data=binding_info,
            message="绑定成功"
        )
        
    except BindingServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"绑定失败: {str(e)}")


@router.delete("/binding")
async def unbind_chef(
    current_user: User = Depends(require_foodie),
    db: Session = Depends(get_db)
):
    """
    解除与大厨的绑定。
    
    吃货可以随时解除与当前绑定大厨的关系。
    解除后可以重新绑定其他大厨。
    
    Returns:
        解除绑定成功的消息
        
    Raises:
        403: 非吃货角色
        404: 尚未绑定任何大厨
        
    Requirements: 12.6
    """
    try:
        remove_binding(db=db, foodie=current_user)
        
        return success_response(
            data=None,
            message="解除绑定成功"
        )
        
    except BindingServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"解除绑定失败: {str(e)}")


@router.get("/binding")
async def get_binding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取绑定信息。
    
    - 吃货：返回绑定的大厨信息
    - 大厨：返回绑定的吃货列表
    
    Returns:
        绑定信息，根据用户角色返回不同内容
        
    Requirements: 12.4
    """
    try:
        if current_user.role == "foodie":
            # 吃货获取绑定的大厨信息
            binding_info = get_binding_info(db, current_user)
            
            if binding_info is None:
                return success_response(
                    data={"is_bound": False, "chef": None},
                    message="尚未绑定大厨"
                )
            
            return success_response(
                data={
                    "is_bound": True,
                    **binding_info
                }
            )
        else:
            # 大厨获取绑定的吃货列表
            foodies = get_bound_foodies(db, current_user.id)
            
            return success_response(
                data={
                    "binding_code": current_user.binding_code,
                    "bound_foodies_count": len(foodies),
                    "bound_foodies": foodies
                }
            )
            
    except Exception as e:
        return error_response(500, f"获取绑定信息失败: {str(e)}")
