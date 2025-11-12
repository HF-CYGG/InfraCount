# API接入文档（V1.0）

## 概述
- 目标：提供红外计数设备数据的查询与监控接口。
- 基础URL：`http://<server-host>:8000`
- 版本：`/api/v1`
- 认证：当前无认证，建议在生产环境加上网关或Token。

## 接口命名规范
- 资源路径使用小写、用中划线或复合名时统一为单词组合，例如 `data`, `devices`。
- 查询参数使用有意义、简短的英文单词：`uuid`, `start`, `end`, `limit`。
- 所有时间字段为 `YYYY-MM-DD HH:MM:SS` 文本格式。

## 健康检查
- 方法：`GET`
- 路径：`/api/v1/health`
- 响应：
```
{
  "status": "ok"
}
```

## 最新数据查询
- 方法：`GET`
- 路径：`/api/v1/data/latest`
- 参数：
  - `uuid` 必填，设备唯一标识。
- 响应示例：
```
{
  "uuid": "ABC123",
  "in": 10,
  "out": 8,
  "time": "2025-11-12 14:30:00",
  "battery_level": 85,
  "signal_status": 1
}
```
- 说明：当设备无数据时返回空对象 `{}`。

## 历史数据查询
- 方法：`GET`
- 路径：`/api/v1/data/history`
- 参数：
  - `uuid` 必填
  - `start` 选填，开始时间 `YYYY-MM-DD HH:MM:SS`
  - `end` 选填，结束时间 `YYYY-MM-DD HH:MM:SS`
  - `limit` 选填，默认 `500`
- 响应示例：
```
[
  {
    "uuid": "ABC123",
    "in_count": 10,
    "out_count": 8,
    "time": "2025-11-12 14:30:00",
    "battery_level": 85,
    "signal_status": 1
  },
  {
    "uuid": "ABC123",
    "in_count": 12,
    "out_count": 9,
    "time": "2025-11-12 14:00:00",
    "battery_level": 86,
    "signal_status": 1
  }
]
```

## 设备列表
- 方法：`GET`
- 路径：`/api/v1/devices`
- 参数：
  - `limit` 选填，默认 `200`
- 响应示例：
```
[
  {
    "uuid": "ABC123",
    "last_time": "2025-11-12 14:30:00",
    "last_id": 1024
  },
  {
    "uuid": "DEF456",
    "last_time": "2025-11-12 14:28:10",
    "last_id": 998
  }
]
```

## 错误码与约定
- HTTP状态码：2xx 成功，4xx/5xx 失败。
- 数据为空时返回空数组或空对象。
- 字段含义：
  - `battery_level` 为整数百分比
  - `signal_status` 为设备上报的信号状态枚举值

## 调用示例
- 查询健康：
```
curl "http://localhost:8000/api/v1/health"
```
- 最新数据：
```
curl "http://localhost:8000/api/v1/data/latest?uuid=ABC123"
```
- 历史数据：
```
curl "http://localhost:8000/api/v1/data/history?uuid=ABC123&start=2025-11-12%2009:00:00&end=2025-11-12%2018:00:00&limit=100"
```
- 设备列表：
```
curl "http://localhost:8000/api/v1/devices?limit=100"
```

## 设备TCP上行与回包
- 端口：`8085`
- 报文：`[FA F5 F6] + SEQ(2) + TYPE(1) + LEN(2,BE) + XML + [FA F6 F5]`
- 支持类型：
  - `0x21` 数据上报，服务端回包：`<UP_SENSOR_DATA_RES><uuid>{uuid}</uuid><ret>0</ret></UP_SENSOR_DATA_RES>`
  - `0x22` 时间同步，服务端回包：`<TIME_SYNC_RES><ret>0</ret><time>YYYY-MM-DD HH:MM:SS</time></TIME_SYNC_RES>`

## 部署建议
- 依赖：`fastapi`, `uvicorn`, `aiomysql`
- 启动API：`uvicorn api.main:app --host 0.0.0.0 --port 8000`
- 启动TCP：`python tcp_server.py`

## 统计与可视化

### 统计接口
- 日统计：`GET /api/v1/stats/daily?uuid=...&start=YYYY-MM-DD HH:MM:SS&end=YYYY-MM-DD HH:MM:SS`
  - 返回：`[{ day: '2025-11-11', in_total: 120, out_total: 98 }, ...]`
- 小时统计：`GET /api/v1/stats/hourly?uuid=...&date=YYYY-MM-DD`
  - 返回：`[{ hour: '09:00', in_total: 10, out_total: 8 }, ...]`
- 概览统计：`GET /api/v1/stats/summary?uuid=...`
  - 返回：`{ in_total: 1000, out_total: 950, last_in: 12, last_out: 11, last_time: '2025-11-12 14:30:00' }`

### 可视化页面
- 路径：`GET /dashboard`
- 功能：
  - 下拉选择设备，设置日期范围
  - 展示每日 IN/OUT 曲线图（Chart.js）
  - 展示当前设备统计概览（总计与最近上报）
