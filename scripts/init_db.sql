-- ============================================================================
-- Private Chef Booking System Database Initialization Script
-- ============================================================================
-- Database: private_chef_db
-- Host: 192.168.1.70:3306
-- 
-- Usage:
--   1. Connect to MySQL server: mysql -h 192.168.1.70 -u root -p
--   2. Execute this script: source /path/to/init_db.sql
--   
-- Or use the Python script:
--   python scripts/init_database.py --sql
--
-- Tables created:
--   - users              : User accounts (foodie and chef roles)
--   - dishes             : Chef menu items
--   - daily_dish_quantities : Daily booking quantity tracking
--   - orders             : Booking orders
--   - order_items        : Individual items in orders
--   - reviews            : Order reviews and ratings
--   - tips               : Tips from foodies to chefs
--   - addresses          : User delivery addresses
--   - bindings           : Foodie-chef binding relationships
--   - notifications      : System notifications
--   - favorites          : User dish favorites
-- ============================================================================

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS private_chef_db 
    DEFAULT CHARACTER SET utf8mb4 
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE private_chef_db;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    open_id VARCHAR(64) UNIQUE NOT NULL COMMENT '微信openId',
    nickname VARCHAR(64) NOT NULL DEFAULT '' COMMENT '昵称',
    avatar VARCHAR(512) DEFAULT '' COMMENT '头像URL',
    phone VARCHAR(20) DEFAULT NULL COMMENT '手机号',
    role ENUM('foodie', 'chef') NOT NULL DEFAULT 'foodie' COMMENT '角色',
    binding_code VARCHAR(8) UNIQUE NOT NULL COMMENT '专属绑定码',
    couple_code VARCHAR(8) UNIQUE DEFAULT NULL COMMENT '情侣邀请码',
    is_open TINYINT(1) DEFAULT 1 COMMENT '是否营业中',
    service_start_time VARCHAR(5) DEFAULT '09:00' COMMENT '接单开始时间',
    service_end_time VARCHAR(5) DEFAULT '21:00' COMMENT '接单结束时间',
    rest_notice VARCHAR(255) DEFAULT NULL COMMENT '休息说明',
    introduction TEXT COMMENT '大厨简介',
    specialties JSON COMMENT '大厨擅长菜系',
    virtual_coin_balance DECIMAL(10,2) NOT NULL DEFAULT 200.00 COMMENT '虚拟币余额',
    rating DECIMAL(2,1) DEFAULT 5.0 COMMENT '大厨评分',
    total_orders INT DEFAULT 0 COMMENT '总订单数',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_open_id (open_id),
    INDEX idx_binding_code (binding_code),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- Dishes table
CREATE TABLE IF NOT EXISTS dishes (
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (chef_id) REFERENCES users(id),
    INDEX idx_chef_id (chef_id),
    INDEX idx_category (category),
    INDEX idx_is_on_shelf (is_on_shelf)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜品表';

-- Daily dish quantities table
CREATE TABLE IF NOT EXISTS daily_dish_quantities (
    id VARCHAR(36) PRIMARY KEY,
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    date DATE NOT NULL COMMENT '日期',
    booked_quantity INT DEFAULT 0 COMMENT '已预订数量',
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    UNIQUE KEY uk_dish_date (dish_id, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日菜品预订量表';

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
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
    payment_method VARCHAR(32) NOT NULL DEFAULT 'free' COMMENT '支付方式',
    wallet_paid_amount DECIMAL(10,2) DEFAULT 0 COMMENT '虚拟币支付金额',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    completed_at DATETIME COMMENT '完成时间',
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    INDEX idx_order_no (order_no),
    INDEX idx_foodie_id (foodie_id),
    INDEX idx_chef_id (chef_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单表';

-- Order items table
CREATE TABLE IF NOT EXISTS order_items (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL COMMENT '订单ID',
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    dish_name VARCHAR(128) NOT NULL COMMENT '菜品名称快照',
    dish_image VARCHAR(512) COMMENT '菜品图片快照',
    price DECIMAL(10,2) NOT NULL COMMENT '单价快照',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    INDEX idx_order_id (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单项表';

-- Wallet transactions table
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
    transaction_type VARCHAR(32) NOT NULL COMMENT '流水类型',
    change_amount DECIMAL(10,2) NOT NULL COMMENT '变动金额',
    balance_after DECIMAL(10,2) NOT NULL COMMENT '变动后余额',
    related_order_id VARCHAR(36) DEFAULT NULL COMMENT '关联订单ID',
    note VARCHAR(255) DEFAULT NULL COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_wallet_transactions_user_id (user_id),
    INDEX idx_wallet_transactions_order_id (related_order_id),
    INDEX idx_wallet_transactions_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='虚拟币流水表';

-- Reviews table
CREATE TABLE IF NOT EXISTS reviews (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL COMMENT '订单ID',
    foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID',
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    rating TINYINT NOT NULL COMMENT '评分1-5',
    content TEXT COMMENT '评价内容',
    images JSON COMMENT '评价图片',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    INDEX idx_dish_id (dish_id),
    INDEX idx_chef_id (chef_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评价表';

-- Tips table
CREATE TABLE IF NOT EXISTS tips (
    id VARCHAR(36) PRIMARY KEY,
    foodie_id VARCHAR(36) NOT NULL COMMENT '吃货ID',
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    order_id VARCHAR(36) COMMENT '关联订单ID',
    amount DECIMAL(10,2) NOT NULL COMMENT '打赏金额',
    message VARCHAR(256) COMMENT '留言',
    payment_id VARCHAR(64) COMMENT '微信支付订单号',
    status ENUM('pending', 'paid', 'failed') DEFAULT 'pending' COMMENT '支付状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    INDEX idx_chef_id (chef_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='打赏表';

-- Addresses table
CREATE TABLE IF NOT EXISTS addresses (
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地址表';

-- Bindings table
CREATE TABLE IF NOT EXISTS bindings (
    id VARCHAR(36) PRIMARY KEY,
    foodie_id VARCHAR(36) UNIQUE NOT NULL COMMENT '吃货ID',
    chef_id VARCHAR(36) NOT NULL COMMENT '大厨ID',
    binding_code VARCHAR(8) NOT NULL COMMENT '使用的绑定码',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (foodie_id) REFERENCES users(id),
    FOREIGN KEY (chef_id) REFERENCES users(id),
    INDEX idx_chef_id (chef_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='绑定关系表';

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
    type ENUM(
        'new_order', 'order_status', 'binding', 'tip', 'system',
        'couple_memo', 'couple_anniversary', 'couple_bind', 'couple_date_plan'
    ) NOT NULL COMMENT '通知类型',
    title VARCHAR(64) NOT NULL COMMENT '标题',
    content VARCHAR(256) NOT NULL COMMENT '内容',
    data JSON COMMENT '附加数据',
    is_read TINYINT(1) DEFAULT 0 COMMENT '是否已读',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_is_read (is_read),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通知表';

-- Favorites table
CREATE TABLE IF NOT EXISTS favorites (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
    dish_id VARCHAR(36) NOT NULL COMMENT '菜品ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    UNIQUE KEY uk_user_dish (user_id, dish_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='收藏表';

-- Couple relationships table
CREATE TABLE IF NOT EXISTS couple_relationships (
    id VARCHAR(36) PRIMARY KEY,
    user_a_id VARCHAR(36) NOT NULL COMMENT '关系用户A',
    user_b_id VARCHAR(36) NOT NULL COMMENT '关系用户B',
    anniversary_date DATE DEFAULT NULL COMMENT '在一起日期',
    status ENUM('active', 'inactive') NOT NULL DEFAULT 'active' COMMENT '关系状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_a_id) REFERENCES users(id),
    FOREIGN KEY (user_b_id) REFERENCES users(id),
    INDEX idx_couple_relationship_user_a (user_a_id),
    INDEX idx_couple_relationship_user_b (user_b_id),
    INDEX idx_couple_relationship_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情侣关系表';

-- Couple memos table
CREATE TABLE IF NOT EXISTS couple_memos (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    title VARCHAR(100) NOT NULL COMMENT '标题',
    content TEXT DEFAULT NULL COMMENT '内容',
    category VARCHAR(32) NOT NULL DEFAULT '日常' COMMENT '分类',
    remind_at DATETIME DEFAULT NULL COMMENT '提醒时间',
    is_completed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已完成',
    is_pinned TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否置顶',
    created_by VARCHAR(36) NOT NULL COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (relationship_id) REFERENCES couple_relationships(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_couple_memos_relationship (relationship_id),
    INDEX idx_couple_memos_remind_at (remind_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情侣备忘录表';

-- Couple anniversaries table
CREATE TABLE IF NOT EXISTS couple_anniversaries (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    title VARCHAR(100) NOT NULL COMMENT '标题',
    date DATE NOT NULL COMMENT '纪念日日期',
    type VARCHAR(32) NOT NULL DEFAULT '自定义' COMMENT '纪念日类型',
    remind_days_before INT NOT NULL DEFAULT 0 COMMENT '提前提醒天数',
    note TEXT DEFAULT NULL COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (relationship_id) REFERENCES couple_relationships(id),
    INDEX idx_couple_anniversaries_relationship (relationship_id),
    INDEX idx_couple_anniversaries_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情侣纪念日表';

-- Couple date plans table
CREATE TABLE IF NOT EXISTS couple_date_plans (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    title VARCHAR(100) NOT NULL COMMENT '计划标题',
    plan_at DATETIME NOT NULL COMMENT '约饭时间',
    location VARCHAR(128) DEFAULT NULL COMMENT '约饭地点',
    note TEXT DEFAULT NULL COMMENT '备注',
    anniversary_id VARCHAR(36) DEFAULT NULL COMMENT '关联纪念日',
    order_id VARCHAR(36) DEFAULT NULL COMMENT '关联订单',
    menu_items JSON DEFAULT NULL COMMENT '约饭菜单快照',
    menu_total DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '约饭菜单总额',
    status ENUM('planned', 'completed', 'cancelled') NOT NULL DEFAULT 'planned' COMMENT '计划状态',
    created_by VARCHAR(36) NOT NULL COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (relationship_id) REFERENCES couple_relationships(id),
    FOREIGN KEY (anniversary_id) REFERENCES couple_anniversaries(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_couple_date_plans_relationship (relationship_id),
    INDEX idx_couple_date_plans_plan_at (plan_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情侣约饭计划表';

-- Couple restaurant categories table
CREATE TABLE IF NOT EXISTS couple_restaurant_categories (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    name VARCHAR(64) NOT NULL COMMENT '分类名称',
    image VARCHAR(255) DEFAULT NULL COMMENT '分类图片',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序值',
    created_by VARCHAR(36) NOT NULL COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (relationship_id) REFERENCES couple_relationships(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_couple_restaurant_categories_relationship (relationship_id),
    INDEX idx_couple_restaurant_categories_sort (relationship_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情侣小餐厅分类表';

-- Couple restaurant items table
CREATE TABLE IF NOT EXISTS couple_restaurant_items (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    category_id VARCHAR(36) NOT NULL COMMENT '分类ID',
    name VARCHAR(100) NOT NULL COMMENT '菜名',
    price DECIMAL(10,2) NOT NULL COMMENT '价格',
    images JSON NOT NULL COMMENT '图片列表',
    tags JSON DEFAULT NULL COMMENT '偏好标签',
    description TEXT DEFAULT NULL COMMENT '描述',
    created_by VARCHAR(36) NOT NULL COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (relationship_id) REFERENCES couple_relationships(id),
    FOREIGN KEY (category_id) REFERENCES couple_restaurant_categories(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_couple_restaurant_items_relationship (relationship_id),
    INDEX idx_couple_restaurant_items_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情侣小餐厅菜单表';

-- Couple restaurant shared cart table
CREATE TABLE IF NOT EXISTS couple_restaurant_cart_items (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    item_id VARCHAR(36) NOT NULL COMMENT '菜单ID',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    created_by VARCHAR(36) NOT NULL COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_couple_restaurant_cart_relationship_item (relationship_id, item_id),
    INDEX idx_couple_restaurant_cart_relationship (relationship_id),
    INDEX idx_couple_restaurant_cart_item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情侣小餐厅共享点单篮表';

-- ============================================================================
-- Initialization Complete
-- ============================================================================
-- All tables have been created successfully.
-- 
-- Table Summary:
--   1. users              - User accounts (foodie/chef roles)
--   2. dishes             - Chef menu items
--   3. daily_dish_quantities - Daily booking quantity tracking
--   4. orders             - Booking orders
--   5. order_items        - Individual items in orders
--   6. reviews            - Order reviews and ratings
--   7. tips               - Tips from foodies to chefs
--   8. addresses          - User delivery addresses
--   9. bindings           - Foodie-chef binding relationships
--   10. notifications     - System notifications
--   11. favorites         - User dish favorites
-- ============================================================================
