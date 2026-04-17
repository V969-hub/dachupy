# 需求文档

## 简介

为私厨预约系统添加账号密码登录功能，作为微信登录的补充方式。该登录方式以账号为主键，不进行密码校验（任何密码都放行），登录成功后返回与微信登录完全一致的个人数据格式，用户信息使用默认值。

## 术语表

- **System**: 私厨预约系统后端服务
- **Account**: 用户账号，作为登录的唯一标识符
- **Password**: 用户密码，本功能中不做校验
- **JWT_Token**: JSON Web Token，用于用户身份认证
- **UserInfo**: 用户信息数据结构，与微信登录返回格式一致

## 需求

### 需求 1：账号密码登录

**用户故事：** 作为用户，我希望能够通过账号密码登录系统，以便在没有微信的情况下也能使用系统功能。

#### 验收标准

1. WHEN 用户提交账号和密码进行登录 THEN THE System SHALL 接受任何密码并允许登录
2. WHEN 用户首次使用某账号登录 THEN THE System SHALL 创建新用户记录并返回 JWT_Token 和 UserInfo
3. WHEN 用户使用已存在的账号登录 THEN THE System SHALL 返回该用户的 JWT_Token 和 UserInfo
4. THE System SHALL 使用账号作为用户的唯一标识符（类似微信登录的 openId）

### 需求 2：响应数据格式一致性

**用户故事：** 作为前端开发者，我希望账号密码登录返回的数据格式与微信登录完全一致，以便复用现有的登录处理逻辑。

#### 验收标准

1. THE System SHALL 返回与微信登录相同结构的响应数据
2. THE System SHALL 在响应中包含 token 字段（JWT_Token）
3. THE System SHALL 在响应中包含 user 字段（UserInfo 对象）
4. THE UserInfo SHALL 包含以下字段：id、nickname、avatar、phone、role、binding_code、introduction、specialties、rating、total_orders、bound_chef

### 需求 3：默认用户信息

**用户故事：** 作为系统管理员，我希望新创建的账号密码用户有合理的默认值，以便用户可以正常使用系统。

#### 验收标准

1. WHEN 创建新用户 THEN THE System SHALL 设置 nickname 为空字符串
2. WHEN 创建新用户 THEN THE System SHALL 设置 avatar 为空字符串
3. WHEN 创建新用户 THEN THE System SHALL 生成唯一的 binding_code
4. WHEN 创建新用户 THEN THE System SHALL 设置 rating 默认值为 5.0
5. WHEN 创建新用户 THEN THE System SHALL 设置 total_orders 默认值为 0
6. THE System SHALL 支持通过请求参数指定用户角色（foodie 或 chef）

### 需求 4：标准化响应格式

**用户故事：** 作为 API 使用者，我希望登录接口遵循系统统一的响应格式规范。

#### 验收标准

1. WHEN 登录成功 THEN THE System SHALL 返回 code 为 0 的成功响应
2. WHEN 登录失败 THEN THE System SHALL 返回非 0 的 code 和错误信息
3. THE System SHALL 使用 success_response 和 error_response 工具函数格式化响应
