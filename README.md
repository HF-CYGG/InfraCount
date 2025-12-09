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


---

## 📊 项目进度与规划

### 📅 开发路线图 (Roadmap)
```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'darkMode': true }}}%%
gantt
    title InfraCount 开发里程碑
    dateFormat  YYYY-MM-DD
    axisFormat  %m-%d

    section 核心基建
    TCP服务框架       :done,    core1, 2023-12-01, 7d
    协议解析引擎       :done,    core2, after core1, 10d
    数据库架构设计     :done,    core3, after core2, 5d

    section 业务功能
    数据上报与存储     :done,    biz1,  2024-01-01, 10d
    RESTful API开发   :done,    biz2,  after biz1, 14d
    Web可视化看板      :done,    biz3,  after biz2, 14d
    多账户权限体系     :active,  biz4,  2024-02-15, 10d

    section 智能化与高级特性
    场地自动归属       :active,  ai1,   2024-03-01, 14d
    异常流量检测       :         ai2,   after ai1, 20d
    客流预测模型       :         ai3,   2024-04-01, 30d
```

### 🚀 功能完成度
| 模块 | 功能点 | 状态 | 进度 | 说明 |
| :--- | :--- | :---: | :--- | :--- |
| **接入层** | TCP 高并发服务 | ✅ 完成 | ![](https://geps.dev/progress/100) | 基于 asyncio |
| **接入层** | 私有协议解析 | ✅ 完成 | ![](https://geps.dev/progress/100) | XML/二进制混合 |
| **数据层** | 多数据库支持 | ✅ 完成 | ![](https://geps.dev/progress/100) | SQLite + MySQL |
| **Web层** | 实时数据看板 | ✅ 完成 | ![](https://geps.dev/progress/100) | 10s 自动刷新 |
| **Web层** | 账户权限管理 | 🚀 迭代 | ![](https://geps.dev/progress/90) | 角色分级/编辑 |
| **运维层** | 一键部署脚本 | 🚀 迭代 | ![](https://geps.dev/progress/85) | Win/Linux 双端 |
| **智能层** | AI 场地校正 | 🚧 开发 | ![](https://geps.dev/progress/60) | 模糊匹配算法 |
| **智能层** | 流量预测分析 | 📅 规划 | ![](https://geps.dev/progress/0) | 引入机器学习 |

> *注：进度条实时渲染，状态图表自动更新*

---

## 🏗️ 系统架构

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#ffffff' }}}%%
graph TD
    %% 全局样式：白色连线
    linkStyle default stroke:#fff,stroke-width:2px;

    %% 定义样式：高对比度暗色主题配色
    classDef device fill:#8e44ad,stroke:#fff,stroke-width:2px,color:#fff;
    classDef core fill:#2980b9,stroke:#fff,stroke-width:2px,color:#fff;
    classDef db fill:#27ae60,stroke:#fff,stroke-width:2px,color:#fff;
    classDef web fill:#c0392b,stroke:#fff,stroke-width:2px,color:#fff;

    subgraph IoT_Layer [感知层]
        style IoT_Layer fill:#222,stroke:#666,color:#fff
        Device1[📍 红外计数器 A]:::device
        Device2[📍 红外计数器 B]:::device
        Device3[📍 红外计数器 N]:::device
    end

    subgraph Service_Layer [服务层]
        style Service_Layer fill:#222,stroke:#666,color:#fff
        TCPServer[📡 TCP 接入服务 :8085]:::core
        Protocol[⚙️ 协议解析引擎]:::core
        Matcher[🧠 智能归属匹配]:::core
    end

    subgraph Data_Layer [数据层]
        style Data_Layer fill:#222,stroke:#666,color:#fff
        DB[(🗄️ MySQL / SQLite)]:::db
        Cache[🚀 内存缓存]:::db
    end

    subgraph App_Layer [应用层]
        style App_Layer fill:#222,stroke:#666,color:#fff
        API[🔌 FastAPI 网关 :8000]:::web
        Dashboard[📊 可视化看板]:::web
        Admin[🛡️ 管理后台]:::web
    end

    %% 链路关系
    Device1 & Device2 & Device3 -->|TCP/XML| TCPServer
    TCPServer -->|Raw Data| Protocol
    Protocol -->|Clean Data| Matcher
    Matcher -->|Structured Data| DB
    
    API -->|Query| DB
    API -->|Cache| Cache
    
    Dashboard -->|HTTP/WS| API
    Admin -->|HTTP| API
```

---

## 🌳 功能树状图

```mermaid
graph TD
    %% 样式定义 - 强制高对比度
    linkStyle default stroke:#bbb,stroke-width:1px;
    
    %% 定义节点样式：使用深色背景+白色文字，兼容暗色模式
    classDef root fill:#4a148c,stroke:#fff,stroke-width:2px,color:#fff,font-size:16px;
    classDef l1 fill:#0d47a1,stroke:#fff,stroke-width:1px,color:#fff;
    classDef l2 fill:#1b5e20,stroke:#fff,stroke-width:1px,color:#fff;
    classDef l3 fill:#b71c1c,stroke:#fff,stroke-width:1px,color:#fff;

    %% 根节点
    R((InfraCount)):::root

    %% 1. 后端核心
    R --> C1[后端核心]:::l1
    C1 --> C1_1(TCP服务):::l2
    C1_1 --> C1_1_1[并发连接]:::l3
    C1_1 --> C1_1_2[心跳保活]:::l3
    C1_1 --> C1_1_3[异常熔断]:::l3

    C1 --> C1_2(协议处理):::l2
    C1_2 --> C1_2_1[XML解析]:::l3
    C1_2 --> C1_2_2[数据清洗]:::l3
    C1_2 --> C1_2_3[ACK回包]:::l3

    C1 --> C1_3(数据存储):::l2
    C1_3 --> C1_3_1[连接池管理]:::l3
    C1_3 --> C1_3_2[自动迁移]:::l3

    %% 2. Web应用
    R --> C2[Web应用]:::l1
    C2 --> C2_1(可视化):::l2
    C2_1 --> C2_1_1[实时流量图]:::l3
    C2_1 --> C2_1_2[热力分布]:::l3
    C2_1 --> C2_1_3[历史回溯]:::l3

    C2 --> C2_2(API接口):::l2
    C2_2 --> C2_2_1[RESTful规范]:::l3
    C2_2 --> C2_2_2[Token认证]:::l3
    C2_2 --> C2_2_3[数据导出]:::l3

    %% 3. 管理后台
    R --> C3[管理后台]:::l1
    C3 --> C3_1(设备管理):::l2
    C3_1 --> C3_1_1[状态监控]:::l3
    C3_1 --> C3_1_2[远程配置]:::l3

    C3 --> C3_2(场地管理):::l2
    C3_2 --> C3_2_1[自动校正]:::l3
    C3_2 --> C3_2_2[手工绑定]:::l3

    C3 --> C3_3(用户管理):::l2
    C3_3 --> C3_3_1[权限分配]:::l3
    C3_3 --> C3_3_2[操作审计]:::l3

    %% 4. 运维支持
    R --> C4[运维支持]:::l1
    C4 --> C4_1(一键脚本):::l2
    C4_1 --> C4_1_1[Windows]:::l3
    C4_1 --> C4_1_2[Linux]:::l3

    C4 --> C4_2(日志系统):::l2
    C4_2 --> C4_2_1[轮转归档]:::l3
    C4_2 --> C4_2_2[错误追踪]:::l3
```
