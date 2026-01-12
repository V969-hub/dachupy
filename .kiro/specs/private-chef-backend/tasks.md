# Implementation Plan: 私厨预订小程序后端API

## Overview

本实现计划将后端API服务分解为可执行的开发任务，采用Python FastAPI框架，MySQL数据库，按照模块化方式逐步实现。

## Tasks

- [x] 1. 项目基础架构搭建
  - [x] 1.1 创建项目目录结构和基础文件
    - 创建 app/ 目录及子目录 (api, models, schemas, services, middleware, utils)
    - 创建 requirements.txt 依赖文件
    - 创建 .env 环境变量文件
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 配置数据库连接
    - 创建 app/config.py 配置文件
    - 创建 app/database.py 数据库连接
    - 配置MySQL连接 (192.168.1.70, root, 123456)
    - _Requirements: 1.2_

  - [x] 1.3 创建FastAPI应用入口
    - 创建 app/main.py 主入口
    - 配置CORS中间件
    - 配置请求日志中间件
    - 配置异常处理
    - _Requirements: 1.1, 1.5, 1.6_

  - [x] 1.4 创建通用响应模型
    - 创建 app/schemas/common.py
    - 定义 ApiResponse, PaginatedResponse 模型
    - _Requirements: 1.4_

- [x] 2. 数据库模型实现
  - [x] 2.1 创建用户模型
    - 创建 app/models/user.py
    - 定义 User 表结构
    - _Requirements: 2.1, 2.2, 3.1_

  - [x] 2.2 创建菜品模型
    - 创建 app/models/dish.py
    - 定义 Dish, DailyDishQuantity 表结构
    - _Requirements: 4.1, 4.2_

  - [x] 2.3 创建订单模型
    - 创建 app/models/order.py
    - 定义 Order, OrderItem 表结构
    - _Requirements: 6.1, 6.2_

  - [x] 2.4 创建其他模型
    - 创建 Review, Tip, Address, Binding, Notification, Favorite 模型
    - _Requirements: 9.1, 10.1, 11.1, 12.1, 13.1, 15.1_

  - [x] 2.5 创建数据库初始化脚本
    - 创建所有表的SQL脚本
    - 执行数据库初始化
    - _Requirements: 1.2_

- [x] 3. 认证模块实现
  - [x] 3.1 实现JWT工具函数
    - 创建 app/utils/security.py
    - 实现 create_token, verify_token 函数
    - 实现绑定码生成函数
    - _Requirements: 2.5, 2.6, 3.4_

  - [x] 3.2 实现认证中间件
    - 创建 app/middleware/auth.py
    - 实现 get_current_user 依赖
    - 实现 require_chef, require_foodie 角色验证
    - _Requirements: 1.3, 2.5, 2.6_

  - [ ]* 3.3 编写属性测试: JWT认证
    - **Property 1: JWT Authentication Enforcement**
    - **Validates: Requirements 1.3, 2.5, 2.6**

  - [x] 3.4 实现微信登录服务
    - 创建 app/services/wechat_service.py
    - 实现 code2session 接口调用
    - _Requirements: 2.1_

  - [x] 3.5 实现认证API
    - 创建 app/api/auth.py
    - 实现 POST /auth/login 登录接口
    - 实现 POST /auth/bind-phone 绑定手机接口
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.6 编写属性测试: 绑定码唯一性

    - **Property 3: Binding Code Uniqueness**
    - **Validates: Requirements 3.4**

- [ ] 4. Checkpoint - 基础架构验证
  - 确保数据库连接正常
  - 确保JWT认证工作正常
  - 确保所有测试通过，如有问题请询问用户

- [x] 5. 用户模块实现
  - [x] 5.1 实现用户服务
    - 创建 app/services/user_service.py
    - 实现获取用户信息、更新用户信息
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 5.2 实现用户API
    - 创建 app/api/user.py
    - 实现 GET /user/profile
    - 实现 PUT /user/profile
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. 菜品模块实现
  - [x] 6.1 实现菜品服务
    - 创建 app/services/dish_service.py
    - 实现菜品CRUD操作
    - 实现菜品搜索和筛选
    - 实现可用数量计算
    - _Requirements: 4.1-4.6, 5.1-5.5_

  - [x] 6.2 实现菜品API(吃货端)
    - 创建 app/api/dish.py
    - 实现 GET /dishes 菜品列表
    - 实现 GET /dishes/{dish_id} 菜品详情
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 6.3 实现菜品API(大厨端)
    - 实现 POST /chef/dishes 创建菜品
    - 实现 PUT /chef/dishes/{dish_id} 更新菜品
    - 实现 DELETE /chef/dishes/{dish_id} 删除菜品
    - 实现 PUT /chef/dishes/{dish_id}/status 切换状态
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 6.4 编写属性测试: 菜品所有权验证

    - **Property 4: Dish Ownership Validation**
    - **Validates: Requirements 4.3**

- [x] 7. 绑定模块实现
  - [x] 7.1 实现绑定服务
    - 创建 app/services/binding_service.py
    - 实现绑定、解绑逻辑
    - 实现绑定验证
    - _Requirements: 12.1-12.6_

  - [x] 7.2 实现绑定API
    - 创建 app/api/binding.py
    - 实现 POST /bindingcode 绑定大厨
    - 实现 DELETE /binding 解除绑定
    - 实现 GET /binding 获取绑定信息
    - _Requirements: 12.1, 12.2, 12.6_

  - [x] 7.3 编写属性测试: 一对一绑定约束

    - **Property 9: One-to-One Binding Constraint**
    - **Validates: Requirements 12.4, 12.5**

  - [x] 7.4 编写属性测试: 绑定大厨菜品过滤

    - **Property 5: Bound Chef Dish Filter**
    - **Validates: Requirements 5.1, 12.4**

- [x] 8. Checkpoint - 核心功能验证
  - 确保用户、菜品、绑定功能正常
  - 确保所有测试通过，如有问题请询问用户

- [x] 9. 订单模块实现
  - [x] 9.1 实现订单服务
    - 创建 app/services/order_service.py
    - 实现订单创建、查询
    - 实现订单号生成
    - 实现价格计算
    - 实现状态转换验证
    - _Requirements: 6.1-6.6, 7.1-7.6_

  - [x] 9.2 实现订单API(吃货端)
    - 创建 app/api/order.py
    - 实现 POST /orders 创建订单
    - 实现 GET /orders 订单列表
    - 实现 GET /orders/{order_id} 订单详情
    - 实现 PUT /orders/{order_id}/cancel 取消订单
    - 实现 PUT /orders/{order_id}/confirm 确认收货
    - _Requirements: 6.1-6.6, 7.1, 7.5_

  - [x] 9.3 实现订单API(大厨端)
    - 实现 GET /chef/orders 大厨订单列表
    - 实现 PUT /chef/orders/{order_id}/accept 接受订单
    - 实现 PUT /chef/orders/{order_id}/reject 拒绝订单
    - 实现 PUT /chef/orders/{order_id}/cooking-done 烹饪完成
    - 实现 PUT /chef/orders/{order_id}/delivering 配送中
    - _Requirements: 7.2, 7.3, 7.4_

  - [x] 9.4 编写属性测试: 订单价格计算

    - **Property 6: Order Total Price Calculation**
    - **Validates: Requirements 6.3**

  - [x] 9.5 编写属性测试: 订单状态转换

    - **Property 7: Order Status State Machine**
    - **Validates: Requirements 7.1-7.6**

  - [x] 9.6 编写属性测试: 订单号唯一性

    - **Property 13: Order Number Uniqueness**
    - **Validates: Requirements 6.2**

- [x] 10. 支付模块实现
  - [x] 10.1 实现支付服务
    - 创建 app/services/payment_service.py
    - 实现微信支付下单
    - 实现支付回调验证
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 10.2 实现支付API
    - 实现 POST /payment/notify 支付回调
    - _Requirements: 8.2_

- [x] 11. Checkpoint - 订单支付验证
  - 确保订单创建、状态流转正常
  - 确保所有测试通过，如有问题请询问用户

- [x] 12. 评价模块实现
  - [x] 12.1 实现评价服务
    - 创建 app/services/review_service.py
    - 实现评价创建
    - 实现评分更新
    - _Requirements: 9.1-9.4_

  - [x] 12.2 实现评价API
    - 创建 app/api/review.py
    - 实现 POST /orders/{order_id}/review 提交评价
    - 实现 GET /dishes/{dish_id}/reviews 获取评价列表
    - _Requirements: 9.1, 9.2, 9.4_

  - [x] 12.3 编写属性测试: 评分计算

    - **Property 8: Dish Rating Calculation**
    - **Validates: Requirements 9.3**

  - [x] 12.4 编写属性测试: 评价约束

    - **Property 15: Review Constraint**
    - **Validates: Requirements 9.1**

- [x] 13. 打赏模块实现
  - [x] 13.1 实现打赏服务
    - 创建 app/services/tip_service.py
    - 实现打赏创建和查询
    - _Requirements: 10.1-10.3_

  - [x] 13.2 实现打赏API
    - 创建 app/api/tip.py
    - 实现 POST /tips 创建打赏
    - 实现 GET /tips 打赏记录
    - _Requirements: 10.1, 10.3_

- [x] 14. 地址模块实现
  - [x] 14.1 实现地址服务
    - 创建 app/services/address_service.py
    - 实现地址CRUD
    - 实现默认地址管理
    - _Requirements: 11.1-11.5_

  - [x] 14.2 实现地址API
    - 创建 app/api/address.py
    - 实现 GET /addresses 地址列表
    - 实现 POST /addresses 添加地址
    - 实现 PUT /addresses/{address_id} 更新地址
    - 实现 DELETE /addresses/{address_id} 删除地址
    - 实现 PUT /addresses/{address_id}/default 设为默认
    - _Requirements: 11.1-11.5_

  - [x] 14.3 编写属性测试: 默认地址唯一性

    - **Property 12: Address Default Uniqueness**
    - **Validates: Requirements 11.4**

- [x] 15. 通知模块实现
  - [x] 15.1 实现通知服务
    - 创建 app/services/notification_service.py
    - 实现通知创建和查询
    - 实现未读数量统计
    - _Requirements: 13.1-13.6_

  - [x] 15.2 实现通知API
    - 创建 app/api/notification.py
    - 实现 GET /notifications 通知列表
    - 实现 GET /notifications/unread-count 未读数量
    - 实现 PUT /notifications/{id}/read 标记已读
    - 实现 PUT /notifications/read-all 全部已读
    - _Requirements: 13.4, 13.5, 13.6_

  - [x] 15.3 编写属性测试: 订单事件通知


    - **Property 14: Notification Creation on Order Events**
    - **Validates: Requirements 6.4, 13.1, 13.2**

- [ ] 16. 收益模块实现
  - [x] 16.1 实现收益服务
    - 创建 app/services/earnings_service.py
    - 实现收益汇总计算
    - 实现图表数据聚合
    - _Requirements: 14.1-14.4_

  - [x] 16.2 实现收益API
    - 创建 app/api/earnings.py
    - 实现 GET /chef/earnings/summary 收益汇总
    - 实现 GET /chef/earnings/chart 收益图表
    - 实现 GET /chef/earnings/detail 收益明细
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ]* 16.3 编写属性测试: 收益计算
    - **Property 10: Chef Earnings Calculation**
    - **Validates: Requirements 14.4**

- [x] 17. 收藏模块实现
  - [x] 17.1 实现收藏服务
    - 创建 app/services/favorite_service.py
    - 实现收藏/取消收藏
    - _Requirements: 15.1-15.4_

  - [x] 17.2 实现收藏API
    - 创建 app/api/favorite.py
    - 实现 POST /favorites/{dish_id} 收藏
    - 实现 DELETE /favorites/{dish_id} 取消收藏
    - 实现 GET /favorites 收藏列表
    - _Requirements: 15.1, 15.2, 15.3_

  - [x] 17.3 编写属性测试: 收藏操作一致性

    - **Property 11: Favorite Toggle Consistency**
    - **Validates: Requirements 15.1, 15.2, 15.4**

- [x] 18. 文件上传模块实现
  - [x] 18.1 实现上传服务
    - 创建 app/services/upload_service.py
    - 实现文件类型验证
    - 实现文件大小验证
    - 实现文件存储
    - _Requirements: 16.1-16.4_

  - [x] 18.2 实现上传API
    - 创建 app/api/upload.py
    - 实现 POST /upload/image 图片上传
    - _Requirements: 16.1, 16.2, 16.3_

- [x] 19. Checkpoint - 全功能验证
  - 确保所有API接口正常工作
  - 确保所有测试通过，如有问题请询问用户

- [x] 20. 最终集成和文档
  - [x] 20.1 注册所有路由
    - 在 main.py 中注册所有API路由
    - 配置API文档 (Swagger/OpenAPI)
    - _Requirements: 1.1_

  - [ ] 20.2 编写属性测试: 响应格式


    - **Property 2: Standardized Response Format**
    - **Validates: Requirements 1.4**

  - [x] 20.3 创建README文档
    - 编写项目说明
    - 编写启动指南
    - 编写API文档链接

- [x] 21. Final Checkpoint - 项目完成
  - 确保所有功能正常
  - 确保所有测试通过
  - 确保文档完整

## Notes

- 标记 `*` 的任务为可选的属性测试任务
- 每个Checkpoint确保阶段性功能完整
- 属性测试使用 hypothesis 库
- 数据库配置: 192.168.1.70:3306, root/123456
