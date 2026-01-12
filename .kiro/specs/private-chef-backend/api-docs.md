# 私厨预订小程序 API 接口对接文档

## 基础信息

- **Base URL**: `http://192.168.1.70:8000/api`
- **Content-Type**: `application/json`
- **认证方式**: JWT Bearer Token

## 通用响应格式

所有接口返回统一的JSON格式：

```json
{
    "code": 200,
    "message": "success",
    "data": {}
}
```

## 通用错误码

| code | 说明 |
|------|------|
| 200 | 成功 |
| 1001 | 参数错误 |
| 1002 | 未授权 |
| 1003 | 无权限 |
| 1004 | 资源不存在 |
| 2002 | 绑定码无效 |
| 2003 | 已绑定其他大厨 |
| 3003 | 菜品已售罄 |
| 4002 | 订单状态无效 |

---

## 1. 认证接口

### 1.1 微信登录

**POST** `/auth/login`

**Request:**
```json
{
    "code": "微信登录code",
    "role": "foodie"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 微信wx.login获取的code |
| role | string | 是 | 角色: foodie/chef |

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIs...",
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

### 1.2 绑定手机号

**POST** `/auth/bind-phone`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "encrypted_data": "加密数据",
    "iv": "初始向量"
}
```

---

## 2. 用户接口

### 2.1 获取用户信息

**GET** `/user/profile`

**Headers:** `Authorization: Bearer {token}`

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": "uuid",
        "nickname": "用户昵称",
        "avatar": "头像URL",
        "phone": "13800138000",
        "role": "foodie",
        "binding_code": "ABC12345",
        "bound_chef": {
            "id": "chef_uuid",
            "nickname": "张大厨",
            "avatar": "头像URL",
            "rating": 4.9
        }
    }
}
```

### 2.2 更新用户信息

**PUT** `/user/profile`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "nickname": "新昵称",
    "avatar": "新头像URL",
    "introduction": "大厨简介(仅大厨)",
    "specialties": ["川菜", "粤菜"]
}
```

---

## 3. 菜品接口

### 3.1 获取菜品列表(吃货端)

**GET** `/dishes`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码,默认1 |
| page_size | int | 否 | 每页数量,默认10 |
| category | string | 否 | 分类筛选 |
| keyword | string | 否 | 搜索关键词 |
| date | string | 否 | 预订日期YYYY-MM-DD |

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

### 3.2 获取菜品详情

**GET** `/dishes/{dish_id}`

**Headers:** `Authorization: Bearer {token}`

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": "uuid",
        "name": "红烧肉",
        "price": 68.00,
        "images": ["url1", "url2"],
        "description": "精选五花肉，慢火炖煮",
        "ingredients": ["五花肉", "冰糖", "酱油"],
        "tags": ["家常", "下饭"],
        "category": "中餐",
        "available_dates": ["2024-01-15", "2024-01-16"],
        "max_quantity": 10,
        "rating": 4.8,
        "review_count": 25,
        "chef": {
            "id": "uuid",
            "nickname": "张大厨",
            "avatar": "url",
            "introduction": "10年烹饪经验",
            "rating": 4.9
        },
        "is_favorited": false
    }
}
```

### 3.3 创建菜品(大厨端)

**POST** `/chef/dishes`

**Headers:** `Authorization: Bearer {token}`

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

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 菜品名称 |
| price | number | 是 | 价格 |
| images | array | 是 | 图片URL列表,至少1张 |
| description | string | 否 | 描述 |
| ingredients | array | 是 | 食材列表 |
| tags | array | 否 | 口味标签 |
| category | string | 否 | 菜系分类 |
| available_dates | array | 否 | 可预订日期 |
| max_quantity | int | 否 | 每日最大份数,默认10 |

### 3.4 更新菜品(大厨端)

**PUT** `/chef/dishes/{dish_id}`

**Headers:** `Authorization: Bearer {token}`

**Request:** 同创建菜品

### 3.5 删除菜品(大厨端)

**DELETE** `/chef/dishes/{dish_id}`

**Headers:** `Authorization: Bearer {token}`

### 3.6 切换上下架状态(大厨端)

**PUT** `/chef/dishes/{dish_id}/status`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "is_on_shelf": true
}
```

### 3.7 获取大厨菜品列表(大厨端)

**GET** `/chef/dishes`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| is_on_shelf | bool | 否 | 上架状态筛选 |

---

## 4. 订单接口

### 4.1 创建订单

**POST** `/orders`

**Headers:** `Authorization: Bearer {token}`

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

### 4.2 获取订单列表(吃货端)

**GET** `/orders`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | all/pending/cooking/completed |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": "uuid",
            "order_no": "202401150001",
            "status": "pending",
            "total_price": 136.00,
            "delivery_time": "2024-01-15 12:00:00",
            "items": [
                {
                    "dish_name": "红烧肉",
                    "dish_image": "url",
                    "price": 68.00,
                    "quantity": 2
                }
            ],
            "created_at": "2024-01-14 10:00:00"
        }
    ],
    "page_info": {...}
}
```

### 4.3 获取订单详情

**GET** `/orders/{order_id}`

**Headers:** `Authorization: Bearer {token}`

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": "uuid",
        "order_no": "202401150001",
        "status": "cooking",
        "total_price": 136.00,
        "delivery_time": "2024-01-15 12:00:00",
        "remarks": "少放辣",
        "items": [
            {
                "dish_id": "uuid",
                "dish_name": "红烧肉",
                "dish_image": "url",
                "price": 68.00,
                "quantity": 2
            }
        ],
        "address": {
            "name": "张三",
            "phone": "13800138000",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园xxx"
        },
        "chef": {
            "id": "uuid",
            "nickname": "张大厨",
            "avatar": "url",
            "phone": "13900139000"
        },
        "created_at": "2024-01-14 10:00:00"
    }
}
```

### 4.4 取消订单

**PUT** `/orders/{order_id}/cancel`

**Headers:** `Authorization: Bearer {token}`

### 4.5 确认收货

**PUT** `/orders/{order_id}/confirm`

**Headers:** `Authorization: Bearer {token}`

---

## 5. 大厨订单管理接口

### 5.1 获取订单列表(大厨端)

**GET** `/chef/orders`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:** 同吃货端

### 5.2 接受订单

**PUT** `/chef/orders/{order_id}/accept`

**Headers:** `Authorization: Bearer {token}`

### 5.3 拒绝订单

**PUT** `/chef/orders/{order_id}/reject`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "reason": "今日已约满"
}
```

### 5.4 标记烹饪完成

**PUT** `/chef/orders/{order_id}/cooking-done`

**Headers:** `Authorization: Bearer {token}`

### 5.5 标记配送中

**PUT** `/chef/orders/{order_id}/delivering`

**Headers:** `Authorization: Bearer {token}`

---

## 6. 评价接口

### 6.1 提交评价

**POST** `/orders/{order_id}/review`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "rating": 5,
    "content": "非常好吃！",
    "images": ["url1", "url2"]
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| rating | int | 是 | 评分1-5 |
| content | string | 否 | 评价内容 |
| images | array | 否 | 图片URL,最多3张 |

### 6.2 获取菜品评价列表

**GET** `/dishes/{dish_id}/reviews`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": "uuid",
            "rating": 5,
            "content": "非常好吃！",
            "images": ["url1"],
            "user": {
                "nickname": "吃货小王",
                "avatar": "url"
            },
            "created_at": "2024-01-15 14:00:00"
        }
    ],
    "page_info": {...}
}
```

---

## 7. 打赏接口

### 7.1 创建打赏

**POST** `/tips`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "chef_id": "uuid",
    "order_id": "uuid",
    "amount": 10.00,
    "message": "感谢大厨！"
}
```

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "tip_id": "uuid",
        "payment_params": {...}
    }
}
```

### 7.2 获取打赏记录

**GET** `/tips`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 8. 地址接口

### 8.1 获取地址列表

**GET** `/addresses`

**Headers:** `Authorization: Bearer {token}`

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": "uuid",
            "name": "张三",
            "phone": "13800138000",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园xxx",
            "is_default": true
        }
    ]
}
```

### 8.2 添加地址

**POST** `/addresses`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "name": "张三",
    "phone": "13800138000",
    "province": "广东省",
    "city": "深圳市",
    "district": "南山区",
    "detail": "科技园xxx",
    "is_default": false
}
```

### 8.3 更新地址

**PUT** `/addresses/{address_id}`

**Headers:** `Authorization: Bearer {token}`

**Request:** 同添加地址

### 8.4 删除地址

**DELETE** `/addresses/{address_id}`

**Headers:** `Authorization: Bearer {token}`

### 8.5 设为默认地址

**PUT** `/addresses/{address_id}/default`

**Headers:** `Authorization: Bearer {token}`

---

## 9. 绑定接口

### 9.1 绑定大厨

**POST** `/bindingcode`

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
    "binding_code": "ABC12345"
}
```

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "chef": {
            "id": "uuid",
            "nickname": "张大厨",
            "avatar": "url",
            "introduction": "10年烹饪经验",
            "rating": 4.9
        }
    }
}
```

### 9.2 解除绑定

**DELETE** `/binding`

**Headers:** `Authorization: Bearer {token}`

### 9.3 获取绑定信息

**GET** `/binding`

**Headers:** `Authorization: Bearer {token}`

---

## 10. 通知接口

### 10.1 获取通知列表

**GET** `/notifications`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": "uuid",
            "type": "new_order",
            "title": "新订单",
            "content": "您有一个新订单，红烧肉x2",
            "data": {
                "order_id": "uuid"
            },
            "is_read": false,
            "created_at": "2024-01-15 10:00:00"
        }
    ],
    "page_info": {...}
}
```

### 10.2 获取未读数量

**GET** `/notifications/unread-count`

**Headers:** `Authorization: Bearer {token}`

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "count": 5
    }
}
```

### 10.3 标记已读

**PUT** `/notifications/{notification_id}/read`

**Headers:** `Authorization: Bearer {token}`

### 10.4 全部标记已读

**PUT** `/notifications/read-all`

**Headers:** `Authorization: Bearer {token}`

---

## 11. 收益接口(大厨端)

### 11.1 获取收益汇总

**GET** `/chef/earnings/summary`

**Headers:** `Authorization: Bearer {token}`

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

### 11.2 获取收益图表

**GET** `/chef/earnings/chart`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | weekly/monthly |

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        "values": [120, 200, 150, 80, 70, 110, 120]
    }
}
```

### 11.3 获取收益明细

**GET** `/chef/earnings/detail`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| type | string | 否 | order/tip |

---

## 12. 收藏接口

### 12.1 收藏菜品

**POST** `/favorites/{dish_id}`

**Headers:** `Authorization: Bearer {token}`

### 12.2 取消收藏

**DELETE** `/favorites/{dish_id}`

**Headers:** `Authorization: Bearer {token}`

### 12.3 获取收藏列表

**GET** `/favorites`

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 13. 上传接口

### 13.1 上传图片

**POST** `/upload/image`

**Headers:** 
- `Authorization: Bearer {token}`
- `Content-Type: multipart/form-data`

**Request:**
- `file`: 图片文件 (jpg/png/gif, 最大5MB)

**Response:**
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "url": "http://192.168.1.70:8000/uploads/xxx.jpg"
    }
}
```

---

## 14. 支付回调接口

### 14.1 微信支付回调

**POST** `/payment/notify`

> 此接口由微信服务器调用，前端无需关注

---

## 前端对接示例

### Axios配置

```javascript
// api/index.ts
import axios from 'axios';

const instance = axios.create({
    baseURL: 'http://192.168.1.70:8000/api',
    timeout: 10000
});

// 请求拦截器
instance.interceptors.request.use(config => {
    const token = uni.getStorageSync('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// 响应拦截器
instance.interceptors.response.use(
    response => {
        const { code, message, data } = response.data;
        if (code === 200) {
            return data;
        }
        if (code === 1002) {
            // 未授权，跳转登录
            uni.navigateTo({ url: '/pages/login/index' });
        }
        uni.showToast({ title: message, icon: 'none' });
        return Promise.reject(response.data);
    },
    error => {
        uni.showToast({ title: '网络错误', icon: 'none' });
        return Promise.reject(error);
    }
);

export default instance;
```

### API调用示例

```javascript
// api/dish.ts
import request from './index';

// 获取菜品列表
export const getDishes = (params) => {
    return request.get('/dishes', { params });
};

// 获取菜品详情
export const getDishDetail = (dishId) => {
    return request.get(`/dishes/${dishId}`);
};

// 创建菜品(大厨端)
export const createDish = (data) => {
    return request.post('/chef/dishes', data);
};
```

```javascript
// api/order.ts
import request from './index';

// 创建订单
export const createOrder = (data) => {
    return request.post('/orders', data);
};

// 获取订单列表
export const getOrders = (params) => {
    return request.get('/orders', { params });
};

// 取消订单
export const cancelOrder = (orderId) => {
    return request.put(`/orders/${orderId}/cancel`);
};
```
