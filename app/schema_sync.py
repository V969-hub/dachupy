"""Startup database schema synchronization.

This module keeps the running database compatible with the current models.
It is intentionally additive: it creates missing tables, adds missing columns,
and refreshes enum definitions/indexes without deleting user data.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import Base, engine as app_engine

logger = logging.getLogger(__name__)

MYSQL_UNKNOWN_DATABASE_ERROR_CODE = 1049
MYSQL_DEFAULT_CHARSET = "utf8mb4"
MYSQL_DEFAULT_COLLATION = "utf8mb4_general_ci"

_COLUMN_ATTRIBUTE_KEYWORDS = (
    "NOT NULL",
    "NULL",
    "DEFAULT",
    "COMMENT",
    "PRIMARY KEY",
    "ON UPDATE",
    "AUTO_INCREMENT",
)


NOTIFICATION_TYPES = (
    "new_order",
    "order_status",
    "binding",
    "tip",
    "system",
    "couple_memo",
    "couple_anniversary",
    "couple_bind",
    "couple_date_plan",
    "couple_date_draw",
)


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    ddl: str

    @property
    def definition(self) -> str:
        _, _, definition = self.ddl.partition(" ")
        return definition or self.ddl

    @property
    def alter_sql(self) -> str:
        sanitized = re.sub(r"\s+PRIMARY\s+KEY\b", "", self.definition, flags=re.IGNORECASE).strip()
        return f"{self.name} {sanitized}"


@dataclass(frozen=True)
class IndexSpec:
    name: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]
    indexes: tuple[IndexSpec, ...] = field(default_factory=tuple)

    def create_sql(
        self,
        charset: str = MYSQL_DEFAULT_CHARSET,
        collation: str = MYSQL_DEFAULT_COLLATION,
    ) -> str:
        column_sql = ",\n    ".join(column.ddl for column in self.columns)
        return (
            f"CREATE TABLE IF NOT EXISTS {self.name} (\n"
            f"    {column_sql}\n"
            f") ENGINE=InnoDB DEFAULT CHARSET={charset} "
            f"COLLATE={collation}"
        )


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        "users",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("open_id", "open_id VARCHAR(64) NOT NULL COMMENT '微信openId'"),
            ColumnSpec("nickname", "nickname VARCHAR(64) NOT NULL DEFAULT '' COMMENT '昵称'"),
            ColumnSpec("avatar", "avatar VARCHAR(512) DEFAULT '' COMMENT '头像URL'"),
            ColumnSpec("phone", "phone VARCHAR(20) DEFAULT NULL COMMENT '手机号'"),
            ColumnSpec("role", "role ENUM('foodie', 'chef') NOT NULL DEFAULT 'foodie' COMMENT '角色'"),
            ColumnSpec("binding_code", "binding_code VARCHAR(8) NOT NULL COMMENT '专属绑定码'"),
            ColumnSpec("couple_code", "couple_code VARCHAR(8) DEFAULT NULL COMMENT '情侣邀请码'"),
            ColumnSpec("is_open", "is_open TINYINT(1) DEFAULT 1 COMMENT '是否营业中'"),
            ColumnSpec("service_start_time", "service_start_time VARCHAR(5) DEFAULT '09:00' COMMENT '接单开始时间'"),
            ColumnSpec("service_end_time", "service_end_time VARCHAR(5) DEFAULT '21:00' COMMENT '接单结束时间'"),
            ColumnSpec("rest_notice", "rest_notice VARCHAR(255) DEFAULT NULL COMMENT '休息说明'"),
            ColumnSpec("introduction", "introduction TEXT DEFAULT NULL COMMENT '大厨简介'"),
            ColumnSpec("specialties", "specialties JSON DEFAULT NULL COMMENT '大厨擅长菜系'"),
            ColumnSpec("virtual_coin_balance", "virtual_coin_balance DECIMAL(10,2) NOT NULL DEFAULT 200.00 COMMENT '虚拟币余额'"),
            ColumnSpec("rating", "rating DECIMAL(2,1) DEFAULT 5.0 COMMENT '大厨评分'"),
            ColumnSpec("total_orders", "total_orders INT DEFAULT 0 COMMENT '总订单数'"),
            ColumnSpec("is_deleted", "is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("uq_users_open_id", ("open_id",), unique=True),
            IndexSpec("uq_users_binding_code", ("binding_code",), unique=True),
            IndexSpec("uq_users_couple_code", ("couple_code",), unique=True),
            IndexSpec("idx_users_role", ("role",)),
        ),
    ),
    TableSpec(
        "dishes",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("chef_id", "chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID'"),
            ColumnSpec("name", "name VARCHAR(128) NOT NULL COMMENT '菜品名称'"),
            ColumnSpec("price", "price DECIMAL(10,2) NOT NULL COMMENT '价格'"),
            ColumnSpec("images", "images JSON NOT NULL COMMENT '图片URL列表'"),
            ColumnSpec("description", "description TEXT DEFAULT NULL COMMENT '描述'"),
            ColumnSpec("ingredients", "ingredients JSON DEFAULT NULL COMMENT '食材列表'"),
            ColumnSpec("tags", "tags JSON DEFAULT NULL COMMENT '口味标签'"),
            ColumnSpec("category", "category VARCHAR(32) DEFAULT NULL COMMENT '菜系分类'"),
            ColumnSpec("available_dates", "available_dates JSON DEFAULT NULL COMMENT '可预订日期'"),
            ColumnSpec("max_quantity", "max_quantity INT DEFAULT 10 COMMENT '每日最大份数'"),
            ColumnSpec("rating", "rating DECIMAL(2,1) DEFAULT 5.0 COMMENT '评分'"),
            ColumnSpec("review_count", "review_count INT DEFAULT 0 COMMENT '评价数'"),
            ColumnSpec("is_on_shelf", "is_on_shelf TINYINT(1) DEFAULT 1 COMMENT '是否上架'"),
            ColumnSpec("is_deleted", "is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_dishes_chef_id", ("chef_id",)),
            IndexSpec("idx_dishes_category", ("category",)),
            IndexSpec("idx_dishes_is_on_shelf", ("is_on_shelf",)),
        ),
    ),
    TableSpec(
        "daily_dish_quantities",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("dish_id", "dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID'"),
            ColumnSpec("date", "date DATE NOT NULL COMMENT '日期'"),
            ColumnSpec("booked_quantity", "booked_quantity INT DEFAULT 0 COMMENT '已预订数量'"),
        ),
        (
            IndexSpec("uk_dish_date", ("dish_id", "date"), unique=True),
        ),
    ),
    TableSpec(
        "orders",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("order_no", "order_no VARCHAR(32) NOT NULL COMMENT '订单号'"),
            ColumnSpec("foodie_id", "foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID'"),
            ColumnSpec("chef_id", "chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID'"),
            ColumnSpec(
                "status",
                "status ENUM('unpaid', 'pending', 'accepted', 'cooking', 'delivering', 'completed', 'cancelled') "
                "NOT NULL DEFAULT 'unpaid' COMMENT '订单状态'",
            ),
            ColumnSpec("total_price", "total_price DECIMAL(10,2) NOT NULL COMMENT '总价'"),
            ColumnSpec("delivery_time", "delivery_time DATETIME NOT NULL COMMENT '配送时间'"),
            ColumnSpec("address_snapshot", "address_snapshot JSON NOT NULL COMMENT '地址快照'"),
            ColumnSpec("remarks", "remarks TEXT DEFAULT NULL COMMENT '备注'"),
            ColumnSpec("cancel_reason", "cancel_reason VARCHAR(256) DEFAULT NULL COMMENT '取消原因'"),
            ColumnSpec("is_reviewed", "is_reviewed TINYINT(1) DEFAULT 0 COMMENT '是否已评价'"),
            ColumnSpec("payment_id", "payment_id VARCHAR(64) DEFAULT NULL COMMENT '微信支付订单号'"),
            ColumnSpec("payment_method", "payment_method VARCHAR(32) NOT NULL DEFAULT 'free' COMMENT '支付方式'"),
            ColumnSpec("wallet_paid_amount", "wallet_paid_amount DECIMAL(10,2) DEFAULT 0 COMMENT '虚拟币支付金额'"),
            ColumnSpec(
                "refund_status",
                "refund_status ENUM('none', 'partial', 'refunded') NOT NULL DEFAULT 'none' COMMENT '退款状态'",
            ),
            ColumnSpec("refund_amount", "refund_amount DECIMAL(10,2) DEFAULT 0 COMMENT '累计退款金额'"),
            ColumnSpec("refund_reason", "refund_reason VARCHAR(256) DEFAULT NULL COMMENT '最近一次退款原因'"),
            ColumnSpec("refunded_at", "refunded_at DATETIME DEFAULT NULL COMMENT '最近退款时间'"),
            ColumnSpec("is_deleted", "is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
            ColumnSpec("completed_at", "completed_at DATETIME DEFAULT NULL COMMENT '完成时间'"),
        ),
        (
            IndexSpec("uq_orders_order_no", ("order_no",), unique=True),
            IndexSpec("idx_orders_foodie_id", ("foodie_id",)),
            IndexSpec("idx_orders_chef_id", ("chef_id",)),
            IndexSpec("idx_orders_status", ("status",)),
            IndexSpec("idx_orders_refund_status", ("refund_status",)),
            IndexSpec("idx_orders_created_at", ("created_at",)),
        ),
    ),
    TableSpec(
        "order_items",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("order_id", "order_id VARCHAR(36) NOT NULL COMMENT '订单ID'"),
            ColumnSpec("dish_id", "dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID'"),
            ColumnSpec("dish_name", "dish_name VARCHAR(128) NOT NULL COMMENT '菜品名称快照'"),
            ColumnSpec("dish_image", "dish_image VARCHAR(512) DEFAULT NULL COMMENT '菜品图片快照'"),
            ColumnSpec("price", "price DECIMAL(10,2) NOT NULL COMMENT '单价快照'"),
            ColumnSpec("quantity", "quantity INT NOT NULL DEFAULT 1 COMMENT '数量'"),
        ),
        (
            IndexSpec("idx_order_items_order_id", ("order_id",)),
        ),
    ),
    TableSpec(
        "order_refunds",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("order_id", "order_id VARCHAR(36) NOT NULL COMMENT '订单ID'"),
            ColumnSpec("amount", "amount DECIMAL(10,2) NOT NULL COMMENT '退款金额'"),
            ColumnSpec("status", "status ENUM('refunded', 'voided') NOT NULL DEFAULT 'refunded' COMMENT '退款记录状态'"),
            ColumnSpec("method", "method VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '退款方式'"),
            ColumnSpec("reason", "reason VARCHAR(256) NOT NULL COMMENT '退款原因'"),
            ColumnSpec("note", "note TEXT DEFAULT NULL COMMENT '退款备注'"),
            ColumnSpec("operator_name", "operator_name VARCHAR(64) NOT NULL COMMENT '操作人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_order_refunds_order_id", ("order_id",)),
            IndexSpec("idx_order_refunds_created_at", ("created_at",)),
            IndexSpec("idx_order_refunds_status", ("status",)),
        ),
    ),
    TableSpec(
        "wallet_transactions",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("user_id", "user_id VARCHAR(36) NOT NULL COMMENT '用户ID'"),
            ColumnSpec("transaction_type", "transaction_type VARCHAR(32) NOT NULL COMMENT '流水类型'"),
            ColumnSpec("change_amount", "change_amount DECIMAL(10,2) NOT NULL COMMENT '变动金额'"),
            ColumnSpec("balance_after", "balance_after DECIMAL(10,2) NOT NULL COMMENT '变动后余额'"),
            ColumnSpec("related_order_id", "related_order_id VARCHAR(36) DEFAULT NULL COMMENT '关联订单ID'"),
            ColumnSpec("note", "note VARCHAR(255) DEFAULT NULL COMMENT '备注'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
        ),
        (
            IndexSpec("idx_wallet_transactions_user_id", ("user_id",)),
            IndexSpec("idx_wallet_transactions_order_id", ("related_order_id",)),
            IndexSpec("idx_wallet_transactions_created_at", ("created_at",)),
        ),
    ),
    TableSpec(
        "reviews",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("order_id", "order_id VARCHAR(36) NOT NULL COMMENT '订单ID'"),
            ColumnSpec("foodie_id", "foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID'"),
            ColumnSpec("chef_id", "chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID'"),
            ColumnSpec("dish_id", "dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID'"),
            ColumnSpec("rating", "rating TINYINT NOT NULL COMMENT '评分1-5'"),
            ColumnSpec("content", "content TEXT DEFAULT NULL COMMENT '评价内容'"),
            ColumnSpec("images", "images JSON DEFAULT NULL COMMENT '评价图片'"),
            ColumnSpec("is_deleted", "is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
        ),
        (
            IndexSpec("idx_reviews_dish_id", ("dish_id",)),
            IndexSpec("idx_reviews_chef_id", ("chef_id",)),
        ),
    ),
    TableSpec(
        "tips",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("foodie_id", "foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID'"),
            ColumnSpec("chef_id", "chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID'"),
            ColumnSpec("order_id", "order_id VARCHAR(36) DEFAULT NULL COMMENT '关联订单ID'"),
            ColumnSpec("amount", "amount DECIMAL(10,2) NOT NULL COMMENT '打赏金额'"),
            ColumnSpec("message", "message VARCHAR(256) DEFAULT NULL COMMENT '留言'"),
            ColumnSpec("payment_id", "payment_id VARCHAR(64) DEFAULT NULL COMMENT '微信支付订单号'"),
            ColumnSpec("status", "status ENUM('pending', 'paid', 'failed') DEFAULT 'pending' COMMENT '支付状态'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
        ),
        (
            IndexSpec("idx_tips_chef_id", ("chef_id",)),
            IndexSpec("idx_tips_created_at", ("created_at",)),
        ),
    ),
    TableSpec(
        "addresses",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("user_id", "user_id VARCHAR(36) NOT NULL COMMENT '用户ID'"),
            ColumnSpec("name", "name VARCHAR(32) NOT NULL COMMENT '联系人'"),
            ColumnSpec("phone", "phone VARCHAR(20) NOT NULL COMMENT '联系电话'"),
            ColumnSpec("province", "province VARCHAR(32) NOT NULL COMMENT '省'"),
            ColumnSpec("city", "city VARCHAR(32) NOT NULL COMMENT '市'"),
            ColumnSpec("district", "district VARCHAR(32) NOT NULL COMMENT '区'"),
            ColumnSpec("detail", "detail VARCHAR(256) NOT NULL COMMENT '详细地址'"),
            ColumnSpec("is_default", "is_default TINYINT(1) DEFAULT 0 COMMENT '是否默认'"),
            ColumnSpec("is_deleted", "is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_addresses_user_id", ("user_id",)),
        ),
    ),
    TableSpec(
        "bindings",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("foodie_id", "foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID'"),
            ColumnSpec("chef_id", "chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID'"),
            ColumnSpec("binding_code", "binding_code VARCHAR(8) NOT NULL COMMENT '使用的绑定码'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
        ),
        (
            IndexSpec("uq_bindings_foodie_id", ("foodie_id",), unique=True),
            IndexSpec("idx_bindings_chef_id", ("chef_id",)),
        ),
    ),
    TableSpec(
        "notifications",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("user_id", "user_id VARCHAR(36) NOT NULL COMMENT '用户ID'"),
            ColumnSpec(
                "type",
                "type ENUM("
                + ", ".join(f"'{item}'" for item in NOTIFICATION_TYPES)
                + ") NOT NULL COMMENT '通知类型'",
            ),
            ColumnSpec("title", "title VARCHAR(64) NOT NULL COMMENT '标题'"),
            ColumnSpec("content", "content VARCHAR(256) NOT NULL COMMENT '内容'"),
            ColumnSpec("data", "data JSON DEFAULT NULL COMMENT '附加数据'"),
            ColumnSpec("is_read", "is_read TINYINT(1) DEFAULT 0 COMMENT '是否已读'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
        ),
        (
            IndexSpec("idx_notifications_user_id", ("user_id",)),
            IndexSpec("idx_notifications_is_read", ("is_read",)),
            IndexSpec("idx_notifications_created_at", ("created_at",)),
            IndexSpec("idx_notifications_type", ("type",)),
        ),
    ),
    TableSpec(
        "admin_broadcasts",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("title", "title VARCHAR(64) NOT NULL COMMENT '广播标题'"),
            ColumnSpec("content", "content VARCHAR(256) NOT NULL COMMENT '广播内容'"),
            ColumnSpec("target_role", "target_role VARCHAR(16) DEFAULT NULL COMMENT '目标角色'"),
            ColumnSpec("recipient_count", "recipient_count INT DEFAULT 0 COMMENT '接收人数'"),
            ColumnSpec("created_by", "created_by VARCHAR(64) NOT NULL COMMENT '创建人'"),
            ColumnSpec("filters", "filters JSON DEFAULT NULL COMMENT '筛选条件快照'"),
            ColumnSpec("note", "note TEXT DEFAULT NULL COMMENT '补充说明'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
        ),
        (
            IndexSpec("idx_admin_broadcasts_created_at", ("created_at",)),
            IndexSpec("idx_admin_broadcasts_target_role", ("target_role",)),
        ),
    ),
    TableSpec(
        "favorites",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("user_id", "user_id VARCHAR(36) NOT NULL COMMENT '用户ID'"),
            ColumnSpec("dish_id", "dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
        ),
        (
            IndexSpec("uk_user_dish", ("user_id", "dish_id"), unique=True),
            IndexSpec("idx_favorites_user_id", ("user_id",)),
        ),
    ),
    TableSpec(
        "couple_relationships",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("user_a_id", "user_a_id VARCHAR(36) NOT NULL COMMENT '关系用户A'"),
            ColumnSpec("user_b_id", "user_b_id VARCHAR(36) NOT NULL COMMENT '关系用户B'"),
            ColumnSpec("anniversary_date", "anniversary_date DATE DEFAULT NULL COMMENT '在一起日期'"),
            ColumnSpec("status", "status ENUM('active', 'inactive') NOT NULL DEFAULT 'active' COMMENT '关系状态'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_couple_relationship_user_a", ("user_a_id",)),
            IndexSpec("idx_couple_relationship_user_b", ("user_b_id",)),
            IndexSpec("idx_couple_relationship_status", ("status",)),
        ),
    ),
    TableSpec(
        "couple_memos",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("title", "title VARCHAR(100) NOT NULL COMMENT '标题'"),
            ColumnSpec("content", "content TEXT DEFAULT NULL COMMENT '内容'"),
            ColumnSpec("category", "category VARCHAR(32) NOT NULL DEFAULT '日常' COMMENT '分类'"),
            ColumnSpec("remind_at", "remind_at DATETIME DEFAULT NULL COMMENT '提醒时间'"),
            ColumnSpec("is_completed", "is_completed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已完成'"),
            ColumnSpec("is_pinned", "is_pinned TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否置顶'"),
            ColumnSpec("created_by", "created_by VARCHAR(36) NOT NULL COMMENT '创建人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_couple_memos_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_memos_remind_at", ("remind_at",)),
        ),
    ),
    TableSpec(
        "couple_anniversaries",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("title", "title VARCHAR(100) NOT NULL COMMENT '标题'"),
            ColumnSpec("date", "date DATE NOT NULL COMMENT '纪念日日期'"),
            ColumnSpec("type", "type VARCHAR(32) NOT NULL DEFAULT '自定义' COMMENT '纪念日类型'"),
            ColumnSpec("remind_days_before", "remind_days_before INT NOT NULL DEFAULT 0 COMMENT '提前提醒天数'"),
            ColumnSpec("note", "note TEXT DEFAULT NULL COMMENT '备注'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_couple_anniversaries_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_anniversaries_date", ("date",)),
        ),
    ),
    TableSpec(
        "couple_date_plans",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("title", "title VARCHAR(100) NOT NULL COMMENT '计划标题'"),
            ColumnSpec("plan_at", "plan_at DATETIME NOT NULL COMMENT '约饭时间'"),
            ColumnSpec("location", "location VARCHAR(128) DEFAULT NULL COMMENT '约饭地点'"),
            ColumnSpec("note", "note TEXT DEFAULT NULL COMMENT '备注'"),
            ColumnSpec("anniversary_id", "anniversary_id VARCHAR(36) DEFAULT NULL COMMENT '关联纪念日'"),
            ColumnSpec("order_id", "order_id VARCHAR(36) DEFAULT NULL COMMENT '关联订单'"),
            ColumnSpec("menu_items", "menu_items JSON DEFAULT NULL COMMENT '约饭菜单快照'"),
            ColumnSpec("menu_total", "menu_total DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '约饭菜单总额'"),
            ColumnSpec(
                "status",
                "status ENUM('planned', 'completed', 'cancelled') NOT NULL DEFAULT 'planned' COMMENT '计划状态'",
            ),
            ColumnSpec("created_by", "created_by VARCHAR(36) NOT NULL COMMENT '创建人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_couple_date_plans_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_date_plans_plan_at", ("plan_at",)),
        ),
    ),
    TableSpec(
        "couple_restaurant_categories",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("name", "name VARCHAR(64) NOT NULL COMMENT '分类名称'"),
            ColumnSpec("image", "image VARCHAR(255) DEFAULT NULL COMMENT '分类图片'"),
            ColumnSpec("sort_order", "sort_order INT NOT NULL DEFAULT 0 COMMENT '排序值'"),
            ColumnSpec("created_by", "created_by VARCHAR(36) NOT NULL COMMENT '创建人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_couple_restaurant_categories_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_restaurant_categories_sort", ("relationship_id", "sort_order")),
        ),
    ),
    TableSpec(
        "couple_restaurant_items",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("category_id", "category_id VARCHAR(36) NOT NULL COMMENT '分类ID'"),
            ColumnSpec("name", "name VARCHAR(100) NOT NULL COMMENT '菜名'"),
            ColumnSpec("price", "price DECIMAL(10,2) NOT NULL COMMENT '价格'"),
            ColumnSpec("images", "images JSON NOT NULL COMMENT '图片列表'"),
            ColumnSpec("tags", "tags JSON DEFAULT NULL COMMENT '偏好标签'"),
            ColumnSpec("description", "description TEXT DEFAULT NULL COMMENT '描述'"),
            ColumnSpec("created_by", "created_by VARCHAR(36) NOT NULL COMMENT '创建人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_couple_restaurant_items_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_restaurant_items_category", ("category_id",)),
        ),
    ),
    TableSpec(
        "couple_restaurant_cart_items",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("item_id", "item_id VARCHAR(36) NOT NULL COMMENT '菜单ID'"),
            ColumnSpec("quantity", "quantity INT NOT NULL DEFAULT 1 COMMENT '数量'"),
            ColumnSpec("created_by", "created_by VARCHAR(36) NOT NULL COMMENT '创建人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec(
                "uk_couple_restaurant_cart_relationship_item",
                ("relationship_id", "item_id"),
                unique=True,
            ),
            IndexSpec("idx_couple_restaurant_cart_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_restaurant_cart_item", ("item_id",)),
        ),
    ),
    TableSpec(
        "couple_restaurant_wishes",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("item_id", "item_id VARCHAR(36) NOT NULL COMMENT '菜单ID'"),
            ColumnSpec("note", "note TEXT DEFAULT NULL COMMENT '想吃备注'"),
            ColumnSpec("priority", "priority INT NOT NULL DEFAULT 0 COMMENT '优先级'"),
            ColumnSpec(
                "status",
                "status ENUM('active', 'done', 'archived') NOT NULL DEFAULT 'active' COMMENT '想吃状态'",
            ),
            ColumnSpec("created_by", "created_by VARCHAR(36) NOT NULL COMMENT '创建人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec(
                "uk_couple_restaurant_wish_relationship_item",
                ("relationship_id", "item_id"),
                unique=True,
            ),
            IndexSpec("idx_couple_restaurant_wishes_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_restaurant_wishes_status", ("relationship_id", "status")),
            IndexSpec("idx_couple_restaurant_wishes_item", ("item_id",)),
        ),
    ),
    TableSpec(
        "couple_date_draws",
        (
            ColumnSpec("id", "id VARCHAR(36) PRIMARY KEY"),
            ColumnSpec("relationship_id", "relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID'"),
            ColumnSpec("title", "title VARCHAR(100) NOT NULL COMMENT '卡片标题'"),
            ColumnSpec("subtitle", "subtitle VARCHAR(255) DEFAULT NULL COMMENT '卡片副标题'"),
            ColumnSpec("card_type", "card_type VARCHAR(32) NOT NULL COMMENT '卡片类型'"),
            ColumnSpec("source_item_id", "source_item_id VARCHAR(36) DEFAULT NULL COMMENT '来源记录ID'"),
            ColumnSpec("source_item_type", "source_item_type VARCHAR(32) DEFAULT NULL COMMENT '来源记录类型'"),
            ColumnSpec("content", "content TEXT DEFAULT NULL COMMENT '卡片内容'"),
            ColumnSpec("payload", "payload JSON DEFAULT NULL COMMENT '卡片数据'"),
            ColumnSpec("plan_id", "plan_id VARCHAR(36) DEFAULT NULL COMMENT '关联约饭计划'"),
            ColumnSpec(
                "status",
                "status ENUM('drawn', 'accepted', 'completed', 'cancelled') NOT NULL DEFAULT 'drawn' COMMENT '抽卡状态'",
            ),
            ColumnSpec("created_by", "created_by VARCHAR(36) NOT NULL COMMENT '创建人'"),
            ColumnSpec("created_at", "created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"),
            ColumnSpec(
                "updated_at",
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            ),
        ),
        (
            IndexSpec("idx_couple_date_draws_relationship", ("relationship_id",)),
            IndexSpec("idx_couple_date_draws_status", ("relationship_id", "status")),
            IndexSpec("idx_couple_date_draws_card_type", ("relationship_id", "card_type")),
            IndexSpec("idx_couple_date_draws_plan", ("plan_id",)),
        ),
    ),
)


def _get_mysql_operational_error_code(error: Exception) -> int | None:
    orig = getattr(error, "orig", None)
    args = getattr(orig, "args", None) or getattr(error, "args", ())
    if not args:
        return None

    try:
        return int(args[0])
    except (TypeError, ValueError):
        return None


def create_database_if_missing(engine: Engine = app_engine) -> None:
    if engine.dialect.name != "mysql":
        return

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return
    except OperationalError as exc:
        error_code = _get_mysql_operational_error_code(exc)
        if error_code != MYSQL_UNKNOWN_DATABASE_ERROR_CODE:
            raise
        logger.info("数据库自检: 数据库 %s 不存在，准备自动创建", settings.DB_NAME)

    server_url = (
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/"
    )
    server_engine = create_engine(server_url, pool_pre_ping=True)
    try:
        with server_engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
                    "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"
                )
            )
        logger.info("数据库自检: 已确保数据库 %s 存在", settings.DB_NAME)
    finally:
        server_engine.dispose()
        engine.dispose()


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _get_index(inspector, table_name: str, index_name: str) -> dict | None:
    if not _table_exists(inspector, table_name):
        return None
    for index in inspector.get_indexes(table_name):
        if index["name"] == index_name:
            return index
    return None


def _unique_index_on_columns_exists(inspector, table_name: str, columns: Iterable[str]) -> bool:
    if not _table_exists(inspector, table_name):
        return False

    target = tuple(columns)
    for index in inspector.get_indexes(table_name):
        if bool(index.get("unique")) and tuple(index.get("column_names") or ()) == target:
            return True
    return False


def _index_on_columns_exists(
    inspector,
    table_name: str,
    columns: Iterable[str],
    *,
    unique: bool,
) -> bool:
    if not _table_exists(inspector, table_name):
        return False

    target = tuple(columns)
    for index in inspector.get_indexes(table_name):
        if tuple(index.get("column_names") or ()) == target and bool(index.get("unique")) == unique:
            return True
    return False


def _index_matches(index: dict, spec: IndexSpec) -> bool:
    return (
        tuple(index.get("column_names") or ()) == spec.columns
        and bool(index.get("unique")) == spec.unique
    )


def _normalize_sql_fragment(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).replace("`", "").strip().lower()
    normalized = normalized.replace("current_timestamp()", "current_timestamp")
    normalized = normalized.replace(", ", ",")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _normalize_default_value(value) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if not normalized:
        return ""

    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1]

    normalized = normalized.replace("''", "'").replace('""', '"').strip()
    lowered = normalized.lower()
    if lowered == "null":
        return None
    if lowered in {"current_timestamp()", "current_timestamp"}:
        return "current_timestamp"
    return normalized


def _split_sql_fragment(value: str, stop_keywords: tuple[str, ...] = _COLUMN_ATTRIBUTE_KEYWORDS) -> tuple[str, str]:
    text = value.lstrip()
    if not text:
        return "", ""

    depth = 0
    quote_char = ""
    index = 0

    while index < len(text):
        char = text[index]

        if quote_char:
            if char == quote_char:
                if index + 1 < len(text) and text[index + 1] == quote_char:
                    index += 2
                    continue
                quote_char = ""
        else:
            if char in {"'", '"'}:
                quote_char = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)
            elif char.isspace() and depth == 0:
                remainder = text[index:].lstrip()
                remainder_upper = remainder.upper()
                if any(remainder_upper.startswith(keyword) for keyword in stop_keywords):
                    return text[:index].rstrip(), remainder

        index += 1

    return text.rstrip(), ""


def _consume_quoted_value(value: str) -> tuple[str, str]:
    text = value.lstrip()
    if not text:
        return "", ""
    if text[0] not in {"'", '"'}:
        return _split_sql_fragment(text)

    quote_char = text[0]
    index = 1
    while index < len(text):
        if text[index] == quote_char:
            if index + 1 < len(text) and text[index + 1] == quote_char:
                index += 2
                continue
            return text[: index + 1], text[index + 1 :].lstrip()
        index += 1

    return text, ""


def _parse_expected_column(column: ColumnSpec) -> dict:
    column_type, remainder = _split_sql_fragment(column.definition)
    expected = {
        "column_type": _normalize_sql_fragment(column_type),
        "nullable": None,
        "default": None,
        "comment": "",
        "primary": False,
        "on_update": None,
        "auto_increment": False,
    }

    remainder = remainder.lstrip()
    while remainder:
        upper = remainder.upper()

        if upper.startswith("NOT NULL"):
            expected["nullable"] = False
            remainder = remainder[len("NOT NULL") :].lstrip()
            continue

        if upper.startswith("NULL"):
            expected["nullable"] = True
            remainder = remainder[len("NULL") :].lstrip()
            continue

        if upper.startswith("DEFAULT"):
            raw_value = remainder[len("DEFAULT") :].lstrip()
            if raw_value.upper().startswith("NULL"):
                expected["default"] = None
                remainder = raw_value[len("NULL") :].lstrip()
            else:
                default_value, remainder = _split_sql_fragment(raw_value)
                expected["default"] = _normalize_default_value(default_value)
            continue

        if upper.startswith("COMMENT"):
            raw_value = remainder[len("COMMENT") :].lstrip()
            comment_value, remainder = _consume_quoted_value(raw_value)
            if comment_value.startswith(("'", '"')) and comment_value.endswith(("'", '"')):
                expected["comment"] = comment_value[1:-1].replace("''", "'")
            else:
                expected["comment"] = comment_value
            continue

        if upper.startswith("PRIMARY KEY"):
            expected["primary"] = True
            expected["nullable"] = False
            remainder = remainder[len("PRIMARY KEY") :].lstrip()
            continue

        if upper.startswith("ON UPDATE"):
            raw_value = remainder[len("ON UPDATE") :].lstrip()
            on_update_value, remainder = _split_sql_fragment(raw_value)
            expected["on_update"] = _normalize_sql_fragment(on_update_value)
            continue

        if upper.startswith("AUTO_INCREMENT"):
            expected["auto_increment"] = True
            remainder = remainder[len("AUTO_INCREMENT") :].lstrip()
            continue

        _, next_remainder = _split_sql_fragment(remainder)
        if next_remainder == remainder:
            break
        remainder = next_remainder.lstrip()

    if expected["nullable"] is None:
        expected["nullable"] = not expected["primary"]

    return expected


def _get_current_column_state(conn, table_name: str, column_name: str) -> dict | None:
    row = conn.execute(
        text(
            """
            SELECT
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                EXTRA,
                COLUMN_COMMENT,
                COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :schema
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
            """
        ),
        {
            "schema": settings.DB_NAME,
            "table_name": table_name,
            "column_name": column_name,
        },
    ).mappings().first()

    if not row:
        return None

    extra = _normalize_sql_fragment(row["EXTRA"]) or ""
    return {
        "column_type": _normalize_sql_fragment(row["COLUMN_TYPE"]),
        "nullable": str(row["IS_NULLABLE"]).upper() == "YES",
        "default": _normalize_default_value(row["COLUMN_DEFAULT"]),
        "comment": row["COLUMN_COMMENT"] or "",
        "primary": str(row["COLUMN_KEY"]).upper() == "PRI",
        "on_update": "on update current_timestamp" in extra,
        "extra": extra,
        "auto_increment": "auto_increment" in extra,
    }


def _column_definition_matches(conn, table_name: str, column: ColumnSpec) -> bool:
    expected = _parse_expected_column(column)
    current = _get_current_column_state(conn, table_name, column.name)
    if not current:
        return False

    if current["column_type"] != expected["column_type"]:
        return False
    if current["nullable"] != expected["nullable"]:
        return False
    if current["default"] != expected["default"]:
        return False
    if current["comment"] != expected["comment"]:
        return False
    if current["primary"] != expected["primary"]:
        return False
    if current["auto_increment"] != expected["auto_increment"]:
        return False

    expected_on_update = bool(expected["on_update"])
    if current["on_update"] != expected_on_update:
        return False
    if expected_on_update and expected["on_update"] not in current["extra"]:
        return False

    return True


def _get_current_table_collation(conn, table_name: str) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT TABLE_COLLATION
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :schema
              AND TABLE_NAME = :table_name
            """
        ),
        {
            "schema": settings.DB_NAME,
            "table_name": table_name,
        },
    ).mappings().first()

    if not row:
        return None

    value = row.get("TABLE_COLLATION")
    return str(value).strip() if value else None


def _get_schema_charset_and_collation(conn) -> tuple[str, str]:
    row = conn.execute(
        text(
            """
            SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
            FROM information_schema.SCHEMATA
            WHERE SCHEMA_NAME = :schema
            """
        ),
        {"schema": settings.DB_NAME},
    ).mappings().first()

    if not row:
        return MYSQL_DEFAULT_CHARSET, MYSQL_DEFAULT_COLLATION

    charset = str(row.get("DEFAULT_CHARACTER_SET_NAME") or MYSQL_DEFAULT_CHARSET).strip() or MYSQL_DEFAULT_CHARSET
    collation = str(row.get("DEFAULT_COLLATION_NAME") or MYSQL_DEFAULT_COLLATION).strip() or MYSQL_DEFAULT_COLLATION
    return charset, collation


def _refresh_inspector(engine: Engine):
    return inspect(engine)


def _sync_mysql_schema(engine: Engine) -> None:
    create_database_if_missing(engine)
    inspector = _refresh_inspector(engine)

    with engine.begin() as conn:
        target_charset, target_collation = _get_schema_charset_and_collation(conn)

        for table in TABLE_SPECS:
            if not _table_exists(inspector, table.name):
                conn.execute(text(table.create_sql(target_charset, target_collation)))
                logger.info("数据库自检: 已创建缺失表 %s", table.name)
                inspector = _refresh_inspector(engine)

            current_collation = _get_current_table_collation(conn, table.name)
            if current_collation and current_collation != target_collation:
                conn.execute(
                    text(
                        f"ALTER TABLE {table.name} "
                        f"CONVERT TO CHARACTER SET {target_charset} "
                        f"COLLATE {target_collation}"
                    )
                )
                logger.info(
                    "数据库自检: 已统一表排序规则 %s (%s -> %s)",
                    table.name,
                    current_collation,
                    target_collation,
                )
                inspector = _refresh_inspector(engine)

            for column in table.columns:
                if not _column_exists(inspector, table.name, column.name):
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.ddl}"))
                    logger.info("数据库自检: 已补充字段 %s.%s", table.name, column.name)
                    inspector = _refresh_inspector(engine)
                    continue

                if not _column_definition_matches(conn, table.name, column):
                    conn.execute(text(f"ALTER TABLE {table.name} MODIFY COLUMN {column.alter_sql}"))
                    logger.info("数据库自检: 已校准字段定义 %s.%s", table.name, column.name)
                    inspector = _refresh_inspector(engine)

            for index in table.indexes:
                existing_index = _get_index(inspector, table.name, index.name)
                if existing_index and _index_matches(existing_index, index):
                    continue

                if existing_index and not _index_matches(existing_index, index):
                    conn.execute(text(f"DROP INDEX {index.name} ON {table.name}"))
                    logger.info("数据库自检: 已移除旧索引 %s.%s", table.name, index.name)
                    inspector = _refresh_inspector(engine)

                if index.unique and _unique_index_on_columns_exists(inspector, table.name, index.columns):
                    continue
                if _index_on_columns_exists(inspector, table.name, index.columns, unique=index.unique):
                    continue
                unique_sql = "UNIQUE " if index.unique else ""
                column_sql = ", ".join(index.columns)
                conn.execute(text(f"CREATE {unique_sql}INDEX {index.name} ON {table.name} ({column_sql})"))
                logger.info("数据库自检: 已补充索引 %s.%s", table.name, index.name)
                inspector = _refresh_inspector(engine)

        notification_enum_sql = ", ".join(f"'{item}'" for item in NOTIFICATION_TYPES)
        if _table_exists(inspector, "notifications") and _column_exists(inspector, "notifications", "type"):
            conn.execute(
                text(
                    "ALTER TABLE notifications "
                    f"MODIFY COLUMN type ENUM({notification_enum_sql}) NOT NULL COMMENT '通知类型'"
                )
            )
            logger.info("数据库自检: 已同步 notifications.type 枚举")


def _sqlite_table_columns(conn, table_name: str) -> list[dict]:
    rows = conn.execute(text(f"PRAGMA table_info('{table_name}')")).mappings().all()
    return [
        {
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": row["notnull"],
            "default": row["dflt_value"],
            "pk": row["pk"],
        }
        for row in rows
    ]


def _sqlite_index_names(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA index_list('{table_name}')")).mappings().all()
    return {str(row["name"]) for row in rows}


def _sqlite_type_from_column(column: ColumnSpec) -> str:
    definition = column.definition.strip()
    upper = definition.upper()

    if upper.startswith("ENUM("):
        return "TEXT"
    if upper.startswith("TINYINT(1)") or upper.startswith("BOOLEAN"):
        return "BOOLEAN"
    if upper.startswith("INT"):
        return "INTEGER"
    if upper.startswith("DECIMAL"):
        return "DECIMAL"
    if upper.startswith("DATETIME"):
        return "DATETIME"
    if upper.startswith("DATE"):
        return "DATE"
    if upper.startswith("JSON"):
        return "JSON"
    if upper.startswith("TEXT"):
        return "TEXT"
    if upper.startswith("VARCHAR("):
        return definition.split(" ", 1)[0]
    return definition.split(" ", 1)[0]


def _sqlite_column_sql(column: ColumnSpec) -> str:
    expected = _parse_expected_column(column)
    parts = [column.name, _sqlite_type_from_column(column)]

    if expected["primary"]:
        parts.append("PRIMARY KEY")
    if expected["nullable"] is False and not expected["primary"]:
        parts.append("NOT NULL")

    if expected["default"] is not None:
        default_value = expected["default"]
        if isinstance(default_value, str):
            lowered = default_value.lower()
            if lowered == "current_timestamp":
                parts.append("DEFAULT CURRENT_TIMESTAMP")
            elif re.fullmatch(r"-?\d+(\.\d+)?", default_value):
                parts.append(f"DEFAULT {default_value}")
            else:
                escaped = default_value.replace("'", "''")
                parts.append(f"DEFAULT '{escaped}'")
        else:
            parts.append(f"DEFAULT {default_value}")

    return " ".join(parts)


def _sync_sqlite_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)

    inspector = _refresh_inspector(engine)
    with engine.begin() as conn:
        for table in TABLE_SPECS:
            if not _table_exists(inspector, table.name):
                continue

            existing_columns = {column["name"] for column in _sqlite_table_columns(conn, table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {_sqlite_column_sql(column)}"))
                logger.info("数据库自检: SQLite 已补充字段 %s.%s", table.name, column.name)
                existing_columns.add(column.name)

            existing_indexes = _sqlite_index_names(conn, table.name)
            for index in table.indexes:
                if index.name in existing_indexes:
                    continue
                unique_sql = "UNIQUE " if index.unique else ""
                column_sql = ", ".join(index.columns)
                conn.execute(text(f"CREATE {unique_sql}INDEX {index.name} ON {table.name} ({column_sql})"))
                logger.info("数据库自检: SQLite 已补充索引 %s.%s", table.name, index.name)
                existing_indexes.add(index.name)


def sync_database_schema() -> None:
    """Create or patch database schema for the current configured database."""
    import app.models  # noqa: F401

    if app_engine.dialect.name == "mysql":
        _sync_mysql_schema(app_engine)
        return

    _sync_sqlite_schema(app_engine)
    logger.info("数据库自检: 非 MySQL 环境已完成建表与补字段补索引")
