# Design Document

## Overview

本设计文档描述私厨预订微信小程序的技术架构和实现方案。项目采用 UniApp + Vue3 + UniNutUI + Axios 技术栈，支持吃货端和大厨端两个用户角色，通过专属绑定机制建立一对一服务关系。

## Architecture

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    微信小程序容器                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐         ┌─────────────────┐           │
│  │    吃货端页面     │         │    大厨端页面     │           │
│  │  (pages/foodie)  │         │  (pages/chef)   │           │
│  └────────┬────────┘         └────────┬────────┘           │
│           │                           │                     │
│  ┌────────┴───────────────────────────┴────────┐           │
│  │              共享组件层 (components)          │           │
│  │    UniNutUI + 自定义业务组件                  │           │
│  └────────────────────┬────────────────────────┘           │
│                       │                                     │
│  ┌────────────────────┴────────────────────────┐           │
│  │              状态管理层 (store)               │           │
│  │         Pinia (用户、订单、菜品状态)           │           │
│  └────────────────────┬────────────────────────┘           │
│                       │                                     │
│  ┌────────────────────┴────────────────────────┐           │
│  │              API层 (api)                     │           │
│  │    请求拦截器 → Axios实例 → 响应拦截器         │           │
│  └────────────────────┬────────────────────────┘           │
│                       │                                     │
│  ┌────────────────────┴────────────────────────┐           │
│  │              Mock层 (mock)                   │           │
│  │         开发环境数据模拟                       │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
├── src/
│   ├── api/                    # API接口层
│   │   ├── index.ts            # Axios实例和拦截器
│   │   ├── dish.ts             # 菜品相关API
│   │   ├── order.ts            # 订单相关API
│   │   ├── user.ts             # 用户相关API
│   │   └── chef.ts             # 大厨相关API
│   ├── components/             # 共享组件
│   │   ├── DishCard/           # 菜品卡片
│   │   ├── OrderCard/          # 订单卡片
│   │   ├── StatusBar/          # 状态进度条
│   │   └── EmptyState/         # 空状态组件
│   ├── mock/                   # Mock数据
│   │   ├── index.ts            # Mock入口
│   │   ├── dish.ts             # 菜品模拟数据
│   │   ├── order.ts            # 订单模拟数据
│   │   └── user.ts             # 用户模拟数据
│   ├── pages/                  # 页面
│   │   ├── foodie/             # 吃货端页面
│   │   │   ├── home/           # 首页
│   │   │   ├── dish-detail/    # 菜品详情
│   │   │   ├── cart/           # 点菜/预订
│   │   │   ├── payment/        # 支付确认
│   │   │   ├── orders/         # 订单列表
│   │   │   ├── order-detail/   # 订单详情
│   │   │   ├── review/         # 评价
│   │   │   ├── tip/            # 打赏
│   │   │   └── profile/        # 个人中心
│   │   └── chef/               # 大厨端页面
│   │       ├── login/          # 登录
│   │       ├── dishes/         # 菜品管理
│   │       ├── dish-edit/      # 发布/编辑菜品
│   │       ├── orders/         # 订单管理
│   │       ├── order-detail/   # 订单详情
│   │       ├── earnings/       # 收益统计
│   │       ├── profile/        # 个人主页
│   │       └── messages/       # 消息通知
│   ├── store/                  # 状态管理
│   │   ├── index.ts            # Pinia入口
│   │   ├── user.ts             # 用户状态
│   │   ├── cart.ts             # 购物车状态
│   │   └── notification.ts     # 通知状态
│   ├── utils/                  # 工具函数
│   │   ├── request.ts          # 请求封装
│   │   ├── storage.ts          # 本地存储
│   │   └── format.ts           # 格式化工具
│   ├── static/                 # 静态资源
│   │   ├── images/             # 图片
│   │   └── icons/              # 图标
│   ├── App.vue                 # 应用入口
│   ├── main.ts                 # 主入口
│   ├── pages.json              # 页面配置
│   ├── manifest.json           # 应用配置
│   └── uni.scss                # 全局样式变量
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Components and Interfaces

### 请求拦截器设计

```typescript
// api/index.ts
interface RequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  data?: any;
  headers?: Record<string, string>;
}

interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

// 请求拦截器
function requestInterceptor(config: RequestConfig): RequestConfig {
  // 添加token
  const token = uni.getStorageSync('token');
  if (token) {
    config.headers = {
      ...config.headers,
      Authorization: `Bearer ${token}`
    };
  }
  return config;
}

// 响应拦截器
function responseInterceptor<T>(response: ApiResponse<T>): T | Promise<never> {
  if (response.code === 200) {
    return response.data;
  }
  // 处理错误码
  switch (response.code) {
    case 401:
      // 未授权，跳转登录
      uni.navigateTo({ url: '/pages/foodie/login/index' });
      break;
    case 403:
      uni.showToast({ title: '无权限访问', icon: 'none' });
      break;
    case 500:
      uni.showToast({ title: '服务器错误', icon: 'none' });
      break;
  }
  return Promise.reject(response);
}
```

### Mock服务设计

```typescript
// mock/index.ts
interface MockHandler {
  url: string | RegExp;
  method: string;
  response: (params: any) => any;
}

const mockHandlers: MockHandler[] = [];

function setupMock(handler: MockHandler): void {
  mockHandlers.push(handler);
}

function matchMock(url: string, method: string): MockHandler | undefined {
  return mockHandlers.find(h => {
    const urlMatch = typeof h.url === 'string' 
      ? h.url === url 
      : h.url.test(url);
    return urlMatch && h.method.toUpperCase() === method.toUpperCase();
  });
}
```

### 核心组件接口

```typescript
// components/DishCard/types.ts
interface DishCardProps {
  dish: Dish;
  showChef?: boolean;
  showDistance?: boolean;
  onClick?: (dish: Dish) => void;
}

// components/OrderCard/types.ts
interface OrderCardProps {
  order: Order;
  showActions?: boolean;
  onAction?: (action: OrderAction, order: Order) => void;
}

type OrderAction = 'cancel' | 'confirm' | 'review' | 'tip';

// components/StatusBar/types.ts
interface StatusBarProps {
  status: OrderStatus;
  steps: StatusStep[];
}

interface StatusStep {
  key: OrderStatus;
  label: string;
  icon: string;
}
```

### Store接口

```typescript
// store/user.ts
interface UserState {
  userInfo: UserInfo | null;
  token: string;
  role: 'foodie' | 'chef';
  bindingCode: string;
  boundChef: ChefInfo | null;
}

interface UserActions {
  login(code: string): Promise<void>;
  logout(): void;
  bindChef(code: string): Promise<boolean>;
  unbindChef(): Promise<void>;
  generateBindingCode(): string;
}

// store/cart.ts
interface CartState {
  items: CartItem[];
  deliveryTime: string;
  remarks: string;
}

interface CartActions {
  addItem(dish: Dish, quantity: number): void;
  removeItem(dishId: string): void;
  updateQuantity(dishId: string, quantity: number): void;
  clearCart(): void;
  getTotalPrice(): number;
}
```

## Data Models

### 用户模型

```typescript
interface UserInfo {
  id: string;
  openId: string;
  nickname: string;
  avatar: string;
  phone?: string;
  role: 'foodie' | 'chef';
  bindingCode: string;
  boundChefId?: string;  // 吃货绑定的大厨ID
  createdAt: string;
}

interface ChefInfo extends UserInfo {
  introduction: string;
  specialties: string[];
  rating: number;
  totalOrders: number;
  totalEarnings: number;
}
```

### 菜品模型

```typescript
interface Dish {
  id: string;
  chefId: string;
  name: string;
  price: number;
  images: string[];
  description: string;
  ingredients: string[];
  tags: string[];           // 口味标签
  category: string;         // 菜系分类
  availableDates: string[]; // 可预订日期
  maxQuantity: number;      // 每日最大份数
  currentQuantity: number;  // 当日已预订份数
  rating: number;
  reviewCount: number;
  isOnShelf: boolean;
  createdAt: string;
  updatedAt: string;
}

interface CartItem {
  dish: Dish;
  quantity: number;
  selectedDate: string;
}
```

### 订单模型

```typescript
type OrderStatus = 'pending' | 'accepted' | 'cooking' | 'delivering' | 'completed' | 'cancelled';

interface Order {
  id: string;
  orderNo: string;
  foodieId: string;
  chefId: string;
  items: OrderItem[];
  totalPrice: number;
  status: OrderStatus;
  deliveryTime: string;
  deliveryAddress: Address;
  remarks: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

interface OrderItem {
  dishId: string;
  dishName: string;
  dishImage: string;
  price: number;
  quantity: number;
}

interface Address {
  id: string;
  name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail: string;
  isDefault: boolean;
}
```

### 评价模型

```typescript
interface Review {
  id: string;
  orderId: string;
  foodieId: string;
  chefId: string;
  dishId: string;
  rating: number;          // 1-5星
  content: string;
  images: string[];
  createdAt: string;
}
```

### 打赏模型

```typescript
interface Tip {
  id: string;
  foodieId: string;
  chefId: string;
  orderId?: string;
  amount: number;
  message?: string;
  createdAt: string;
}
```

### 消息通知模型

```typescript
type NotificationType = 'new_order' | 'order_status' | 'binding' | 'tip';

interface Notification {
  id: string;
  userId: string;
  type: NotificationType;
  title: string;
  content: string;
  data: Record<string, any>;
  isRead: boolean;
  createdAt: string;
}
```

### 绑定关系模型

```typescript
interface Binding {
  id: string;
  foodieId: string;
  chefId: string;
  bindingCode: string;
  createdAt: string;
}
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Request Interceptor Token Injection

*For any* API request made through the request interceptor, if a valid token exists in storage, the request headers SHALL contain the Authorization header with the token value.

**Validates: Requirements 1.3**

### Property 2: Response Interceptor Error Handling

*For any* API response with error code (401, 403, 500), the response interceptor SHALL handle it according to the defined error handling logic (redirect for 401, toast for 403/500).

**Validates: Requirements 1.4**

### Property 3: Mock Service Interception

*For any* registered mock endpoint, when the API is called in development mode, the mock service SHALL return the configured mock data without making actual network requests.

**Validates: Requirements 1.5**

### Property 4: Cart Price Calculation

*For any* cart state with items, the total price SHALL equal the sum of (item.price × item.quantity) for all items in the cart.

**Validates: Requirements 4.2**

### Property 5: Cart Item Removal Consistency

*For any* cart with N items, after removing one item, the cart SHALL contain exactly N-1 items and the removed item SHALL not be present.

**Validates: Requirements 4.3**

### Property 6: Order Status Filter

*For any* order list filtered by status S, all returned orders SHALL have status equal to S.

**Validates: Requirements 6.1**

### Property 7: Order Action Availability

*For any* order with status S, the available actions SHALL match the defined action rules:
- pending: [cancel]
- accepted/cooking: [cancel]
- delivering: [confirm]
- completed: [review, tip]

**Validates: Requirements 7.4**

### Property 8: Rating Update After Review

*For any* dish, after a new review with rating R is submitted, the dish's average rating SHALL be recalculated to include the new rating.

**Validates: Requirements 8.4**

### Property 9: Binding Code Uniqueness

*For any* two users (foodie or chef), their binding codes SHALL be different.

**Validates: Requirements 10.7, 17.1**

### Property 10: One-to-One Binding Constraint

*For any* foodie, they SHALL be bound to at most one chef at any time. Attempting to bind to a second chef SHALL fail or require unbinding first.

**Validates: Requirements 17.4**

### Property 11: Bound Chef Dish Filter

*For any* foodie bound to a chef, the dish list displayed SHALL only contain dishes from that bound chef.

**Validates: Requirements 17.5**

### Property 12: Order Status Transition Validity

*For any* order, status transitions SHALL follow the valid state machine:
- pending → accepted | cancelled
- accepted → cooking | cancelled
- cooking → delivering
- delivering → completed

**Validates: Requirements 14.3, 14.4, 14.5**

### Property 13: Dish Validation Rules

*For any* dish being published, it SHALL have: non-empty name, price > 0, at least one image, and at least one available date.

**Validates: Requirements 13.5**

### Property 14: Earnings Calculation

*For any* chef, total earnings SHALL equal the sum of all completed order amounts plus all received tips.

**Validates: Requirements 15.1**

### Property 15: Notification on Order Creation

*For any* new order created by a foodie, a notification SHALL be created for the bound chef containing dish names and delivery time.

**Validates: Requirements 18.1, 18.2**

## Error Handling

### API错误处理策略

| 错误码 | 处理方式 | 用户提示 |
|--------|----------|----------|
| 401 | 清除token，跳转登录页 | "登录已过期，请重新登录" |
| 403 | 显示toast | "无权限访问" |
| 404 | 显示空状态 | "内容不存在" |
| 500 | 显示toast，可重试 | "服务器错误，请稍后重试" |
| 网络错误 | 显示toast，可重试 | "网络连接失败" |

### 业务错误处理

```typescript
// 订单相关错误
enum OrderError {
  DISH_SOLD_OUT = 'DISH_SOLD_OUT',           // 菜品已售罄
  CHEF_UNAVAILABLE = 'CHEF_UNAVAILABLE',     // 大厨不可用
  INVALID_DELIVERY_TIME = 'INVALID_TIME',    // 配送时间无效
  PAYMENT_FAILED = 'PAYMENT_FAILED',         // 支付失败
}

// 绑定相关错误
enum BindingError {
  INVALID_CODE = 'INVALID_CODE',             // 绑定码无效
  ALREADY_BOUND = 'ALREADY_BOUND',           // 已绑定其他大厨
  SELF_BINDING = 'SELF_BINDING',             // 不能绑定自己
}
```

### 表单验证错误

- 必填字段为空：显示红色边框和提示文字
- 格式错误（如手机号）：显示格式要求提示
- 数值超出范围：显示允许范围提示

## Testing Strategy

### 测试框架选择

- 单元测试：Vitest
- 组件测试：@vue/test-utils
- 属性测试：fast-check
- E2E测试：微信小程序开发者工具自动化

### 单元测试覆盖

1. **工具函数测试**
   - 价格计算函数
   - 日期格式化函数
   - 绑定码生成函数

2. **Store测试**
   - Cart store: 添加、删除、更新数量、计算总价
   - User store: 登录、登出、绑定状态管理

3. **API拦截器测试**
   - 请求拦截器token注入
   - 响应拦截器错误处理

### 属性测试配置

```typescript
// 使用 fast-check 进行属性测试
import * as fc from 'fast-check';

// 每个属性测试运行至少100次迭代
const testConfig = { numRuns: 100 };
```

### 属性测试用例

| 属性编号 | 测试描述 | 生成器 |
|----------|----------|--------|
| Property 4 | 购物车价格计算 | 生成随机CartItem数组 |
| Property 5 | 购物车删除一致性 | 生成随机Cart状态和要删除的索引 |
| Property 6 | 订单状态过滤 | 生成随机Order数组和状态值 |
| Property 9 | 绑定码唯一性 | 生成多个用户，验证码不重复 |
| Property 10 | 一对一绑定约束 | 生成绑定操作序列 |
| Property 12 | 订单状态转换 | 生成状态转换序列 |

### Mock数据策略

开发阶段使用Mock数据模拟所有API响应：

```typescript
// mock/dish.ts - 菜品模拟数据示例
export const mockDishes: Dish[] = [
  {
    id: '1',
    name: '红烧肉',
    price: 68,
    images: ['/static/images/dish1.jpg'],
    description: '精选五花肉，慢火炖煮',
    ingredients: ['五花肉', '冰糖', '酱油'],
    tags: ['家常', '下饭'],
    category: '中餐',
    // ...
  }
];
```

### 测试命名规范

```typescript
// Feature: private-chef-miniprogram, Property 4: Cart Price Calculation
describe('Cart Store', () => {
  it('Property 4: total price equals sum of item prices times quantities', () => {
    // ...
  });
});
```
