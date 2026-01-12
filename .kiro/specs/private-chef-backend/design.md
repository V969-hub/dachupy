# Design Document

## Overview

本设计文档描述私厨预订微信小程序后端API服务的技术架构、数据库设计和API接口规范。后端采用Python FastAPI框架，使用MySQL数据库存储数据，通过SQLAlchemy ORM进行数据操作，JWT进行身份认证。

## Architecture

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    微信小程序客户端                           │
│              (吃货端 / 大厨端)                                │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   路由层 (Routers)                    │   │
│  │  auth | user | dish | order | review | tip | ...    │   │
│  └────────────────────────┬────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────────┐   │
│  │                   中间件层 (Middleware)               │   │
│  │    CORS | JWT认证 | 请求日志 | 异常处理               │   │
│  └────────────────────────┬────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────────┐   │
│  │                   服务层 (Services)                   │   │
│  │  UserService | DishService | OrderService | ...     │   │
│  └────────────────────────┬────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────────┐   │
│  │                   数据层 (Models/Schemas)             │   │
│  │              SQLAlchemy ORM + Pydantic              │   │
│  └────────────────────────┬────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    MySQL Database                           │
│                   192.168.1.70:3306                         │
│                   private_chef_db                           │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
private-chef-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI应用入口
│   ├── config.py               # 配置文件
│   ├── database.py             # 数据库连接
│   ├── dependencies.py         # 依赖注入
│   ├── api/                    # API路由
│   │   ├── __init__.py
│   │   ├── auth.py             # 认证接口
│   │   ├── user.py             # 用户接口
│   │   ├── dish.py             # 菜品接口
│   │   ├── order.py            # 订单接口
│   │   ├── review.py           # 评价接口
│   │   ├── tip.py              # 打赏接口
│   │   ├── address.py          # 地址接口
│   │   ├── binding.py          # 绑定接口
│   │   ├── notification.py     # 通知接口
│   │   ├── earnings.py         # 收益接口
│   │   ├── favorite.py         # 收藏接口
│   │   └── upload.py           # 上传接口
│   ├── models/                 # 数据库模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── dish.py
│   │   ├── order.py
│   │   ├── review.py
│   │   ├── tip.py
│   │   ├── address.py
│   │   ├── binding.py
│   │   ├── notification.py
│   │   └── favorite.py
│   ├── schemas/                # Pydantic模型
│   │   ├── __init__.py
│   │   ├── common.py           # 通用响应模型
│   │   ├── user.py
│   │   ├── dish.py
│   │   ├── order.py
│   │   ├── review.py
│   │   ├── tip.py
│   │   ├── address.py
│   │   ├── binding.py
│   │   └── notification.py
│   ├── services/               # 业务逻辑
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── dish_service.py
│   │   ├── order_service.py
│   │   ├── review_service.py
│   │   ├── tip_service.py
│   │   ├── binding_service.py
│   │   ├── notification_service.py
│   │   ├── wechat_service.py   # 微信API服务
│   │   └── payment_service.py  # 支付服务
│   ├── middleware/             # 中间件
│   │   ├── __init__.py
│   │   ├── auth.py             # JWT认证
│   │   └── logging.py          # 请求日志
│   └── utils/                  # 工具函数
│       ├── __init__.py
│       ├── security.py         # 安全相关
│       └── helpers.py          # 辅助函数
├── tests/                      # 测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_dish.py
│   ├── test_order.py
│   └── ...
├── uploads/                    # 上传文件目录
├── requirements.txt
├── .env                        # 环境变量
└── README.md
```

## Components and Interfaces

### 数据库配置

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
    DB_HOST: str = "192.168.1.70"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "private_chef_db"
    
    # JWT配置
    JWT_SECRET_KEY: str = "your-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
    # 微信配置
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_MCH_ID: str = ""  # 商户号
    WECHAT_API_KEY: str = ""  # API密钥
    
    # 上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
```

### 统一响应格式

```python
# app/schemas/common.py
from typing import TypeVar, Generic, Optional
from pydantic import BaseModel

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

class PageInfo(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

class PaginatedResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[list[T]] = None
    page_info: Optional[PageInfo] = None
```

### JWT认证中间件

```python
# app/middleware/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.config import settings

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return {"user_id": user_id, "role": payload.get("role")}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

async def require_chef(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "chef":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chef role required"
        )
    return current_user

async def require_foodie(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "foodie":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foodie role required"
        )
    return current_user
```



## Data Models

### 数据库ER图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │     │   Binding   │     │    Dish     │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id (PK)     │◄────┤ foodie_id   │     │ id (PK)     │
│ open_id     │     │ chef_id     │────►│ chef_id(FK) │
│ nickname    │     │ binding_code│     │ name        │
│ avatar      │     │ created_at  │     │ price       │
│ phone       │     └─────────────┘     │ images      │
│ role        │                         │ description │
│ binding_code│     ┌─────────────┐     │ ingredients │
│ introduction│     │   Address   │     │ tags        │
│ specialties │     ├─────────────┤     │ category    │
│ rating      │     │ id (PK)     │     │ is_on_shelf │
│ created_at  │◄────┤ user_id(FK) │     │ created_at  │
└──────┬──────┘     │ name        │     └──────┬──────┘
       │            │ phone       │            │
       │            │ province    │            │
       │            │ city        │     ┌──────┴──────┐
       │            │ district    │     │             │
       │            │ detail      │     ▼             ▼
       │            │ is_default  │ ┌─────────┐ ┌─────────┐
       │            └─────────────┘ │ Review  │ │Favorite │
       │                            ├─────────┤ ├─────────┤
       │     ┌─────────────┐        │ id (PK) │ │ id (PK) │
       │     │    Order    │        │ dish_id │ │ user_id │
       │     ├─────────────┤        │ user_id │ │ dish_id │
       │     │ id (PK)     │        │ rating  │ └─────────┘
       └────►│ foodie_id   │        │ content │
             │ chef_id     │        │ images  │
             │ order_no    │        └─────────┘
             │ status      │
             │ total_price │     ┌─────────────┐
             │ delivery_at │     │ OrderItem   │
             │ address_id  │     ├─────────────┤
             │ remarks     │◄────┤ order_id(FK)│
             │ created_at  │     │ dish_id     │
             └──────┬──────┘     │ dish_name   │
                    │            │ price       │
                    │            │ quantity    │
                    ▼            └─────────────┘
             ┌─────────────┐
             │    Tip      │     ┌─────────────┐
             ├─────────────┤     │Notification │
             │ id (PK)     │     ├─────────────┤
             │ foodie_id   │     │ id (PK)     │
             │ chef_id     │     │ user_id(FK) │
             │ order_id    │     │ type        │
             │ amount      │     │ title       │
             │ message     │     │ content     │
             │ created_at  │     │ data        │
             └─────────────┘     │ is_read     │
                                 │ created_at  │
                                 └─────────────┘
```

### 数据库表设计

#### users 用户表

```sql
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    open_id VARCHAR(64) UNIQUE NOT NULL COMMENT '微信openId',
    nickname VARCHAR(64) NOT NULL DEFAULT '' COMMENT '昵称',
    avatar VARCHAR(512) DEFAULT '' COMMENT '头像URL',
    phone VARCHAR(20) DEFAULT NULL COMMENT '手机号',
    role ENUM('foodie', 'chef') NOT NULL DEFAULT 'foodie' COMMENT '角色',
    binding_code VARCHAR(8) UNIQUE NOT NULL COMMENT '专属绑定码',
    introduction TEXT COMMENT '大厨简介',
    specialties JSON COMMENT '大厨擅长菜系',
    rating DECIMAL(2,1) DEFAULT 5.0 COMMENT '大厨评分',
    total_orders INT DEFAULT 0 COMMENT '总订单数',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_open_id (open_id),
    INDEX idx_binding_code (binding_code),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';
```

#### dishes 菜品表

```sql
CREATE TABLE dishes (
    id VARCHAR(36) PRIMARY KEY,
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    name VARCHAR(128) NOT NULL COMMENT '菜品名称',
    price DECIMAL(10,2) NOT NULL COMMENT '价格',
    images JSON NOT NULL COMMENT '图片URL列表',
    description TEXT COMMENT '描述',
    ingredients JSON COMMENT '食材列表',
    tags JSON COMMENT '口味标签',
    category VARCHAR(32) COMMENT '菜系分类',
    available_dates JSON COMMENT '可预订日期',
    max_quantity INT DEFAULT 10 COMMENT '每日最大份数',
    rating DECIMAL(2,1) DEFAULT 5.0 COMMENT '评分',
    review_count INT DEFAULT 0 COMMENT '评价数',
    is_on_shelf TINYINT(1) DEFAULT 1 COMMENT '是否上架',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (chef_id) REFERENCES users(id),
    INDEX idx_chef_id (chef_id),
    INDEX idx_category (category),
    INDEX idx_is_on_shelf (is_on_shelf)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜品表';
```

#### orders 订单表

```sql
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY,
    order_no VARCHAR(32) UNIQUE NOT NULL COMMENT '订单号',
    foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID',
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    status ENUM('unpaid', 'pending', 'accepted', 'cooking', 'delivering', 'completed', 'cancelled') 
        NOT NULL DEFAULT 'unpaid' COMMENT '订单状态',
    total_price DECIMAL(10,2) NOT NULL COMMENT '总价',
    delivery_time DATETIME NOT NULL COMMENT '配送时间',
    address_snapshot JSON NOT NULL COMMENT '地址快照',
    remarks TEXT COMMENT '备注',
    cancel_reason VARCHAR(256) COMMENT '取消原因',
    is_reviewed TINYINT(1) DEFAULT 0 COMMENT '是否已评价',
    payment_id VARCHAR(64) COMMENT '微信支付订单号',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME COMMENT '完成时间',
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    INDEX idx_order_no (order_no),
    INDEX idx_foodie_id (foodie_id),
    INDEX idx_chef_id (chef_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';
```

#### order_items 订单项表

```sql
CREATE TABLE order_items (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL COMMENT '订单ID',
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    dish_name VARCHAR(128) NOT NULL COMMENT '菜品名称快照',
    dish_image VARCHAR(512) COMMENT '菜品图片快照',
    price DECIMAL(10,2) NOT NULL COMMENT '单价快照',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    INDEX idx_order_id (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单项表';
```

#### reviews 评价表

```sql
CREATE TABLE reviews (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL COMMENT '订单ID',
    foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID',
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    rating TINYINT NOT NULL COMMENT '评分1-5',
    content TEXT COMMENT '评价内容',
    images JSON COMMENT '评价图片',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    INDEX idx_dish_id (dish_id),
    INDEX idx_chef_id (chef_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价表';
```

#### tips 打赏表

```sql
CREATE TABLE tips (
    id VARCHAR(36) PRIMARY KEY,
    foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID',
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    order_id VARCHAR(36) COMMENT '关联订单ID',
    amount DECIMAL(10,2) NOT NULL COMMENT '打赏金额',
    message VARCHAR(256) COMMENT '留言',
    payment_id VARCHAR(64) COMMENT '微信支付订单号',
    status ENUM('pending', 'paid', 'failed') DEFAULT 'pending' COMMENT '支付状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    INDEX idx_chef_id (chef_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='打赏表';
```

#### addresses 地址表

```sql
CREATE TABLE addresses (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
    name VARCHAR(32) NOT NULL COMMENT '联系人',
    phone VARCHAR(20) NOT NULL COMMENT '联系电话',
    province VARCHAR(32) NOT NULL COMMENT '省',
    city VARCHAR(32) NOT NULL COMMENT '市',
    district VARCHAR(32) NOT NULL COMMENT '区',
    detail VARCHAR(256) NOT NULL COMMENT '详细地址',
    is_default TINYINT(1) DEFAULT 0 COMMENT '是否默认',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址表';
```

#### bindings 绑定关系表

```sql
CREATE TABLE bindings (
    id VARCHAR(36) PRIMARY KEY,
    foodie_id VARCHAR(36) UNIQUE NOT NULL COMMENT '吃货ID',
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    binding_code VARCHAR(8) NOT NULL COMMENT '使用的绑定码',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    INDEX idx_chef_id (chef_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='绑定关系表';
```

#### notifications 通知表

```sql
CREATE TABLE notifications (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
    type ENUM('new_order', 'order_status', 'binding', 'tip', 'system') NOT NULL COMMENT '通知类型',
    title VARCHAR(64) NOT NULL COMMENT '标题',
    content VARCHAR(256) NOT NULL COMMENT '内容',
    data JSON COMMENT '附加数据',
    is_read TINYINT(1) DEFAULT 0 COMMENT '是否已读',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_is_read (is_read),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通知表';
```

#### favorites 收藏表

```sql
CREATE TABLE favorites (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    UNIQUE KEY uk_user_dish (user_id, dish_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏表';
```

#### daily_dish_quantities 每日菜品预订量表

```sql
CREATE TABLE daily_dish_quantities (
    id VARCHAR(36) PRIMARY KEY,
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    date DATE NOT NULL COMMENT '日期',
    booked_quantity INT DEFAULT 0 COMMENT '已预订数量',
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    UNIQUE KEY uk_dish_date (dish_id, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日菜品预订量表';
```



### SQLAlchemy模型定义

```python
# app/models/user.py
from sqlalchemy import Column, String, Enum, Text, JSON, DECIMAL, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    open_id = Column(String(64), unique=True, nullable=False)
    nickname = Column(String(64), default="")
    avatar = Column(String(512), default="")
    phone = Column(String(20), nullable=True)
    role = Column(Enum("foodie", "chef"), default="foodie")
    binding_code = Column(String(8), unique=True, nullable=False)
    introduction = Column(Text, nullable=True)
    specialties = Column(JSON, nullable=True)
    rating = Column(DECIMAL(2, 1), default=5.0)
    total_orders = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

```python
# app/models/dish.py
from sqlalchemy import Column, String, Text, JSON, DECIMAL, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Dish(Base):
    __tablename__ = "dishes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chef_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    images = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    ingredients = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    category = Column(String(32), nullable=True)
    available_dates = Column(JSON, nullable=True)
    max_quantity = Column(Integer, default=10)
    rating = Column(DECIMAL(2, 1), default=5.0)
    review_count = Column(Integer, default=0)
    is_on_shelf = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    chef = relationship("User", backref="dishes")
```

```python
# app/models/order.py
from sqlalchemy import Column, String, Enum, Text, JSON, DECIMAL, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_no = Column(String(32), unique=True, nullable=False)
    foodie_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    chef_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(
        Enum("unpaid", "pending", "accepted", "cooking", "delivering", "completed", "cancelled"),
        default="unpaid"
    )
    total_price = Column(DECIMAL(10, 2), nullable=False)
    delivery_time = Column(DateTime, nullable=False)
    address_snapshot = Column(JSON, nullable=False)
    remarks = Column(Text, nullable=True)
    cancel_reason = Column(String(256), nullable=True)
    is_reviewed = Column(Boolean, default=False)
    payment_id = Column(String(64), nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    foodie = relationship("User", foreign_keys=[foodie_id])
    chef = relationship("User", foreign_keys=[chef_id])
    items = relationship("OrderItem", backref="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    dish_id = Column(String(36), nullable=False)
    dish_name = Column(String(128), nullable=False)
    dish_image = Column(String(512), nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    quantity = Column(Integer, default=1)
```

## API接口设计

### 认证接口

#### POST /api/auth/login
微信登录

**Request:**
```json
{
    "code": "微信登录code",
    "role": "foodie"  // 或 "chef"
}
```

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "token": "jwt_token_string",
        "user": {
            "id": "uuid",
            "nickname": "用户昵称",
            "avatar": "头像URL",
            "role": "foodie",
            "binding_code": "ABC12345",
            "bound_chef": null
        }
    }
}
```

#### POST /api/auth/bind-phone
绑定手机号

**Request:**
```json
{
    "encrypted_data": "加密数据",
    "iv": "初始向量"
}
```

### 用户接口

#### GET /api/user/profile
获取当前用户信息

#### PUT /api/user/profile
更新用户信息

**Request:**
```json
{
    "nickname": "新昵称",
    "avatar": "新头像URL",
    "introduction": "大厨简介",
    "specialties": ["川菜", "粤菜"]
}
```

### 菜品接口

#### GET /api/dishes
获取菜品列表（吃货端）

**Query Parameters:**
- `page`: 页码，默认1
- `page_size`: 每页数量，默认10
- `category`: 分类筛选
- `keyword`: 搜索关键词
- `date`: 预订日期

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": "uuid",
            "name": "红烧肉",
            "price": 68.00,
            "images": ["url1", "url2"],
            "tags": ["家常", "下饭"],
            "category": "中餐",
            "rating": 4.8,
            "review_count": 25,
            "chef": {
                "id": "uuid",
                "nickname": "张大厨",
                "avatar": "url",
                "rating": 4.9
            },
            "available_quantity": 5,
            "is_favorited": false
        }
    ],
    "page_info": {
        "page": 1,
        "page_size": 10,
        "total": 50,
        "total_pages": 5
    }
}
```

#### GET /api/dishes/{dish_id}
获取菜品详情

#### POST /api/chef/dishes
创建菜品（大厨端）

**Request:**
```json
{
    "name": "红烧肉",
    "price": 68.00,
    "images": ["url1", "url2"],
    "description": "精选五花肉，慢火炖煮",
    "ingredients": ["五花肉", "冰糖", "酱油"],
    "tags": ["家常", "下饭"],
    "category": "中餐",
    "available_dates": ["2024-01-15", "2024-01-16"],
    "max_quantity": 10
}
```

#### PUT /api/chef/dishes/{dish_id}
更新菜品

#### DELETE /api/chef/dishes/{dish_id}
删除菜品

#### PUT /api/chef/dishes/{dish_id}/status
切换上下架状态

**Request:**
```json
{
    "is_on_shelf": true
}
```

### 订单接口

#### POST /api/orders
创建订单

**Request:**
```json
{
    "items": [
        {
            "dish_id": "uuid",
            "quantity": 2
        }
    ],
    "delivery_time": "2024-01-15 12:00:00",
    "address_id": "uuid",
    "remarks": "少放辣"
}
```

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "order_id": "uuid",
        "order_no": "202401150001",
        "total_price": 136.00,
        "payment_params": {
            "timeStamp": "1234567890",
            "nonceStr": "xxx",
            "package": "prepay_id=xxx",
            "signType": "RSA",
            "paySign": "xxx"
        }
    }
}
```

#### GET /api/orders
获取订单列表

**Query Parameters:**
- `status`: 状态筛选（all/pending/cooking/completed）
- `page`: 页码
- `page_size`: 每页数量

#### GET /api/orders/{order_id}
获取订单详情

#### PUT /api/orders/{order_id}/cancel
取消订单

#### PUT /api/orders/{order_id}/confirm
确认收货

### 大厨订单管理接口

#### GET /api/chef/orders
获取大厨订单列表

#### PUT /api/chef/orders/{order_id}/accept
接受订单

#### PUT /api/chef/orders/{order_id}/reject
拒绝订单

**Request:**
```json
{
    "reason": "今日已约满"
}
```

#### PUT /api/chef/orders/{order_id}/cooking-done
标记烹饪完成

#### PUT /api/chef/orders/{order_id}/delivering
标记配送中

### 评价接口

#### POST /api/orders/{order_id}/review
提交评价

**Request:**
```json
{
    "rating": 5,
    "content": "非常好吃！",
    "images": ["url1", "url2"]
}
```

#### GET /api/dishes/{dish_id}/reviews
获取菜品评价列表

### 打赏接口

#### POST /api/tips
创建打赏

**Request:**
```json
{
    "chef_id": "uuid",
    "order_id": "uuid",
    "amount": 10.00,
    "message": "感谢大厨！"
}
```

#### GET /api/tips
获取打赏记录

### 地址接口

#### GET /api/addresses
获取地址列表

#### POST /api/addresses
添加地址

#### PUT /api/addresses/{address_id}
更新地址

#### DELETE /api/addresses/{address_id}
删除地址

#### PUT /api/addresses/{address_id}/default
设为默认地址

### 绑定接口

#### POST /api/bindingcode
绑定大厨

**Request:**
```json
{
    "binding_code": "ABC12345"
}
```

#### DELETE /api/binding
解除绑定

#### GET /api/binding
获取绑定信息

### 通知接口

#### GET /api/notifications
获取通知列表

#### GET /api/notifications/unread-count
获取未读数量

#### PUT /api/notifications/{notification_id}/read
标记已读

#### PUT /api/notifications/read-all
全部标记已读

### 收益接口

#### GET /api/chef/earnings/summary
获取收益汇总

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "total_earnings": 12580.00,
        "order_earnings": 11800.00,
        "tip_earnings": 780.00,
        "this_month": 3200.00,
        "this_week": 850.00
    }
}
```

#### GET /api/chef/earnings/chart
获取收益图表数据

**Query Parameters:**
- `type`: weekly/monthly

#### GET /api/chef/earnings/detail
获取收益明细

### 收藏接口

#### POST /api/favorites/{dish_id}
收藏菜品

#### DELETE /api/favorites/{dish_id}
取消收藏

#### GET /api/favorites
获取收藏列表

### 上传接口

#### POST /api/upload/image
上传图片

**Request:** multipart/form-data
- `file`: 图片文件

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "url": "http://xxx/uploads/xxx.jpg"
    }
}
```

### 支付回调接口

#### POST /api/payment/notify
微信支付回调（内部接口）



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: JWT Authentication Enforcement

*For any* protected API endpoint and any request without a valid JWT token, the API_Server SHALL return a 401 Unauthorized response.

**Validates: Requirements 1.3, 2.5, 2.6**

### Property 2: Standardized Response Format

*For any* API response from the server, the response body SHALL contain `code`, `message`, and `data` fields in JSON format.

**Validates: Requirements 1.4**

### Property 3: Binding Code Uniqueness

*For any* two users in the system, their binding codes SHALL be different. Generating a new binding code SHALL never produce a duplicate.

**Validates: Requirements 3.4**

### Property 4: Dish Ownership Validation

*For any* dish update or delete operation, if the requesting user is not the dish owner (chef_id), the API_Server SHALL return a 403 Forbidden response.

**Validates: Requirements 4.3**

### Property 5: Bound Chef Dish Filter

*For any* foodie with an active binding to a chef, the dish list returned SHALL only contain dishes where dish.chef_id equals the bound chef's ID.

**Validates: Requirements 5.1, 12.4**

### Property 6: Order Total Price Calculation

*For any* order, the total_price SHALL equal the sum of (item.price × item.quantity) for all items in the order.

**Validates: Requirements 6.3**

### Property 7: Order Status State Machine

*For any* order status transition, the transition SHALL follow the valid state machine:
- unpaid → pending (after payment) | cancelled
- pending → accepted | cancelled
- accepted → cooking | cancelled
- cooking → delivering
- delivering → completed

Any invalid transition SHALL be rejected with an error.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**

### Property 8: Dish Rating Calculation

*For any* dish with reviews, the dish.rating SHALL equal the average of all review ratings for that dish, rounded to one decimal place.

**Validates: Requirements 9.3**

### Property 9: One-to-One Binding Constraint

*For any* foodie, they SHALL be bound to at most one chef at any time. Attempting to create a second binding without unbinding first SHALL fail.

**Validates: Requirements 12.4, 12.5**

### Property 10: Chef Earnings Calculation

*For any* chef, total_earnings SHALL equal the sum of all completed order amounts (where chef_id matches) plus the sum of all received tips (where chef_id matches and status is 'paid').

**Validates: Requirements 14.4**

### Property 11: Favorite Toggle Consistency

*For any* dish and user, after favoriting the dish, the favorite record SHALL exist. After unfavoriting, the favorite record SHALL not exist. The isFavorited flag in dish info SHALL accurately reflect the current state.

**Validates: Requirements 15.1, 15.2, 15.4**

### Property 12: Address Default Uniqueness

*For any* user, at most one address SHALL have is_default=true. Setting a new default address SHALL automatically unset the previous default.

**Validates: Requirements 11.4**

### Property 13: Order Number Uniqueness

*For any* two orders in the system, their order_no values SHALL be different.

**Validates: Requirements 6.2**

### Property 14: Notification Creation on Order Events

*For any* order creation or status change, a notification SHALL be created for the relevant user (chef for new orders, foodie for status changes).

**Validates: Requirements 6.4, 13.1, 13.2**

### Property 15: Review Constraint

*For any* order, a review can only be submitted if order.status is 'completed' and order.is_reviewed is false. After submission, is_reviewed SHALL be true.

**Validates: Requirements 9.1**

## Error Handling

### HTTP状态码规范

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | 成功 | 请求成功处理 |
| 201 | 已创建 | 资源创建成功 |
| 400 | 请求错误 | 参数验证失败 |
| 401 | 未授权 | Token无效或过期 |
| 403 | 禁止访问 | 无权限操作 |
| 404 | 未找到 | 资源不存在 |
| 409 | 冲突 | 资源状态冲突 |
| 500 | 服务器错误 | 内部错误 |

### 业务错误码

```python
class ErrorCode:
    # 通用错误 1xxx
    PARAM_ERROR = 1001          # 参数错误
    UNAUTHORIZED = 1002         # 未授权
    FORBIDDEN = 1003            # 无权限
    NOT_FOUND = 1004            # 资源不存在
    
    # 用户相关 2xxx
    USER_NOT_FOUND = 2001       # 用户不存在
    INVALID_BINDING_CODE = 2002 # 绑定码无效
    ALREADY_BOUND = 2003        # 已绑定其他大厨
    SELF_BINDING = 2004         # 不能绑定自己
    NOT_CHEF = 2005             # 绑定码不属于大厨
    
    # 菜品相关 3xxx
    DISH_NOT_FOUND = 3001       # 菜品不存在
    DISH_NOT_AVAILABLE = 3002   # 菜品不可用
    DISH_SOLD_OUT = 3003        # 菜品已售罄
    NOT_DISH_OWNER = 3004       # 非菜品所有者
    
    # 订单相关 4xxx
    ORDER_NOT_FOUND = 4001      # 订单不存在
    INVALID_ORDER_STATUS = 4002 # 订单状态无效
    ORDER_NOT_CANCELLABLE = 4003 # 订单不可取消
    ORDER_ALREADY_REVIEWED = 4004 # 订单已评价
    
    # 支付相关 5xxx
    PAYMENT_FAILED = 5001       # 支付失败
    INVALID_PAYMENT_CALLBACK = 5002 # 支付回调无效
    
    # 文件相关 6xxx
    FILE_TOO_LARGE = 6001       # 文件过大
    INVALID_FILE_TYPE = 6002    # 文件类型无效
```

### 异常处理中间件

```python
# app/middleware/exception_handler.py
from fastapi import Request
from fastapi.responses import JSONResponse
from app.schemas.common import ApiResponse

class BusinessException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

async def exception_handler(request: Request, exc: Exception):
    if isinstance(exc, BusinessException):
        return JSONResponse(
            status_code=200,
            content=ApiResponse(
                code=exc.code,
                message=exc.message,
                data=None
            ).dict()
        )
    # 其他异常返回500
    return JSONResponse(
        status_code=500,
        content=ApiResponse(
            code=500,
            message="Internal Server Error",
            data=None
        ).dict()
    )
```

## Testing Strategy

### 测试框架选择

- 单元测试：pytest
- 属性测试：hypothesis
- API测试：pytest + httpx
- 数据库测试：pytest-asyncio + SQLAlchemy

### 测试配置

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.main import app
from httpx import AsyncClient

# 使用SQLite内存数据库进行测试
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture
def test_db():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### 属性测试配置

```python
# 使用 hypothesis 进行属性测试
from hypothesis import given, settings, strategies as st

# 每个属性测试运行至少100次迭代
test_settings = settings(max_examples=100)
```

### 属性测试用例

| 属性编号 | 测试描述 | 生成器 |
|----------|----------|--------|
| Property 3 | 绑定码唯一性 | 生成多个用户，验证绑定码不重复 |
| Property 5 | 绑定大厨菜品过滤 | 生成绑定关系和菜品，验证过滤结果 |
| Property 6 | 订单价格计算 | 生成随机订单项，验证总价计算 |
| Property 7 | 订单状态转换 | 生成状态转换序列，验证合法性 |
| Property 8 | 菜品评分计算 | 生成随机评价，验证平均分计算 |
| Property 10 | 收益计算 | 生成订单和打赏，验证收益汇总 |
| Property 11 | 收藏操作一致性 | 生成收藏/取消操作序列 |
| Property 12 | 默认地址唯一性 | 生成多个地址，验证默认唯一 |

### 单元测试覆盖

1. **服务层测试**
   - UserService: 登录、注册、更新资料
   - DishService: CRUD操作、上下架
   - OrderService: 创建、状态转换、取消
   - BindingService: 绑定、解绑

2. **工具函数测试**
   - JWT生成和验证
   - 绑定码生成
   - 订单号生成
   - 价格计算

3. **API端点测试**
   - 认证流程
   - 权限验证
   - 参数验证
   - 响应格式

### 测试命名规范

```python
# Feature: private-chef-backend, Property 6: Order Total Price Calculation
class TestOrderPriceCalculation:
    @given(st.lists(st.tuples(st.decimals(min_value=0.01, max_value=1000), st.integers(min_value=1, max_value=10))))
    @test_settings
    def test_property_6_total_price_equals_sum_of_items(self, items):
        """Property 6: total price equals sum of item prices times quantities"""
        # ...
```

