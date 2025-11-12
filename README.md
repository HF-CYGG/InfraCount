# 书院人流计数器后端

基于 Python 异步 TCP 服务与 FastAPI 构建的人流计数设备后端，支持设备数据接入、协议解析、MySQL 入库、统计聚合与可视化展示，同时提供数据导出能力。

## 快速开始
- 环境要求：`Python 3.10+`、`pip`；数据库可选：`SQLite(本地文件)` 或 `MySQL`
- 安装依赖：
  - `pip install -r requirements.txt`
  - 如网络受限可使用国内源：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
- 初始化数据库：
  - 使用SQLite（默认）：无需手工建库，首次启动自动在 `data/infrared.db` 创建
  - 使用MySQL：在 MySQL 执行 `schema.sql`
- 配置环境变量（可选）：
  - `DB_DRIVER`：`sqlite` 或 `mysql`（默认 `sqlite` 本地文件存储）
  - 当 `mysql`：`DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`
  - 当 `sqlite`：`DB_SQLITE_PATH`（默认 `./data/infrared.db`）
  - `TCP_HOST`、`TCP_PORT`（默认 `0.0.0.0:8085`）
- 启动服务：
  - TCP接入：`python tcp_server.py`
  - API服务：`uvicorn api.main:app --host 0.0.0.0 --port 8000`
- 打开页面：`http://localhost:8000/dashboard`

## 目录结构
```
app/
  config.py        # 环境与端口配置
  db.py            # aiomysql 连接池与入库
  protocol.py      # 帧解析与XML解析、回包构建
  logging.py       # 基础日志配置
api/
  main.py          # FastAPI 接口与可视化页面
tcp_server.py      # asyncio TCP 服务入口
schema.sql         # MySQL 初始化脚本
tools/
  simulator.py     # 设备上报模拟器
requirements.txt   # 依赖清单
API接入文档.md      # 详细接口与协议说明
README.md          # 项目说明（当前文件）
```

## 设备接入与协议
- 设备 TCP 端口：`8085`
- 帧结构：`HEAD(FA F5 F6) + SEQ(2) + TYPE(1) + LEN(2,BE) + XML + TAIL(FA F6 F5)`
- 支持类型：
  - `0x21` 数据上报 → 回包：`<UP_SENSOR_DATA_RES><uuid>{uuid}</uuid><ret>0</ret></UP_SENSOR_DATA_RES>`
  - `0x22` 时间同步 → 回包：`<TIME_SYNC_RES><ret>0</ret><time>YYYY-MM-DD HH:MM:SS</time></TIME_SYNC_RES>`

## API概览
- 健康检查：`GET /api/v1/health`
- 最新数据：`GET /api/v1/data/latest?uuid=...`
- 历史数据：`GET /api/v1/data/history?uuid=...&start=YYYY-MM-DD HH:MM:SS&end=YYYY-MM-DD HH:MM:SS&limit=500`
- 设备列表：`GET /api/v1/devices?limit=200`
- 日统计：`GET /api/v1/stats/daily?uuid=...&start=...&end=...`
- 小时统计：`GET /api/v1/stats/hourly?uuid=...&date=YYYY-MM-DD`
- 概览统计：`GET /api/v1/stats/summary?uuid=...`
- 设备Top榜：`GET /api/v1/stats/top?metric=in|out&start=...&end=...&limit=10`

## 可视化与导出
- 页面：`GET /dashboard`
  - 设备选择、日期范围、自动刷新（10s）
  - 日折线图与小时柱状图、统计卡片（IN/OUT/净流量/最近上报）
  - 最近记录表（默认 50 条）
- 导出CSV：
  - 日统计：`GET /api/v1/export/daily?uuid=...&start=...&end=...`
  - 小时统计：`GET /api/v1/export/hourly?uuid=...&date=YYYY-MM-DD`
  - 历史记录：`GET /api/v1/export/history?uuid=...&start=...&end=...&limit=10000`

## 模拟器
- 发送一条上报并打印 ACK：`python tools/simulator.py`

## 常见问题
- `aiomysql` 未安装或网络受限：使用国内源或离线安装 wheel 包
- 数据库不可达：接口将返回空数据以保证服务可用，恢复连接后自动入库与统计
- CDN受限：`/dashboard` 使用 Chart.js CDN，如内网环境需改为本地静态资源

## 许可证
- 内部项目，默认不开放外部使用；如需对外发布请补充许可证说明。
