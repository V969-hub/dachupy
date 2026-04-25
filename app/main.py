import asyncio
from contextlib import asynccontextmanager, suppress
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import os

from app.config import settings
from app.database import SessionLocal
from app.middleware.logging import RequestLoggingMiddleware
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from app.api.dish import router as dish_router
from app.api.binding import router as binding_router
from app.api.order import router as order_router
from app.api.payment import router as payment_router
from app.api.review import router as review_router
from app.api.tip import router as tip_router
from app.api.address import router as address_router
from app.api.notification import router as notification_router
from app.api.earnings import router as earnings_router
from app.api.favorite import router as favorite_router
from app.api.upload import router as upload_router
from app.api.couple import router as couple_router
from app.api.wallet import router as wallet_router
from app.api.admin import router as admin_router
from app.schema_sync import sync_database_schema
from app.services.couple_service import sync_all_due_notifications
import app.models  # noqa: F401

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("private_chef")


def should_start_background_jobs() -> bool:
    if not settings.COUPLE_NOTIFICATION_SYNC_ENABLED:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if "pytest" in sys.modules:
        return False
    return True


def should_sync_database_schema() -> bool:
    if not settings.DATABASE_SCHEMA_SYNC_ENABLED:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if "pytest" in sys.modules:
        return False
    return True


def should_validate_runtime_configuration() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if "pytest" in sys.modules:
        return False
    return True


def validate_runtime_configuration() -> None:
    insecure_items: list[str] = []

    if settings.JWT_SECRET_KEY == "your-super-secret-key-change-in-production":
        insecure_items.append("JWT_SECRET_KEY 使用默认值")

    admin_password = (settings.ADMIN_PASSWORD or "").strip()
    if not admin_password:
        insecure_items.append("ADMIN_PASSWORD 未设置")
    elif admin_password == "ChangeMe123!":
        insecure_items.append("ADMIN_PASSWORD 使用默认值")

    if not insecure_items:
        return

    app_env = (settings.APP_ENV or "development").strip().lower() or "development"
    message = "启动配置校验发现高风险默认配置: " + "，".join(insecure_items)

    if app_env in {"production", "staging"} and not settings.ALLOW_INSECURE_STARTUP:
        raise RuntimeError(
            message + "。请先在环境变量中更新配置后再启动，"
            "如需临时放行请显式设置 ALLOW_INSECURE_STARTUP=true。"
        )

    logger.warning("%s。当前 APP_ENV=%s，将继续启动。", message, app_env)


async def couple_notification_sync_worker() -> None:
    interval_seconds = max(settings.COUPLE_NOTIFICATION_SYNC_INTERVAL_SECONDS, 10)

    while True:
        try:
            with SessionLocal() as db:
                processed_count = sync_all_due_notifications(db)
            logger.debug("情侣提醒后台同步完成，处理关系数: %s", processed_count)
        except Exception:
            logger.exception("情侣提醒后台同步失败")

        await asyncio.sleep(interval_seconds)

# API文档标签配置
tags_metadata = [
    {
        "name": "Health",
        "description": "健康检查接口"
    },
    {
        "name": "认证",
        "description": "用户认证相关接口，包括微信登录、手机号绑定等"
    },
    {
        "name": "用户",
        "description": "用户信息管理接口，包括获取和更新个人资料"
    },
    {
        "name": "菜品",
        "description": "菜品管理接口，包括吃货端浏览和大厨端管理"
    },
    {
        "name": "订单",
        "description": "订单管理接口，包括创建订单、状态流转等"
    },
    {
        "name": "Payment",
        "description": "支付相关接口，包括微信支付回调"
    },
    {
        "name": "评价",
        "description": "评价管理接口，包括提交评价和查看评价"
    },
    {
        "name": "Tips",
        "description": "打赏相关接口，包括创建打赏和查看打赏记录"
    },
    {
        "name": "地址",
        "description": "配送地址管理接口"
    },
    {
        "name": "绑定",
        "description": "吃货与大厨的专属绑定关系管理"
    },
    {
        "name": "通知",
        "description": "系统通知管理接口"
    },
    {
        "name": "收益管理",
        "description": "大厨收益统计和明细查询接口"
    },
    {
        "name": "收藏",
        "description": "菜品收藏管理接口"
    },
    {
        "name": "钱包",
        "description": "虚拟币钱包、充值和流水接口"
    },
    {
        "name": "情侣",
        "description": "情侣备忘录、纪念日与绑定关系接口"
    },
    {
        "name": "Upload",
        "description": "文件上传接口"
    },
    {
        "name": "后台管理",
        "description": "后台管理控制台接口"
    }
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    background_task = None
    logger.info("私厨预订小程序后端API服务启动")
    logger.info("API文档地址: /docs")
    logger.info("ReDoc文档地址: /redoc")

    if should_validate_runtime_configuration():
        validate_runtime_configuration()

    if should_sync_database_schema():
        sync_database_schema()
        logger.info("数据库结构自检完成")

    if should_start_background_jobs():
        background_task = asyncio.create_task(couple_notification_sync_worker())
        logger.info(
            "情侣提醒后台同步已启动，轮询间隔 %s 秒",
            max(settings.COUPLE_NOTIFICATION_SYNC_INTERVAL_SECONDS, 10)
        )

    yield

    if background_task is not None:
        background_task.cancel()
        with suppress(asyncio.CancelledError):
            await background_task

    logger.info("私厨预订小程序后端API服务关闭")


# 创建FastAPI应用
app = FastAPI(
    title="私厨预订小程序后端API",
    description="""
## 概述

私厨预订微信小程序后端API服务，为吃货端和大厨端小程序提供数据支持。

## 功能模块

- **认证模块**: 微信登录、JWT认证
- **用户模块**: 个人信息管理
- **菜品模块**: 菜品CRUD、搜索筛选
- **订单模块**: 订单创建、状态管理
- **支付模块**: 微信支付集成
- **评价模块**: 订单评价
- **打赏模块**: 大厨打赏
- **地址模块**: 配送地址管理
- **绑定模块**: 吃货-大厨绑定
- **通知模块**: 系统消息通知
- **收益模块**: 大厨收益统计
- **收藏模块**: 菜品收藏

## 认证方式

除了登录接口和支付回调接口外，所有接口都需要在请求头中携带JWT Token：

```
Authorization: Bearer <token>
```

## 响应格式

所有接口返回统一的JSON格式：

```json
{
    "code": 200,
    "message": "success",
    "data": {}
}
```

分页接口额外返回分页信息：

```json
{
    "code": 200,
    "message": "success",
    "data": [],
    "page_info": {
        "page": 1,
        "page_size": 10,
        "total": 100,
        "total_pages": 10
    }
}
```
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
    contact={
        "name": "私厨预订小程序",
        "email": "support@privatechef.com"
    },
    license_info={
        "name": "MIT License"
    }
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（微信小程序）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加请求日志中间件
app.add_middleware(RequestLoggingMiddleware)

# 挂载静态文件目录（用于上传的图片）
uploads_dir = "uploads"  # 使用相对路径
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


# 异常处理器
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理HTTP异常，返回标准化响应格式"""
    logger.error(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
            "data": None
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误，返回标准化响应格式"""
    logger.error(f"验证错误: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "data": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理所有其他异常，返回标准化响应格式"""
    logger.error(f"未处理异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None
        }
    )


# 健康检查接口
@app.get("/health", tags=["Health"])
async def health_check():
    """
    健康检查接口
    
    用于检查服务是否正常运行。
    """
    return {"code": 200, "message": "success", "data": {"status": "healthy"}}


# 根路径接口
@app.get("/", tags=["Health"])
async def root():
    """
    根路径接口
    
    返回API基本信息和文档链接。
    """
    return {
        "code": 200,
        "message": "success",
        "data": {
            "name": "私厨预订小程序后端API",
            "version": "1.0.0",
            "description": "为吃货端和大厨端小程序提供数据支持",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


# 注册所有API路由
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(dish_router, prefix="/api")
app.include_router(binding_router, prefix="/api")
app.include_router(order_router, prefix="/api")
app.include_router(payment_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(tip_router, prefix="/api")
app.include_router(address_router, prefix="/api")
app.include_router(notification_router, prefix="/api")
app.include_router(earnings_router, prefix="/api")
app.include_router(favorite_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(couple_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
