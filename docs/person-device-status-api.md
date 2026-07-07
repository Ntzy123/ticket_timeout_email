# 万物云人员设备状态 API

## 概述

定时查询指定人员在项目范围内的实时位置与距项目中心距离，结果以缓存 JSON 形式供前端读取。

- 调度方式：守护线程 **每分钟 0 秒** 轮询一次
- 最新快照：`cache/person_device_status.json`
- 历史记录：`cache/person_device_status_history.json`（最多 100 条，仅状态变化或距离变动 >100m 时记录）
- 上游 API：`https://heimdallr.onewo.com/api/headquarter/zyt/last/allDevice`
- 查询人员：**李仕科**
- 项目编号：`52010017`

---

## 接口列表

### 1. 获取最新位置数据

```
GET /api/person-device-status/location-latest
```

返回调度线程最近一次查询的结果（缓存文件内容）。

#### 正常响应（200）

```json
{
  "timestamp": 1748428800000,
  "is_ok": true,
  "code": "200",
  "records": [
    {
      "name": "李仕科",
      "distance_m": 1234.56,
      "status": "1"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `timestamp` | long | 查询时间戳（毫秒） |
| `is_ok` | bool | 上游接口是否成功 |
| `code` | string | 上游业务状态码 |
| `records[].name` | string | 人员姓名 |
| `records[].distance_m` | float | 距项目中心距离（米） |
| `records[].status` | string | `"1"`=设备在线 `"0"`=设备离线；在线但未开定位时仍为 `"1"`（`distance_m` 为 `0`） |

#### 错误响应

| 状态码 | 可能原因 |
|---|---|
| `404` | 调度线程尚未完成首次查询 (`{"error":"暂无数据"}`) |
| `500` | 缓存文件损坏 (`{"error":"<异常信息>"}`) |
| `200` (但 `is_ok=false`) | 上游查询失败，records 中的 `status` 为 `"0"`，`distance_m` 为 `0` |

---

### 2. 获取位置历史记录

```
GET /api/person-device-status/location-history
```

返回按时间顺序排列的位置变化记录。仅在 **状态变更** 或 **距离变化超过 100 米** 时写入，避免冗余。

- 最大保留 **100 条**，超出时自动丢弃最旧记录

#### 正常响应（200）

```json
[
  {
    "timestamp": 1748428800000,
    "name": "李仕科",
    "status": "1",
    "distance_m": 1234.56
  },
  {
    "timestamp": 1748432400000,
    "name": "李仕科",
    "status": "0",
    "distance_m": 0
  }
]
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `[].timestamp` | long | 记录时间戳（毫秒） |
| `[].name` | string | 人员姓名 |
| `[].status` | string | `"1"`=在线 `"0"`=离线 |
| `[].distance_m` | float | 距项目中心距离（米） |

#### 错误响应

| 状态码 | 可能原因 |
|---|---|
| `500` | 缓存文件损坏 (`{"error":"<异常信息>"}`) |

> 无历史记录时返回空数组 `[]`（而非 404）。

