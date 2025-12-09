import io
import logging
import difflib
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
    return await db.stats_hourly(uuid, date)

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
