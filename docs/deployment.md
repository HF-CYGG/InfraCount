# InfraCount Docker 部署说明

本文说明使用 Docker Compose 部署 InfraCount。部署者必须先复制配置示例并设置初始管理员密码；示例文件只包含空密码字段和非敏感默认值，不要把真实密钥提交到仓库。

## 配置与首次初始化

```bash
cp .env.example .env
```

至少设置以下配置：

```dotenv
INITIAL_ADMIN_PASSWORD=请替换为部署者设置的强密码
INFRACOUNT_LOG_MODE=stdio
```

`INITIAL_ADMIN_PASSWORD` 只用于首次初始化管理员账号，必须由部署者设置，不能使用示例值或把密码写入 Git。使用已有 SQLite 数据库启动时不会覆盖现有管理员密码；只有初始化新数据库时才使用该值。

`.env.example` 保留了 Web/TCP 端口、SQLite 路径、鉴权与 CSRF、设备时间同步、告警阈值、Session、CORS、自动同步和 SMTP 告警配置。Compose 会通过 `--env-file .env` 将其声明的参数用于端口映射、镜像选择和运行环境；修改 `.env` 后需要重新创建容器才能使配置生效。

## 方式一：从仓库构建

在仓库根目录执行：

```bash
docker compose --env-file .env -f docker/docker-compose.yml up --build -d
```

查看状态和日志：

```bash
docker compose --env-file .env -f docker/docker-compose.yml ps
docker logs -f infracount
```

`INFRACOUNT_LOG_MODE` 可配置日志去向，Compose 默认使用 `stdio` 并接受 `.env` 覆盖。`stdio` 会让 Web API 与 TCP 子进程日志进入容器标准输出，因此可以通过 `docker logs` 查看启动、退出和运行期日志；设置为其他值并重新创建容器后，启动器会把日志写入 `/app/data`。

## 方式二：从 GHCR 拉取

镜像地址为 `ghcr.io/hf-cygg/infracount`。按需要选择发布标签：

- `main`：main 分支构建的滚动标签。
- `latest`：main 分支构建的滚动标签。
- `sha-<commit>`：按提交固定版本，适合可审计部署。
- `1.2.3`、`1.2`、`1`：由源 Git 标签 `v1.2.3` 生成的 semver 镜像标签；部署时优先固定使用完整的 `1.2.3` 标签或 `sha-<commit>`。

拉取并启动指定版本（以下示例使用提交标签）：

```bash
docker pull ghcr.io/hf-cygg/infracount:sha-<commit>
INFRACOUNT_IMAGE=ghcr.io/hf-cygg/infracount:sha-<commit> docker compose --env-file .env -f docker/docker-compose.yml up -d
```

在 PowerShell 中可先设置环境变量：

```powershell
$env:INFRACOUNT_IMAGE = 'ghcr.io/hf-cygg/infracount:sha-<commit>'
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

不要依赖服务器自动部署；升级、回滚和配置变更均由运维人员手动执行并留存记录。

## 健康检查与网络暴露

访问：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

健康检查用于联检 API、SQLite/DB 连接和 TCP 服务状态；同时确认 Compose 的 `healthy` 状态以及 TCP 端口可连通：

```bash
docker compose --env-file .env -f docker/docker-compose.yml ps
nc -z 127.0.0.1 8085
```

容器默认暴露 Web API `8000` 和设备 TCP 接入 `8085`。TCP `8085` 只应向设备所在的可信网段开放，并在防火墙或安全组中拒绝公网及其他不可信来源。

生产环境应使用 HTTPS 反向代理，并在 `.env` 中设置：

```dotenv
SESSION_COOKIE_SECURE=1
```

同时将 `CORS_ALLOW_ORIGINS` 限定为实际前端来源，不要使用通配符。

## 升级与回滚

升级前先确认当前镜像、配置和数据库备份；固定使用 SHA 或完整 semver 标签（例如 `1.2.3`，不是源 Git 标签 `v1.2.3`）。示例：

```bash
docker compose --env-file .env -f docker/docker-compose.yml pull
docker compose --env-file .env -f docker/docker-compose.yml up -d
docker compose --env-file .env -f docker/docker-compose.yml ps
```

回滚时把 `.env` 中的 `INFRACOUNT_IMAGE` 改回已验证的旧 SHA/semver 标签，再执行：

```bash
docker compose --env-file .env -f docker/docker-compose.yml pull
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

升级或回滚后重新检查 `/api/v1/health`、`docker logs infracount` 和 TCP `8085`。不要在未备份或未确认数据库一致性的情况下切换版本。

## SQLite 命名卷备份与恢复

本节只适用于 `DB_DRIVER=sqlite`。Compose 的持久化卷挂载在 `/app/data`，因此生产环境的 `DB_SQLITE_PATH` 必须位于该目录内；使用 MySQL 或自定义其他挂载路径时，应采用对应数据库或存储系统的备份工具。

备份前必须停止容器，或确保应用已暂停写入并且 SQLite 处于一致状态。下列每个会读取或写入数据卷的命令块都会从 Compose 容器的 `/app/data` 挂载重新解析实际卷名，不假设 Compose 项目名前缀或卷名。

```bash
set -eu
docker compose --env-file .env -f docker/docker-compose.yml stop infracount
CONTAINER_ID="$(docker compose --env-file .env -f docker/docker-compose.yml ps --all --quiet infracount)"
test -n "$CONTAINER_ID"
test "$(printf '%s\n' "$CONTAINER_ID" | sed '/^$/d' | wc -l | tr -d ' ')" -eq 1
VOLUME="$(docker inspect --format '{{range .Mounts}}{{if and (eq .Destination "/app/data") (eq .Type "volume")}}{{.Name}}{{end}}{{end}}' "$CONTAINER_ID")"
test -n "$VOLUME"
docker volume inspect "$VOLUME" >/dev/null
DB_SQLITE_PATH="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_ID" | sed -n 's/^DB_SQLITE_PATH=//p')"
case "$DB_SQLITE_PATH" in /app/data/*) ;; *) echo 'DB_SQLITE_PATH must be inside /app/data.' >&2; exit 1 ;; esac
DB_RELATIVE_PATH="${DB_SQLITE_PATH#/app/data/}"
case "$DB_RELATIVE_PATH" in ""|/*|../*|*/../*|*/..) echo 'Unsafe DB_SQLITE_PATH.' >&2; exit 1 ;; esac

BACKUP_DIR="$(pwd)/backups"
mkdir -p "$BACKUP_DIR"
BACKUP_NAME="infracount-data-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
test ! -e "$BACKUP_DIR/$BACKUP_NAME"
docker run --rm -v "$VOLUME:/source:ro" -v "$BACKUP_DIR:/backup" -e BACKUP_NAME="$BACKUP_NAME" alpine:3.20 sh -ceu 'tar czf "/backup/$BACKUP_NAME" -C /source .'
test -s "$BACKUP_DIR/$BACKUP_NAME"
docker run --rm -v "$BACKUP_DIR:/backup:ro" -e BACKUP_NAME="$BACKUP_NAME" alpine:3.20 sh -ceu 'tar tzf "/backup/$BACKUP_NAME" >/dev/null'
printf 'Validated backup: %s\n' "$BACKUP_DIR/$BACKUP_NAME"
```

恢复操作会在确认归档、创建当前数据的安全备份并在临时卷中验证解压后，才清空目标卷。将下面的 `ARCHIVE_NAME` 替换为已验证归档的实际文件名；不要传入任意路径或跳过任一检查。

```bash
set -eu
docker compose --env-file .env -f docker/docker-compose.yml stop infracount
CONTAINER_ID="$(docker compose --env-file .env -f docker/docker-compose.yml ps --all --quiet infracount)"
test -n "$CONTAINER_ID"
test "$(printf '%s\n' "$CONTAINER_ID" | sed '/^$/d' | wc -l | tr -d ' ')" -eq 1
VOLUME="$(docker inspect --format '{{range .Mounts}}{{if and (eq .Destination "/app/data") (eq .Type "volume")}}{{.Name}}{{end}}{{end}}' "$CONTAINER_ID")"
test -n "$VOLUME"
docker volume inspect "$VOLUME" >/dev/null
DB_SQLITE_PATH="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_ID" | sed -n 's/^DB_SQLITE_PATH=//p')"
case "$DB_SQLITE_PATH" in /app/data/*) ;; *) echo 'DB_SQLITE_PATH must be inside /app/data.' >&2; exit 1 ;; esac
DB_RELATIVE_PATH="${DB_SQLITE_PATH#/app/data/}"
case "$DB_RELATIVE_PATH" in ""|/*|../*|*/../*|*/..) echo 'Unsafe DB_SQLITE_PATH.' >&2; exit 1 ;; esac

BACKUP_DIR="$(pwd)/backups"
ARCHIVE_NAME='infracount-data-<UTC时间>.tar.gz'
ARCHIVE_FILE="$BACKUP_DIR/$ARCHIVE_NAME"
case "$ARCHIVE_NAME" in infracount-data-*.tar.gz) ;; *) echo 'Archive name is not allowed.' >&2; exit 1 ;; esac
test -f "$ARCHIVE_FILE"
test -s "$ARCHIVE_FILE"
docker run --rm -v "$BACKUP_DIR:/backup:ro" -e ARCHIVE_NAME="$ARCHIVE_NAME" alpine:3.20 sh -ceu 'tar tzf "/backup/$ARCHIVE_NAME" >/dev/null'

STAGING_VOLUME="$(docker volume create)"
cleanup() { docker volume rm "$STAGING_VOLUME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --rm -v "$STAGING_VOLUME:/staged" -v "$BACKUP_DIR:/backup:ro" -e ARCHIVE_NAME="$ARCHIVE_NAME" -e DB_RELATIVE_PATH="$DB_RELATIVE_PATH" alpine:3.20 sh -ceu 'tar xzf "/backup/$ARCHIVE_NAME" -C /staged; test -f "/staged/$DB_RELATIVE_PATH"'

SAFETY_NAME="infracount-pre-restore-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
test ! -e "$BACKUP_DIR/$SAFETY_NAME"
docker run --rm -v "$VOLUME:/source:ro" -v "$BACKUP_DIR:/backup" -e SAFETY_NAME="$SAFETY_NAME" alpine:3.20 sh -ceu 'tar czf "/backup/$SAFETY_NAME" -C /source .'
test -s "$BACKUP_DIR/$SAFETY_NAME"
docker run --rm -v "$BACKUP_DIR:/backup:ro" -e SAFETY_NAME="$SAFETY_NAME" alpine:3.20 sh -ceu 'tar tzf "/backup/$SAFETY_NAME" >/dev/null'

docker run --rm -v "$STAGING_VOLUME:/staged:ro" -v "$VOLUME:/target" -e DB_RELATIVE_PATH="$DB_RELATIVE_PATH" alpine:3.20 sh -ceu 'test -d /target; find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; cp -a /staged/. /target/; test -f "/target/$DB_RELATIVE_PATH"'
printf 'Restore completed. Safety backup: %s\n' "$BACKUP_DIR/$SAFETY_NAME"
```

如果恢复后的健康检查或关键数据验证失败，保持服务停止，并使用刚才输出的 `SAFETY_NAME` 执行下列回滚。该命令同样会先验证归档并在临时卷中解压，再覆盖目标卷：

```bash
set -eu
docker compose --env-file .env -f docker/docker-compose.yml stop infracount
CONTAINER_ID="$(docker compose --env-file .env -f docker/docker-compose.yml ps --all --quiet infracount)"
test -n "$CONTAINER_ID"
test "$(printf '%s\n' "$CONTAINER_ID" | sed '/^$/d' | wc -l | tr -d ' ')" -eq 1
VOLUME="$(docker inspect --format '{{range .Mounts}}{{if and (eq .Destination "/app/data") (eq .Type "volume")}}{{.Name}}{{end}}{{end}}' "$CONTAINER_ID")"
test -n "$VOLUME"
docker volume inspect "$VOLUME" >/dev/null
DB_SQLITE_PATH="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_ID" | sed -n 's/^DB_SQLITE_PATH=//p')"
case "$DB_SQLITE_PATH" in /app/data/*) ;; *) echo 'DB_SQLITE_PATH must be inside /app/data.' >&2; exit 1 ;; esac
DB_RELATIVE_PATH="${DB_SQLITE_PATH#/app/data/}"
case "$DB_RELATIVE_PATH" in ""|/*|../*|*/../*|*/..) echo 'Unsafe DB_SQLITE_PATH.' >&2; exit 1 ;; esac

BACKUP_DIR="$(pwd)/backups"
SAFETY_NAME='infracount-pre-restore-<UTC时间>.tar.gz'
case "$SAFETY_NAME" in infracount-pre-restore-*.tar.gz) ;; *) echo 'Safety archive name is not allowed.' >&2; exit 1 ;; esac
test -s "$BACKUP_DIR/$SAFETY_NAME"
docker run --rm -v "$BACKUP_DIR:/backup:ro" -e SAFETY_NAME="$SAFETY_NAME" alpine:3.20 sh -ceu 'tar tzf "/backup/$SAFETY_NAME" >/dev/null'

STAGING_VOLUME="$(docker volume create)"
cleanup() { docker volume rm "$STAGING_VOLUME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --rm -v "$STAGING_VOLUME:/staged" -v "$BACKUP_DIR:/backup:ro" -e SAFETY_NAME="$SAFETY_NAME" -e DB_RELATIVE_PATH="$DB_RELATIVE_PATH" alpine:3.20 sh -ceu 'tar xzf "/backup/$SAFETY_NAME" -C /staged; test -f "/staged/$DB_RELATIVE_PATH"'
docker run --rm -v "$STAGING_VOLUME:/staged:ro" -v "$VOLUME:/target" -e DB_RELATIVE_PATH="$DB_RELATIVE_PATH" alpine:3.20 sh -ceu 'test -d /target; find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; cp -a /staged/. /target/; test -f "/target/$DB_RELATIVE_PATH"'
printf 'Rollback completed from: %s\n' "$BACKUP_DIR/$SAFETY_NAME"
```

恢复或回滚完成后启动服务并检查健康状态、管理员登录和关键数据，再对外开放服务：

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
docker compose --env-file .env -f docker/docker-compose.yml ps
curl --fail http://127.0.0.1:8000/api/v1/health
```

不要把 SQLite 文件、备份归档、SMTP 密码或其他运行时密钥加入 Git。
