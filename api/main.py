import io
import logging
import difflib
import csv
import json
import re
import uuid as uuidlib
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Body, File, UploadFile, Request, Response
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app import config
from app.matcher import matcher

app = FastAPI(title="InfraCount API", version="1.0.0")

_LOG_IMPORT_CACHE: Dict[str, Dict[str, Any]] = {}

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    if db.use_sqlite():
        await db.init_sqlite()
    else:
        await db.init_pool()

@app.on_event("shutdown")
async def shutdown_event():
    await db.close_pool()

# --- Auth ---

@app.post("/api/v1/auth/login")
async def auth_login(response: Response, payload: Dict[str, str] = Body(...)):
    username = payload.get("username")
    password = payload.get("password")
    user = await db.authenticate_user(username, password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    session_token = await db.create_session(user["id"])
    # Set cookie
    response.set_cookie(key="session_token", value=session_token, httponly=True, max_age=7*24*3600)
    return {"status": "ok", "user": user}

@app.post("/api/v1/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.delete_session(token)
    response.delete_cookie("session_token")
    return {"status": "ok"}

@app.get("/api/v1/auth/me")
async def auth_me(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not logged in")
    user = await db.get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Invalid session")
    return {"user": user}

@app.post("/api/v1/auth/password")
async def auth_change_password(request: Request, payload: Dict[str, str] = Body(...)):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not logged in")
    user = await db.get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Invalid session")
        
    new_pw = payload.get("new_password")
    if not new_pw:
        raise HTTPException(400, "Missing password")
        
    await db.change_password(user["id"], new_pw)
    return {"status": "ok"}

# --- User Management (Admin) ---

@app.get("/api/v1/users")
async def list_users(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not logged in")
    user = await db.get_user_by_token(token)
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "Access denied")
        
    users = await db.get_all_users()
    return {"users": users}

@app.post("/api/v1/users")
async def create_user_api(request: Request, payload: Dict[str, str] = Body(...)):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not logged in")
    user = await db.get_user_by_token(token)
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "Access denied")
        
    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role", "user")
    
    if not username or not password:
        raise HTTPException(400, "Missing username or password")
        
    success = await db.create_user(username, password, role)
    if not success:
        raise HTTPException(400, "Failed to create user (might already exist)")
        
    return {"status": "ok"}

@app.put("/api/v1/users/{user_id}")
async def update_user_api(user_id: int, request: Request, payload: Dict[str, Any] = Body(...)):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not logged in")
    user = await db.get_user_by_token(token)
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "Access denied")
        
    # Prevent self-lockout or critical edits if needed, but let's allow for now.
    
    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role")
    
    success = await db.update_user(user_id, username, password, role)
    if not success:
        raise HTTPException(400, "Failed to update user")
        
    return {"status": "ok"}

@app.delete("/api/v1/users/{user_id}")
async def delete_user_api(user_id: int, request: Request):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not logged in")
    user = await db.get_user_by_token(token)
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "Access denied")
        
    if user["id"] == user_id:
        raise HTTPException(400, "Cannot delete yourself")
        
    await db.delete_user(user_id)
    return {"status": "ok"}


# --- Pages ---

@app.get("/login")
async def login_page():
    return FileResponse("templates/login.html")

@app.get("/account")
async def account_page():
    return FileResponse("templates/account.html")

# --- Static & Pages ---

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.svg", media_type="image/svg+xml")

@app.get("/")
async def index():
    return FileResponse("templates/dashboard.html")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("templates/dashboard.html")

@app.get("/activity-dashboard")
async def activity_dashboard():
    return FileResponse("activity_dashboard.html")

@app.get("/activity")
async def activity():
    return FileResponse("templates/activity.html")

@app.get("/history")
async def history():
    return FileResponse("templates/history.html")

@app.get("/history/academy")
async def history_academy():
    return FileResponse("templates/history_academy.html")

@app.get("/history/device")
async def history_device():
    return FileResponse("templates/history.html")

@app.get("/devices")
async def devices():
    return FileResponse("templates/devices.html")

@app.get("/alerts")
async def alerts():
    return FileResponse("templates/alerts.html")

# --- Records ---

@app.get("/api/v1/records/latest")
async def get_records_latest(uuid: str):
    return await db.fetch_latest(uuid)

@app.get("/api/v1/records/history")
async def get_records_history(
    uuid: Optional[str] = None, 
    limit: int = 100, 
    start: Optional[str] = None, 
    end: Optional[str] = None
):
    if uuid == "undefined":
        return []
    return await db.fetch_history(uuid=uuid, start=start, end=end, limit=limit)

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

@app.post("/api/v1/activity/walkin/sync")
async def walkin_sync(payload: Dict[str, Any] = Body(...)):
    items = payload.get("items", [])
    mode = payload.get("mode", "skip")
    result = await db.activity_bulk_insert(items, mode=mode)
    return result

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
    btx_max: Optional[int] = None
):
    items = await db.admin_list_records(page, size, uuid, start, end, warn, rec_type, btx_min, btx_max)
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
    if not date: raise HTTPException(400, "Missing date")
    count = await db.activity_sync_visitors(date)
    return {"count": count}

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
