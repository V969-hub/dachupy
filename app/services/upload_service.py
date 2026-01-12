"""
文件上传服务模块
实现文件类型验证、大小验证和文件存储功能
支持本地存储和云存储
"""
import os
import uuid
from datetime import datetime
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException, status

from app.config import settings
from app.services.cloud_storage import storage_service


# 允许的图片类型
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif"
}

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}


class UploadService:
    """文件上传服务类"""
    
    def __init__(self):
        """初始化上传服务，确保上传目录存在"""
        self.upload_dir = settings.UPLOAD_DIR
        self.max_size = settings.MAX_UPLOAD_SIZE
        self._ensure_upload_dir()
    
    def _ensure_upload_dir(self) -> None:
        """确保上传目录存在"""
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir, exist_ok=True)
    
    def validate_file_type(self, file: UploadFile) -> Tuple[bool, str]:
        """
        验证文件类型
        
        Args:
            file: 上传的文件对象
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息或文件扩展名)
        """
        # 检查content_type
        content_type = file.content_type
        if content_type not in ALLOWED_IMAGE_TYPES:
            return False, f"不支持的文件类型: {content_type}，仅支持 jpg, png, gif 格式"
        
        # 检查文件扩展名
        if file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                return False, f"不支持的文件扩展名: {ext}，仅支持 jpg, png, gif 格式"
        
        return True, ALLOWED_IMAGE_TYPES[content_type]
    
    async def validate_file_size(self, file: UploadFile) -> Tuple[bool, str]:
        """
        验证文件大小
        
        Args:
            file: 上传的文件对象
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        # 读取文件内容获取大小
        content = await file.read()
        file_size = len(content)
        
        # 重置文件指针
        await file.seek(0)
        
        if file_size > self.max_size:
            max_mb = self.max_size / (1024 * 1024)
            file_mb = file_size / (1024 * 1024)
            return False, f"文件大小 {file_mb:.2f}MB 超过限制 {max_mb:.0f}MB"
        
        if file_size == 0:
            return False, "文件内容为空"
        
        return True, ""
    
    def generate_filename(self, extension: str) -> str:
        """
        生成唯一的文件名
        
        Args:
            extension: 文件扩展名
            
        Returns:
            str: 生成的文件名
        """
        # 使用日期目录组织文件
        date_dir = datetime.now().strftime("%Y%m%d")
        unique_id = uuid.uuid4().hex[:16]
        timestamp = datetime.now().strftime("%H%M%S")
        
        return f"{date_dir}/{timestamp}_{unique_id}{extension}"
    
    async def save_file(self, file: UploadFile, filename: str) -> str:
        """
        保存文件到磁盘
        
        Args:
            file: 上传的文件对象
            filename: 要保存的文件名（包含子目录）
            
        Returns:
            str: 保存后的文件相对路径
        """
        # 确保子目录存在
        file_path = os.path.join(self.upload_dir, filename)
        dir_path = os.path.dirname(file_path)
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        
        # 读取并保存文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        return filename
    
    async def upload_image(self, file: UploadFile) -> str:
        """
        上传图片的完整流程
        
        Args:
            file: 上传的文件对象
            
        Returns:
            str: 上传后的文件URL路径
            
        Raises:
            HTTPException: 当文件验证失败时
        """
        # 验证文件类型
        is_valid_type, type_result = self.validate_file_type(file)
        if not is_valid_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=type_result
            )
        extension = type_result
        
        # 验证文件大小
        is_valid_size, size_error = await self.validate_file_size(file)
        if not is_valid_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=size_error
            )
        
        # 生成文件名
        filename = self.generate_filename(extension)
        
        # 使用云存储服务上传文件
        url = await storage_service.upload_file(file, filename)
        
        return url
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否删除成功
        """
        return storage_service.delete_file(file_path)


# 创建服务单例
upload_service = UploadService()
