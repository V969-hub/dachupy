"""
云存储服务模块
支持多种云存储服务：阿里云OSS、腾讯云COS等
"""
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, HTTPException

from app.config import settings


class CloudStorageService:
    """云存储服务基类"""
    
    async def upload_file(self, file: UploadFile, filename: str) -> str:
        """上传文件到云存储"""
        raise NotImplementedError
    
    def delete_file(self, file_path: str) -> bool:
        """从云存储删除文件"""
        raise NotImplementedError


class LocalStorageService(CloudStorageService):
    """本地存储服务"""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self._ensure_upload_dir()
    
    def _ensure_upload_dir(self):
        """确保上传目录存在"""
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir, exist_ok=True)
    
    async def upload_file(self, file: UploadFile, filename: str) -> str:
        """保存文件到本地"""
        file_path = os.path.join(self.upload_dir, filename)
        dir_path = os.path.dirname(file_path)
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        return f"/{self.upload_dir}/{filename}"
    
    def delete_file(self, file_path: str) -> bool:
        """删除本地文件"""
        if file_path.startswith("/"):
            file_path = file_path[1:]
        if file_path.startswith(f"{self.upload_dir}/"):
            file_path = file_path[len(self.upload_dir) + 1:]
        
        full_path = os.path.join(self.upload_dir, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False


class OSSStorageService(CloudStorageService):
    """阿里云 OSS 存储服务"""
    
    def __init__(self):
        try:
            import oss2
            self.oss2 = oss2
        except ImportError:
            raise ImportError("请安装 oss2: pip install oss2")
        
        # 初始化 OSS 客户端
        auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
        self.bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)
        self.domain = settings.OSS_DOMAIN or f"https://{settings.OSS_BUCKET_NAME}.{settings.OSS_ENDPOINT}"
    
    async def upload_file(self, file: UploadFile, filename: str) -> str:
        """上传文件到 OSS"""
        try:
            content = await file.read()
            result = self.bucket.put_object(filename, content)
            
            if result.status == 200:
                return f"{self.domain}/{filename}"
            else:
                raise HTTPException(status_code=500, detail="OSS 上传失败")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OSS 上传错误: {str(e)}")
    
    def delete_file(self, file_path: str) -> bool:
        """从 OSS 删除文件"""
        try:
            # 提取文件名（去掉域名部分）
            if file_path.startswith("http"):
                filename = file_path.split("/")[-1]
            else:
                filename = file_path.lstrip("/")
            
            result = self.bucket.delete_object(filename)
            return result.status == 204
        except Exception:
            return False


def get_storage_service() -> CloudStorageService:
    """根据配置获取存储服务实例"""
    storage_type = settings.STORAGE_TYPE.lower()
    
    if storage_type == "oss":
        return OSSStorageService()
    elif storage_type == "local":
        return LocalStorageService()
    else:
        # 默认使用本地存储
        return LocalStorageService()


# 创建存储服务单例
storage_service = get_storage_service()