from fastapi import FastAPI, Query
from typing import Optional
from starlette.responses import HTMLResponse
from starlette.responses import Response
from app.db import init_pool, close_pool

def _aiomysql():
    try:
        import aiomysql  # type: ignore
        return aiomysql
    except Exception:
        return None

app = FastAPI(title="Infrared Counter API", version="1.0")

@app.on_event("startup")
async def startup():
    try:
        await init_pool()
    except Exception:
        pass

@app.on_event("shutdown")
async def shutdown():
    await close_pool()

async def get_pool():
    from app.db import _pool
    return _pool

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/data/latest")
async def get_latest(uuid: str = Query(...)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT uuid,in_count,out_count,time,battery_level,signal_status FROM device_data WHERE uuid=%s ORDER BY id DESC LIMIT 1",
                (uuid,),
            )
            row = await cur.fetchone()
            if not row:
                return {}
            return {
                "uuid": row[0],
                "in": row[1],
                "out": row[2],
                "time": row[3],
                "battery_level": row[4],
                "signal_status": row[5],
            }

@app.get("/api/v1/data/history")
async def get_history(uuid: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 500):
    pool = await get_pool()
    if not pool:
        return []
    where = ["uuid=%s"]
    params = [uuid]
    if start:
        where.append("time>=%s")
        params.append(start)
    if end:
        where.append("time<=%s")
        params.append(end)
    sql = "SELECT uuid,in_count,out_count,time,battery_level,signal_status FROM device_data WHERE " + " AND ".join(where) + " ORDER BY time DESC LIMIT %s"
    params.append(limit)
    async with pool.acquire() as conn:
        aio = _aiomysql()
        cursor_kwargs = {}
        if aio:
            cursor_kwargs = {"cursor": aio.DictCursor}
        async with conn.cursor(**cursor_kwargs) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return rows

@app.get("/api/v1/devices")
async def list_devices(limit: int = 200):
    pool = await get_pool()
    if not pool:
        return []
    sql = "SELECT uuid, MAX(time) AS last_time, MAX(id) AS last_id FROM device_data GROUP BY uuid ORDER BY last_time DESC LIMIT %s"
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (limit,))
            rows = await cur.fetchall()
            data = []
            for r in rows:
                data.append({"uuid": r[0], "last_time": r[1], "last_id": r[2]})
            return data

# 统计聚合：按天
@app.get("/api/v1/stats/daily")
async def stats_daily(uuid: str, start: Optional[str] = None, end: Optional[str] = None):
    pool = await get_pool()
    if not pool:
        return []
    sql = "SELECT DATE(time) AS day, SUM(in_count) AS in_total, SUM(out_count) AS out_total FROM device_data WHERE uuid=%s"
    params = [uuid]
    if start:
        sql += " AND time>=%s"
        params.append(start)
    if end:
        sql += " AND time<=%s"
        params.append(end)
    sql += " GROUP BY day ORDER BY day ASC"
    async with pool.acquire() as conn:
        aio = _aiomysql()
        cursor_kwargs = {}
        if aio:
            cursor_kwargs = {"cursor": aio.DictCursor}
        async with conn.cursor(**cursor_kwargs) as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()

# 统计聚合：按小时
@app.get("/api/v1/stats/hourly")
async def stats_hourly(uuid: str, date: str):
    pool = await get_pool()
    if not pool:
        return []
    sql = (
        "SELECT DATE_FORMAT(time, '%H:00') AS hour, SUM(in_count) AS in_total, SUM(out_count) AS out_total "
        "FROM device_data WHERE uuid=%s AND DATE(time)=%s GROUP BY hour ORDER BY hour ASC"
    )
    async with pool.acquire() as conn:
        aio = _aiomysql()
        cursor_kwargs = {}
        if aio:
            cursor_kwargs = {"cursor": aio.DictCursor}
        async with conn.cursor(**cursor_kwargs) as cur:
            await cur.execute(sql, (uuid, date))
            return await cur.fetchall()

# 统计概览
@app.get("/api/v1/stats/summary")
async def stats_summary(uuid: str):
    pool = await get_pool()
    if not pool:
        return {"in_total": 0, "out_total": 0, "last_in": None, "last_out": None, "last_time": None}
    sql_total = "SELECT SUM(in_count), SUM(out_count) FROM device_data WHERE uuid=%s"
    sql_last = "SELECT in_count,out_count,time FROM device_data WHERE uuid=%s ORDER BY id DESC LIMIT 1"
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql_total, (uuid,))
            totals = await cur.fetchone()
            await cur.execute(sql_last, (uuid,))
            last = await cur.fetchone()
            return {
                "in_total": (totals[0] or 0) if totals else 0,
                "out_total": (totals[1] or 0) if totals else 0,
                "last_in": last[0] if last else None,
                "last_out": last[1] if last else None,
                "last_time": last[2] if last else None,
            }

# 可视化Dashboard（HTMLResponse，无需模板）
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html = """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>红外计数可视化</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body{font-family:system-ui,Arial;margin:24px}
    .row{display:flex;gap:24px;flex-wrap:wrap}
    .card{border:1px solid #ddd;border-radius:8px;padding:16px;flex:1;min-width:320px}
    .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
    .mini{border:1px solid #eee;border-radius:6px;padding:10px;background:#fafafa}
    table{width:100%;border-collapse:collapse}
    th,td{border:1px solid #eee;padding:8px;text-align:left;font-size:13px}
  </style>
</head>
<body>
  <h2>红外计数数据可视化</h2>
  <div>
    设备：<select id="device"></select>
    日期范围：<input id="start" type="date"> - <input id="end" type="date">
    <button id="load">加载</button>
    <label><input type="checkbox" id="auto">自动刷新</label>
    <button id="today">今天</button>
    <button id="last7">最近7天</button>
    <button id="exportDaily">导出日统计CSV</button>
    <button id="exportHourly">导出小时统计CSV</button>
    <button id="exportHistory">导出历史CSV</button>
  </div>
  <div class="row" style="margin-top:16px">
    <div class="card"><canvas id="dailyChart" style="height:320px"></canvas></div>
    <div class="card"><canvas id="hourChart" style="height:320px"></canvas></div>
  </div>
  <div class="grid" style="margin-top:16px">
    <div class="mini" id="sum_in"></div>
    <div class="mini" id="sum_out"></div>
    <div class="mini" id="sum_net"></div>
    <div class="mini" id="sum_last"></div>
  </div>
  <div class="card" style="margin-top:16px">
    <h3>最近记录</h3>
    <table>
      <thead><tr><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>信号</th></tr></thead>
      <tbody id="tbl"></tbody>
    </table>
  </div>
  <script>
    const deviceSel = document.getElementById('device');
    const startEl = document.getElementById('start');
    const endEl = document.getElementById('end');
    const autoEl = document.getElementById('auto');
    const tbl = document.getElementById('tbl');
    let dailyChart, hourChart, timer;
    async function loadDevices(){
      const res = await fetch('/api/v1/devices');
      const list = await res.json();
      deviceSel.innerHTML = '';
      for(const d of list){
        const opt = document.createElement('option');
        opt.value = d.uuid; opt.textContent = d.uuid;
        deviceSel.appendChild(opt);
      }
    }
    async function loadStats(){
      const uuid = deviceSel.value;
      const start = startEl.value? startEl.value + ' 00:00:00' : '';
      const end = endEl.value? endEl.value + ' 23:59:59' : '';
      const q = new URLSearchParams({uuid});
      if(start) q.append('start', start);
      if(end) q.append('end', end);
      const res = await fetch('/api/v1/stats/daily?' + q.toString());
      const daily = await res.json();
      const lab = daily.map(x=>x.day);
      const inData = daily.map(x=>x.in_total || 0);
      const outData = daily.map(x=>x.out_total || 0);
      const ctx = document.getElementById('dailyChart').getContext('2d');
      if(dailyChart) dailyChart.destroy();
      dailyChart = new Chart(ctx, {
        type: 'line',
        data: {labels: lab, datasets:[
          {label:'IN', data: inData, borderColor:'#2b8a3e'},
          {label:'OUT', data: outData, borderColor:'#d9480f'}
        ]},
        options: {responsive:true, maintainAspectRatio:false}
      });
      const sumRes = await fetch('/api/v1/stats/summary?' + new URLSearchParams({uuid}).toString());
      const sum = await sumRes.json();
      document.getElementById('sum_in').innerText = 'IN总计：' + (sum.in_total||0);
      document.getElementById('sum_out').innerText = 'OUT总计：' + (sum.out_total||0);
      document.getElementById('sum_net').innerText = '净流量：' + ((sum.in_total||0)-(sum.out_total||0));
      document.getElementById('sum_last').innerText = '最近上报：' + (sum.last_time||'') + ' IN=' + (sum.last_in||'') + ' OUT=' + (sum.last_out||'');
      const endDate = endEl.value || new Date().toISOString().slice(0,10);
      const hq = new URLSearchParams({uuid, date: endDate});
      const hres = await fetch('/api/v1/stats/hourly?' + hq.toString());
      const hourly = await hres.json();
      const hLab = hourly.map(x=>x.hour);
      const hIn = hourly.map(x=>x.in_total||0);
      const hOut = hourly.map(x=>x.out_total||0);
      const hctx = document.getElementById('hourChart').getContext('2d');
      if(hourChart) hourChart.destroy();
      hourChart = new Chart(hctx, {
        type: 'bar',
        data: {labels: hLab, datasets:[
          {label:'IN', data: hIn, backgroundColor:'#74c69d'},
          {label:'OUT', data: hOut, backgroundColor:'#f4a261'}
        ]},
        options: {responsive:true, maintainAspectRatio:false}
      });
      const hist = await (await fetch('/api/v1/data/history?' + new URLSearchParams({uuid, limit: 50}).toString())).json();
      tbl.innerHTML = '';
      for(const r of hist){
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.time}</td><td>${r.in_count||r.in||''}</td><td>${r.out_count||r.out||''}</td><td>${r.battery_level||''}</td><td>${r.signal_status||''}</td>`;
        tbl.appendChild(tr);
      }
    }
    document.getElementById('load').addEventListener('click', loadStats);
    document.getElementById('today').addEventListener('click', ()=>{
      const d = new Date().toISOString().slice(0,10);
      startEl.value = d; endEl.value = d; loadStats();
    });
    document.getElementById('last7').addEventListener('click', ()=>{
      const now = new Date();
      const end = now.toISOString().slice(0,10);
      const start = new Date(now.getTime()-6*24*3600*1000).toISOString().slice(0,10);
      startEl.value = start; endEl.value = end; loadStats();
    });
    autoEl.addEventListener('change', ()=>{
      if(autoEl.checked){
        timer = setInterval(loadStats, 10000);
      } else { clearInterval(timer); }
    });
    document.getElementById('exportDaily').addEventListener('click', ()=>{
      const uuid = deviceSel.value;
      const start = startEl.value? startEl.value + ' 00:00:00' : '';
      const end = endEl.value? endEl.value + ' 23:59:59' : '';
      const q = new URLSearchParams({uuid}); if(start) q.append('start', start); if(end) q.append('end', end);
      window.open('/api/v1/export/daily?' + q.toString(), '_blank');
    });
    document.getElementById('exportHourly').addEventListener('click', ()=>{
      const uuid = deviceSel.value;
      const date = endEl.value || new Date().toISOString().slice(0,10);
      window.open('/api/v1/export/hourly?' + new URLSearchParams({uuid,date}).toString(), '_blank');
    });
    document.getElementById('exportHistory').addEventListener('click', ()=>{
      const uuid = deviceSel.value;
      const start = startEl.value? startEl.value + ' 00:00:00' : '';
      const end = endEl.value? endEl.value + ' 23:59:59' : '';
      const q = new URLSearchParams({uuid}); if(start) q.append('start', start); if(end) q.append('end', end);
      window.open('/api/v1/export/history?' + q.toString(), '_blank');
    });
    (async()=>{ await loadDevices(); await loadStats(); })();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

# 导出CSV
def _csv_response(name: str, csv_text: str):
    return Response(content=csv_text, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={name}"})

@app.get("/api/v1/export/daily")
async def export_daily(uuid: str, start: Optional[str] = None, end: Optional[str] = None):
    rows = await stats_daily(uuid, start, end)
    csv = "day,in_total,out_total,net\n" + "\n".join([f"{r['day']},{r['in_total'] or 0},{r['out_total'] or 0},{(r['in_total'] or 0)-(r['out_total'] or 0)}" for r in rows])
    return _csv_response("daily.csv", csv)

@app.get("/api/v1/export/hourly")
async def export_hourly(uuid: str, date: str):
    rows = await stats_hourly(uuid, date)
    csv = "hour,in_total,out_total,net\n" + "\n".join([f"{r['hour']},{r['in_total'] or 0},{r['out_total'] or 0},{(r['in_total'] or 0)-(r['out_total'] or 0)}" for r in rows])
    return _csv_response("hourly.csv", csv)

@app.get("/api/v1/export/history")
async def export_history(uuid: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 10000):
    rows = await get_history(uuid, start, end, limit)
    def row_to_csv(r):
        t = r.get('time') if isinstance(r, dict) else r[3]
        inc = r.get('in_count') if isinstance(r, dict) else r[1]
        outc = r.get('out_count') if isinstance(r, dict) else r[2]
        bat = r.get('battery_level') if isinstance(r, dict) else r[4]
        sig = r.get('signal_status') if isinstance(r, dict) else r[5]
        return f"{t},{inc or ''},{outc or ''},{bat or ''},{sig or ''}"
    csv = "time,in_count,out_count,battery_level,signal_status\n" + "\n".join([row_to_csv(r) for r in rows])
    return _csv_response("history.csv", csv)

# Top榜统计
@app.get("/api/v1/stats/top")
async def stats_top(metric: str = "in", start: Optional[str] = None, end: Optional[str] = None, limit: int = 10):
    pool = await get_pool()
    if not pool:
        return []
    field = "in_count" if metric == "in" else "out_count"
    sql = f"SELECT uuid, SUM({field}) AS total FROM device_data WHERE 1=1"
    params = []
    if start:
        sql += " AND time>=%s"; params.append(start)
    if end:
        sql += " AND time<=%s"; params.append(end)
    sql += " GROUP BY uuid ORDER BY total DESC LIMIT %s"; params.append(limit)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [{"uuid": r[0], "total": r[1]} for r in rows]
