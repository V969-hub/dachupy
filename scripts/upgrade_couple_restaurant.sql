-- ============================================================================
-- Couple Restaurant Incremental Upgrade
-- ============================================================================
-- Purpose:
--   Patch an existing eatpy/private_chef_db database so the couple restaurant
--   feature can run without recreating existing business data.
--
-- Usage:
--   mysql -h <host> -u <user> -p <database> < scripts/upgrade_couple_restaurant.sql
--
-- Safe to run repeatedly.
-- ============================================================================

DROP PROCEDURE IF EXISTS upgrade_couple_restaurant_schema;

DELIMITER //

CREATE PROCEDURE upgrade_couple_restaurant_schema()
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'users'
          AND COLUMN_NAME = 'couple_code'
    ) THEN
        ALTER TABLE users
            ADD COLUMN couple_code VARCHAR(8) NULL COMMENT '情侣邀请码' AFTER binding_code;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'users'
          AND COLUMN_NAME = 'couple_code'
          AND NON_UNIQUE = 0
    ) THEN
        ALTER TABLE users
            ADD UNIQUE INDEX uq_users_couple_code (couple_code);
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'notifications'
          AND COLUMN_NAME = 'type'
    ) THEN
        ALTER TABLE notifications
            MODIFY COLUMN type ENUM(
                'new_order',
                'order_status',
                'binding',
                'tip',
                'system',
                'couple_memo',
                'couple_anniversary',
                'couple_bind',
                'couple_date_plan'
            ) NOT NULL COMMENT '通知类型';
    END IF;
END //

DELIMITER ;

CALL upgrade_couple_restaurant_schema();

DROP PROCEDURE IF EXISTS upgrade_couple_restaurant_schema;


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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='情侣关系表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='情侣备忘录表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='情侣纪念日表';

CREATE TABLE IF NOT EXISTS couple_date_plans (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    title VARCHAR(100) NOT NULL COMMENT '计划标题',
    plan_at DATETIME NOT NULL COMMENT '约饭时间',
    location VARCHAR(128) DEFAULT NULL COMMENT '约饭地点',
    note TEXT DEFAULT NULL COMMENT '备注',
    anniversary_id VARCHAR(36) DEFAULT NULL COMMENT '关联纪念日',
    order_id VARCHAR(36) DEFAULT NULL COMMENT '关联订单',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='情侣约饭计划表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='情侣小餐厅分类表';

CREATE TABLE IF NOT EXISTS couple_restaurant_items (
    id VARCHAR(36) PRIMARY KEY,
    relationship_id VARCHAR(36) NOT NULL COMMENT '情侣关系ID',
    category_id VARCHAR(36) NOT NULL COMMENT '分类ID',
    name VARCHAR(100) NOT NULL COMMENT '菜名',
    price DECIMAL(10,2) NOT NULL COMMENT '价格',
    images JSON NOT NULL COMMENT '图片列表',
    description TEXT DEFAULT NULL COMMENT '描述',
    created_by VARCHAR(36) NOT NULL COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (relationship_id) REFERENCES couple_relationships(id),
    FOREIGN KEY (category_id) REFERENCES couple_restaurant_categories(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_couple_restaurant_items_relationship (relationship_id),
    INDEX idx_couple_restaurant_items_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='情侣小餐厅菜单表';
