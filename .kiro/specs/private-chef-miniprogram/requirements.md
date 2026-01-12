# Requirements Document

## Introduction

私厨预订微信小程序是一个连接"吃货"（食客）和"大厨"（私人厨师）的平台。吃货可以浏览、预订私厨制作的菜品，大厨可以发布菜品、管理订单和查看收益。系统采用专属绑定机制，每个吃货只能绑定一个专属大厨。

技术栈：UniApp + Vue3 + UniNutUI + Axios

## Glossary

- **Foodie_App**: 吃货端小程序应用
- **Chef_App**: 大厨端小程序应用
- **Dish**: 菜品实体，包含名称、价格、食材、描述等信息
- **Order**: 订单实体，包含菜品列表、状态、配送信息等
- **Binding_Code**: 专属绑定码，用于吃货与大厨建立专属关系
- **Request_Interceptor**: 请求拦截器，处理请求前的统一逻辑
- **Response_Interceptor**: 响应拦截器，处理响应后的统一逻辑
- **Mock_Service**: 模拟数据服务，用于开发阶段的数据模拟

## Requirements

### Requirement 1: 项目基础架构搭建

**User Story:** 作为开发者，我需要搭建UniApp+Vue3项目基础架构，以便后续功能开发有统一的代码规范和工具支持。

#### Acceptance Criteria

1. THE Project_Structure SHALL include standard UniApp directories (pages, components, utils, api, store, static)
2. THE Project SHALL configure UniNutUI component library correctly
3. THE Request_Interceptor SHALL add authorization token to all API requests
4. THE Response_Interceptor SHALL handle common error codes (401, 403, 500) uniformly
5. THE Mock_Service SHALL intercept API calls and return simulated data during development
6. THE Project SHALL support both Foodie_App and Chef_App page routing

### Requirement 2: 吃货端首页

**User Story:** 作为吃货，我想在首页浏览推荐菜品和搜索菜品，以便快速找到想要预订的美食。

#### Acceptance Criteria

1. WHEN the Foodie_App loads the home page, THE System SHALL display a search bar at the top
2. WHEN the Foodie_App loads the home page, THE System SHALL display a carousel banner for promotions
3. WHEN the Foodie_App loads the home page, THE System SHALL display category filters (cuisine type, price range, date)
4. WHEN the Foodie_App loads the home page, THE System SHALL display recommended dishes in a list format
5. WHEN displaying a dish item, THE System SHALL show dish image, name, chef avatar, rating, price, and distance
6. WHEN a user searches for a keyword, THE System SHALL return matching dishes and chefs
7. WHEN a user selects a category filter, THE System SHALL filter the dish list accordingly

### Requirement 3: 菜品详情页

**User Story:** 作为吃货，我想查看菜品的详细信息，以便决定是否预订该菜品。

#### Acceptance Criteria

1. WHEN viewing dish details, THE System SHALL display dish images in a carousel format
2. WHEN viewing dish details, THE System SHALL display dish name, price, and chef information (avatar, nickname, rating)
3. WHEN viewing dish details, THE System SHALL display dish description, ingredients, and flavor tags
4. WHEN viewing dish details, THE System SHALL provide a calendar component for selecting reservation date
5. WHEN viewing dish details, THE System SHALL allow selecting quantity
6. WHEN viewing dish details, THE System SHALL display selected user reviews
7. WHEN a user clicks the favorite button, THE System SHALL add the dish to user's collection
8. WHEN a user clicks add to order button, THE System SHALL add the dish to the current order

### Requirement 4: 点菜/预订页

**User Story:** 作为吃货，我想管理已选菜品并设置配送信息，以便完成预订流程。

#### Acceptance Criteria

1. WHEN viewing the order page, THE System SHALL display all selected dishes with adjustable quantities
2. WHEN a user adjusts quantity, THE System SHALL recalculate the total price
3. WHEN a user removes a dish, THE System SHALL update the dish list and total price
4. WHEN viewing the order page, THE System SHALL allow selecting delivery time slot
5. WHEN viewing the order page, THE System SHALL provide a remarks input for dietary preferences
6. WHEN a user clicks submit order, THE System SHALL navigate to the payment confirmation page

### Requirement 5: 订单确认与支付页

**User Story:** 作为吃货，我想确认订单信息并完成支付，以便成功预订菜品。

#### Acceptance Criteria

1. WHEN viewing payment page, THE System SHALL display order summary (dishes, total price, delivery time)
2. WHEN viewing payment page, THE System SHALL allow selecting or adding delivery address
3. WHEN viewing payment page, THE System SHALL display WeChat Pay as payment method
4. WHEN a user confirms payment, THE System SHALL initiate WeChat payment process
5. IF payment succeeds, THEN THE System SHALL create the order and navigate to order success page
6. IF payment fails, THEN THE System SHALL display error message and allow retry

### Requirement 6: 订单列表页

**User Story:** 作为吃货，我想查看所有订单的状态，以便跟踪我的预订情况。

#### Acceptance Criteria

1. WHEN viewing order list, THE System SHALL display tabs for filtering (All, Pending, In Progress, Completed)
2. WHEN displaying an order item, THE System SHALL show order number, dish thumbnail, status, and total price
3. WHEN an order is cancellable, THE System SHALL display cancel button
4. WHEN an order is deliverable, THE System SHALL display confirm receipt button
5. WHEN a user clicks an order item, THE System SHALL navigate to order detail page

### Requirement 7: 订单详情页

**User Story:** 作为吃货，我想查看订单的详细信息和状态进度，以便了解订单的完整情况。

#### Acceptance Criteria

1. WHEN viewing order detail, THE System SHALL display order status progress bar (Pending, Cooking, Delivering, Completed)
2. WHEN viewing order detail, THE System SHALL display dish list with prices
3. WHEN viewing order detail, THE System SHALL display delivery information and chef contact
4. WHEN order status allows, THE System SHALL display appropriate action buttons (Cancel, Confirm Receipt, Review, Tip)

### Requirement 8: 评价页

**User Story:** 作为吃货，我想对已完成的订单进行评价，以便分享我的用餐体验。

#### Acceptance Criteria

1. WHEN reviewing an order, THE System SHALL provide a 5-star rating component
2. WHEN reviewing an order, THE System SHALL provide a text input for comments
3. WHEN reviewing an order, THE System SHALL allow uploading up to 3 images
4. WHEN a user submits review, THE System SHALL save the review and update dish ratings

### Requirement 9: 打赏页

**User Story:** 作为吃货，我想给大厨打赏，以便表达对美食的感谢。

#### Acceptance Criteria

1. WHEN tipping a chef, THE System SHALL display preset amounts (5, 10, 20 yuan) and custom input
2. WHEN tipping a chef, THE System SHALL allow adding an optional message
3. WHEN a user confirms tip, THE System SHALL process the payment and record the tip

### Requirement 10: 吃货个人中心

**User Story:** 作为吃货，我想管理我的个人信息和查看各类记录，以便更好地使用小程序。

#### Acceptance Criteria

1. WHEN viewing personal center, THE System SHALL display user avatar and nickname
2. WHEN viewing personal center, THE System SHALL provide entry to My Orders
3. WHEN viewing personal center, THE System SHALL provide entry to My Favorites
4. WHEN viewing personal center, THE System SHALL provide entry to My Addresses
5. WHEN viewing personal center, THE System SHALL provide entry to My Tips Record
6. WHEN viewing personal center, THE System SHALL provide entry to Settings
7. WHEN viewing personal center, THE System SHALL display binding code and bound chef info

### Requirement 11: 大厨登录/注册

**User Story:** 作为大厨，我想通过微信登录小程序，以便开始使用大厨端功能。

#### Acceptance Criteria

1. WHEN accessing Chef_App, THE System SHALL display WeChat login button
2. WHEN a chef logs in via WeChat, THE System SHALL authenticate and create/retrieve chef profile
3. WHERE phone binding is required, THE System SHALL provide phone number binding flow

### Requirement 12: 大厨菜品管理

**User Story:** 作为大厨，我想管理我发布的菜品，以便控制可预订的菜品列表。

#### Acceptance Criteria

1. WHEN viewing dish management, THE System SHALL display all chef's dishes
2. WHEN viewing a dish item, THE System SHALL allow toggling on/off shelf status
3. WHEN viewing a dish item, THE System SHALL allow editing or deleting the dish
4. WHEN a chef clicks add new dish, THE System SHALL navigate to dish publish page

### Requirement 13: 发布/编辑菜品页

**User Story:** 作为大厨，我想发布或编辑菜品信息，以便吃货可以浏览和预订。

#### Acceptance Criteria

1. WHEN publishing a dish, THE System SHALL require dish name, price, ingredients, and description
2. WHEN publishing a dish, THE System SHALL allow adding flavor tags
3. WHEN publishing a dish, THE System SHALL require at least one image upload
4. WHEN publishing a dish, THE System SHALL allow setting available dates and quantity limits
5. WHEN a chef saves the dish, THE System SHALL validate and save the dish information

### Requirement 14: 大厨订单管理

**User Story:** 作为大厨，我想管理收到的订单，以便及时处理吃货的预订。

#### Acceptance Criteria

1. WHEN viewing order management, THE System SHALL display orders categorized by status
2. WHEN displaying an order, THE System SHALL show order number, dishes, time, and customer info
3. WHEN an order is pending, THE System SHALL allow accepting or rejecting the order
4. WHEN an order is accepted, THE System SHALL allow marking as cooking complete
5. WHEN cooking is complete, THE System SHALL allow marking as delivering

### Requirement 15: 大厨收益统计

**User Story:** 作为大厨，我想查看我的收益情况，以便了解经营状况。

#### Acceptance Criteria

1. WHEN viewing earnings, THE System SHALL display total earnings and tip earnings
2. WHEN viewing earnings, THE System SHALL display weekly/monthly earnings chart
3. WHEN viewing earnings, THE System SHALL provide withdrawal button
4. WHEN viewing earnings, THE System SHALL display earnings detail list

### Requirement 16: 大厨个人主页编辑

**User Story:** 作为大厨，我想编辑我的个人主页信息，以便展示给吃货。

#### Acceptance Criteria

1. WHEN editing profile, THE System SHALL allow updating avatar and nickname
2. WHEN editing profile, THE System SHALL allow updating introduction and specialties
3. WHEN viewing profile, THE System SHALL display the chef's binding code

### Requirement 17: 专属绑定机制

**User Story:** 作为用户，我想通过绑定码建立吃货与大厨的专属关系，以便获得专属服务。

#### Acceptance Criteria

1. WHEN a user views personal center, THE System SHALL display their unique binding code
2. WHEN a foodie enters a chef's binding code, THE System SHALL establish exclusive binding
3. WHEN binding succeeds, THE System SHALL send notification to both parties
4. THE System SHALL ensure each foodie can only bind to one chef at a time
5. WHEN a foodie is bound to a chef, THE System SHALL only show that chef's dishes

### Requirement 18: 消息通知

**User Story:** 作为大厨，我想收到订单通知，以便及时了解吃货的预订信息。

#### Acceptance Criteria

1. WHEN a foodie places an order, THE System SHALL notify the bound chef
2. WHEN notifying chef, THE System SHALL include dish names and delivery time
3. WHEN viewing Chef_App, THE System SHALL display notification list
4. WHEN a new notification arrives, THE System SHALL show badge indicator

### Requirement 19: UI设计规范

**User Story:** 作为用户，我想使用美观一致的界面，以便获得良好的使用体验。

#### Acceptance Criteria

1. THE System SHALL use warm color scheme (orange, red) as primary colors
2. THE System SHALL use consistent icon style (linear or filled)
3. THE System SHALL display dish images in rounded rectangle format
4. THE System SHALL implement skeleton loading screens
5. THE System SHALL display empty state prompts when no content
6. THE System SHALL show toast notifications for operation feedback
7. THE System SHALL adapt to mainstream phone screen sizes
