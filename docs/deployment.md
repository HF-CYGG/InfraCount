# InfraCount Docker 与 CI 交付说明

## 本地容器运行

1. 复制 `.env.example` 为 `.env`，按部署域名调整 `CORS_ALLOW_ORIGINS` 和 `SESSION_COOKIE_SECURE`。
2. 构建并启动服务：

```bash
docker compose --env-file .env -f docker/docker-compose.yml up --build -d
```

3. 验证健康检查：

```bash
curl http://localhost:8000/api/v1/health
```

默认容器会同时启动 Web API `8000` 和 TCP 接入 `8085`。SQLite 数据持久化在 Compose volume `infracount-data` 中。

## 安全默认值

- `SESSION_COOKIE_SECURE=0` 仅适合本地 HTTP；HTTPS 生产部署应设置为 `1`。
- `CORS_ALLOW_ORIGINS` 不再默认 `*`，生产环境必须写明可信前端域名。
- 首次启动仍会创建 `admin/admin`，交付部署后应立即登录修改密码。

## GitHub Actions

- `ci.yml`：PR 和 push 执行后端测试、API 合约校验、前端 typecheck/build、Docker build。
- `docker-publish.yml`：`main` 分支或 `v*` tag 构建并推送镜像到 GHCR。
- GHCR 发布使用 `GITHUB_TOKEN`，不需要额外 Docker Hub 密钥。
