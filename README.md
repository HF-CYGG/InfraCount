# 书院人流计数器后端 (InfraCount Backend)

> **基于 Python Asyncio + FastAPI 的高性能红外设备接入与数据分析平台**

本项目专为高校书院/场馆场景设计，提供从设备接入、数据清洗、持久化存储到实时可视化的一站式解决方案。支持高并发 TCP 连接、多租户权限管理、AI 辅助场地归属匹配以及多维度流量统计分析。

## 核心特性
- **高并发接入**：基于 `asyncio` 的 TCP 服务，单机轻松支撑数千台设备长连接。
- **稳定可靠**：内置心跳保活、断线重连、异常熔断机制，确保数据不丢失。
- **智能归属**：集成模糊匹配算法，自动关联设备与物理场地，减少人工配置。
- **实时看板**：集成 ECharts/Chart.js，提供秒级刷新的流量趋势图与热力分布。
- **安全可控**：完善的 RBAC 权限体系，支持多级管理员与操作审计。

## 快速开始 (Quick Start)

### 方式一：脚本一键部署 (推荐)
无需手动安装依赖，脚本自动检测环境并启动服务。

**Windows (PowerShell):**
```powershell
# 安装并启动
.\install.ps1
.\start.ps1
```

**Linux / macOS:**
```bash
# 赋予权限并启动
chmod +x install.sh start.sh
./install.sh
./start.sh
```

### 方式二：手动部署
1. **环境准备**：确保 Python 3.10+ 及 pip 已安装。
2. **安装依赖**：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```
3. **数据库初始化**：
   - **SQLite (默认)**：直接启动，系统自动创建 `data/infrared.db`。
   - **MySQL**：需导入 `schema.sql` 并配置环境变量。
4. **启动服务**：
   ```bash
   # 终端 1：启动 TCP 接入服务 (默认端口 8085)
   python tcp_server.py
   
   # 终端 2：启动 Web API 服务 (默认端口 8000)
   uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

访问管理面板：[http://localhost:8000/dashboard](http://localhost:8000/dashboard) (默认账号：admin / admin123)

## 目录结构
```text
InfraCount/
├── api/
│   └── main.py          # FastAPI 路由入口与 Web 页面控制器
├── app/
│   ├── config.py        # 全局配置加载
│   ├── db.py            # 数据库连接池 (MySQL/SQLite)
│   ├── protocol.py      # 私有协议解析与封包构建
│   ├── matcher.py       # 场地归属智能匹配逻辑
│   ├── security.py      # 密码哈希与 Token 校验
│   └── events.py        # 全局事件总线
├── templates/           # Jinja2 前端模板 (Dashboard, Login, Devices...)
├── static/              # 静态资源 (CSS, JS, Fonts, Libs)
├── tools/
│   └── simulator.py     # 设备上报模拟器 (测试用)
├── tcp_server.py        # TCP 接入层主程序
├── requirements.txt     # Python 依赖清单
├── schema.sql           # MySQL 数据库结构定义
├── install.ps1/sh       # 一键安装脚本
└── start.ps1/sh         # 一键启动脚本
```

## 设备接入与协议
- **TCP 监听端口**：`8085` (可通过 `TCP_PORT` 环境变量修改)
- **协议格式**：`HEAD(3) + SEQ(2) + TYPE(1) + LEN(2) + PAYLOAD(XML) + TAIL(3)`
- **主要指令**：
  - `0x21` **数据上报**：设备上传进出人数 → 服务器回复 ACK。
  - `0x22` **时间同步**：设备请求校时 → 服务器下发当前时间。
  - `0x23` **心跳包**：维持 TCP 连接活跃 (默认 60s)。

## API 接口概览
| 模块 | 方法 | 路径 | 说明 |
| :--- | :--- | :--- | :--- |
| **基础** | `GET` | `/api/v1/health` | 服务健康检查 |
| **数据** | `GET` | `/api/v1/data/latest` | 获取指定设备的最新上报 |
| **数据** | `GET` | `/api/v1/data/history` | 查询历史流量记录 (支持分页) |
| **统计** | `GET` | `/api/v1/stats/daily` | 获取日流量统计趋势 |
| **统计** | `GET` | `/api/v1/stats/top` | 获取流量 Top N 设备榜单 |
| **设备** | `GET` | `/api/v1/devices` | 获取设备列表与在线状态 |
| **导出** | `GET` | `/api/v1/export/*` | 导出 CSV 格式报表 |

## 可视化功能
- **综合看板**：`GET /dashboard` - 实时流量卡片、小时级趋势图、设备状态概览。
- **设备管理**：`GET /devices` - 设备列表、在线状态监控、场地绑定编辑。
- **历史查询**：`GET /history` - 原始数据明细查询与导出。
- **账户中心**：`GET /account` - 修改密码、管理子账号 (Admin only)。

## 常见问题 (FAQ)
- **Q: 数据库连接失败？**
  - A: 请检查 `config.py` 或环境变量。如使用 SQLite，确保 `data/` 目录有写入权限。
- **Q: 页面图表不显示？**
  - A: 项目内置了常用图表库的本地资源。如遇显示问题，请检查浏览器控制台是否有静态资源加载错误。
- **Q: 如何修改监听端口？**
  - A: 修改 `app/config.py` 文件或设置环境变量 `TCP_PORT=9000`。


---

## 项目进度与规划

### 项目发展历程 (History)
```mermaid
timeline
    title InfraCount 演进时间轴
    2023 Q4 : 项目立项
            : TCP 核心框架搭建
            : 基础协议定义
    2024 Q1 : 数据库架构设计
            : 数据清洗引擎
            : Web 看板 V1.0 上线
    2024 Q2 : 多租户权限体系
            : Docker 容器化支持
            : 稳定性压测优化
    2024 Q3 : 智能归属算法 (Beta)
            : 移动端适配调研
            : 开放 API 初版
```

### 开发路线图 (Roadmap)
```mermaid
gantt
    title InfraCount 开发里程碑 (2025-2026)
    dateFormat  YYYY-MM-DD
    axisFormat  %m-%d
    
    %% 定义颜色
    %% classDef planned fill:#b71c1c,stroke:#fff,stroke-width:1px;
    %% classDef active fill:#e65100,stroke:#fff,stroke-width:1px;
    %% classDef done fill:#1b5e20,stroke:#fff,stroke-width:1px;

    section 核心基建
    TCP服务框架       :done,    core1, 2023-12-01, 7d
    协议解析引擎       :done,    core2, after core1, 10d
    数据库架构设计     :done,    core3, after core2, 5d
    Docker容器化支持  :active,  core4, 2024-04-01, 10d

    section 业务功能
    数据上报与存储     :done,    biz1,  2024-01-01, 10d
    RESTful API开发   :done,    biz2,  after biz1, 14d
    Web可视化看板      :done,    biz3,  after biz2, 14d
    多账户权限体系     :active,  biz4,  2024-02-15, 14d
    标准场地管理       :active,  biz5,  2024-03-01, 10d

    section 智能化与AI
    场地自动归属(模糊) :active,  ai1,   2024-03-01, 14d
    异常流量检测(规则) :         ai2,   after ai1, 20d
    LSTM客流预测模型   :         ai3,   2024-05-01, 45d
    热力图深度分析     :         ai4,   after ai3, 20d

    section 生态与集成
    Webhook消息推送    :         eco1,  2024-04-15, 10d
    钉钉/飞书集成      :         eco2,  after eco1, 10d
    移动端App (Beta)   :         eco3,  2024-06-01, 60d
    OpenAPI V2.0      :         eco4,  2024-08-01, 30d

    section 2025 架构演进
    微服务拆分        :         arch1, 2025-01-01, 60d
    边缘计算节点      :         arch2, after arch1, 45d
    云原生部署        :         arch3, 2025-04-01, 30d
```

### 功能完成度
| 模块 | 功能点 | 状态 | 进度 | 说明 |
| :--- | :--- | :---: | :--- | :--- |
| **接入层** | TCP 高并发服务 | 完成 | ![](https://geps.dev/progress/100) | 基于 asyncio |
| **接入层** | 私有协议解析 | 完成 | ![](https://geps.dev/progress/100) | XML/二进制混合 |
| **数据层** | 多数据库支持 | 完成 | ![](https://geps.dev/progress/100) | SQLite + MySQL |
| **Web层** | 实时数据看板 | 完成 | ![](https://geps.dev/progress/100) | 10s 自动刷新 |
| **Web层** | 账户权限管理 | 迭代 | ![](https://geps.dev/progress/90) | 角色分级/编辑 |
| **Web层** | 标准场地配置 | 迭代 | ![](https://geps.dev/progress/85) | 一键校正/反馈 |
| **运维层** | 一键部署脚本 | 完成 | ![](https://geps.dev/progress/100) | Win/Linux 双端 |
| **智能层** | AI 场地校正 | 开发 | ![](https://geps.dev/progress/70) | 模糊匹配/自学习 |
| **智能层** | 流量预测分析 | 规划 | ![](https://geps.dev/progress/0) | 引入机器学习 |
| **生态层** | 消息推送集成 | 规划 | ![](https://geps.dev/progress/0) | Webhook/钉钉 |

> *注：进度条实时渲染，状态图表自动更新*

### 未来规划详情 (Future Plans)
为了进一步提升系统的智能化与实用性，我们制定了详细的 2024-2025 演进计划：

#### 1. AI 增强 (AI Intelligence)
- **LSTM 客流预测模型**：
  - 基于历史流量数据与节假日/天气因子，构建 LSTM 深度学习模型。
  - 实现未来 24 小时至 7 天的客流趋势预测，辅助场馆运营调度。
- **异常行为检测**：
  - 识别非正常的流量突增/骤降（如火警逃生、设备遮挡）。
  - 结合设备信号强度与电池数据，通过规则引擎+统计学模型自动告警。

#### 2. 移动端生态 (Mobile)
- **微信小程序 (Lite)**：提供核心数据概览、实时告警推送，方便运维人员随时查看。
- **原生 App (Pro)**：集成蓝牙配置功能，支持现场对红外计数器进行参数设置与固件升级。

#### 3. 企业级集成 (Integration)
- **IM 消息推送**：
  - 支持钉钉/飞书/企业微信的 Webhook 机器人，实时推送设备离线、低电量及流量阈值告警。
- **OpenAPI V2.0**：
  - 开放更加标准化的 RESTful 接口，支持 OAuth2.0 认证，方便第三方系统（如教务系统、楼宇自控系统）集成数据。

### 战略规划脑图 (Strategic Map)
```mermaid
mindmap
  root((InfraCount 2025))
    AI 智能化
      LSTM 客流预测
      异常行为检测
      热力图深度分析
    移动端生态
      微信小程序
      运维 APP
      蓝牙现场配置
    企业级集成
      消息推送
        钉钉
        飞书
        企业微信
      OpenAPI V2.0
      OAuth2.0 认证
    系统架构
      微服务拆分
      云原生部署
      边缘计算节点
```

### 技术栈构成
```mermaid
pie
    title 项目代码构成 (预估)
    "Python (Backend)" : 45
    "HTML/JS (Frontend)" : 30
    "SQL (Database)" : 10
    "Shell/PowerShell (Ops)" : 10
    "Markdown (Docs)" : 5
```

---

## 系统架构

本系统采用经典的分层架构设计，实现了从底层硬件接入到上层应用展示的全链路打通：

- **感知层 (IoT Layer)**：负责红外计数器设备的物理连接与数据采集，通过 XML 协议打包上报。
- **服务层 (Service Layer)**：基于 asyncio 的高并发 TCP 服务，负责协议解析、心跳保活及 AI 归属匹配。
- **数据层 (Data Layer)**：采用 MySQL/SQLite 混合存储，支持原始日志与聚合统计分离，Redis/Memory 提供高速缓存。
- **应用层 (App Layer)**：FastAPI 构建的 RESTful 网关，服务于 Web Dashboard 与管理后台，并为第三方提供 API 能力。

```mermaid
graph TD
    %% 全局样式：使用默认连线颜色以适应亮/暗主题
    %% linkStyle default stroke-width:2px;

    %% 定义样式：保留彩色背景与白字，边框设为透明以适应不同背景
    classDef device fill:#8e44ad,stroke:none,color:#fff;
    classDef core fill:#2980b9,stroke:none,color:#fff;
    classDef db fill:#27ae60,stroke:none,color:#fff;
    classDef web fill:#c0392b,stroke:none,color:#fff;

    subgraph IoT_Layer [感知层]
        Device1[红外计数器 A]:::device
        Device2[红外计数器 B]:::device
        Device3[红外计数器 N]:::device
    end

    subgraph Service_Layer [服务层]
        TCPServer[TCP 接入服务 :8085]:::core
        Protocol[协议解析引擎]:::core
        Matcher[智能归属匹配]:::core
    end

    subgraph Data_Layer [数据层]
        DB[(MySQL / SQLite)]:::db
        Cache[内存缓存]:::db
    end

    subgraph App_Layer [应用层]
        API[FastAPI 网关 :8000]:::web
        Dashboard[可视化看板]:::web
        Admin[管理后台]:::web
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

## 核心数据模型

系统基于关系型数据库设计，主要包含以下核心实体：
- **Device**：设备基础信息表，记录 UUID、电量、信号及当前状态。
- **InfraredRecord**：流水日志表，存储每一次进出计数事件及其关联的地理位置。
- **LocationMapping**：位置映射规则表，定义设备与物理场地的绑定关系（AI 匹配基础）。
- **User**：系统用户表，包含角色权限与认证信息。

```mermaid
classDiagram
    %% 样式适配：深色背景白字，边框透明
    classDef table fill:#2c3e50,stroke:none,color:#fff;
    
    class Device {
        +String uuid (PK)
        +DateTime last_time
        +Int battery_level
        +Int signal_status
        +String current_location
        +update_status()
    }
    
    class InfraredRecord {
        +Int id (PK)
        +String device_uuid (FK)
        +Int in_count
        +Int out_count
        +DateTime record_time
        +String location
        +String academy
    }

    class LocationMapping {
        +Int id (PK)
        +String device_uuid
        +String standard_location
        +String academy_category
        +match_rule()
    }

    class User {
        +Int id (PK)
        +String username
        +String password_hash
        +String role [admin, user]
        +check_permission()
    }

    Device "1" -- "n" InfraredRecord : generates
    Device "1" -- "1" LocationMapping : binds
    LocationMapping "1" -- "n" InfraredRecord : tags
    
    class Device table
    class InfraredRecord table
    class LocationMapping table
    class User table
```

---

## 数据与设备流程

为了清晰展示数据如何在系统中流转，以及设备的生命周期管理，我们梳理了以下核心流程：

### 1. 设备上报与告警流程 (Sequence Diagram)
```mermaid
sequenceDiagram
    %% 样式定义
    participant D as Device (红外设备)
    participant T as TCP Server
    participant M as Matcher (AI归属)
    participant DB as Database
    participant WS as WebSocketMgr
    participant W as Web/Dashboard

    Note over D,T: TCP 长连接保持

    %% 数据上报
    D->>T: 发送 XML 数据包 (0x21)
    activate T
    T->>T: 解析帧头 & XML
    T->>DB: 写入原始记录 (Raw Data)
    
    T->>M: 请求场地归属匹配
    activate M
    M->>M: 模糊匹配/规则查找
    M-->>T: 返回 Location/Academy
    deactivate M

    T->>DB: 更新归属信息
    T->>WS: 广播新数据事件
    WS-->>W: 推送实时更新
    
    T-->>D: 返回 ACK (0x21 Response)
    deactivate T

    %% 告警触发
    par 异步检测
        T->>T: 检查电量/信号/心跳
        opt 电量 < 20%
            T->>DB: 写入告警记录
            T->>WS: 推送告警通知
            WS-->>W: 弹窗提示 "低电量"
        end
    end
```

### 2. 设备生命周期状态 (State Diagram)
```mermaid
stateDiagram-v2
    [*] --> Unknown: 设备初次接入

    state "在线 (Online)" as Online {
        [*] --> Idle: 等待数据
        Idle --> Reporting: 上报数据
        Reporting --> Idle: ACK确认
        Idle --> Syncing: 时间同步
        Syncing --> Idle: 完成同步
    }

    Unknown --> Online: TCP握手成功
    Online --> Offline: 心跳超时/连接断开
    Offline --> Online: 重连成功

    state "异常状态" as Error {
        LowBattery: 低电量 (<20%)
        WeakSignal: 弱信号 (RSSI < -90)
    }

    Online --> LowBattery: 电量检测
    LowBattery --> Online: 更换电池
    Online --> WeakSignal: 信号检测
    WeakSignal --> Online: 信号恢复
```

---

## 功能树状图

```mermaid
graph TD
    %% 样式定义 - 使用默认连线颜色
    %% linkStyle default stroke:#bbb,stroke-width:1px;
    
    %% 定义节点样式：深色背景+白色文字，边框透明
    classDef root fill:#4a148c,stroke:none,color:#fff,font-size:16px;
    classDef l1 fill:#0d47a1,stroke:none,color:#fff;
    classDef l2 fill:#1b5e20,stroke:none,color:#fff;
    classDef l3 fill:#b71c1c,stroke:none,color:#fff;

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

    %% 5. 未来规划 (New)
    R --> C5[未来规划]:::l1
    C5 --> C5_1(AI增强):::l2
    C5_1 --> C5_1_1[流量预测]:::l3
    C5_1 --> C5_1_2[异常检测]:::l3
    
    C5 --> C5_2(移动端):::l2
    C5_2 --> C5_2_1[小程序]:::l3
    C5_2 --> C5_2_2[App]:::l3
    
    C5 --> C5_3(集成):::l2
    C5_3 --> C5_3_1[钉钉/飞书]:::l3
    C5_3 --> C5_3_2[Webhook]:::l3
```
