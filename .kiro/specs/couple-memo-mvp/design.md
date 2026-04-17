# 设计文档

## 概述

情侣备忘录 MVP 后端采用现有 FastAPI + SQLAlchemy 架构实现，在 `users` 表上新增 `couple_code` 字段，并新增情侣关系、备忘录、纪念日三张表。站内提醒通过复用 `notifications` 表的 `system` 类型完成。

## 架构

### 整体结构

```
客户端
  -> /api/couple/*
  -> Couple Router
  -> Couple Service
  -> Couple Models
  -> notifications / users / couple_* tables
```

### 新增数据表

#### users

- `couple_code`: `VARCHAR(8)`，唯一，可为空

#### couple_relationships

- `id`
- `user_a_id`
- `user_b_id`
- `anniversary_date`
- `status`
- `created_at`
- `updated_at`

#### couple_memos

- `id`
- `relationship_id`
- `title`
- `content`
- `category`
- `remind_at`
- `is_completed`
- `is_pinned`
- `created_by`
- `created_at`
- `updated_at`

#### couple_anniversaries

- `id`
- `relationship_id`
- `title`
- `date`
- `type`
- `remind_days_before`
- `note`
- `created_at`
- `updated_at`

## 接口设计

### 绑定相关

- `GET /api/couple/profile`
- `POST /api/couple/bind`
- `DELETE /api/couple/bind`
- `POST /api/couple/code/refresh`

### 备忘录

- `GET /api/couple/memos`
- `POST /api/couple/memos`
- `GET /api/couple/memos/{memo_id}`
- `PUT /api/couple/memos/{memo_id}`
- `PUT /api/couple/memos/{memo_id}/status`
- `DELETE /api/couple/memos/{memo_id}`

### 纪念日

- `GET /api/couple/anniversaries`
- `POST /api/couple/anniversaries`
- `PUT /api/couple/anniversaries/{anniversary_id}`
- `DELETE /api/couple/anniversaries/{anniversary_id}`

### 首页聚合

- `GET /api/couple/dashboard`

## 核心规则

### 规则 1：一对一绑定

任意时刻，一个用户只能出现在一条激活中的情侣关系里。

### 规则 2：共享数据隔离

备忘录和纪念日必须归属某条情侣关系，关系外用户不可访问。

### 规则 3：提醒去重

同一用户对同一情侣事件在同一天内只生成一条站内提醒。

### 规则 4：首页聚合稳定性

首页接口在未绑定时也必须返回结构完整的空数据，便于前端直接渲染。

## 错误处理

- 未绑定关系：返回 `400`
- 邀请码无效：返回 `404`
- 重复绑定：返回 `400`
- 越权访问情侣数据：返回 `403`
- 资源不存在：返回 `404`

## 测试策略

- 绑定流程测试
- 备忘录 CRUD 测试
- 纪念日 CRUD 测试
- 首页聚合结构测试
- 提醒去重测试
