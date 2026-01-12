"""
文件上传API模块
实现图片上传接口
"""
from fastapi import APIRouter, UploadFile, File, Depends

from app.schemas.common import ApiResponse
from app.middleware.auth import get_current_user
from app.services.upload_service import upload_service

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/image", response_model=ApiResponse)
async def upload_image(
    file: UploadFile = File(..., description="图片文件，支持jpg、png、gif格式，最大5MB"),
    current_user: dict = Depends(get_current_user)
):
    """
    上传图片
    
    - 支持的格式: jpg, png, gif
    - 最大文件大小: 5MB
    - 返回上传后的图片URL
    """
    # 调用上传服务处理文件
    url = await upload_service.upload_image(file)
    
    return ApiResponse(
        code=200,
        message="上传成功",
        data={"url": url}
    )
