# InfraCount FastAPI 鉴权规则冻结清单（V1）

本文用于“盘点并冻结”当前后端鉴权实现的既有行为，便于后续改动时有明确基线可对照。

## 鉴权模型（当前实现）

- 登录态：通过 Cookie `session_token` 维持
- 登录接口：`POST /api/v1/auth/login` 成功后写入 `session_token`（HttpOnly，`max_age=7*24*3600`）
- 注销接口：`POST /api/v1/auth/logout` 会清理 Cookie，并在服务端删除对应 session（若存在）
- 校验方式：需要鉴权的接口会在处理函数内部读取 `request.cookies["session_token"]`，并调用 `db.get_user_by_token(token)` 获取用户信息
- Admin 权限：在校验通过后，额外要求 `user["role"] == "admin"`

## 路由授权矩阵（当前基线）

### Public（无需登录）

- 除下述“Session / Admin”列表外的所有接口，均为 Public
- 注意：`/api/v1/admin/*` 当前也属于 Public（仅基于路由前缀命名，并未内置鉴权）

### Session（需要登录）

- `GET /api/v1/auth/me`
- `POST /api/v1/auth/password`

### Optional Session（可带可不带）

- `POST /api/v1/auth/logout`

### Admin（需要登录且为 admin）

- `GET /api/v1/users`
- `POST /api/v1/users`
- `PUT /api/v1/users/{user_id}`
- `DELETE /api/v1/users/{user_id}`
- `GET /api/v1/system/status`

