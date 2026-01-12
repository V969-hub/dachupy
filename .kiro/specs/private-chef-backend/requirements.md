# Requirements Document

## Introduction

私厨预订微信小程序后端API服务，为吃货端和大厨端小程序提供数据支持。后端采用Python技术栈，使用MySQL数据库存储数据，提供RESTful API接口供前端调用。

技术栈：Python + Flask/FastAPI + MySQL + SQLAlchemy

数据库配置：
- 主机：192.168.1.70
- 用户名：root
- 密码：123456

## Glossary

- **API_Server**: 后端API服务器，处理所有HTTP请求
- **Database**: MySQL数据库，存储所有业务数据
- **User**: 用户实体，包含吃货和大厨两种角色
- **Dish**: 菜品实体，由大厨创建和管理
- **Order**: 订单实体，记录吃货的预订信息
- **Review**: 评价实体，吃货对订单的评价
- **Tip**: 打赏实体，吃货对大厨的打赏记录
- **Binding**: 绑定关系实体，吃货与大厨的专属绑定
- **Notification**: 通知实体，系统消息通知
- **Address**: 地址实体，用户的配送地址
- **JWT_Token**: JSON Web Token，用于用户身份认证

## Requirements

### Requirement 1: 项目基础架构

**User Story:** 作为开发者，我需要搭建Python后端项目基础架构，以便提供稳定的API服务。

#### Acceptance Criteria

1. THE API_Server SHALL use FastAPI framework for handling HTTP requests
2. THE API_Server SHALL connect to MySQL database using SQLAlchemy ORM
3. THE API_Server SHALL implement JWT-based authentication for all protected endpoints
4. THE API_Server SHALL return standardized JSON response format with code, message, and data fields
5. THE API_Server SHALL handle CORS for cross-origin requests from WeChat mini-program
6. THE API_Server SHALL log all requests and errors for debugging purposes

### Requirement 2: 用户认证接口

**User Story:** 作为用户，我需要通过微信登录获取访问令牌，以便使用小程序功能。

#### Acceptance Criteria

1. WHEN a user sends WeChat login code, THE API_Server SHALL exchange it for openId via WeChat API
2. WHEN a new user logs in, THE API_Server SHALL create user record and return JWT token
3. WHEN an existing user logs in, THE API_Server SHALL return JWT token with user info
4. WHEN a user binds phone number, THE API_Server SHALL update user record with phone
5. THE API_Server SHALL validate JWT token for all protected endpoints
6. IF JWT token is invalid or expired, THEN THE API_Server SHALL return 401 error

### Requirement 3: 用户信息接口

**User Story:** 作为用户，我需要管理我的个人信息，以便展示给其他用户。

#### Acceptance Criteria

1. WHEN a user requests profile, THE API_Server SHALL return user info including avatar, nickname, bindingCode
2. WHEN a user updates profile, THE API_Server SHALL validate and save the changes
3. WHEN a chef updates profile, THE API_Server SHALL allow updating introduction and specialties
4. THE API_Server SHALL generate unique binding code for each user upon registration

### Requirement 4: 菜品管理接口

**User Story:** 作为大厨，我需要管理我的菜品，以便吃货可以浏览和预订。

#### Acceptance Criteria

1. WHEN a chef creates a dish, THE API_Server SHALL validate required fields (name, price, images, ingredients)
2. WHEN a chef creates a dish, THE API_Server SHALL save dish with chef's ID
3. WHEN a chef updates a dish, THE API_Server SHALL validate ownership and update fields
4. WHEN a chef deletes a dish, THE API_Server SHALL soft-delete the dish record
5. WHEN a chef toggles dish status, THE API_Server SHALL update isOnShelf field
6. WHEN requesting dish list, THE API_Server SHALL support pagination and filtering by category, price range

### Requirement 5: 菜品查询接口

**User Story:** 作为吃货，我需要浏览和搜索菜品，以便找到想要预订的美食。

#### Acceptance Criteria

1. WHEN a foodie requests dish list, THE API_Server SHALL return only dishes from bound chef
2. WHEN a foodie searches dishes, THE API_Server SHALL return matching dishes by name or ingredients
3. WHEN a foodie requests dish detail, THE API_Server SHALL return full dish info with chef info
4. WHEN requesting dish list, THE API_Server SHALL return dishes with available quantity for selected date
5. THE API_Server SHALL calculate and return dish rating based on reviews

### Requirement 6: 订单管理接口

**User Story:** 作为用户，我需要创建和管理订单，以便完成预订流程。

#### Acceptance Criteria

1. WHEN a foodie creates order, THE API_Server SHALL validate dish availability and quantity
2. WHEN a foodie creates order, THE API_Server SHALL generate unique order number
3. WHEN a foodie creates order, THE API_Server SHALL calculate total price from items
4. WHEN a foodie creates order, THE API_Server SHALL create notification for bound chef
5. WHEN requesting order list, THE API_Server SHALL support filtering by status
6. WHEN requesting order detail, THE API_Server SHALL return full order info with items and address

### Requirement 7: 订单状态管理接口

**User Story:** 作为用户，我需要更新订单状态，以便跟踪订单进度。

#### Acceptance Criteria

1. WHEN a foodie cancels order, THE API_Server SHALL validate order is cancellable (pending/accepted)
2. WHEN a chef accepts order, THE API_Server SHALL update status to accepted
3. WHEN a chef rejects order, THE API_Server SHALL update status to cancelled with reason
4. WHEN a chef marks cooking complete, THE API_Server SHALL update status to delivering
5. WHEN a foodie confirms receipt, THE API_Server SHALL update status to completed
6. THE API_Server SHALL validate status transitions follow the state machine rules

### Requirement 8: 支付接口

**User Story:** 作为吃货，我需要完成支付，以便确认订单。

#### Acceptance Criteria

1. WHEN a foodie initiates payment, THE API_Server SHALL create WeChat payment order
2. WHEN WeChat payment callback arrives, THE API_Server SHALL verify signature and update order status
3. IF payment succeeds, THEN THE API_Server SHALL update order status to pending (awaiting chef acceptance)
4. IF payment fails, THEN THE API_Server SHALL keep order in unpaid status

### Requirement 9: 评价接口

**User Story:** 作为吃货，我需要对订单进行评价，以便分享用餐体验。

#### Acceptance Criteria

1. WHEN a foodie submits review, THE API_Server SHALL validate order is completed and not reviewed
2. WHEN a foodie submits review, THE API_Server SHALL save review with rating, content, and images
3. WHEN a review is saved, THE API_Server SHALL update dish average rating
4. WHEN requesting dish reviews, THE API_Server SHALL return paginated review list

### Requirement 10: 打赏接口

**User Story:** 作为吃货，我需要给大厨打赏，以便表达感谢。

#### Acceptance Criteria

1. WHEN a foodie tips chef, THE API_Server SHALL create WeChat payment order for tip amount
2. WHEN tip payment succeeds, THE API_Server SHALL save tip record and notify chef
3. WHEN requesting tip history, THE API_Server SHALL return paginated tip list

### Requirement 11: 地址管理接口

**User Story:** 作为吃货，我需要管理配送地址，以便订单配送。

#### Acceptance Criteria

1. WHEN a foodie adds address, THE API_Server SHALL save address with user ID
2. WHEN a foodie updates address, THE API_Server SHALL validate ownership and update
3. WHEN a foodie deletes address, THE API_Server SHALL soft-delete the address
4. WHEN a foodie sets default address, THE API_Server SHALL update default flag
5. WHEN requesting address list, THE API_Server SHALL return user's addresses sorted by default first

### Requirement 12: 专属绑定接口

**User Story:** 作为用户，我需要建立吃货与大厨的专属绑定关系。

#### Acceptance Criteria

1. WHEN a foodie enters binding code, THE API_Server SHALL validate code belongs to a chef
2. WHEN binding code is valid, THE API_Server SHALL create binding relationship
3. WHEN binding succeeds, THE API_Server SHALL notify both parties
4. THE API_Server SHALL ensure each foodie can only bind to one chef
5. IF foodie is already bound, THEN THE API_Server SHALL return error or require unbind first
6. WHEN a foodie unbinds, THE API_Server SHALL remove binding relationship

### Requirement 13: 消息通知接口

**User Story:** 作为用户，我需要接收系统通知，以便及时了解订单和绑定信息。

#### Acceptance Criteria

1. WHEN an order is created, THE API_Server SHALL create notification for chef
2. WHEN order status changes, THE API_Server SHALL create notification for relevant user
3. WHEN binding occurs, THE API_Server SHALL create notification for both parties
4. WHEN requesting notifications, THE API_Server SHALL return paginated list sorted by time
5. WHEN marking notification as read, THE API_Server SHALL update isRead flag
6. THE API_Server SHALL return unread notification count

### Requirement 14: 收益统计接口

**User Story:** 作为大厨，我需要查看收益统计，以便了解经营状况。

#### Acceptance Criteria

1. WHEN a chef requests earnings summary, THE API_Server SHALL return total earnings and tip earnings
2. WHEN a chef requests earnings chart, THE API_Server SHALL return weekly/monthly aggregated data
3. WHEN a chef requests earnings detail, THE API_Server SHALL return paginated transaction list
4. THE API_Server SHALL calculate earnings from completed orders and received tips

### Requirement 15: 收藏接口

**User Story:** 作为吃货，我需要收藏喜欢的菜品，以便快速找到。

#### Acceptance Criteria

1. WHEN a foodie favorites a dish, THE API_Server SHALL create favorite record
2. WHEN a foodie unfavorites a dish, THE API_Server SHALL delete favorite record
3. WHEN requesting favorites, THE API_Server SHALL return paginated dish list
4. THE API_Server SHALL return isFavorited flag when returning dish info

### Requirement 16: 文件上传接口

**User Story:** 作为用户，我需要上传图片，以便设置头像和菜品图片。

#### Acceptance Criteria

1. WHEN a user uploads image, THE API_Server SHALL validate file type (jpg, png, gif)
2. WHEN a user uploads image, THE API_Server SHALL validate file size (max 5MB)
3. WHEN upload succeeds, THE API_Server SHALL return image URL
4. THE API_Server SHALL store images in accessible location

