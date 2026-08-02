import io
import asyncio
import logging
import difflib
import csv
import json
import os
import platform
import smtplib
import ssl
import re
import time
import uuid as uuidlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import List, Optional, Dict, Any
from email.message import EmailMessage
from fastapi import FastAPI, HTTPException, Query, Body, File, UploadFile, Request, Response
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

import aiosqlite

from app import db
from app import config
from app.matcher import matcher
from api.dependencies import (
    api_auth_middleware,
    require_admin_user,
)
from api.routers import auth as auth_router
from api.routers import users as users_router

app = FastAPI(title="InfraCount API", version="1.0.0")

_APP_START_TS = time.time()
_LOG_IMPORT_CACHE: Dict[str, Dict[str, Any]] = {}
_AUTO_SYNC_TASK: Optional[asyncio.Task] = None
_ALERT_EMAIL_TASK: Optional[asyncio.Task] = None

_DB_MERGE_UPLOAD_CACHE: Dict[str, Dict[str, Any]] = {}
_DB_MERGE_JOB_CACHE: Dict[str, Dict[str, Any]] = {}
_DB_MERGE_UPLOAD_DIR = os.path.abspath(os.path.join("data", "db_merge_uploads"))

def _db_merge_cleanup(now_ts: float, max_age_sec: int = 2 * 3600) -> None:
    """
    清理过期的合并导入上传文件与任务缓存。

    设计说明：
    - 上传的 .db 文件可能较大，不应长期占用磁盘；
    - 任务状态用于前端轮询进度，默认保留 2 小时；
    - 正在运行的任务不清理，避免误删。
    """
    expired_uploads: List[str] = []
    for import_id, v in list(_DB_MERGE_UPLOAD_CACHE.items()):
        created = float(v.get("created_at_ts") or 0)
        if now_ts - created > max_age_sec:
            expired_uploads.append(import_id)
    for import_id in expired_uploads:
        ctx = _DB_MERGE_UPLOAD_CACHE.pop(import_id, None) or {}
        p = str(ctx.get("path") or "").strip()
        if p and os.path.isfile(p):
            try:
                os.remove(p)
            except Exception:
                pass

    expired_jobs: List[str] = []
    for job_id, j in list(_DB_MERGE_JOB_CACHE.items()):
        created = float(j.get("created_at_ts") or 0)
        running = bool(j.get("running"))
        if running:
            continue
        if now_ts - created > max_age_sec:
            expired_jobs.append(job_id)
    for job_id in expired_jobs:
        _DB_MERGE_JOB_CACHE.pop(job_id, None)

async def _require_admin_user(request: Request) -> Dict[str, Any]:
    """
    管理员鉴权统一入口。

    实现逻辑：
    - 从 Cookie 中读取 session_token；
    - 调用数据库查询当前用户；
    - 要求 role=admin，否则拒绝访问。
    """
    return await require_admin_user(request)

def _parse_mail_list(v: str) -> List[str]:
    s = str(v or "").strip()
    if not s:
        return []
    out = []
    for it in s.replace(";", ",").split(","):
        e = it.strip()
        if e:
            out.append(e)
    return out

def _build_alert_mail(alert: Dict[str, Any]) -> EmailMessage:
    uuid = str(alert.get("uuid") or "")
    a_type = str(alert.get("type") or "")
    level = str(alert.get("level") or "")
    time_s = str(alert.get("time") or "")
    info = str(alert.get("info") or "")

    msg = EmailMessage()
    msg["Subject"] = f"{config.SMTP_SUBJECT_PREFIX} 严重告警 {uuid} {a_type}".strip()
    msg["From"] = config.SMTP_FROM
    to_list = _parse_mail_list(config.SMTP_TO)
    msg["To"] = ", ".join(to_list)
    msg.set_content(
        "\n".join([
            "InfraCount 严重告警提醒",
            "",
            f"设备UUID: {uuid}",
            f"类型: {a_type}",
            f"等级: {level}",
            f"时间: {time_s}",
            f"信息: {info}",
        ])
    )
    return msg

def _send_mail_sync(msg: EmailMessage) -> None:
    host = str(config.SMTP_HOST or "").strip()
    port = int(config.SMTP_PORT or 0)
    user = str(config.SMTP_USERNAME or "").strip()
    password = str(config.SMTP_PASSWORD or "")

    if not host or not port:
        raise RuntimeError("SMTP not configured")
    if not msg.get("From"):
        raise RuntimeError("SMTP_FROM not configured")
    if not msg.get("To"):
        raise RuntimeError("SMTP_TO not configured")

    if config.SMTP_USE_SSL:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host=host, port=port, context=ctx, timeout=15) as s:
            if user:
                s.login(user, password)
            s.send_message(msg)
        return

    with smtplib.SMTP(host=host, port=port, timeout=15) as s:
        s.ehlo()
        if config.SMTP_USE_TLS:
            ctx = ssl.create_default_context()
            s.starttls(context=ctx)
            s.ehlo()
        if user:
            s.login(user, password)
        s.send_message(msg)

async def _alert_email_loop():
    while True:
        try:
            if not config.ALERT_EMAIL_ENABLE:
                await asyncio.sleep(5)
                continue

            batch = await db.list_unnotified_critical_alerts(limit=config.ALERT_EMAIL_MAX_PER_SCAN)
            if not batch:
                await asyncio.sleep(max(5, int(config.ALERT_EMAIL_SCAN_INTERVAL_SEC)))
                continue

            for a in batch:
                aid = a.get("id")
                try:
                    msg = _build_alert_mail(a)
                    await asyncio.to_thread(_send_mail_sync, msg)
                    await db.mark_alert_notified(alert_id=int(aid), status=1, error=None)
                except Exception as e:
                    await db.mark_alert_notified(alert_id=int(aid), status=-1, error=str(e))
        except Exception:
            logging.exception("alert email loop failed")

        await asyncio.sleep(max(5, int(config.ALERT_EMAIL_SCAN_INTERVAL_SEC)))

async def _auto_sync_walkin_loop():
    while True:
        try:
            if config.AUTO_SYNC_WALKIN_BACKFILL_DAYS < 1:
                days = 1
            else:
                days = config.AUTO_SYNC_WALKIN_BACKFILL_DAYS

            today = datetime.now().date()
            for i in range(days):
                d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                await db.activity_sync_visitors(date=d)
        except Exception:
            logging.exception("auto sync walkin failed")
        await asyncio.sleep(max(5, int(config.AUTO_SYNC_WALKIN_INTERVAL_SEC)))

def _log_import_cleanup(now_ts: float, max_age_sec: int = 3600) -> None:
    expired = []
    for k, v in _LOG_IMPORT_CACHE.items():
        if now_ts - float(v.get("created_at_ts") or 0) > max_age_sec:
            expired.append(k)
    for k in expired:
        _LOG_IMPORT_CACHE.pop(k, None)

def _coerce_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None

def _normalize_time(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("T", " ").replace("/", "-")
    if re.fullmatch(r"\d{14}", s):
        try:
            dt = datetime.strptime(s, "%Y%m%d%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    if re.fullmatch(r"\d{12}", s):
        try:
            dt = datetime.strptime(s, "%Y%m%d%H%M")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})(?::(\d{2}))?", s)
    if m:
        date_part = m.group(1)
        hm = m.group(2)
        sec = m.group(3) or "00"
        return f"{date_part} {hm}:{sec}"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def _extract_uuid_from_text(s: str) -> Optional[str]:
    if not s:
        return None
    m = re.search(r"(?:uuid|device_uuid|device|sn)\s*[:=]\s*([A-Za-z0-9_-]{4,64})", s, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"<uuid>\s*([^<\s]+)\s*</uuid>", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b([A-Fa-f0-9]{8,32})\b", s)
    if m:
        return m.group(1)
    return None

def _extract_record_from_obj(obj: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None
    if any(isinstance(k, str) and k.lower() != k for k in obj.keys()):
        lowered: Dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str):
                lowered[k.strip().lower()] = v
            else:
                lowered[k] = v
        obj = lowered
    uuid_val = obj.get("uuid") or obj.get("device_uuid") or obj.get("device") or obj.get("sn") or obj.get("id")
    time_val = obj.get("time") or obj.get("record_time") or obj.get("ts") or obj.get("timestamp") or obj.get("datetime")
    in_val = obj.get("in_count") if "in_count" in obj else obj.get("in")
    out_val = obj.get("out_count") if "out_count" in obj else obj.get("out")
    battery_val = obj.get("battery") if "battery" in obj else obj.get("battery_level")
    btx_val = obj.get("btx") if "btx" in obj else obj.get("batterytx_level")
    signal_val = obj.get("signal_strength") if "signal_strength" in obj else obj.get("signal_status")
    warn_val = obj.get("warn_status")
    rec_type_val = obj.get("rec_type")

    uuid_s = str(uuid_val).strip() if uuid_val is not None else None
    t = _normalize_time(time_val)
    if not uuid_s or not t:
        return None

    rec: Dict[str, Any] = {
        "uuid": uuid_s,
        "time": t,
        "in_count": _coerce_int(in_val) or 0,
        "out_count": _coerce_int(out_val) or 0,
        "battery": _coerce_int(battery_val) or 0,
        "btx": _coerce_int(btx_val) or 0,
        "rec_type": _coerce_int(rec_type_val) or 2,
        "signal_strength": _coerce_int(signal_val) or 0,
        "warn_status": _coerce_int(warn_val) or 0,
        "activity_type": str(obj.get("activity_type") or ""),
    }
    return rec

def _extract_record_from_csv_row(row: List[str]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    cols = [str(c).strip() for c in row]
    if any("xml=<" in c for c in cols):
        return None

    def ok_uuid(v: str) -> bool:
        if not v:
            return False
        return re.fullmatch(r"[A-Za-z0-9_-]{4,64}", v) is not None

    def ok_time(v: str) -> bool:
        return _normalize_time(v) is not None

    schemas = [
        {"uuid": 0, "in": 1, "out": 2, "time": 3, "battery": 4, "signal": 5, "btx": 6, "warn": 7, "rec_type": 8},
        {"uuid": 0, "time": 1, "in": 2, "out": 3, "battery": 4, "btx": 5, "signal": 6, "warn": 7, "rec_type": 8},
        {"uuid": 0, "time": 1, "in": 2, "out": 3, "battery": 4, "signal": 5},
        {"uuid": 0, "in": 1, "out": 2, "time": 3},
        {"uuid": 0, "time": 1, "in": 2, "out": 3},
    ]

    for sch in schemas:
        if sch["uuid"] >= len(cols) or sch["time"] >= len(cols):
            continue
        u = cols[sch["uuid"]]
        t_raw = cols[sch["time"]]
        if not ok_uuid(u) or not ok_time(t_raw):
            continue
        t = _normalize_time(t_raw)
        if not t:
            continue

        in_count = _coerce_int(cols[sch["in"]]) if "in" in sch and sch["in"] < len(cols) else 0
        out_count = _coerce_int(cols[sch["out"]]) if "out" in sch and sch["out"] < len(cols) else 0
        battery = _coerce_int(cols[sch["battery"]]) if "battery" in sch and sch["battery"] < len(cols) else 0
        btx = _coerce_int(cols[sch["btx"]]) if "btx" in sch and sch["btx"] < len(cols) else 0
        signal = _coerce_int(cols[sch["signal"]]) if "signal" in sch and sch["signal"] < len(cols) else 0
        warn = _coerce_int(cols[sch["warn"]]) if "warn" in sch and sch["warn"] < len(cols) else 0
        rec_type = _coerce_int(cols[sch["rec_type"]]) if "rec_type" in sch and sch["rec_type"] < len(cols) else 2

        return {
            "uuid": u,
            "time": t,
            "in_count": in_count or 0,
            "out_count": out_count or 0,
            "battery": battery or 0,
            "btx": btx or 0,
            "rec_type": rec_type or 2,
            "signal_strength": signal or 0,
            "warn_status": warn or 0,
            "activity_type": "",
        }

    return None

def _extract_record_from_line(line: str) -> Optional[Dict[str, Any]]:
    s = (line or "").strip()
    if not s:
        return None
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            return _extract_record_from_obj(obj)
        except Exception:
            pass

    if "xml=<" in s:
        if "<UP_SENSOR_DATA_REQ" not in s and "<UP_SENSOR_DATA_RES" not in s:
            return None

        uuid_s = _extract_uuid_from_text(s)
        m_time = re.search(r"<time>\s*([0-9]{12,14})\s*</time>", s, re.IGNORECASE)
        t = _normalize_time(m_time.group(1)) if m_time else None
        if not uuid_s or not t:
            return None

        def tag_int(tag: str) -> Optional[int]:
            m = re.search(rf"<{tag}>\s*([^<]+)\s*</{tag}>", s, re.IGNORECASE)
            return _coerce_int(m.group(1)) if m else None

        in_count = tag_int("in") or tag_int("in_count") or 0
        out_count = tag_int("out") or tag_int("out_count") or 0
        battery = tag_int("battery") or tag_int("battery_level") or 0
        btx = tag_int("btx") or tag_int("batterytx_level") or 0
        signal = tag_int("signal_strength") or tag_int("signal_status") or 0
        warn = tag_int("warn_status") or 0
        rec_type = tag_int("rec_type") or 2

        return {
            "uuid": uuid_s,
            "time": t,
            "in_count": in_count,
            "out_count": out_count,
            "battery": battery,
            "btx": btx,
            "rec_type": rec_type,
            "signal_strength": signal,
            "warn_status": warn,
            "activity_type": "",
        }

    uuid_s = _extract_uuid_from_text(s)
    t = _normalize_time(s)
    if not uuid_s or not t:
        return None

    def pick_int(patterns: List[str]) -> Optional[int]:
        for p in patterns:
            m = re.search(p, s, re.IGNORECASE)
            if m:
                return _coerce_int(m.group(1))
        return None

    in_count = pick_int([r"\bin(?:_count)?\s*[:=]\s*([0-9]+)"])
    out_count = pick_int([r"\bout(?:_count)?\s*[:=]\s*([0-9]+)"])
    battery = pick_int([r"\bbattery(?:_level)?\s*[:=]\s*([0-9]+)", r"\bbat\s*[:=]\s*([0-9]+)"])
    btx = pick_int([r"\bbtx\s*[:=]\s*([0-9]+)", r"\btx(?:_battery)?\s*[:=]\s*([0-9]+)"])
    signal = pick_int([r"\bsignal(?:_strength|_status)?\s*[:=]\s*([0-9]+)"])
    warn = pick_int([r"\bwarn(?:_status)?\s*[:=]\s*([0-9]+)"])
    rec_type = pick_int([r"\brec(?:_type)?\s*[:=]\s*([0-9]+)"])

    return {
        "uuid": uuid_s,
        "time": t,
        "in_count": in_count or 0,
        "out_count": out_count or 0,
        "battery": battery or 0,
        "btx": btx or 0,
        "rec_type": rec_type or 2,
        "signal_strength": signal or 0,
        "warn_status": warn or 0,
        "activity_type": "",
    }

def _parse_device_log_text(text: str) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    unparsed = 0
    detected_format = "text"

    s = (text or "").strip()
    if s:
        if s[0] in "[{":
            try:
                obj = json.loads(s)
                detected_format = "json"
                if isinstance(obj, list):
                    for item in obj:
                        rec = _extract_record_from_obj(item)
                        if rec:
                            records.append(rec)
                        else:
                            unparsed += 1
                elif isinstance(obj, dict):
                    data = obj.get("data") if "data" in obj else obj.get("items")
                    if isinstance(data, list):
                        for item in data:
                            rec = _extract_record_from_obj(item)
                            if rec:
                                records.append(rec)
                            else:
                                unparsed += 1
                    else:
                        rec = _extract_record_from_obj(obj)
                        if rec:
                            records.append(rec)
                        else:
                            unparsed += 1
                return {"records": records, "unparsed": unparsed, "detected_format": detected_format}
            except Exception:
                pass

    lines = text.splitlines()
    if lines:
        head = "\n".join(lines[:80])
        if "xml=<UP_SENSOR_DATA_" in head:
            detected_format = "log"
            for line in lines:
                rec = _extract_record_from_line(line)
                if rec:
                    records.append(rec)
                else:
                    if line.strip():
                        unparsed += 1
            return {"records": records, "unparsed": unparsed, "detected_format": detected_format}

        ndjson_like = 0
        ndjson_try = 0
        for ln in lines[:200]:
            t = ln.strip()
            if not t:
                continue
            ndjson_try += 1
            if t.startswith("{") and t.endswith("}"):
                ndjson_like += 1
        if ndjson_try >= 3 and ndjson_like / max(1, ndjson_try) >= 0.8:
            detected_format = "jsonl"
            for ln in lines:
                t = ln.strip()
                if not t:
                    continue
                try:
                    obj = json.loads(t)
                    rec = _extract_record_from_obj(obj)
                    if rec:
                        records.append(rec)
                    else:
                        unparsed += 1
                except Exception:
                    unparsed += 1
            return {"records": records, "unparsed": unparsed, "detected_format": detected_format}

        try:
            sample = "\n".join(lines[:20])
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            reader = csv.DictReader(lines, dialect=dialect)
            if reader.fieldnames:
                names = []
                for fn in reader.fieldnames:
                    if not fn:
                        continue
                    n = re.sub(r"\s+", "", str(fn)).lower()
                    names.append(n)

                expected = {
                    "uuid", "device_uuid",
                    "time", "timestamp", "record_time",
                    "in", "in_count",
                    "out", "out_count",
                    "battery", "battery_level",
                    "btx", "batterytx_level",
                    "signal_strength", "signal_status",
                    "warn_status",
                    "rec_type"
                }
                hits = set([n for n in names if n in expected])
                looks_like_csv = (("uuid" in hits or "device_uuid" in hits) and ("time" in hits or "timestamp" in hits or "record_time" in hits))
            else:
                looks_like_csv = False

            if looks_like_csv:
                detected_format = "csv"
                parsed_any = False
                for row in reader:
                    rec = _extract_record_from_obj(row)
                    if rec:
                        records.append(rec)
                        parsed_any = True
                    else:
                        unparsed += 1
                if parsed_any:
                    return {"records": records, "unparsed": unparsed, "detected_format": detected_format}
                records = []
                unparsed = 0
                detected_format = "text"
        except Exception:
            pass

        try:
            sample = "\n".join(lines[:20])
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            csv_reader = csv.reader(lines, dialect=dialect)
            parsed_any = False
            for row in csv_reader:
                rec = _extract_record_from_csv_row(row)
                if rec:
                    records.append(rec)
                    parsed_any = True
                else:
                    if any(str(c).strip() for c in row):
                        unparsed += 1
            if parsed_any:
                detected_format = "csv"
                return {"records": records, "unparsed": unparsed, "detected_format": detected_format}
            records = []
            unparsed = 0
        except Exception:
            pass

    for line in lines:
        rec = _extract_record_from_line(line)
        if rec:
            records.append(rec)
        else:
            if line.strip():
                unparsed += 1

    return {"records": records, "unparsed": unparsed, "detected_format": detected_format}

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(api_auth_middleware)

def _task_status(task: Optional[asyncio.Task]) -> Dict[str, Any]:
    if task is None:
        return {"exists": False, "running": False}
    return {
        "exists": True,
        "running": not task.done(),
        "cancelled": task.cancelled(),
        "done": task.done(),
    }

def _uptime_sec() -> int:
    return max(0, int(time.time() - _APP_START_TS))

@app.get("/api/v1/health")
async def health():
    db_status = await db.ping()
    is_healthy = bool(db_status.get("ok"))
    payload = {
        "status": "ok" if is_healthy else "degraded",
        "time": datetime.now(timezone.utc).isoformat(),
        "uptime_sec": _uptime_sec(),
        "db": {
            "driver": config.DB_DRIVER,
            **db_status,
        },
    }
    return JSONResponse(content=payload, status_code=200 if is_healthy else 503)

@app.get("/api/v1/system/status")
async def system_status(request: Request):
    await require_admin_user(request)

    db_info: Dict[str, Any] = {"driver": config.DB_DRIVER}
    if db.use_sqlite():
        db_info["sqlite_path"] = config.DB_SQLITE_PATH
    else:
        db_info.update({
            "host": config.DB_HOST,
            "port": config.DB_PORT,
            "database": config.DB_NAME,
            "user": config.DB_USER,
        })

    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "uptime_sec": _uptime_sec(),
        "app": {"title": app.title, "version": app.version},
        "process": {
            "pid": os.getpid(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "db": {
            **db_info,
            **(await db.ping()),
        },
        "features": {
            "csrf_enable": bool(config.CSRF_ENABLE),
            "auto_sync_walkin_enable": bool(config.AUTO_SYNC_WALKIN_ENABLE),
            "auto_sync_walkin_interval_sec": int(config.AUTO_SYNC_WALKIN_INTERVAL_SEC),
            "alert_email_enable": bool(config.ALERT_EMAIL_ENABLE),
            "alert_email_scan_interval_sec": int(config.ALERT_EMAIL_SCAN_INTERVAL_SEC),
            "time_sync_digits": bool(config.TIME_SYNC_DIGITS),
        },
        "tasks": {
            "auto_sync_walkin": _task_status(_AUTO_SYNC_TASK),
            "alert_email": _task_status(_ALERT_EMAIL_TASK),
        },
    }

@app.on_event("startup")
async def startup_event():
    if db.use_sqlite():
        await db.init_sqlite()
    else:
        await db.init_pool()
    global _AUTO_SYNC_TASK
    if config.AUTO_SYNC_WALKIN_ENABLE and _AUTO_SYNC_TASK is None:
        _AUTO_SYNC_TASK = asyncio.create_task(_auto_sync_walkin_loop())
    global _ALERT_EMAIL_TASK
    if config.ALERT_EMAIL_ENABLE and _ALERT_EMAIL_TASK is None:
        _ALERT_EMAIL_TASK = asyncio.create_task(_alert_email_loop())

@app.on_event("shutdown")
async def shutdown_event():
    global _AUTO_SYNC_TASK
    if _AUTO_SYNC_TASK is not None:
        _AUTO_SYNC_TASK.cancel()
        try:
            await _AUTO_SYNC_TASK
        except BaseException:
            pass
        _AUTO_SYNC_TASK = None
    global _ALERT_EMAIL_TASK
    if _ALERT_EMAIL_TASK is not None:
        _ALERT_EMAIL_TASK.cancel()
        try:
            await _ALERT_EMAIL_TASK
        except BaseException:
            pass
        _ALERT_EMAIL_TASK = None
    await db.close_pool()

app.include_router(auth_router.router)
app.include_router(users_router.router)


# --- Pages ---

_LEGACY_ROOT_DIR = os.path.abspath("legacy_backup")
_LEGACY_TEMPLATES_DIR = os.path.join(_LEGACY_ROOT_DIR, "templates")
_LEGACY_STATIC_DIR = os.path.join(_LEGACY_ROOT_DIR, "static")

app.mount("/legacy/static", StaticFiles(directory=_LEGACY_STATIC_DIR), name="legacy_static")

def _legacy_page_file(full_path: str) -> str | None:
    """
    将 /legacy/* 映射到旧版 templates/ 页面文件。

    设计目标：
    - 旧版页面用于“回退兜底”，因此必须保持可访问；
    - 新版默认入口指向 /spa（Vue3 单页应用）；
    - 旧版页面不做自动探测与目录遍历，避免任意文件读取风险，仅允许白名单路径。
    """
    p = str(full_path or "").strip().lstrip("/")
    if p in {"", "dashboard"}:
        return os.path.join(_LEGACY_TEMPLATES_DIR, "dashboard.html")
    if p == "login":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "login.html")
    if p == "account":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "account.html")
    if p == "devices":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "devices.html")
    if p == "history":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "history.html")
    if p == "history/academy":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "history_academy.html")
    if p == "history/device":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "history.html")
    if p == "activity":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "activity.html")
    if p == "alerts":
        return os.path.join(_LEGACY_TEMPLATES_DIR, "alerts.html")
    if p == "activity-dashboard":
        return os.path.join(_LEGACY_ROOT_DIR, "activity_dashboard.html")
    return None

@app.get("/legacy", include_in_schema=False)
async def legacy_root():
    f = _legacy_page_file("")
    return FileResponse(f)  # type: ignore[arg-type]

@app.get("/legacy/{full_path:path}", include_in_schema=False)
async def legacy_any(full_path: str):
    f = _legacy_page_file(full_path)
    if not f:
        raise HTTPException(404, "Legacy page not found")
    return FileResponse(f)

@app.get("/login", include_in_schema=False)
async def login_page():
    """
    新入口：统一把登录入口指向 SPA。

    兼容性说明：
    - 旧版登录页仍可通过 /legacy/login 访问；
    - 这里保留 /login 作为“习惯入口”，但不再渲染 templates/login.html。
    """
    return RedirectResponse(url="/spa/login", status_code=302)

@app.get("/account", include_in_schema=False)
async def account_page():
    return RedirectResponse(url="/spa/account", status_code=302)

# --- Static & Pages ---

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- SPA（Vue3 单页应用）托管 ---
#
# 设计目标：
# - 前端构建产物输出到 static/spa（由 web/vite.config.ts 控制 outDir）；
# - 后端在 /spa 下托管该单页应用：
#   - 直接访问 /spa 或 /spa/ 会返回 index.html；
#   - 访问 /spa/assets/... 会返回静态资源文件；
#   - 访问 /spa/dashboard 之类的前端路由，也会回落到 index.html（避免刷新 404）。
#
# 为什么不直接使用 StaticFiles(html=True)：
# - Starlette 的 StaticFiles(html=True) 仅对“目录”请求回退 index.html，
#   对 SPA 的“任意路径刷新”并不等价；
# - 因此这里用一个显式的 catch-all 路由：若请求不是实际存在的文件，则返回 index.html。

_SPA_ROOT_DIR = os.path.abspath(os.path.join("static", "spa"))
_SPA_INDEX_FILE = os.path.join(_SPA_ROOT_DIR, "index.html")

def _is_safe_spa_path(target_path: str) -> bool:
    # 防止路径穿越：确保最终路径仍然位于 static/spa 目录内
    abs_target = os.path.abspath(target_path)
    return abs_target.startswith(_SPA_ROOT_DIR + os.sep) or abs_target == _SPA_ROOT_DIR

@app.get("/spa", include_in_schema=False)
async def spa_root():
    if not os.path.isfile(_SPA_INDEX_FILE):
        raise HTTPException(404, "SPA 未构建：请先在 web/ 目录执行 npm install && npm run build")
    return FileResponse(_SPA_INDEX_FILE, media_type="text/html")

@app.get("/spa/{full_path:path}", include_in_schema=False)
async def spa_any(full_path: str):
    if not os.path.isfile(_SPA_INDEX_FILE):
        raise HTTPException(404, "SPA 未构建：请先在 web/ 目录执行 npm install && npm run build")

    # full_path 可能为空（例如访问 /spa/），此时直接回落 index.html
    if full_path:
        candidate = os.path.join(_SPA_ROOT_DIR, full_path)
        if _is_safe_spa_path(candidate) and os.path.isfile(candidate):
            return FileResponse(candidate)

    return FileResponse(_SPA_INDEX_FILE, media_type="text/html")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.svg", media_type="image/svg+xml")

@app.get("/")
async def index():
    """
    默认入口指向 SPA。

    说明：
    - 新版前端在 /spa 下托管（见下方 SPA catch-all）；
    - 旧版 templates 页面保留在 /legacy/*，便于紧急回退与对照验证。
    """
    return RedirectResponse(url="/spa/", status_code=302)

@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return RedirectResponse(url="/spa/dashboard", status_code=302)

@app.get("/activity-dashboard")
async def activity_dashboard():
    return RedirectResponse(url="/legacy/activity-dashboard", status_code=302)

@app.get("/activity", include_in_schema=False)
async def activity():
    return RedirectResponse(url="/spa/activity", status_code=302)

@app.get("/history", include_in_schema=False)
async def history():
    return RedirectResponse(url="/spa/history", status_code=302)

@app.get("/history/academy", include_in_schema=False)
async def history_academy():
    return RedirectResponse(url="/legacy/history/academy", status_code=302)

@app.get("/history/device", include_in_schema=False)
async def history_device():
    return RedirectResponse(url="/legacy/history/device", status_code=302)

@app.get("/devices", include_in_schema=False)
async def devices():
    return RedirectResponse(url="/spa/devices", status_code=302)

@app.get("/alerts", include_in_schema=False)
async def alerts():
    return RedirectResponse(url="/spa/alerts", status_code=302)

# --- Records ---

@app.get("/api/v1/records/latest")
async def get_records_latest(uuid: Optional[str] = None):
    """
    获取最新记录：
    - uuid 为空：返回“每台设备最新一条”列表；
    - uuid 非空：返回指定设备最新一条（列表长度为 0 或 1）。
    """
    return await db.fetch_latest(uuid)

@app.get("/api/v1/records/history")
async def get_records_history(
    uuid: Optional[str] = None, 
    limit: int = 100, 
    start: Optional[str] = None, 
    end: Optional[str] = None,
    order: Optional[str] = None,
    sort_by: Optional[str] = None
):
    if uuid == "undefined":
        return []
    return await db.fetch_history(uuid=uuid, start=start, end=end, limit=limit, order=order or "desc", sort_by=sort_by or "time")

# --- Activity API ---

@app.get("/api/v1/activity/options")
async def activity_options():
    return await db.activity_get_options()

@app.get("/api/v1/activity/events")
async def activity_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    locations: Optional[str] = None,
    types: Optional[str] = None,
    academies: Optional[str] = None,
    weekdays: Optional[str] = None,
    start_times: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    loc_list = locations.split(",") if locations else None
    type_list = types.split(",") if types else None
    aca_list = academies.split(",") if academies else None
    wd_list = weekdays.split(",") if weekdays else None
    time_list = start_times.split(",") if start_times else None
    
    return await db.activity_list(
        start_date=start_date,
        end_date=end_date,
        locations=loc_list,
        types=type_list,
        academies=aca_list,
        weekdays=wd_list,
        start_times=time_list,
        page=page,
        page_size=page_size
    )

@app.get("/api/v1/activity/aggregations")
async def activity_aggregations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    locations: Optional[str] = None,
    types: Optional[str] = None,
    academies: Optional[str] = None,
    weekdays: Optional[str] = None,
    start_times: Optional[str] = None
):
    loc_list = locations.split(",") if locations else None
    type_list = types.split(",") if types else None
    aca_list = academies.split(",") if academies else None
    wd_list = weekdays.split(",") if weekdays else None
    time_list = start_times.split(",") if start_times else None
    
    return await db.activity_stats(
        start_date=start_date,
        end_date=end_date,
        locations=loc_list,
        types=type_list,
        academies=aca_list,
        weekdays=wd_list,
        start_times=time_list
    )

@app.post("/api/v1/activity/upload")
async def activity_upload(file: UploadFile = File(...)):
    # Simple CSV parser
    content = await file.read()
    text = content.decode("utf-8-sig")
    lines = text.splitlines()
    
    if not lines:
        return {"imported": 0}

    # Load Standard Locations for AI Matching
    # Source 1: Location-Academy Mapping (High confidence standards)
    mapping = await db.get_location_academy_mapping()
    standards = list(mapping.keys())
    
    # Source 2: Existing Locations in DB (if we want to converge to existing ones)
    # But usually mapping keys are the 'configured' ones.
    # If mapping is empty, we might want to fetch distinct locations from activity_events too?
    # For now, let's rely on mapping. If mapping is empty, no correction happens.
    matcher.set_standards(standards)
        
    # Headers: 日期,起始时间,结束时间,书院,具体地点,活动名称,活动类型,受众学生数
    # Map to: date, start_time, end_time, academy, location, activity_name, activity_type, audience_count
    
    events = []
    # Skip header if present
    start_idx = 0
    if "日期" in lines[0]:
        start_idx = 1
        
    import datetime
    
    for line in lines[start_idx:]:
        parts = line.split(",")
        if len(parts) < 8: continue
        
        try:
            d_str = parts[0].strip()
            s_time = parts[1].strip()
            e_time = parts[2].strip()
            
            # Calc weekday (Chinese)
            dt = datetime.datetime.strptime(d_str, "%Y-%m-%d")
            wd_map = {1:"周一", 2:"周二", 3:"周三", 4:"周四", 5:"周五", 6:"周六", 7:"周日"}
            weekday = wd_map.get(dt.isoweekday(), "")
            
            # Calc duration
            t1 = datetime.datetime.strptime(f"{d_str} {s_time}", "%Y-%m-%d %H:%M")
            t2 = datetime.datetime.strptime(f"{d_str} {e_time}", "%Y-%m-%d %H:%M")
            duration = int((t2 - t1).total_seconds() / 60)
            
            # AI Match Location
            raw_loc = parts[4].strip()
            best_loc, score = matcher.match(raw_loc)
            # If score is high, use best_loc. Otherwise raw_loc (normalized).
            final_loc = best_loc if score >= 90 else matcher.normalize(raw_loc)

            events.append({
                "date": d_str,
                "weekday": weekday,
                "start_time": s_time,
                "end_time": e_time,
                "duration_minutes": duration,
                "academy": parts[3].strip(),
                "location": final_loc,
                "activity_name": parts[5].strip(),
                "activity_type": parts[6].strip(),
                "audience_count": int(parts[7].strip() or 0),
                "notes": ""
            })
        except:
            continue
            
    count = await db.activity_bulk_insert(events)
    return {"imported": count}

@app.post("/api/v1/activity/walkin/preview")
async def walkin_preview(payload: Dict[str, Any] = Body(...)):
    devices = payload.get("devices", [])
    start = payload.get("start")
    end = payload.get("end")
    items = await db.walkin_preview(devices, start, end)
    return {"items": items}

@app.get("/api/v1/activity/walkin/dates")
async def walkin_dates(
    uuid: Optional[str] = None,
    devices: Optional[str] = None
):
    devs = []
    if uuid:
        devs = [uuid]
    elif devices:
        devs = [d.strip() for d in str(devices).split(",") if d.strip()]
    return await db.walkin_available_dates(devs)

@app.post("/api/v1/activity/walkin/preview-dates")
async def walkin_preview_dates(payload: Dict[str, Any] = Body(...)):
    devices = payload.get("devices", [])
    dates = payload.get("dates", [])
    items = await db.walkin_preview_by_dates(devices, dates)
    return {"items": items}

@app.post("/api/v1/activity/walkin/sync")
async def walkin_sync(payload: Dict[str, Any] = Body(...)):
    items = payload.get("items", [])
    mode = payload.get("mode", "skip")
    result = await db.activity_bulk_insert(items, mode=mode)
    if isinstance(result, dict):
        inserted = int(result.get("inserted") or 0)
        updated = int(result.get("updated") or 0)
        return {**result, "count": inserted}
    return {"count": int(result or 0), "inserted": int(result or 0), "updated": 0, "duplicates": []}

# --- Stats ---

@app.get("/api/v1/stats/summary")
async def get_stats_summary(uuid: Optional[str] = None):
    return await db.stats_summary(uuid)

@app.get("/api/v1/stats/daily")
async def get_stats_daily(
    uuid: Optional[str] = None, 
    start: Optional[str] = None, 
    end: Optional[str] = None
):
    return await db.stats_daily(uuid, start, end)

@app.get("/api/v1/stats/hourly")
async def get_stats_hourly(
    uuid: Optional[str] = None, 
    date: Optional[str] = None
):
    if date:
        d = str(date).split(" ")[0].strip()
        if d:
            return await db.stats_hourly(uuid, f"{d} 00:00:00", f"{d} 23:59:59")
    return await db.stats_hourly(uuid, None, None)

# --- Devices ---

@app.get("/api/v1/devices")
async def list_devices():
    return await db.list_devices()

@app.get("/api/v1/devices/mapping")
async def get_device_mapping():
    return await db.get_device_mapping()

@app.get("/api/v1/device/mapping")
async def get_device_mapping_singular():
    return await db.get_device_mapping()

# --- Alerts ---

@app.get("/api/v1/alerts")
async def list_alerts(uuid: Optional[str] = None, limit: int = 100):
    return await db.list_alerts(uuid, limit)

@app.post("/api/v1/alerts/{alert_id}/ack")
async def ack_alert(alert_id: int):
    await db.set_alert_status(alert_id=alert_id, status=1)
    return {"ok": True}

# --- Admin Records ---

@app.get("/api/v1/admin/records")
async def admin_list_records(
    page: int = 1, 
    size: int = 50, 
    uuid: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    warn: Optional[int] = None,
    rec_type: Optional[int] = None,
    btx_min: Optional[int] = None,
    btx_max: Optional[int] = None,
    order: Optional[str] = None,
    sort_by: Optional[str] = None
):
    items = await db.admin_list_records(
        page=page,
        limit=size,
        uuid=uuid,
        start=start,
        end=end,
        warn=warn,
        rec_type=rec_type,
        btx_min=btx_min,
        btx_max=btx_max,
        order=order or "desc",
        sort_by=sort_by or "time",
    )
    total = await db.admin_count_records(uuid, start, end, warn, rec_type, btx_min, btx_max)
    return {"items": items, "total": total}

@app.post("/api/v1/admin/records")
async def admin_create_record(data: Dict[str, Any] = Body(...)):
    await db.admin_create_record(data)
    return {"status": "ok"}

@app.put("/api/v1/admin/records/{id}")
async def admin_update_record(id: int, data: Dict[str, Any] = Body(...)):
    await db.admin_update_record(id, data)
    return {"status": "ok"}

@app.delete("/api/v1/admin/records/{id}")
async def admin_delete_record(id: int):
    await db.admin_delete_record(id)
    return {"status": "ok"}

@app.post("/api/v1/admin/records/batch-save")
async def admin_batch_save_records(payload: Dict[str, Any] = Body(...)):
    creates = payload.get("creates", [])
    updates = payload.get("updates", [])
    await db.admin_batch_save_records(creates, updates)
    return {"status": "ok"}

@app.post("/api/v1/admin/records/batch-update")
async def admin_batch_update(payload: Dict[str, Any] = Body(...)):
    ids = payload.get("ids", [])
    updates = payload.get("updates", {})
    await db.admin_batch_update(ids, updates)
    return {"status": "ok"}

@app.delete("/api/v1/admin/records/range")
async def admin_delete_range(start: str, end: str):
    await db.admin_delete_range(start, end)
    return {"status": "ok"}

@app.get("/api/v1/admin/records/ids")
async def admin_get_record_ids(
    uuid: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    ids = await db.admin_get_record_ids(uuid, start, end)
    return {"ids": ids}

@app.post("/api/v1/admin/records/batch-delete")
async def admin_batch_delete(payload: Dict[str, Any] = Body(...)):
    ids = payload.get("ids", [])
    await db.admin_batch_delete(ids)
    return {"status": "ok"}

@app.post("/api/v1/admin/device-log/preview")
async def admin_device_log_preview(file: UploadFile = File(...)):
    contents = await file.read()
    text = contents.decode("utf-8-sig", errors="ignore")

    parsed = _parse_device_log_text(text)
    records: List[Dict[str, Any]] = parsed.get("records") or []
    detected_format = str(parsed.get("detected_format") or "")
    filename = file.filename or ""
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    if detected_format == "text":
        if ext in {"txt", "log"}:
            detected_format = ext
    if detected_format == "log":
        detected_format = "log"

    now_ts = datetime.now(timezone.utc).timestamp()
    _log_import_cleanup(now_ts)
    import_id = uuidlib.uuid4().hex

    per_device: Dict[str, Dict[str, Any]] = {}
    for r in records:
        u = r.get("uuid")
        t = r.get("time")
        if not u or not t:
            continue
        if u not in per_device:
            per_device[u] = {"uuid": u, "count": 0, "start": t, "end": t}
        per_device[u]["count"] += 1
        if t < per_device[u]["start"]:
            per_device[u]["start"] = t
        if t > per_device[u]["end"]:
            per_device[u]["end"] = t

    mapping_res = await db.get_device_mapping()
    mapping = (mapping_res or {}).get("mapping") or {}

    devices = []
    for u in sorted(per_device.keys()):
        entry = per_device[u]
        m = mapping.get(u) or {}
        devices.append({
            "uuid": u,
            "name": m.get("name") or "",
            "category": m.get("category") or "",
            "count": entry["count"],
            "start": entry["start"],
            "end": entry["end"],
        })

    _LOG_IMPORT_CACHE[import_id] = {
        "created_at_ts": now_ts,
        "records": records,
        "total": len(records),
        "filename": file.filename,
    }

    return {
        "import_id": import_id,
        "filename": file.filename,
        "detected_format": detected_format,
        "total_records": len(records),
        "devices": devices,
        "sample": records[:30],
    }

@app.post("/api/v1/admin/device-log/import")
async def admin_device_log_import(payload: Dict[str, Any] = Body(...)):
    import_id = str(payload.get("import_id") or "").strip()
    if not import_id or import_id not in _LOG_IMPORT_CACHE:
        raise HTTPException(404, "Import session not found")

    offset = int(payload.get("offset") or 0)
    limit = int(payload.get("limit") or 500)
    if limit <= 0:
        limit = 500
    if offset < 0:
        offset = 0

    now_ts = datetime.now(timezone.utc).timestamp()
    _log_import_cleanup(now_ts)

    ctx = _LOG_IMPORT_CACHE.get(import_id)
    if not ctx:
        raise HTTPException(404, "Import session not found")

    records: List[Dict[str, Any]] = ctx.get("records") or []
    total = int(ctx.get("total") or len(records))

    chunk = records[offset: offset + limit]
    if not chunk:
        _LOG_IMPORT_CACHE.pop(import_id, None)
        return {"imported": 0, "offset": offset, "next_offset": offset, "total": total, "done": True}

    by_uuid: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in chunk:
        u = r.get("uuid")
        t = r.get("time")
        if u and t:
            by_uuid[u].append(r)

    creates: List[Dict[str, Any]] = []
    updates: List[Dict[str, Any]] = []

    for u, items in by_uuid.items():
        times = [it.get("time") for it in items if it.get("time")]
        id_map = await db.admin_get_record_id_map_by_times(u, times)
        for it in items:
            t = it.get("time")
            existing_id = id_map.get(t)
            if existing_id:
                updates.append({
                    "id": existing_id,
                    "in_count": it.get("in_count"),
                    "out_count": it.get("out_count"),
                    "battery": it.get("battery"),
                    "btx": it.get("btx"),
                    "rec_type": it.get("rec_type"),
                    "signal_strength": it.get("signal_strength"),
                    "warn_status": it.get("warn_status"),
                    "activity_type": it.get("activity_type") or ""
                })
            else:
                creates.append(it)

    ok = await db.admin_batch_save_records(creates, updates)
    if ok is False:
        raise HTTPException(500, "Batch save failed")

    next_offset = offset + len(chunk)
    done = next_offset >= total
    if done:
        _LOG_IMPORT_CACHE.pop(import_id, None)

    return {
        "imported": len(chunk),
        "offset": offset,
        "next_offset": next_offset,
        "total": total,
        "done": done
    }

# --- Admin: SQLite 数据库合并导入 ---

class DbMergePreviewPayload(BaseModel):
    import_id: str
    merge_mode: str = "skip_existing"  # skip_existing | update_existing
    conflict_preference: str = "prefer_import"  # prefer_current_non_empty | prefer_import

class DbMergeExecutePayload(BaseModel):
    import_id: str
    merge_mode: str = "skip_existing"  # skip_existing | update_existing
    conflict_preference: str = "prefer_import"  # prefer_current_non_empty | prefer_import

async def _db_merge_validate_strategy(merge_mode: str, conflict_preference: str) -> Dict[str, str]:
    mm = str(merge_mode or "").strip()
    cp = str(conflict_preference or "").strip()
    if mm not in {"skip_existing", "update_existing"}:
        raise HTTPException(400, "Invalid merge_mode")
    if cp not in {"prefer_current_non_empty", "prefer_import"}:
        raise HTTPException(400, "Invalid conflict_preference")
    return {"merge_mode": mm, "conflict_preference": cp}

@app.post("/api/v1/admin/db-merge/upload")
async def admin_db_merge_upload(request: Request, file: UploadFile = File(...)):
    """
    上传 SQLite .db 文件（仅管理员）。

    返回 import_id，前端需携带 import_id 调用预览/执行接口。
    """
    user = await _require_admin_user(request)
    now_ts = datetime.now(timezone.utc).timestamp()
    _db_merge_cleanup(now_ts)

    filename = str(file.filename or "").strip()
    if not filename:
        raise HTTPException(400, "Missing filename")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"db", "sqlite", "sqlite3"}:
        raise HTTPException(400, "Invalid file type")

    os.makedirs(_DB_MERGE_UPLOAD_DIR, exist_ok=True)
    import_id = uuidlib.uuid4().hex
    target_path = os.path.join(_DB_MERGE_UPLOAD_DIR, f"{import_id}.db")

    size_bytes = 0
    try:
        with open(target_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                size_bytes += len(chunk)
    except Exception:
        try:
            if os.path.isfile(target_path):
                os.remove(target_path)
        except Exception:
            pass
        raise HTTPException(500, "Save file failed")

    # 快速校验：确保它是一个能打开的 SQLite 文件
    try:
        async with aiosqlite.connect(target_path) as conn:
            async with conn.execute("SELECT name FROM sqlite_master LIMIT 1") as cur:
                await cur.fetchone()
    except Exception:
        try:
            if os.path.isfile(target_path):
                os.remove(target_path)
        except Exception:
            pass
        raise HTTPException(400, "Invalid sqlite database")

    _DB_MERGE_UPLOAD_CACHE[import_id] = {
        "created_at_ts": now_ts,
        "path": os.path.abspath(target_path),
        "filename": filename,
        "size_bytes": int(size_bytes),
        "actor": str(user.get("username") or ""),
    }

    return {
        "import_id": import_id,
        "filename": filename,
        "size_bytes": int(size_bytes),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

@app.post("/api/v1/admin/db-merge/preview")
async def admin_db_merge_preview(request: Request, payload: DbMergePreviewPayload):
    """
    预览合并影响范围（仅管理员）。
    """
    await _require_admin_user(request)
    now_ts = datetime.now(timezone.utc).timestamp()
    _db_merge_cleanup(now_ts)

    import_id = str(payload.import_id or "").strip()
    ctx = _DB_MERGE_UPLOAD_CACHE.get(import_id)
    if not ctx:
        raise HTTPException(404, "Import file not found")

    strat = await _db_merge_validate_strategy(payload.merge_mode, payload.conflict_preference)
    res = await db.sqlite_db_merge_preview(
        import_db_path=str(ctx.get("path") or ""),
        merge_mode=strat["merge_mode"],  # type: ignore[arg-type]
        conflict_preference=strat["conflict_preference"],  # type: ignore[arg-type]
    )
    return {
        "import_id": import_id,
        "filename": ctx.get("filename"),
        "size_bytes": ctx.get("size_bytes"),
        **res,
    }

async def _run_db_merge_job(job_id: str, import_id: str, actor: str, merge_mode: str, conflict_preference: str) -> None:
    ctx = _DB_MERGE_UPLOAD_CACHE.get(import_id) or {}
    import_path = str(ctx.get("path") or "").strip()
    job = _DB_MERGE_JOB_CACHE.get(job_id) or {}

    def update_progress(p: Dict[str, Any]) -> None:
        job["progress"] = {**(job.get("progress") or {}), **(p or {})}

    try:
        job["running"] = True
        job["status"] = "running"
        job["progress"] = {"status": "running", "stage": "init"}
        result = await db.sqlite_db_merge_execute(
            import_db_path=import_path,
            actor=actor,
            merge_mode=merge_mode,  # type: ignore[arg-type]
            conflict_preference=conflict_preference,  # type: ignore[arg-type]
            progress_cb=update_progress,
        )
        job["running"] = False
        job["status"] = "done"
        job["result"] = result
    except Exception as e:
        job["running"] = False
        job["status"] = "error"
        job["error"] = str(e)
        job["progress"] = {**(job.get("progress") or {}), "status": "error", "error": str(e)}

@app.post("/api/v1/admin/db-merge/execute")
async def admin_db_merge_execute(request: Request, payload: DbMergeExecutePayload):
    """
    启动合并导入任务（仅管理员）。

    说明：
    - 该接口会立即返回 job_id；
    - 前端通过 /api/v1/admin/db-merge/status 轮询进度与最终结果。
    """
    user = await _require_admin_user(request)
    now_ts = datetime.now(timezone.utc).timestamp()
    _db_merge_cleanup(now_ts)

    import_id = str(payload.import_id or "").strip()
    ctx = _DB_MERGE_UPLOAD_CACHE.get(import_id)
    if not ctx:
        raise HTTPException(404, "Import file not found")

    strat = await _db_merge_validate_strategy(payload.merge_mode, payload.conflict_preference)
    job_id = uuidlib.uuid4().hex

    job: Dict[str, Any] = {
        "job_id": job_id,
        "import_id": import_id,
        "filename": ctx.get("filename"),
        "size_bytes": ctx.get("size_bytes"),
        "strategy": strat,
        "created_at_ts": now_ts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor": str(user.get("username") or ""),
        "running": True,
        "status": "running",
        "progress": {"status": "running", "stage": "queued"},
    }
    _DB_MERGE_JOB_CACHE[job_id] = job

    task = asyncio.create_task(
        _run_db_merge_job(
            job_id=job_id,
            import_id=import_id,
            actor=str(user.get("username") or ""),
            merge_mode=strat["merge_mode"],
            conflict_preference=strat["conflict_preference"],
        )
    )
    job["task"] = task

    return {"job_id": job_id}

@app.get("/api/v1/admin/db-merge/status")
async def admin_db_merge_status(request: Request, job_id: str = Query(...)):
    """
    查询合并导入任务状态（仅管理员）。
    """
    await _require_admin_user(request)
    now_ts = datetime.now(timezone.utc).timestamp()
    _db_merge_cleanup(now_ts)

    jid = str(job_id or "").strip()
    job = _DB_MERGE_JOB_CACHE.get(jid)
    if not job:
        raise HTTPException(404, "Job not found")

    # task 对象不可序列化：对外隐藏
    public_job = {k: v for k, v in job.items() if k != "task"}
    public_job["running"] = bool(public_job.get("running"))
    public_job["status"] = str(public_job.get("status") or "")
    return {"job": public_job}

# --- Admin Registry ---

@app.get("/api/v1/admin/registry")
async def admin_list_registry():
    return await db.admin_list_registry()

@app.post("/api/v1/admin/registry")
async def admin_upsert_registry(data: Dict[str, Any] = Body(...)):
    uuid = data.get("uuid")
    name = data.get("name")
    category = data.get("category")
    if not uuid: raise HTTPException(400, "Missing uuid")
    await db.admin_upsert_registry(uuid, name, category)
    return {"status": "ok"}

# --- Academies ---

@app.get("/api/v1/academies")
async def get_academies():
    return await db.get_academies()

@app.post("/api/v1/academies")
async def add_academy(data: Dict[str, Any] = Body(...)):
    name = data.get("name")
    if not name: raise HTTPException(400, "Missing name")
    success = await db.add_academy(name)
    if not success: raise HTTPException(400, "Failed to add academy")
    return {"status": "ok"}

@app.delete("/api/v1/academies/{id}")
async def delete_academy(id: int):
    success = await db.delete_academy(id)
    if not success: raise HTTPException(400, "Failed to delete")
    return {"status": "ok"}

@app.post("/api/v1/academies-reorder")
async def academies_reorder_legacy(payload: Dict[str, Any] = Body(...)):
    """
    旧版页面兼容接口：保存书院排序。

    背景：
    - templates/devices.html 中使用了 /api/v1/academies-reorder；
    - 新版规范接口为 PUT /api/v1/academies/order（直接传 List[int]）。

    兼容策略：
    - 支持两种 body：
      1) {"order": [1,2,3]}
      2) [1,2,3]
    """
    order_list = payload.get("order") if isinstance(payload, dict) else payload
    if not isinstance(order_list, list):
        raise HTTPException(400, "Invalid order list")
    ids: List[int] = []
    for v in order_list:
        try:
            ids.append(int(v))
        except Exception:
            continue
    await db.update_academy_order(ids)
    return {"status": "ok"}

@app.put("/api/v1/academies/order")
async def update_academy_order(order_list: List[int] = Body(...)):
    await db.update_academy_order(order_list)
    return {"status": "ok"}

# --- Activity ---

@app.get("/api/v1/activity/list")
async def activity_list(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    locations: Optional[str] = None, # Comma separated
    types: Optional[str] = None,
    academies: Optional[str] = None,
    weekdays: Optional[str] = None,
    start_times: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    loc_list = locations.split(",") if locations else None
    type_list = types.split(",") if types else None
    aca_list = academies.split(",") if academies else None
    wd_list = weekdays.split(",") if weekdays else None
    time_list = start_times.split(",") if start_times else None
    
    return await db.activity_list(
        start_date, end_date, loc_list, type_list, aca_list, wd_list, time_list, page, page_size
    )

@app.get("/api/v1/activity/options")
async def activity_options():
    return await db.activity_get_options()

@app.get("/api/v1/activity/stats")
async def activity_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    locations: Optional[str] = None,
    types: Optional[str] = None,
    academies: Optional[str] = None
):
    loc_list = locations.split(",") if locations else None
    type_list = types.split(",") if types else None
    aca_list = academies.split(",") if academies else None
    
    return await db.activity_stats(start_date, end_date, loc_list, type_list, aca_list)

@app.post("/api/v1/activity/sync-visitors")
async def api_activity_sync_visitors(payload: Dict[str, Any] = Body(...)):
    date = payload.get("date")
    devices = payload.get("devices")
    start = payload.get("start")
    end = payload.get("end")
    mode = payload.get("mode") or "overwrite"
    if not date and not start and not end and not devices:
        raise HTTPException(400, "Missing date/devices/start/end")
    res = await db.activity_sync_visitors(date=date, devices=devices, start=start, end=end, mode=mode)
    if isinstance(res, dict):
        return res
    return {"count": int(res or 0), "skipped": []}

@app.delete("/api/v1/activity/{id}")
async def api_activity_delete(id: int):
    success = await db.activity_delete(id)
    if not success: raise HTTPException(404, "Not found")
    return {"status": "ok"}

@app.post("/api/v1/activity/import-excel")
async def api_activity_import_excel(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(400, "Invalid file format")
    
    contents = await file.read()
    
    # Try Pandas
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(contents))
        df = df.fillna('')
        iterator = df.to_dict('records')
    except ImportError:
        # Try openpyxl
        try:
            from openpyxl import load_workbook
            wb = load_workbook(filename=io.BytesIO(contents), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.values)
            if not rows: return {"count": 0}
            headers = rows[0]
            data = rows[1:]
            # Convert to list of dicts
            iterator = []
            for r in data:
                d = {headers[i]: (r[i] if r[i] is not None else '') for i in range(len(r)) if i < len(headers)}
                iterator.append(d)
        except ImportError:
             raise HTTPException(500, "Missing libraries (pandas or openpyxl)")
             
    # Helper to get val
    def get_val(row, keys):
        for k in keys:
            if k in row: return row[k]
        return None

    events = []
    
    for row in iterator:
        # Mapping
        date_raw = get_val(row, ['年/月/日', 'Date', '日期'])
        if not date_raw: continue
        
        # Parse Date
        date_str = str(date_raw).split(' ')[0] # 2023-01-01
        
        # Weekday
        weekday = str(get_val(row, ['周几', 'Weekday']) or '')
        
        # Times
        start_time = str(get_val(row, ['起始时间', 'Start']) or '')
        end_time = str(get_val(row, ['结束时间', 'End']) or '')
        
        # Duration
        duration_raw = str(get_val(row, ['时长', 'Duration']) or '')
        # Parse "X时Y分" or "30"
        duration = 0
        if '时' in duration_raw:
            parts = duration_raw.split('时')
            h = int(parts[0]) if parts[0].isdigit() else 0
            m_part = parts[1].replace('分', '')
            m = int(m_part) if m_part.isdigit() else 0
            duration = h * 60 + m
        elif '分' in duration_raw:
             m = int(duration_raw.replace('分', ''))
             duration = m
        elif duration_raw.isdigit():
             duration = int(duration_raw)
             
        academy = str(get_val(row, ['书院', 'Academy']) or '')
        location = str(get_val(row, ['具体地点', 'Location']) or '')
        act_name = str(get_val(row, ['活动名称', 'Activity Name']) or '')
        act_type = str(get_val(row, ['活动类型', 'Activity Type']) or '')
        
        audience = get_val(row, ['受众学生数', 'Audience'])
        try:
            audience = int(audience)
        except:
            audience = 0
            
        notes = str(get_val(row, ['备注', 'Remarks']) or '')
        
        events.append({
            "date": date_str,
            "weekday": weekday,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration,
            "academy": academy,
            "location": location,
            "activity_name": act_name,
            "activity_type": act_type,
            "audience_count": audience,
            "notes": notes
        })
        
    count = 0
    if events:
        res = await db.activity_bulk_insert(events)
        if isinstance(res, dict):
             count = res.get("inserted", 0) + res.get("updated", 0)
        else:
             count = res
        
    return {"count": count}

# --- Location Mapping API ---

@app.get("/api/v1/locations/mapping")
async def get_location_mapping():
    mapping = await db.get_location_academy_mapping()
    return {"mapping": mapping}

@app.post("/api/v1/locations/mapping")
async def update_location_mapping(payload: Dict[str, str] = Body(...)):
    location = payload.get("location")
    academy = payload.get("academy")
    if not location or not academy:
        raise HTTPException(status_code=400, detail="Missing location or academy")
    await db.update_location_academy_mapping(location, academy)
    return {"status": "ok"}

@app.delete("/api/v1/locations/mapping")
async def delete_location_mapping(location: str = Query(...)):
    await db.delete_location_academy_mapping(location)
    return {"status": "ok"}

@app.get("/api/v1/locations/all")
async def get_all_locations():
    locs = await db.get_all_activity_locations()
    return locs

class CorrectionPayload(BaseModel):
    location: str
    academy: str
    merge_locations: List[str] = []

@app.get("/api/v1/locations/correction-candidates")
async def get_correction_candidates(location: str = Query(...)):
    all_locs = await db.get_all_activity_locations()
    mapping = await db.get_location_academy_mapping()
    mapped_locs = set(mapping.keys())
    
    # Candidates are locations that are NOT the target location AND NOT already mapped
    # We assume if it's already mapped, it's correct and shouldn't be merged automatically
    candidates = [l for l in all_locs if l != location and l not in mapped_locs]
    
    # Use close matches
    matches = difflib.get_close_matches(location, candidates, n=10, cutoff=0.6)
    return matches

@app.post("/api/v1/locations/correct")
async def execute_correction(payload: CorrectionPayload):
    count = await db.correct_location_data(payload.location, payload.academy, payload.merge_locations)
    return {"count": count}

@app.post("/api/v1/locations/auto-correct-scan")
async def auto_correct_scan():
    all_locs = await db.get_all_activity_locations()
    mapping = await db.get_location_academy_mapping()
    standards = list(mapping.keys())
    matcher.set_standards(standards)
    
    mapped_locs = set(standards)
    unmapped = [l for l in all_locs if l not in mapped_locs]
    
    high_conf = [] 
    manual = []
    
    # Group by target for better UI/Processing
    # But for scan, flat list is fine, frontend can group.
    # Actually, let's group by target here to make frontend easier?
    # No, flat list is more flexible.
    
    for loc in unmapped:
        match, score = matcher.match(loc)
        if score >= 90:
            high_conf.append({"target": match, "source": loc, "score": score, "academy": mapping.get(match)})
        elif score >= 60:
            manual.append({"target": match, "source": loc, "score": score, "academy": mapping.get(match)})
            
    return {
        "high_confidence": high_conf,
        "manual_review": manual
    }

@app.post("/api/v1/locations/batch-correct")
async def batch_correct(payload: Dict[str, Any] = Body(...)):
    corrections = payload.get("corrections", [])
    total = 0
    for item in corrections:
        t = item.get("target")
        a = item.get("academy")
        s = item.get("sources", [])
        if t and a and s:
            total += await db.correct_location_data(t, a, s)
    return {"count": total}
