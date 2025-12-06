from fastapi import FastAPI, Query, Body, Request, WebSocket, HTTPException
from typing import Optional, List
from starlette.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from starlette.staticfiles import StaticFiles
import os
import json
import logging
import csv
import io
from app import config
from app.db import (
    init_pool, close_pool, fetch_latest, fetch_history, list_devices, 
    stats_daily, stats_hourly, stats_summary, stats_top, stats_total, 
    admin_count_records, admin_list_records, admin_update_record, 
    admin_delete_record, admin_create_record, list_alerts, 
    admin_list_registry, admin_upsert_registry, admin_write_op, 
    admin_delete_range, admin_get_categories, admin_get_uuids, 
    get_device_mapping, admin_batch_upsert, admin_fetch_range, 
    activity_bulk_insert, activity_list, activity_stats, activity_get_options,
    get_academies, add_academy, delete_academy, admin_batch_update, admin_batch_save_records,
    get_device_ip, update_academy_order
)
from app.security import issue_csrf, validate_csrf
import urllib.request
import urllib.parse
import ssl
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=5)

app = FastAPI(title="Infrared Counter API", version="1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup():
    try:
        await init_pool()
    except Exception as e:
        logging.error(f"Startup failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    await close_pool()

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# --- Data & Stats API ---

@app.get("/api/v1/data/latest")
async def get_latest(uuid: str = Query(...)):
    rows = await fetch_latest()
    # Filter for specific uuid if needed, though fetch_latest gets all
    for r in rows:
        if r.get("uuid") == uuid:
            return {
                "uuid": r.get("uuid"),
                "in": r.get("in_count"),
                "out": r.get("out_count"),
                "time": r.get("time"),
                "battery_level": r.get("battery"),
                "signal_status": r.get("signal_strength"),
            }
    return {}

@app.get("/api/data/latest")
async def get_latest_compat(uuid: str = Query(...)):
    # Compat endpoint
    return await get_latest(uuid)

@app.get("/api/v1/data/history")
async def get_history(uuid: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 500):
    rows = await fetch_history(uuid, start, end, limit)
    return rows

@app.get("/api/v1/devices")
async def api_list_devices(limit: int = 200):
    # This should return list of device objects with metadata
    uuids = await list_devices()
    mapping = await get_device_mapping()
    res = []
    for u in uuids:
        meta = mapping.get(u, {})
        res.append({
            "uuid": u,
            "name": meta.get("name"),
            "category": meta.get("category")
        })
    return res

@app.get("/api/v1/stats/daily")
async def api_stats_daily(uuid: str = None, start: Optional[str] = None, end: Optional[str] = None):
    if start and len(start) == 10: start += " 00:00:00"
    if end and len(end) == 10: end += " 23:59:59"
    return await stats_daily(uuid, start, end)

@app.get("/api/v1/stats/hourly")
async def api_stats_hourly(uuid: str = None, date: str = None):
    start = None
    end = None
    if date:
        start = f"{date} 00:00:00"
        end = f"{date} 23:59:59"
    return await stats_hourly(uuid, start=start, end=end)

@app.get("/api/v1/stats/summary")
async def api_stats_summary(uuid: str = None):
    return await stats_summary(uuid)

@app.get("/api/v1/stats/total")
async def api_stats_total(uuid: str = None, start: Optional[str] = None, end: Optional[str] = None):
    return await stats_total(uuid, start, end)

# --- Export API ---

def make_csv(headers, rows, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/api/v1/export/daily")
async def export_daily(uuid: str = None, start: str = None, end: str = None):
    data = await stats_daily(uuid, start, end)
    rows = [[d['date'], d['in'], d['out']] for d in data]
    return make_csv(['Date', 'In', 'Out'], rows, f'daily_{uuid or "all"}.csv')

@app.get("/api/v1/export/hourly")
async def export_hourly(uuid: str = None, date: str = None):
    data = await stats_hourly(uuid, start=date, end=date)
    rows = [[d['hour'], d['in'], d['out']] for d in data]
    return make_csv(['Hour', 'In', 'Out'], rows, f'hourly_{uuid or "all"}_{date}.csv')

@app.get("/api/v1/export/history")
async def export_history(uuid: str = None, start: str = None, end: str = None):
    rows = await fetch_history(uuid, start, end, limit=100000)
    if not rows:
        return make_csv([], [], 'empty.csv')
    headers = list(rows[0].keys())
    # Ensure headers are strings
    headers = [str(h) for h in headers]
    csv_rows = [[r[h] for h in headers] for r in rows]
    return make_csv(headers, csv_rows, f'history_{uuid or "all"}.csv')

# --- Admin / Registry API ---

@app.get("/api/v1/device/mapping")
async def api_device_mapping():
    m = await get_device_mapping()
    return {"mapping": {k: v.get("name") for k, v in m.items()}, "full_mapping": m}

@app.get("/api/v1/admin/device/registry")
async def api_registry_list():
    items = await admin_list_registry()
    return {"items": items}

@app.post("/api/v1/admin/device/registry")
async def api_registry_update(payload: dict = Body(...)):
    uuid = payload.get("uuid")
    name = payload.get("name")
    category = payload.get("category")
    if not uuid:
        raise HTTPException(400, "Missing UUID")
    await admin_upsert_registry(uuid, name, category)
    return {"status": "ok"}

@app.get("/api/v1/academies")
async def api_list_academies():
    return await get_academies()

@app.post("/api/v1/academies")
async def api_add_academy(payload: dict = Body(...)):
    name = payload.get("name")
    if not name:
        raise HTTPException(400, "Missing name")
    ok = await add_academy(name)
    return {"ok": ok}

@app.post("/api/v1/academies-reorder")
async def api_reorder_academies(payload: dict = Body(...)):
    order = payload.get("order") # List of IDs
    if not order:
        raise HTTPException(400, "Missing order list")
    await update_academy_order(order)
    return {"status": "ok"}

@app.delete("/api/v1/academies/{id}")
async def api_delete_academy(id: int):
    ok = await delete_academy(id)
    return {"ok": ok}

@app.post("/api/v1/admin/record/create")
async def api_record_create(payload: dict = Body(...)):
    # Validate payload
    if not payload.get("uuid"):
        raise HTTPException(400, "Missing UUID")
    if not payload.get("time"):
        raise HTTPException(400, "Missing time")
        
    # Allowed fields
    allowed = ["uuid", "time", "in_count", "out_count", "battery", "btx", "rec_type", "signal_strength", "warn_status", "activity_type"]
    data = {k: v for k, v in payload.items() if k in allowed}
    
    # Map frontend keys if needed (battery_level -> battery)
    if "battery_level" in payload and "battery" not in data:
        data["battery"] = payload["battery_level"]
    if "batterytx_level" in payload and "btx" not in data:
        data["btx"] = payload["batterytx_level"]
        
    await admin_create_record(data)
    return {"status": "ok"}

@app.post("/api/v1/admin/record/delete")
async def api_record_delete(payload: dict = Body(...)):
    id = payload.get("id")
    if not id:
        raise HTTPException(400, "Missing ID")
    await admin_delete_record(id)
    return {"status": "ok"}

@app.post("/api/v1/admin/record/update")
async def api_record_update(payload: dict = Body(...)):
    id = payload.get("id")
    if not id:
        raise HTTPException(400, "Missing ID")
    # Clean payload to only allowed fields
    allowed = ["time", "in_count", "out_count", "battery_level", "batterytx_level", "activity_type"]
    data = {k: v for k, v in payload.items() if k in allowed}
    # Map keys
    if "battery_level" in data:
        data["battery"] = data.pop("battery_level")
    if "batterytx_level" in data:
        data["btx"] = data.pop("batterytx_level")
        
    await admin_update_record(id, data)
    return {"status": "ok"}

@app.post("/api/v1/admin/record/batch-update")
async def api_record_batch_update(payload: dict = Body(...)):
    ids = payload.get("ids")
    updates = payload.get("updates")
    if not ids or not updates:
        raise HTTPException(400, "Missing ids or updates")
        
    # Allowed
    allowed = ["time", "in_count", "out_count", "battery_level", "batterytx_level", "activity_type"]
    data = {k: v for k, v in updates.items() if k in allowed}
    # Map keys
    if "battery_level" in data:
        data["battery"] = data.pop("battery_level")
    if "batterytx_level" in data:
        data["btx"] = data.pop("batterytx_level")
        
    await admin_batch_update(ids, data)
    return {"status": "ok"}

@app.post("/api/v1/admin/record/batch-save")
async def api_record_batch_save(payload: dict = Body(...)):
    creates = payload.get("creates", [])
    updates = payload.get("updates", [])
    
    # Allowed fields
    allowed = ["uuid", "time", "in_count", "out_count", "battery", "btx", "rec_type", "signal_strength", "warn_status", "activity_type", "id"]
    
    clean_creates = []
    for c in creates:
        # Map keys
        if "battery_level" in c: c["battery"] = c.pop("battery_level")
        if "batterytx_level" in c: c["btx"] = c.pop("batterytx_level")
        clean = {k: v for k, v in c.items() if k in allowed and k != "id"} # creates don't have id
        clean_creates.append(clean)
        
    clean_updates = []
    for u in updates:
        # Map keys
        if "battery_level" in u: u["battery"] = u.pop("battery_level")
        if "batterytx_level" in u: u["btx"] = u.pop("batterytx_level")
        clean = {k: v for k, v in u.items() if k in allowed}
        clean_updates.append(clean)
        
    await admin_batch_save_records(clean_creates, clean_updates)
    return {"status": "ok"}

@app.post("/api/v1/admin/sync/fetch")
async def api_sync_fetch(payload: dict = Body(...)):
    url = payload.get("url")
    uuid = payload.get("uuid")
    start = payload.get("start")
    end = payload.get("end")
    
    if not uuid:
        raise HTTPException(400, "Missing UUID")
        
    if not url:
        ip = await get_device_ip(uuid)
        if not ip:
            raise HTTPException(400, "Device IP unknown and no URL provided")
        url = f"http://{ip}:8000"
        
    # Parse URL to ensure it has scheme
    if not url.startswith("http"):
        url = "http://" + url
        
    # Build query params
    params = {"uuid": uuid}
    if start: params["start"] = start
    if end: params["end"] = end
    
    query = urllib.parse.urlencode(params)
    target = f"{url}/api/v1/data/history?{query}"
    
    def _fetch():
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(target, context=ctx, timeout=10) as response:
                if response.status == 200:
                    return json.loads(response.read().decode())
                else:
                    return None
        except Exception as e:
            logging.error(f"Fetch failed: {e}")
            return None
            
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(_executor, _fetch)
    
    if data is None:
        raise HTTPException(502, "Fetch failed from remote device")
        
    return data

@app.post("/api/v1/admin/record/delete-range")
async def api_record_delete_range(payload: dict = Body(...)):
    start = payload.get("start")
    end = payload.get("end")
    if not start or not end:
        raise HTTPException(400, "Missing range")
    await admin_delete_range(start, end)
    return {"status": "ok"}

@app.get("/api/v1/alerts")
async def api_list_alerts(uuid: str = None, limit: int = 100):
    return await list_alerts(uuid, limit)

# --- Pages ---

@app.get("/", response_class=RedirectResponse)
async def index():
    return "/dashboard"

@app.get("/dashboard", response_class=FileResponse)
async def page_dashboard():
    return "templates/dashboard.html"

@app.get("/history", response_class=FileResponse)
async def page_history_view():
    return "templates/history.html"

@app.get("/classification", response_class=FileResponse)
async def page_classification():
    return "templates/devices.html"

@app.get("/devices", response_class=RedirectResponse)
async def page_devices_redirect():
    return "/classification"

@app.get("/alerts", response_class=FileResponse)
async def page_alerts():
    return "templates/alerts.html"

@app.get("/activity-dashboard", response_class=FileResponse)
async def page_activity_dashboard():
    if os.path.exists("templates/activity.html"):
        return "templates/activity.html"
    return Response("Activity page not found", status_code=404)

# --- Activity API ---

@app.get("/api/v1/activity/list")
async def api_activity_list(start: str = None, end: str = None, locations: str = None, types: str = None, academies: str = None, weekdays: str = None, min_time: str = None, page: int = 1, page_size: int = 50):
    loc_list = locations.split(",") if locations else None
    type_list = types.split(",") if types else None
    aca_list = academies.split(",") if academies else None
    wd_list = weekdays.split(",") if weekdays else None
    return await activity_list(start, end, loc_list, type_list, aca_list, wd_list, min_time, page, page_size)

@app.get("/api/v1/activity/options")
async def api_activity_options():
    return await activity_get_options()

@app.get("/api/v1/activity/stats")
async def api_activity_stats(start: str = None, end: str = None, locations: str = None, types: str = None, academies: str = None):
    loc_list = locations.split(",") if locations else None
    type_list = types.split(",") if types else None
    aca_list = academies.split(",") if academies else None
    return await activity_stats(start, end, loc_list, type_list, aca_list)

@app.post("/api/v1/activity/upload")
async def api_activity_upload(payload: List[dict] = Body(...)):
    count = await activity_bulk_insert(payload)
    return {"count": count}
