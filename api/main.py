from fastapi import FastAPI, Query
from typing import Optional
from starlette.responses import HTMLResponse
from starlette.responses import RedirectResponse
from starlette.responses import Response
from starlette.responses import FileResponse
from fastapi import Body, UploadFile, Request, WebSocket
from starlette.staticfiles import StaticFiles
import os
from app import config
from app.db import init_pool, close_pool, fetch_latest, fetch_history, list_devices as db_list_devices, stats_daily as db_stats_daily, stats_hourly as db_stats_hourly, stats_summary as db_stats_summary, stats_top as db_stats_top, stats_total as db_stats_total, admin_count_records, admin_list_records, admin_update_record, admin_delete_record, admin_create_record, list_alerts, admin_list_registry, admin_upsert_registry, admin_write_op, admin_delete_range
from app.security import issue_csrf, validate_csrf

pass

app = FastAPI(title="Infrared Counter API", version="1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    return None

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/data/latest")
async def get_latest(uuid: str = Query(...)):
    row = await fetch_latest(uuid)
    if not row:
        return {}
    return {
        "uuid": row.get("uuid"),
        "in": row.get("in_count"),
        "out": row.get("out_count"),
        "time": row.get("time"),
        "battery_level": row.get("battery_level"),
        "signal_status": row.get("signal_status"),
    }

# 文档兼容：/api/data/latest
@app.get("/api/data/latest")
async def get_latest_compat(uuid: str = Query(...)):
    row = await fetch_latest(uuid)
    if not row:
        return {}
    return {
        "uuid": row.get("uuid"),
        "in": row.get("in_count"),
        "out": row.get("out_count"),
        "time": row.get("time"),
    }

@app.get("/api/v1/data/history")
async def get_history(uuid: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 500, warn_status: Optional[int] = None, rec_type: Optional[int] = None, batterytx_min: Optional[int] = None, batterytx_max: Optional[int] = None):
    rows = await fetch_history(uuid, start, end, limit, warn_status, rec_type, batterytx_min, batterytx_max)
    return rows

@app.get("/api/v1/devices")
async def list_devices(limit: int = 200):
    return await db_list_devices(limit)

# 统计聚合：按天
@app.get("/api/v1/stats/daily")
async def stats_daily(uuid: str, start: Optional[str] = None, end: Optional[str] = None):
    return await db_stats_daily(uuid, start, end)

# 统计聚合：按小时
@app.get("/api/v1/stats/hourly")
async def stats_hourly(uuid: str, date: str):
    return await db_stats_hourly(uuid, date)

# 统计概览
@app.get("/api/v1/stats/summary")
async def stats_summary(uuid: str):
    return await db_stats_summary(uuid)

@app.get("/api/v1/stats/total")
async def stats_total(start: Optional[str] = None, end: Optional[str] = None):
    return await db_stats_total(start, end)

# 可视化Dashboard（HTMLResponse，无需模板）
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html = """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>红外计数可视化</title>
  <script src="/static/chart.min.js"></script>
  <style>
    body{font-family:system-ui,Arial;margin:24px}
    .row{display:flex;gap:24px;flex-wrap:wrap}
    .card{border:1px solid #ddd;border-radius:10px;padding:16px;flex:1;min-width:320px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
    .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
    .mini{border:1px solid #eee;border-radius:8px;padding:10px;background:#fafafa}
    table{width:100%;border-collapse:collapse}
    th,td{border:1px solid #eee;padding:8px;text-align:left;font-size:13px}
    .tabs{display:flex;gap:12px;margin:12px 0}
    .tab{padding:8px 12px;border-radius:6px;background:#e9ecef;cursor:pointer}
    .tab.active{background:#ced4da}
    .hidden{display:none}
    .toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
    .btn{padding:8px 14px;border-radius:8px;border:1px solid #ddd;background:#fff;cursor:pointer}
    .btn:hover{border-color:#58a6ff;box-shadow:0 0 0 2px rgba(88,166,255,.2)}
    .btn-primary{background:#2b8a3e;color:#fff;border:1px solid #2b8a3e}
    .btn-danger{background:#d9480f;color:#fff;border:1px solid #d9480f}
    input,select{padding:8px 12px;border:1px solid #ddd;border-radius:8px;background:#fff}
    .filter-bar{background:#f8f9fa;border:1px solid #e5e7eb;padding:12px;border-radius:12px;box-shadow:0 1px 6px rgba(0,0,0,.05)}
    .filter-bar .field{display:flex;align-items:center;gap:8px}
    .filter-bar .spacer{flex:1}
    .chip{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid #e5e7eb;border-radius:999px;background:#fff}
    .chip input{accent-color:#2b8a3e}
    .ant-picker{display:inline-flex;align-items:center;gap:8px;border:1px solid #ddd;border-radius:8px;padding:4px 8px;background:#fff}
    .ant-picker-input input{border:none;outline:none;background:transparent;padding:4px 6px}
    .ant-picker-range-separator{color:#888}
    .ant-picker-clear{cursor:pointer;color:#bbb;margin-left:4px}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
    <h2 style="margin:0">红外计数数据可视化</h2>
    <div id="allTotals" style="font-weight:600;color:#2b8a3e"></div>
  </div>
  <div class="toolbar filter-bar">
    <div class="field">
      <span>设备</span>
      <select id="device"></select>
    </div>
    <div class="field">
      <span>日期</span>
      <div class="ant-picker ant-picker-range">
        <div class="ant-picker-input"><input id="start" type="date" placeholder="开始日期" size="12" autocomplete="off"></div>
        <div class="ant-picker-range-separator"><span aria-label="to" class="ant-picker-separator"><span role="img" aria-label="swap-right" class="anticon anticon-swap-right"><svg focusable="false" data-icon="swap-right" width="1em" height="1em" fill="currentColor" aria-hidden="true" viewBox="0 0 1024 1024"><path d="M873.1 596.2l-164-208A32 32 0 00684 376h-64.8c-6.7 0-10.4 7.7-6.3 13l144.3 183H152c-4.4 0-8 3.6-8 8v60c0 4.4 3.6 8 8 8h695.9c26.8 0 41.7-30.8 25.2-51.8z"></path></svg></span></span></div>
        <div class="ant-picker-input"><input id="end" type="date" placeholder="结束日期" size="12" autocomplete="off"></div>
        <span class="ant-picker-clear" id="dateClear" title="清除">×</span>
      </div>
    </div>
    <button class="btn btn-primary" id="load">加载</button>
    <label class="chip"><input type="checkbox" id="auto"> 自动刷新</label>
    <button class="btn" id="today">今天</button>
    <button class="btn" id="last7">最近7天</button>
    <button class="btn" id="resetFilter">重置</button>
    <div class="spacer"></div>
    <button class="btn" id="exportDaily">导出日统计CSV</button>
    <button class="btn" id="exportHourly">导出小时统计CSV</button>
    <button class="btn" id="exportHistory">导出历史CSV</button>
  </div>
  <div class="row" style="margin-top:16px">
    <div class="card"><canvas id="dailyChart" style="height:320px"></canvas></div>
    <div class="card"><canvas id="hourChart" style="height:320px"></canvas></div>
  </div>
  <div class="card" style="margin-top:16px">
    <div class="toolbar">
      <h3 style="margin:0">设备对比</h3>
      <button class="btn" id="downloadDaily">下载日图PNG</button>
      <button class="btn" id="downloadHour">下载小时图PNG</button>
    </div>
    <div id="compareDevices" class="toolbar"></div>
    <canvas id="compareChart" style="height:320px"></canvas>
  </div>
  <div class="card" style="margin-top:16px">
    <h3>排行榜</h3>
    <div class="toolbar">
      <button class="btn" id="rankRefresh">刷新排行榜</button>
    </div>
    <div class="row">
      <div style="flex:1">
        <h4>IN Top</h4>
        <table><thead><tr><th>UUID</th><th>Total IN</th></tr></thead><tbody id="rankIn"></tbody></table>
      </div>
      <div style="flex:1">
        <h4>OUT Top</h4>
        <table><thead><tr><th>UUID</th><th>Total OUT</th></tr></thead><tbody id="rankOut"></tbody></table>
      </div>
    </div>
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
      <thead><tr><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>发射端是否在线</th><th>Tx电量</th><th>记录类型</th></tr></thead>
      <tbody id="tbl"></tbody>
    </table>
    <div id="hourDate" class="mini"></div>
  </div>
  <div class="tabs">
    <div class="tab" data-tab="db">数据库管理</div>
    <div class="tab" data-tab="reg">设备分类</div>
  </div>
  <div id="pane_db" class="card hidden">
    <div class="toolbar">
      <input id="filterUuid" placeholder="设备UUID" style="padding:6px 10px;border:1px solid #ddd;border-radius:6px;"> 
      <input id="filterStart" type="datetime-local"> 
      <input id="filterEnd" type="datetime-local"> 
      <button class="btn btn-primary" id="query">查询</button>
      <button class="btn" id="reset">重置</button>
      <button class="btn btn-primary" id="add">新增记录</button>
      <input id="adminToken" placeholder="Admin Token" style="padding:6px 10px;border:1px solid #ddd;border-radius:6px;">
      <button class="btn" id="backup">备份数据库</button>
      <input id="restoreFile" type="file">
      <button class="btn" id="restore">还原数据库</button>
    </div>
    <table>
      <thead><tr><th>ID</th><th>UUID</th><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>信号</th><th>warn_status</th><th>Tx电量</th><th>记录类型</th><th>操作</th></tr></thead>
      <tbody id="adminTbl"></tbody>
    </table>
    <div class="toolbar">
      <button class="btn" id="prev">上一页</button> <span id="pageInfo"></span> <button class="btn" id="next">下一页</button>
    </div>
  </div>
  <div id="pane_reg" class="card hidden">
    <div class="toolbar">
      <input id="regCategory" placeholder="分类" style="padding:6px 10px;border:1px solid #ddd;border-radius:6px;">
      <input id="regSearch" placeholder="搜索UUID/名称" style="padding:6px 10px;border:1px solid #ddd;border-radius:6px;">
      <input id="regToken" placeholder="Admin Token" style="padding:6px 10px;border:1px solid #ddd;border-radius:6px;">
      <button class="btn btn-primary" id="regQuery">查询</button>
    </div>
    <table>
      <thead><tr><th>UUID</th><th>名称</th><th>分类</th><th>操作</th></tr></thead>
      <tbody id="regTbl"></tbody>
    </table>
    <div class="toolbar">
      <button class="btn" id="regPrev">上一页</button> <span id="regPageInfo"></span> <button class="btn" id="regNext">下一页</button>
    </div>
  </div>
  <script>
    const deviceSel = document.getElementById('device');
    const startEl = document.getElementById('start');
    const endEl = document.getElementById('end');
    const autoEl = document.getElementById('auto');
    const tbl = document.getElementById('tbl');
    let dailyChart, hourChart, timer;
    async function loadAllTotals(){
      const res = await fetch('/api/v1/stats/total');
      if(!res.ok){ return; }
      const d = await res.json();
      const el = document.getElementById('allTotals');
      el.textContent = '全部设备 IN: ' + (d.in_total||0) + '  OUT: ' + (d.out_total||0);
    }
    function fmtTime(s){ if(!s) return ''; const t = String(s).trim(); if(/^[0-9]{14}$/.test(t)) return t.slice(0,4)+'-'+t.slice(4,6)+'-'+t.slice(6,8)+' '+t.slice(8,10)+':'+t.slice(10,12)+':'+t.slice(12,14); return t; }
    function fmtSignal(s){ return (s===0 || s==='0') ? '在线' : '离线'; }
    function fmtTxOnline(s){ return (s===0 || s==='0') ? '在线' : '离线'; }
    function fmtRecType(t){ return (t===1 || t==='1') ? '实时数据' : ((t===2 || t==='2') ? '历史数据' : (t??'')); }
    async function loadDevices(){
      const res = await fetch('/api/v1/devices');
      const list = await res.json();
      deviceSel.innerHTML = '';
      for(const d of list){
        const opt = document.createElement('option');
        opt.value = d.uuid; opt.textContent = (d.name? `${d.name} (${d.uuid})` : d.uuid);
        deviceSel.appendChild(opt);
      }
    }
    async function loadStats(){
      const uuid = deviceSel.value;
      if (!uuid) {
        console.log('No device selected, skipping loadStats.');
        return;
      }
      console.log('--- Running loadStats for', uuid, '---');
      try {
        // --- 统一日期范围 ---
        const now = new Date();
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0,10) + ' 00:00:00';
        const monthEnd = (endEl.value || now.toISOString().slice(0,10)) + ' 23:59:59';
        
        // --- 左侧图表：当月每日IN/OUT ---
        console.log('Fetching daily stats for left chart...');
        const dailyQ = new URLSearchParams({uuid, start: monthStart, end: monthEnd});
        const dailyRes = await fetch('/api/v1/stats/daily?' + dailyQ.toString());
        if (!dailyRes.ok) throw new Error(`Failed to fetch daily stats: ${dailyRes.status}`);
        const daily = await dailyRes.json();
        console.log('Daily stats data:', daily);

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
        console.log('Left chart (dailyChart) rendered.');

        // --- 右侧图表：所选设备当日按小时IN/OUT ---
        let usedDate = (endEl.value || new Date().toISOString().slice(0,10));
        let hourlyRes = await fetch('/api/v1/stats/hourly?' + new URLSearchParams({uuid, date: usedDate}).toString());
        if (!hourlyRes.ok) throw new Error(`Failed to fetch hourly stats: ${hourlyRes.status}`);
        let hourly = await hourlyRes.json();
        let sumHour = hourly.reduce((a,x)=> a + (x.in_total||0) + (x.out_total||0), 0);
        if(!hourly.length || sumHour===0){
          const latestRes = await fetch('/api/v1/data/history?' + new URLSearchParams({uuid, limit: 1}).toString());
          if(latestRes.ok){
            const latest = await latestRes.json();
            if(latest && latest.length>0){
              const tt = String(latest[0].time||'');
              usedDate = (/^[0-9]{14}$/.test(tt)) ? (tt.slice(0,4)+'-'+tt.slice(4,6)+'-'+tt.slice(6,8)) : tt.slice(0,10);
              const h2 = await fetch('/api/v1/stats/hourly?' + new URLSearchParams({uuid, date: usedDate}).toString());
              if(h2.ok){ hourly = await h2.json(); }
            }
          }
        }
        const hLab = hourly.map(x=>x.hour);
        const hIn = hourly.map(x=>x.in_total||0);
        const hOut = hourly.map(x=>x.out_total||0);
        const hctx = document.getElementById('hourChart').getContext('2d');
        if(hourChart) hourChart.destroy();
        hourChart = new Chart(hctx, {type: 'bar', data: {labels: hLab, datasets:[{label:'IN', data: hIn, backgroundColor:'#74c69d'},{label:'OUT', data: hOut, backgroundColor:'#f4a261'}]}, options: {responsive:true, maintainAspectRatio:false}});
        const dtEl = document.getElementById('hourDate'); if(dtEl) dtEl.textContent = '右侧图日期：' + usedDate;

        // --- 统计概览 & 最近记录 ---
        console.log('Fetching summary and history...');
        const sumRes = await fetch('/api/v1/stats/summary?' + new URLSearchParams({uuid}).toString());
        if (sumRes.ok) {
            const sum = await sumRes.json();
            document.getElementById('sum_in').innerText = 'IN总计：' + (sum.in_total||0);
            document.getElementById('sum_out').innerText = 'OUT总计：' + (sum.out_total||0);
            document.getElementById('sum_net').innerText = '净流量：' + ((sum.in_total||0)-(sum.out_total||0));
            document.getElementById('sum_last').innerText = '最近上报：' + fmtTime(sum.last_time||'') + ' IN=' + (sum.last_in??'') + ' OUT=' + (sum.last_out??'');
        } else {
            console.error('Failed to fetch summary stats:', sumRes.status);
        }
        
        const histRes = await fetch('/api/v1/data/history?' + new URLSearchParams({uuid, limit: 50}).toString());
        if (histRes.ok) {
            const hist = await histRes.json();
            tbl.innerHTML = '';
            for(const r of hist){
              const tr = document.createElement('tr');
              tr.innerHTML = `<td>${r.time}</td><td>${r.in_count??r.in??''}</td><td>${r.out_count??r.out??''}</td><td>${r.battery_level??''}</td><td>${fmtTxOnline(r.warn_status)}</td><td>${r.batterytx_level??''}</td><td>${fmtRecType(r.rec_type)}</td>`;
              tbl.appendChild(tr);
            }
        } else {
            console.error('Failed to fetch history:', histRes.status);
        }
        console.log('Summary and history loaded.');

      } catch (error) {
        console.error('Error in loadStats:', error);
      }
    }
    document.getElementById('load').addEventListener('click', ()=>{ loadStats(); loadAllTotals(); });
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
    document.getElementById('resetFilter').addEventListener('click', ()=>{
      deviceSel.selectedIndex = 0;
      startEl.value = '';
      endEl.value = '';
      autoEl.checked = false;
      if(timer) { clearInterval(timer); }
      loadStats();
      loadAllTotals();
    });
    autoEl.addEventListener('change', ()=>{
      if(autoEl.checked){
        timer = setInterval(()=>{ loadStats(); loadAllTotals(); }, 10000);
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
    (async()=>{
      try {
        console.log('Initial script execution started.');
        await loadDevices();
        if(typeof Chart === 'undefined'){
          console.log('Chart.js not found, attempting to load from CDN...');
          const s = document.createElement('script');
          s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
        s.onload = async ()=>{ 
            console.log('Chart.js loaded successfully from CDN.');
            await loadStats(); await buildCompareDevices(); await loadRank(); await loadAllTotals();
          };
          s.onerror = ()=>{
            console.error('Failed to load Chart.js from CDN. Please check network connection and ad-blockers.');
          };
          document.head.appendChild(s);
        } else {
          console.log('Chart.js already loaded.');
          await loadStats(); await buildCompareDevices(); await loadRank(); await loadAllTotals();
        }
      } catch (e) {
        console.error('An error occurred during initial page load:', e);
      }
    })();
    document.getElementById('downloadDaily').addEventListener('click', ()=>{
      const url = document.getElementById('dailyChart').toDataURL('image/png');
      const a = document.createElement('a'); a.href = url; a.download = 'daily.png'; a.click();
    });
    document.getElementById('downloadHour').addEventListener('click', ()=>{
      const url = document.getElementById('hourChart').toDataURL('image/png');
      const a = document.createElement('a'); a.href = url; a.download = 'hour.png'; a.click();
    });
    let compareChart;
    function dateChanged(){
      const s = startEl.value; const e = endEl.value;
      if(s && e){ loadStats(); loadAllTotals(); }
    }
    document.getElementById('dateClear').addEventListener('click', ()=>{
      startEl.value=''; endEl.value=''; loadStats(); loadAllTotals();
    });
    startEl.addEventListener('change', dateChanged);
    endEl.addEventListener('change', dateChanged);
    async function buildCompareDevices(){
      const list = await (await fetch('/api/v1/devices')).json();
      const wrap = document.getElementById('compareDevices');
      wrap.innerHTML = '';
      for(const d of list){
        const id = 'chk_'+d.uuid;
        const label = document.createElement('label');
        label.style.marginRight = '8px';
        label.innerHTML = `<input type='checkbox' id='${id}' value='${d.uuid}'> ${(d.name? `${d.name} (${d.uuid})` : d.uuid)}`;
        wrap.appendChild(label);
      }
      wrap.addEventListener('change', loadCompare);
    }
    async function loadCompare(){
      const wrap = document.getElementById('compareDevices');
      const chks = wrap.querySelectorAll('input[type=checkbox]:checked');
      const selected = Array.from(chks).map(x=>x.value).slice(0,6);
      const start = startEl.value? startEl.value + ' 00:00:00' : '';
      const end = endEl.value? endEl.value + ' 23:59:59' : '';
      const labelsSet = new Set();
      const datasets = [];
      for(const u of selected){
        const q = new URLSearchParams({uuid:u}); if(start) q.append('start', start); if(end) q.append('end', end);
        const res = await fetch('/api/v1/stats/daily?' + q.toString());
        const rows = await res.json();
        rows.forEach(r=>labelsSet.add(r.day));
        datasets.push({label:u, data: rows.map(r=>r.in_total||0), borderColor:'#'+Math.floor(Math.random()*16777215).toString(16)});
      }
      const labels = Array.from(labelsSet).sort();
      const ctx = document.getElementById('compareChart').getContext('2d');
      if(compareChart) compareChart.destroy();
      compareChart = new Chart(ctx, {type:'line', data:{labels, datasets}, options:{responsive:true, maintainAspectRatio:false}});
    }
    async function loadRank(){
      const rIn = await (await fetch('/api/v1/stats/top?metric=in&limit=10')).json();
      const rOut = await (await fetch('/api/v1/stats/top?metric=out&limit=10')).json();
      const rankIn = document.getElementById('rankIn'); const rankOut = document.getElementById('rankOut');
      rankIn.innerHTML = ''; rankOut.innerHTML = '';
      for(const r of rIn){ const tr = document.createElement('tr'); tr.innerHTML = `<td>${r.uuid}</td><td>${r.total}</td>`; rankIn.appendChild(tr);} 
      for(const r of rOut){ const tr = document.createElement('tr'); tr.innerHTML = `<td>${r.uuid}</td><td>${r.total}</td>`; rankOut.appendChild(tr);} 
    }
    document.getElementById('rankRefresh').addEventListener('click', loadRank);
    const tabs = document.querySelectorAll('.tab');
    function showTab(name){
      document.getElementById('pane_db').classList.toggle('hidden', name!=='db');
      document.getElementById('pane_reg').classList.toggle('hidden', name!=='reg');
      tabs.forEach(t=>t.classList.toggle('active', t.dataset.tab===name));
    }
    tabs.forEach(t=>t.addEventListener('click', ()=>showTab(t.dataset.tab)));
    const adminTbl = document.getElementById('adminTbl');
    const filterUuid = document.getElementById('filterUuid');
    const filterStart = document.getElementById('filterStart');
    const filterEnd = document.getElementById('filterEnd');
    const pageInfo = document.getElementById('pageInfo');
    let page = 1, pageSize = 20, total = 0;
    async function loadAdmin(){
      const q = new URLSearchParams();
      if(filterUuid.value) q.append('uuid', filterUuid.value);
      if(filterStart.value) q.append('start', filterStart.value.replace('T',' '));
      if(filterEnd.value) q.append('end', filterEnd.value.replace('T',' '));
      q.append('page', page); q.append('page_size', pageSize);
      const res = await fetch('/api/v1/admin/records?' + q.toString(), {headers: {'X-Admin-Token': document.getElementById('adminToken').value || ''}});
      const data = await res.json();
      total = data.total || 0;
      adminTbl.innerHTML = '';
      for(const r of (data.items||[])){
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.id}</td><td>${r.uuid||''}</td><td>${r.time||''}</td><td>${r.in_count??''}</td><td>${r.out_count??''}</td><td>${r.battery_level??''}</td><td>${(r.signal_status===0||r.signal_status==='0')?'在线':'离线'}</td>`;
        adminTbl.appendChild(tr);
      }
      const pages = Math.max(1, Math.ceil(total/pageSize));
      pageInfo.textContent = `第 ${page}/${pages} 页，共 ${total} 条`;
    }
    document.getElementById('query').addEventListener('click', ()=>{ page=1; loadAdmin(); });
    document.getElementById('reset').addEventListener('click', ()=>{ filterUuid.value=''; filterStart.value=''; filterEnd.value=''; page=1; loadAdmin(); });
    document.getElementById('prev').addEventListener('click', ()=>{ if(page>1){ page--; loadAdmin(); }});
    document.getElementById('next').addEventListener('click', ()=>{ page++; loadAdmin(); });
    document.getElementById('add').addEventListener('click', async ()=>{
      const uuid = prompt('UUID'); if(!uuid) return;
      const time = prompt('时间 YYYY-MM-DD HH:MM:SS', new Date().toISOString().slice(0,19).replace('T',' '));
      const inc = parseInt(prompt('IN', '0')||'0');
      const outc = parseInt(prompt('OUT', '0')||'0');
      const bat = parseInt(prompt('电量', '80')||'0');
      const sig = parseInt(prompt('信号', '1')||'0');
      await fetch('/api/v1/admin/record/create', {method:'POST', headers:{'Content-Type':'application/json','X-Admin-Token': document.getElementById('adminToken').value || ''}, body: JSON.stringify({uuid, time, in_count: inc, out_count: outc, battery_level: bat, signal_status: sig})});
      loadAdmin();
    });
    const regTbl = document.getElementById('regTbl');
    const regCategory = document.getElementById('regCategory');
    const regSearch = document.getElementById('regSearch');
    const regToken = document.getElementById('regToken');
    const regPageInfo = document.getElementById('regPageInfo');
    let regPage = 1, regPageSize = 20;
    async function loadRegistry(){
      const q = new URLSearchParams();
      if(regCategory.value) q.append('category', regCategory.value);
      if(regSearch.value) q.append('search', regSearch.value);
      q.append('page', regPage); q.append('page_size', regPageSize);
      const res = await fetch('/api/v1/admin/device/registry?' + q.toString(), {headers:{'X-Admin-Token': regToken.value || ''}});
      const data = await res.json();
      regTbl.innerHTML = '';
      for(const r of (data.items||[])){
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.uuid}</td><td><input value='${r.name||''}' data-uuid='${r.uuid}' class='rn'></td><td><input value='${r.category||''}' data-uuid='${r.uuid}' class='rc'></td><td><button class='btn btn-primary' data-uuid='${r.uuid}' class='rs'>保存</button></td>`;
        regTbl.appendChild(tr);
      }
      regPageInfo.textContent = `第 ${regPage} 页`;
    }
    document.getElementById('regQuery').addEventListener('click', ()=>{ regPage=1; loadRegistry(); });
    document.getElementById('regPrev').addEventListener('click', ()=>{ if(regPage>1){ regPage--; loadRegistry(); }});
    document.getElementById('regNext').addEventListener('click', ()=>{ regPage++; loadRegistry(); });
    regTbl.addEventListener('click', async (e)=>{
      const b = e.target.closest('button'); if(!b) return;
      const uuid = b.dataset.uuid;
      const name = regTbl.querySelector(`input.rn[data-uuid='${uuid}']`).value;
      const category = regTbl.querySelector(`input.rc[data-uuid='${uuid}']`).value;
      await fetch('/api/v1/admin/device/registry/upsert', {method:'POST', headers:{'Content-Type':'application/json','X-Admin-Token': regToken.value || ''}, body: JSON.stringify({uuid, name, category})});
      loadRegistry();
    });
    document.getElementById('backup').addEventListener('click', async ()=>{
      const res = await fetch('/api/v1/admin/backup', {headers: {'X-Admin-Token': document.getElementById('adminToken').value || ''}});
      if(!res.ok){ alert('备份失败'); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'infrared.db'; a.click(); URL.revokeObjectURL(url);
    });
    document.getElementById('restore').addEventListener('click', async ()=>{
      const f = document.getElementById('restoreFile').files[0]; if(!f){ alert('请选择文件'); return; }
      const fd = new FormData(); fd.append('file', f);
      const res = await fetch('/api/v1/admin/restore', {method:'POST', headers: {'X-Admin-Token': document.getElementById('adminToken').value || ''}, body: fd});
      if(res.ok){ alert('还原成功'); } else { alert('还原失败'); }
      loadAdmin();
    });
    // 默认隐藏管理面板
    showTab('recent');
  </script>
</body>
</html>
"""
    return await page_board()

@app.get("/board", response_class=HTMLResponse)
async def page_board():
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>数据看板</title>
<link rel="stylesheet" href="/static/style.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
.filters{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
.filter-card{border:1px solid #ddd;border-radius:10px;padding:10px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,0.04)}
.filter-card h4{margin:0 0 8px 0;font-size:14px;color:#333}
.filter-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.filter-row label{color:#666;font-size:13px}
.filter-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ant-picker{display:inline-flex;align-items:center;gap:8px;border:1px solid #ddd;border-radius:8px;padding:4px 8px;background:#fff}
.ant-picker-input input{border:none;outline:none;background:transparent;padding:4px 6px}
.ant-picker-range-separator{color:#888}
.filter-hint{font-size:12px;color:#888;margin-top:6px}
 .btn{transition:transform .3s ease, background-color .3s ease, opacity .3s ease}
 .btn:hover{transform:translateY(-1px)}
 .btn:active{transform:scale(0.98)}
 .btn.loading{position:relative;pointer-events:none;opacity:.85}
 .btn.loading::after{content:"";position:absolute;right:-26px;top:50%;width:16px;height:16px;border-radius:50%;border:2px solid #999;border-top-color:transparent;transform:translateY(-50%);animation:spin .9s linear infinite}
 @keyframes spin{to{transform:translateY(-50%) rotate(360deg)}}
 .toast-root{position:fixed;left:50%;top:12px;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:8px;width:min(680px, 92vw)}
 .toast{display:flex;align-items:center;justify-content:space-between;border-radius:8px;padding:10px 12px;color:#fff;box-shadow:0 6px 18px rgba(0,0,0,.08);opacity:0;transform:translateY(-8px);transition:opacity .3s ease, transform .3s ease}
 .toast.enter{opacity:1;transform:translateY(0)}
 .toast.leave{opacity:0;transform:translateY(-8px)}
 .toast .msg{font-size:14px}
 .toast .close{background:transparent;border:none;color:inherit;cursor:pointer;font-size:14px}
 .toast-success{background:#2b8a3e}
 .toast-warning{background:#f59f00}
 .toast-error{background:#d9480f}
 .toast-info{background:#228be6}
@media (max-width: 768px){.filter-row{flex-direction:column;align-items:flex-start}.filter-actions{flex-direction:column;align-items:flex-start}.ant-picker{width:100%}}
</style>
</head><body>
<div id='toastRoot' class='toast-root'></div>
          <div class='sidebar'><h3>导航</h3><a class='nav-link' href='/dashboard'>数据看板</a><a class='nav-link' href='/history'>历史数据</a><a class='nav-link' href='/classification'>设备分类</a><a class='nav-link' href='/alerts'>告警中心</a></div>
<div class='main'>
  <div style='display:flex;align-items:center;justify-content:space-between'>
    <h2 style='margin:0'>红外计数数据看板</h2>
    <div id='allTotals' style='font-weight:600;color:var(--primary)'></div>
  </div>
  <div class='filters'>
    <div class='filter-card'>
      <h4>主筛选</h4>
      <div class='filter-row'>
        <label>设备</label>
        <select id='device'></select>
        <label>日期</label>
        <div class="ant-picker ant-picker-range"><div class="ant-picker-input"><input id='start' type='date' placeholder='开始日期' size='12' autocomplete='off'></div><div class="ant-picker-range-separator"><span aria-label='to' class='ant-picker-separator'><span role='img' aria-label='swap-right' class='anticon anticon-swap-right'><svg focusable='false' data-icon='swap-right' width='1em' height='1em' fill='currentColor' aria-hidden='true' viewBox='0 0 1024 1024'><path d='M873.1 596.2l-164-208A32 32 0 00684 376h-64.8c-6.7 0-10.4 7.7-6.3 13l144.3 183H152c-4.4 0-8 3.6-8 8v60c0 4.4 3.6 8 8 8h695.9c26.8 0 41.7-30.8 25.2-51.8z'></path></svg></span></span></div><div class="ant-picker-input"><input id='end' type='date' placeholder='结束日期' size='12' autocomplete='off'></div></div>
      </div>
      <div class='filter-hint'>选择开始与结束日期后生效</div>
    </div>
    <div class='filter-card'>
      <h4>操作</h4>
      <div class='filter-actions'>
        <button id='load' class='btn btn-primary'>加载数据</button>
        <button id='resetFilter' class='btn'>重置筛选</button>
        <button id='today' class='btn'>今天</button>
        <button id='last7' class='btn'>最近7天</button>
        <button id='refreshLatest' class='btn'>加载最新</button>
        <label><input type='checkbox' id='auto'>自动刷新</label>
        <button id='themeToggle' class='btn'>主题</button>
      </div>
    </div>
    <details class='filter-card'>
      <summary><h4 style='display:inline'>高级筛选</h4></summary>
      <div class='filter-row' style='margin-top:8px'>
        <input id='filterWarn' type='number' placeholder='warn_status' style='width:120px'>
        <input id='filterRecType' type='number' placeholder='rec_type' style='width:120px'>
        <input id='filterBtxMin' type='number' placeholder='Tx电量最小' style='width:140px'>
        <input id='filterBtxMax' type='number' placeholder='Tx电量最大' style='width:140px'>
      </div>
    </details>
    <details class='filter-card'>
      <summary><h4 style='display:inline'>页面操作</h4></summary>
      <div class='filter-actions' style='margin-top:8px'>
        <button id='exportDaily' class='btn'>导出日统计CSV</button>
        <button id='exportHourly' class='btn'>导出小时统计CSV</button>
        <button id='exportHistory' class='btn'>导出历史CSV</button>
        <button id='runToastTests' class='btn'>消息系统测试</button>
        <button id='runAnimPerf' class='btn'>动画性能测试</button>
      </div>
    </details>
  </div>
  <div class='row'><div class='card'><canvas id='dailyChart' style='height:320px'></canvas></div><div class='card'><canvas id='hourChart' style='height:320px'></canvas></div></div>
  <div class='grid' style='margin-top:16px'><div class='mini' id='sum_in'>IN总计：</div><div class='mini' id='sum_out'>OUT总计：</div><div class='mini' id='sum_net'>净流量：</div><div class='mini' id='sum_last'>最近上报：</div></div>
  <div class='card' style='margin-top:16px'><h3><a href='/history' style='text-decoration:none;color:inherit'>设备记录</a></h3><div class='table-wrap'><table><thead><tr><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>发射端是否在线</th><th>Tx电量</th><th>记录类型</th></tr></thead><tbody id='tbl'></tbody></table></div></div>
</div>
<script>
document.body.setAttribute('data-theme',(localStorage.getItem('theme')||'light'));
document.querySelectorAll('.sidebar a').forEach(a=>{if(a.getAttribute('href')===location.pathname){a.classList.add('active');}});
document.getElementById('themeToggle').addEventListener('click',()=>{const cur=document.body.getAttribute('data-theme')||'light';const nxt=cur==='light'?'dark':'light';document.body.setAttribute('data-theme',nxt);localStorage.setItem('theme',nxt);});
const deviceSel=document.getElementById('device');const startEl=document.getElementById('start');const endEl=document.getElementById('end');const autoEl=document.getElementById('auto');const tbl=document.getElementById('tbl');const filterWarn=document.getElementById('filterWarn');const filterRecType=document.getElementById('filterRecType');const filterBtxMin=document.getElementById('filterBtxMin');const filterBtxMax=document.getElementById('filterBtxMax');let dailyChart,hourChart,timer,fetchCtl;function fmtTime(s){if(!s)return'';const t=String(s).trim();if(/^[0-9]{14}$/.test(t))return t.slice(0,4)+'-'+t.slice(4,6)+'-'+t.slice(6,8)+' '+t.slice(8,10)+':'+t.slice(10,12)+':'+t.slice(12,14);return t;}function fmtSignal(s){return (s===0||s==='0')?'在线':'离线'}window.addEventListener('load',()=>{(async()=>{try{await loadDevices();await loadStats();if(typeof Chart==='undefined'){const s=document.createElement('script');s.src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';s.onload=()=>loadStats();document.head.appendChild(s);}}catch(e){}})();});
async function loadDevices(){const res=await fetch('/api/v1/devices');const list=await res.json();deviceSel.innerHTML='';for(const d of list){const opt=document.createElement('option');opt.value=d.uuid;opt.textContent=(d.name? `${d.name} (${d.uuid})`:d.uuid);deviceSel.appendChild(opt);}}
async function loadAllTotals(){const r=await fetch('/api/v1/stats/total');if(!r.ok)return;const j=await r.json();document.getElementById('allTotals').textContent='全部设备 IN: '+(j.in_total||0)+'  OUT: '+(j.out_total||0)}
async function loadStats(){const uuid=deviceSel.value;const today=new Date().toISOString().slice(0,10);const startDate=startEl.value|| (endEl.value? '' : new Date(Date.now()-29*24*3600*1000).toISOString().slice(0,10));const endDate=endEl.value|| today;const start=startDate? startDate+' 00:00:00':'';const end=endDate? endDate+' 23:59:59':'';const q=new URLSearchParams({uuid});if(start)q.append('start',start);if(end)q.append('end',end);const sumRes=await fetch('/api/v1/stats/summary?'+new URLSearchParams({uuid}).toString());const sum=await sumRes.json();document.getElementById('sum_in').innerText='IN总计：'+(sum.in_total||0);document.getElementById('sum_out').innerText='OUT总计：'+(sum.out_total||0);document.getElementById('sum_net').innerText='净流量：'+((sum.in_total||0)-(sum.out_total||0));document.getElementById('sum_last').innerText='最近上报：'+fmtTime(sum.last_time||'')+' IN='+(sum.last_in??'')+' OUT='+(sum.last_out??'');const res=await fetch('/api/v1/stats/daily?'+q.toString());const daily=await res.json();const lab=daily.map(x=>x.day);const inData=daily.map(x=>x.in_total||0);const outData=daily.map(x=>x.out_total||0);try{if(typeof Chart!=='undefined'){const ctx=document.getElementById('dailyChart').getContext('2d');if(dailyChart)dailyChart.destroy();dailyChart=new Chart(ctx,{type:'line',data:{labels:lab,datasets:[{label:'IN',data:inData,borderColor:'#2b8a3e'},{label:'OUT',data:outData,borderColor:'#d9480f'}]},options:{responsive:true,maintainAspectRatio:false}});}}catch(e){}const hq=new URLSearchParams({uuid,date:endDate});const hres=await fetch('/api/v1/stats/hourly?'+hq.toString());const hourly=await hres.json();const hLab=hourly.map(x=>x.hour);const hIn=hourly.map(x=>x.in_total||0);const hOut=hourly.map(x=>x.out_total||0);try{if(typeof Chart!=='undefined'){const hctx=document.getElementById('hourChart').getContext('2d');if(hourChart)hourChart.destroy();hourChart=new Chart(hctx,{type:'bar',data:{labels:hLab,datasets:[{label:'IN',data:hIn,backgroundColor:'#74c69d'},{label:'OUT',data:hOut,backgroundColor:'#f4a261'}]},options:{responsive:true,maintainAspectRatio:false}});}}catch(e){}const hparams=new URLSearchParams({uuid,limit:200});if(filterWarn&&filterWarn.value)hparams.append('warn_status',filterWarn.value);if(filterRecType&&filterRecType.value)hparams.append('rec_type',filterRecType.value);if(filterBtxMin&&filterBtxMin.value)hparams.append('batterytx_min',filterBtxMin.value);if(filterBtxMax&&filterBtxMax.value)hparams.append('batterytx_max',filterBtxMax.value);const hist=await (await fetch('/api/v1/data/history?'+hparams.toString())).json();tbl.innerHTML='';for(const r of hist){const tr=document.createElement('tr');tr.innerHTML=`<td>${fmtTime(r.time)}</td><td>${r.in_count??r.in??''}</td><td>${r.out_count??r.out??''}</td><td>${r.battery_level??''}</td><td>${fmtTxOnline(r.warn_status)}</td><td>${r.batterytx_level??''}</td><td>${fmtRecType(r.rec_type)}</td>`;tbl.appendChild(tr);}}
document.getElementById('load').addEventListener('click',async(e)=>{const b=e.currentTarget;b.classList.add('loading');await loadStats();await loadAllTotals();b.classList.remove('loading');});
document.getElementById('today').addEventListener('click',async(e)=>{const b=e.currentTarget;const d=new Date().toISOString().slice(0,10);startEl.value=d;endEl.value=d;b.classList.add('loading');await loadStats();await loadAllTotals();b.classList.remove('loading');});
document.getElementById('last7').addEventListener('click',async(e)=>{const b=e.currentTarget;const now=new Date();const end=now.toISOString().slice(0,10);const start=new Date(now.getTime()-6*24*3600*1000).toISOString().slice(0,10);startEl.value=start;endEl.value=end;b.classList.add('loading');await loadStats();await loadAllTotals();b.classList.remove('loading');});
document.getElementById('resetFilter').addEventListener('click',async(e)=>{const b=e.currentTarget;deviceSel.selectedIndex=0;startEl.value='';endEl.value='';if(filterWarn)filterWarn.value='';if(filterRecType)filterRecType.value='';if(filterBtxMin)filterBtxMin.value='';if(filterBtxMax)filterBtxMax.value='';autoEl.checked=false;if(timer)clearInterval(timer);b.classList.add('loading');await loadStats();await loadAllTotals();b.classList.remove('loading');});
autoEl.addEventListener('change',()=>{if(autoEl.checked){timer=setInterval(()=>{loadStats();loadAllTotals()},10000);}else{clearInterval(timer);}});
document.getElementById('exportDaily').addEventListener('click',()=>{const uuid=deviceSel.value;const start=startEl.value? startEl.value+' 00:00:00':'';const end=endEl.value? endEl.value+' 23:59:59':'';const q=new URLSearchParams({uuid});if(start)q.append('start',start);if(end)q.append('end',end);window.open('/api/v1/export/daily?'+q.toString(),'_blank');});
document.getElementById('exportHourly').addEventListener('click',()=>{const uuid=deviceSel.value;const date=endEl.value||new Date().toISOString().slice(0,10);window.open('/api/v1/export/hourly?'+new URLSearchParams({uuid,date}).toString(),'_blank');});
document.getElementById('exportHistory').addEventListener('click',()=>{const uuid=deviceSel.value;const start=startEl.value? startEl.value+' 00:00:00':'';const end=endEl.value? endEl.value+' 23:59:59':'';const q=new URLSearchParams({uuid});if(start)q.append('start',start);if(end)q.append('end',end);if(filterWarn&&filterWarn.value)q.append('warn_status',filterWarn.value);if(filterRecType&&filterRecType.value)q.append('rec_type',filterRecType.value);if(filterBtxMin&&filterBtxMin.value)q.append('batterytx_min',filterBtxMin.value);if(filterBtxMax&&filterBtxMax.value)q.append('batterytx_max',filterBtxMax.value);window.open('/api/v1/export/history?'+q.toString(),'_blank');});
(async()=>{await loadDevices();await loadStats();await loadAllTotals();})();
document.getElementById('runToastTests').addEventListener('click',()=>{const types=['info','success','warning','error'];const tr=document.getElementById('toastRoot');if(!tr)return;types.forEach((t,i)=>{setTimeout(()=>{const d=document.createElement('div');d.className='toast toast-'+t;const m=document.createElement('div');m.className='msg';m.textContent='测试 '+t;const c=document.createElement('button');c.className='close';c.textContent='×';d.appendChild(m);d.appendChild(c);tr.appendChild(d);requestAnimationFrame(()=>{d.classList.add('enter')});setTimeout(()=>{d.classList.remove('enter');d.classList.add('leave');setTimeout(()=>{if(d.parentNode)tr.removeChild(d)},300)},3000);c.addEventListener('click',()=>{d.classList.remove('enter');d.classList.add('leave');setTimeout(()=>{if(d.parentNode)tr.removeChild(d)},300)});},i*300)})});
document.getElementById('runAnimPerf').addEventListener('click',()=>{let frames=0;const start=performance.now();function step(ts){frames++;if(ts-start<1000){requestAnimationFrame(step);}else{const tr=document.getElementById('toastRoot');if(!tr)return;const d=document.createElement('div');d.className='toast toast-info';const m=document.createElement('div');m.className='msg';m.textContent='1s帧数:'+frames;const c=document.createElement('button');c.className='close';c.textContent='×';d.appendChild(m);d.appendChild(c);tr.appendChild(d);requestAnimationFrame(()=>{d.classList.add('enter')});setTimeout(()=>{d.classList.remove('enter');d.classList.add('leave');setTimeout(()=>{if(d.parentNode)tr.removeChild(d)},300)},3000);c.addEventListener('click',()=>{d.classList.remove('enter');d.classList.add('leave');setTimeout(()=>{if(d.parentNode)tr.removeChild(d)},300)});}}requestAnimationFrame(step)});
document.getElementById('refreshLatest').addEventListener('click',loadLatest);
document.getElementById('load').addEventListener('click',()=>{const v={device:deviceSel.value,start:startEl.value,end:endEl.value,warn:filterWarn?filterWarn.value:'',rectype:filterRecType?filterRecType.value:'',btxmin:filterBtxMin?filterBtxMin.value:'',btxmax:filterBtxMax?filterBtxMax.value:'',auto:autoEl?autoEl.checked:false};localStorage.setItem('dashboardFilters',JSON.stringify(v));},{capture:true});
document.getElementById('today').addEventListener('click',()=>{const d=new Date().toISOString().slice(0,10);startEl.value=d;endEl.value=d;const v={device:deviceSel.value,start:startEl.value,end:endEl.value,warn:filterWarn?filterWarn.value:'',rectype:filterRecType?filterRecType.value:'',btxmin:filterBtxMin?filterBtxMin.value:'',btxmax:filterBtxMax?filterBtxMax.value:'',auto:autoEl?autoEl.checked:false};localStorage.setItem('dashboardFilters',JSON.stringify(v));},{capture:true});
document.getElementById('last7').addEventListener('click',()=>{const now=new Date();const end=now.toISOString().slice(0,10);const start=new Date(now.getTime()-6*24*3600*1000).toISOString().slice(0,10);startEl.value=start;endEl.value=end;const v={device:deviceSel.value,start:startEl.value,end:endEl.value,warn:filterWarn?filterWarn.value:'',rectype:filterRecType?filterRecType.value:'',btxmin:filterBtxMin?filterBtxMin.value:'',btxmax:filterBtxMax?filterBtxMax.value:'',auto:autoEl?autoEl.checked:false};localStorage.setItem('dashboardFilters',JSON.stringify(v));},{capture:true});
document.getElementById('resetFilter').addEventListener('click',()=>{localStorage.removeItem('dashboardFilters');},{capture:true});
if(autoEl)autoEl.addEventListener('change',()=>{const v={device:deviceSel.value,start:startEl.value,end:endEl.value,warn:filterWarn?filterWarn.value:'',rectype:filterRecType?filterRecType.value:'',btxmin:filterBtxMin?filterBtxMin.value:'',btxmax:filterBtxMax?filterBtxMax.value:'',auto:autoEl?autoEl.checked:false};localStorage.setItem('dashboardFilters',JSON.stringify(v));});
let debounceT;function debounceSave(){if(debounceT)clearTimeout(debounceT);debounceT=setTimeout(()=>{const v={device:deviceSel.value,start:startEl.value,end:endEl.value,warn:filterWarn?filterWarn.value:'',rectype:filterRecType?filterRecType.value:'',btxmin:filterBtxMin?filterBtxMin.value:'',btxmax:filterBtxMax?filterBtxMax.value:'',auto:autoEl?autoEl.checked:false};localStorage.setItem('dashboardFilters',JSON.stringify(v));},200);}startEl.addEventListener('change',debounceSave);endEl.addEventListener('change',debounceSave);
async function loadLatest(){const uuid=deviceSel.value;await loadStats();const r=await fetch('/api/v1/data/latest?'+new URLSearchParams({uuid}).toString());const x=await r.json();const t=fmtTime(x.time||'');const inc=x.in_count??x.in??'';const outc=x.out_count??x.out??'';document.getElementById('sum_last').textContent='最近上报：'+t+' IN='+inc+' OUT='+outc;await fetch('/api/v1/device/time-sync/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uuid})});}
</script>
<script>
function fmtTxOnline(s){return (s===0||s==='0')?'在线':'离线'}
function fmtRecType(t){return (t===1||t==='1')?'实时数据':(t===2||t==='2')?'历史数据':(t??'')}
</script>
</body></html>
"""
    return HTMLResponse(content=html)
@app.get("/history", response_class=HTMLResponse)
async def page_history():
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>历史数据</title>
<link rel='stylesheet' href='/static/style.css'>
<style>.table-wrap{min-height:calc(100vh - 70px);height:auto;overflow:visible}</style>
</head><body>
          <div class='sidebar'><h3>导航</h3><a class='nav-link' href='/dashboard'>数据看板</a><a class='nav-link' href='/history'>历史数据</a><a class='nav-link' href='/classification'>设备分类</a><a class='nav-link' href='/alerts'>告警中心</a></div>
<div class='main'>
  <h2>历史数据</h2>
  <div class='toolbar'>设备：<select id='device'></select> 日期范围：<input id='start' type='date'> - <input id='end' type='date'> 过滤：<input id='filterWarn' type='number' placeholder='warn_status' style='width:90px'> <input id='filterRecType' type='number' placeholder='rec_type' style='width:90px'> <input id='filterBtxMin' type='number' placeholder='Tx电量最小' style='width:110px'> <input id='filterBtxMax' type='number' placeholder='Tx电量最大' style='width:110px'> <input id='histAdminToken' placeholder='Admin Token' style='width:140px'> <button id='query' class='btn btn-primary'>查询</button> <button id='reset' class='btn'>重置</button></div>
  <div class='table-wrap'><table><thead><tr><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>发射端是否在线</th><th>Tx电量</th><th>记录类型</th><th style='width:140px'>操作</th></tr></thead><tbody id='tbl'></tbody></table></div>
</div>
<script>
document.querySelectorAll('.sidebar a').forEach(a=>{if(a.getAttribute('href')===location.pathname){a.classList.add('active');}});
const deviceSel=document.getElementById('device');const startEl=document.getElementById('start');const endEl=document.getElementById('end');const tbl=document.getElementById('tbl');const filterWarn=document.getElementById('filterWarn');const filterRecType=document.getElementById('filterRecType');const filterBtxMin=document.getElementById('filterBtxMin');const filterBtxMax=document.getElementById('filterBtxMax');
async function loadDevices(){const res=await fetch('/api/v1/devices');const list=await res.json();deviceSel.innerHTML='';for(const d of list){const opt=document.createElement('option');opt.value=d.uuid;opt.textContent=(d.name? `${d.name} (${d.uuid})`:d.uuid);deviceSel.appendChild(opt);}}
function fmtTime(s){ if(!s) return ''; const t = String(s).trim(); if(/^[0-9]{14}$/.test(t)) return t.slice(0,4)+'-'+t.slice(4,6)+'-'+t.slice(6,8)+' '+t.slice(8,10)+':'+t.slice(10,12)+':'+t.slice(12,14); return t; }
function fmtTxOnline(s){return (s===0||s==='0')?'在线':'离线'}
function fmtRecType(t){return (t===1||t==='1')?'实时数据':(t===2||t==='2')?'历史数据':(t??'')}
async function loadHistory(){const uuid=deviceSel.value;const start=startEl.value? startEl.value+' 00:00:00':'';const end=endEl.value? endEl.value+' 23:59:59':'';const q=new URLSearchParams({uuid});if(start)q.append('start',start);if(end)q.append('end',end);if(filterWarn&&filterWarn.value)q.append('warn_status',filterWarn.value);if(filterRecType&&filterRecType.value)q.append('rec_type',filterRecType.value);if(filterBtxMin&&filterBtxMin.value)q.append('batterytx_min',filterBtxMin.value);if(filterBtxMax&&filterBtxMax.value)q.append('batterytx_max',filterBtxMax.value);const rows=await (await fetch('/api/v1/data/history?'+q.toString())).json();tbl.innerHTML='';for(const r of rows){const id=r.id??'';const tr=document.createElement('tr');tr.innerHTML=`<td>${fmtTime(r.time)}</td><td>${r.in_count??r.in??''}</td><td>${r.out_count??r.out??''}</td><td>${r.battery_level??''}</td><td>${fmtTxOnline(r.warn_status)}</td><td>${r.batterytx_level??''}</td><td>${fmtRecType(r.rec_type)}</td><td style='white-space:nowrap'><span class='op-actions'><button class='btn btn-primary' data-act='edit' data-id='${id}'>✎ 编辑</button><button class='btn' data-act='del' data-id='${id}'>🗑 删除</button></span></td>`;tbl.appendChild(tr);}}
document.getElementById('query').addEventListener('click',loadHistory);
document.getElementById('reset').addEventListener('click',()=>{deviceSel.selectedIndex=0;startEl.value='';endEl.value='';if(filterWarn)filterWarn.value='';if(filterRecType)filterRecType.value='';if(filterBtxMin)filterBtxMin.value='';if(filterBtxMax)filterBtxMax.value='';loadHistory()});
(async()=>{await loadDevices();await loadHistory();})();
</script>
<div id='histToast' class='toast'></div>
<div id='editModal' class='modal-backdrop' role='dialog' aria-modal='true' aria-labelledby='m_title'><div class='modal'><h3 id='m_title'>编辑记录</h3><div class='form-grid'><div class='form-row'><label for='m_time'>时间</label><input id='m_time' class='input' type='datetime-local'></div><div class='form-row'><label for='m_in'>IN计数</label><input id='m_in' class='input' type='number' min='0'></div><div class='form-row'><label for='m_out'>OUT计数</label><input id='m_out' class='input' type='number' min='0'></div><div class='form-row'><label for='m_bat'>电量(%)</label><input id='m_bat' class='input' type='number' min='0' max='100'></div><div class='form-row'><label>发射端在线</label><div class='radio-group' role='radiogroup' aria-label='发射端在线'><label><input type='radio' name='m_txonline' value='0'> 在线</label><label><input type='radio' name='m_txonline' value='1'> 离线</label></div></div><div class='form-row'><label for='m_btx'>Tx电量</label><input id='m_btx' class='input' type='number' min='0' max='100'></div><div class='form-row'><label for='m_rectype'>记录类型</label><select id='m_rectype' class='input'><option value='1'>实时数据</option><option value='2'>历史数据</option></select></div></div><div class='actions'><button class='btn' id='m_cancel' aria-label='取消编辑'>取消</button><button class='btn btn-primary' id='m_save' aria-label='保存编辑'>保存</button></div></div></div>
<script>
const modal=document.getElementById('editModal');const toast=document.getElementById('histToast');const m_time=document.getElementById('m_time');const m_inout=document.getElementById('m_inout');const m_in=document.getElementById('m_in');const m_out=document.getElementById('m_out');const m_bat=document.getElementById('m_bat');const m_btx=document.getElementById('m_btx');const m_rectype=document.getElementById('m_rectype');let editingId=null,editingRow=null;function showToast(t){toast.textContent=t;toast.style.display='block';setTimeout(()=>toast.style.display='none',1500)}function openModal(row){editingRow=row;modal.classList.remove('closing');modal.classList.add('show')}function closeModal(){modal.classList.add('closing');setTimeout(()=>{modal.classList.remove('closing');modal.classList.remove('show');editingId=null;editingRow=null;m_time.classList.remove('err');m_in.classList.remove('err');m_out.classList.remove('err');m_bat.classList.remove('err');m_btx.classList.remove('err')},300)}document.getElementById('m_cancel').addEventListener('click',closeModal);modal.addEventListener('click',(e)=>{if(e.target===modal)closeModal()});document.addEventListener('keydown',(e)=>{if(e.key==='Escape')closeModal()});function toLocal(s){if(!s)return'';let t=String(s).trim();if(/^\d{14}$/.test(t)){t=t.slice(0,4)+'-'+t.slice(4,6)+'-'+t.slice(6,8)+' '+t.slice(8,10)+':'+t.slice(10,12)+':'+t.slice(12,14)}t=t.replace(/\//g,'-');const d=new Date(t.replace(' ','T'));if(isNaN(d.getTime()))return t.replace(' ','T').slice(0,19);const z=d.getTimezoneOffset()*60000;return new Date(d.getTime()-z).toISOString().slice(0,19)}function fromLocal(v){return (v||'').replace('T',' ').slice(0,19)}function validInt(v){if(v===''||v===null||v===undefined)return true;const n=Number(v);return Number.isFinite(n)&&Math.floor(n)===n}function nonNegInt(v){if(v===''||v===null||v===undefined)return true;const n=Number(v);return Number.isFinite(n)&&Math.floor(n)===n&&n>=0}function inRange(n,min,max){if(n===''||n===null||n===undefined)return true;const x=Number(n);return Number.isFinite(x)&&x>=min&&x<=max}function onEdit(btn){const id=btn.dataset.id;const row=btn.closest('tr');if(!id){showToast('缺少ID');return}editingId=parseInt(id);const c=row.querySelectorAll('td');m_time.value=toLocal((c[0].textContent||'').trim());m_inout.value=btn.dataset.warn||'0';m_in.value=(c[1].textContent||'').trim();m_out.value=(c[2].textContent||'').trim();m_bat.value=(c[3].textContent||'').trim();m_btx.value=(c[5].textContent||'').trim();m_rectype.value=((c[6].textContent||'').trim()==='实时数据')?'1':'2';const online=(c[4].textContent||'').trim()==='在线'?'0':'1';document.querySelectorAll("input[name='m_txonline']").forEach(r=>{r.checked=(r.value===online)});openModal(row)}async function onDel(btn){const id=btn.dataset.id;const row=btn.closest('tr');if(!id){showToast('缺少ID');return}if(!confirm('确认删除该条记录？'))return;btn.disabled=true;btn.textContent='删除中…';try{const res=await fetch('/api/v1/admin/record/delete',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':(document.getElementById('histAdminToken')?.value||'')},body:JSON.stringify({id:parseInt(id)})});if(res.ok){showToast('删除成功');await loadHistory()}else{showToast('删除失败')}}finally{btn.disabled=false;btn.textContent='🗑 删除'}}document.getElementById('m_save').addEventListener('click',async()=>{let ok=true;m_time.classList.remove('err');m_in.classList.remove('err');m_out.classList.remove('err');m_bat.classList.remove('err');m_btx.classList.remove('err');const t=fromLocal(m_time.value);if(t&&t.length!==19){m_time.classList.add('err');ok=false}if(!nonNegInt(m_in.value)){m_in.classList.add('err');ok=false}if(!nonNegInt(m_out.value)){m_out.classList.add('err');ok=false}if(!inRange(m_bat.value,0,100)){m_bat.classList.add('err');ok=false}if(!inRange(m_btx.value,0,100)){m_btx.classList.add('err');ok=false}if(!ok){showToast('数据不合法');return}const cells=editingRow.querySelectorAll('td');let inc=parseInt(cells[1].textContent||'0');let outc=parseInt(cells[2].textContent||'0');if(m_in.value!=='')inc=parseInt(m_in.value);if(m_out.value!=='')outc=parseInt(m_out.value);const payload={id:editingId};if(m_inout.value!=='')payload.warn_status=parseInt(m_inout.value);if(t)payload.time=t;if(validInt(inc))payload.in_count=inc;if(validInt(outc))payload.out_count=outc;if(m_bat.value!=='')payload.battery_level=parseInt(m_bat.value);const radio=document.querySelector("input[name='m_txonline']:checked");if(radio)payload.signal_status=parseInt(radio.value);if(m_btx.value!=='')payload.batterytx_level=parseInt(m_btx.value);if(m_rectype.value!=='')payload.rec_type=parseInt(m_rectype.value);const saveBtn=document.getElementById('m_save');saveBtn.disabled=true;saveBtn.textContent='保存中…';try{const res=await fetch('/api/v1/admin/record/update',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':(document.getElementById('histAdminToken')?.value||'')},body:JSON.stringify(payload)});if(res.ok){showToast('保存成功');closeModal();await loadHistory()}else{showToast('保存失败')}}finally{saveBtn.disabled=false;saveBtn.textContent='保存'}})
tbl.addEventListener('click',(e)=>{const b=e.target.closest('button');if(!b)return;const act=b.dataset.act;if(act==='edit'){onEdit(b)}else if(act==='del'){onDel(b)}})
</script>
<script>
(function(){
  function fromLocalFixed(v){let s=(v||'').replace('T',' ');if(!s)return'';if(s.length===16)s=s+':00';return s.slice(0,19)}
  window.fromLocal=fromLocalFixed;
  const m_time=document.getElementById('m_time');const m_in=document.getElementById('m_in');const m_out=document.getElementById('m_out');const m_bat=document.getElementById('m_bat');const m_btx=document.getElementById('m_btx');const m_rectype=document.getElementById('m_rectype');const toast=document.getElementById('histToast');
  function showToast(t){toast.textContent=t;toast.style.display='block';setTimeout(()=>toast.style.display='none',1500)}
  window.onEdit=function(btn){const id=btn.dataset.id;const row=btn.closest('tr');if(!id){showToast('缺少ID');return}editingId=parseInt(id);editingRow=row;const c=row.querySelectorAll('td');m_time.value=toLocal((c[0].textContent||'').trim());m_in.value=(c[1].textContent||'').trim();m_out.value=(c[2].textContent||'').trim();m_bat.value=(c[3].textContent||'').trim();m_btx.value=(c[5].textContent||'').trim();m_rectype.value=((c[6].textContent||'').trim()==='实时数据')?'1':'2';const online=(c[4].textContent||'').trim()==='在线'?'0':'1';document.querySelectorAll("input[name='m_txonline']").forEach(r=>{r.checked=(r.value===online)});openModal(row)};
  const save=document.getElementById('m_save');const newSave=save.cloneNode(true);save.parentNode.replaceChild(newSave,save);
  newSave.addEventListener('click',async()=>{let ok=true;m_time.classList.remove('err');m_in.classList.remove('err');m_out.classList.remove('err');m_bat.classList.remove('err');m_btx.classList.remove('err');const t=fromLocalFixed(m_time.value);if(t&&t.length!==19){m_time.classList.add('err');ok=false}if(!nonNegInt(m_in.value)){m_in.classList.add('err');ok=false}if(!nonNegInt(m_out.value)){m_out.classList.add('err');ok=false}if(!inRange(m_bat.value,0,100)){m_bat.classList.add('err');ok=false}if(!inRange(m_btx.value,0,100)){m_btx.classList.add('err');ok=false}if(!ok){showToast('数据不合法');return}const cells=editingRow.querySelectorAll('td');let inc=parseInt(cells[1].textContent||'0');let outc=parseInt(cells[2].textContent||'0');if(m_in.value!=='')inc=parseInt(m_in.value);if(m_out.value!=='')outc=parseInt(m_out.value);const payload={id:editingId};if(t)payload.time=t;if(validInt(inc))payload.in_count=inc;if(validInt(outc))payload.out_count=outc;if(m_bat.value!=='')payload.battery_level=parseInt(m_bat.value);const radio=document.querySelector("input[name='m_txonline']:checked");if(radio)payload.signal_status=parseInt(radio.value);if(m_btx.value!=='')payload.batterytx_level=parseInt(m_btx.value);if(m_rectype.value!=='')payload.rec_type=parseInt(m_rectype.value);const saveBtn=document.getElementById('m_save');saveBtn.disabled=true;saveBtn.textContent='保存中…';try{const res=await fetch('/api/v1/admin/record/update',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':(document.getElementById('histAdminToken')?.value||'')},body:JSON.stringify(payload)});if(res.ok){showToast('保存成功');closeModal();await loadHistory()}else{showToast('保存失败')}}finally{saveBtn.disabled=false;saveBtn.textContent='保存'}});
})();
</script>
</body></html>
"""
    return HTMLResponse(content=html)

@app.get("/admin/db", response_class=HTMLResponse)
async def page_admin_db():
    return RedirectResponse("/classification")
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>数据管理</title>
<link rel='stylesheet' href='/static/style.css'>
</head><body>
          <div class='sidebar'><h3>导航</h3><a class='nav-link' href='/dashboard'>数据看板</a><a class='nav-link' href='/history'>历史数据</a><a class='nav-link' href='/classification'>设备分类</a><a class='nav-link' href='/alerts'>告警中心</a></div>
<div class='main'>
  <h2>数据库记录管理</h2>
  <div class='toolbar'>
    <input id='filterUuid' placeholder='设备UUID'>
    <input id='filterStart' type='datetime-local'>
    <input id='filterEnd' type='datetime-local'>
    <input id='adminToken' placeholder='Admin Token'>
    <button class='btn btn-primary' id='query'>查询</button>
    <button class='btn' id='reset'>重置</button>
    <button class='btn btn-primary' id='add'>新增记录</button>
    <button class='btn' id='backup'>备份数据库</button>
    <input id='restoreFile' type='file'>
    <button class='btn' id='restore'>还原数据库</button>
    <button class='btn' id='showAll'>加载全部</button>
    <button class='btn' id='paged'>分页显示</button>
  </div>
  <div class='table-wrap'><table><thead><tr><th>ID</th><th>UUID</th><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>信号</th><th>操作</th></tr></thead><tbody id='adminTbl'></tbody></table></div>
  <div class='toolbar'><button class='btn' id='prev'>上一页</button> <span id='pageInfo'></span> <button class='btn' id='next'>下一页</button></div>
</div>
<script>
document.querySelectorAll('.sidebar a').forEach(a=>{if(a.getAttribute('href')===location.pathname){a.classList.add('active');}});
const adminTbl=document.getElementById('adminTbl');const filterUuid=document.getElementById('filterUuid');const filterStart=document.getElementById('filterStart');const filterEnd=document.getElementById('filterEnd');const pageInfo=document.getElementById('pageInfo');let page=1,pageSize=20,total=0,showAll=false;
async function loadAdmin(){const q=new URLSearchParams();if(filterUuid.value)q.append('uuid',filterUuid.value);if(filterStart.value)q.append('start',filterStart.value.replace('T',' '));if(filterEnd.value)q.append('end',filterEnd.value.replace('T',' '));q.append('page',page);q.append('page_size',pageSize);const res=await fetch('/api/v1/admin/records?'+q.toString(),{headers:{'X-Admin-Token':document.getElementById('adminToken').value||''}});const data=await res.json();total=data.total||0;adminTbl.innerHTML='';for(const r of (data.items||[])){const tr=document.createElement('tr');tr.innerHTML=`<td>${r.id}</td><td>${r.uuid||''}</td><td>${r.time||''}</td><td>${r.in_count||''}</td><td>${r.out_count||''}</td><td>${r.battery_level||''}</td><td>${(r.signal_status===0||r.signal_status==='0')?'在线':'离线'}</td><td>${r.warn_status??''}</td><td>${r.batterytx_level??''}</td><td>${r.rec_type??''}</td><td><button class='btn btn-primary' data-id='${r.id}' data-act='edit'>编辑</button> <button class='btn' data-id='${r.id}' data-act='del'>删除</button></td>`;adminTbl.appendChild(tr);}const pages=Math.max(1,Math.ceil(total/pageSize));pageInfo.textContent=`第 ${page}/${pages} 页，共 ${total} 条`;}
document.getElementById('query').addEventListener('click',()=>{page=1;loadAdmin();});document.getElementById('reset').addEventListener('click',()=>{filterUuid.value='';filterStart.value='';filterEnd.value='';page=1;loadAdmin();});document.getElementById('prev').addEventListener('click',()=>{if(page>1){page--;loadAdmin();}});document.getElementById('next').addEventListener('click',()=>{page++;loadAdmin();});document.getElementById('add').addEventListener('click',async()=>{const uuid=prompt('UUID');if(!uuid)return;const time=prompt('时间 YYYY-MM-DD HH:MM:SS',new Date().toISOString().slice(0,19).replace('T',' '));const inc=parseInt(prompt('IN','0')||'0');const outc=parseInt(prompt('OUT','0')||'0');const bat=parseInt(prompt('电量','80')||'0');const sig=parseInt(prompt('信号','1')||'0');await fetch('/api/v1/admin/record/create',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('adminToken').value||''},body:JSON.stringify({uuid,time,in_count:inc,out_count:outc,battery_level:bat,signal_status:sig})});loadAdmin();});
document.getElementById('showAll').addEventListener('click',()=>{showAll=true;pageSize=100000;page=1;loadAdmin();});
document.getElementById('paged').addEventListener('click',()=>{showAll=false;pageSize=20;page=1;loadAdmin();});
adminTbl.addEventListener('click',async(e)=>{const btn=e.target.closest('button');if(!btn)return;const id=parseInt(btn.dataset.id);if(btn.dataset.act==='del'){if(confirm('确认删除?')){await fetch('/api/v1/admin/record/delete',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('adminToken').value||''},body:JSON.stringify({id})});loadAdmin();}}else if(btn.dataset.act==='edit'){const inc=prompt('IN');const outc=prompt('OUT');const bat=prompt('电量');const sig=prompt('信号(0在线/1离线)');const warn=prompt('warn_status');const btx=prompt('Tx电量');const rtype=prompt('记录类型rec_type');const time=prompt('时间 YYYY-MM-DD HH:MM:SS');const payload={id};if(inc)payload.in_count=parseInt(inc);if(outc)payload.out_count=parseInt(outc);if(bat)payload.battery_level=parseInt(bat);if(sig)payload.signal_status=parseInt(sig);if(warn)payload.warn_status=parseInt(warn);if(btx)payload.batterytx_level=parseInt(btx);if(rtype)payload.rec_type=parseInt(rtype);if(time)payload.time=time;await fetch('/api/v1/admin/record/update',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('adminToken').value||''},body:JSON.stringify(payload)});loadAdmin();}});
document.getElementById('backup').addEventListener('click',async()=>{const res=await fetch('/api/v1/admin/backup',{headers:{'X-Admin-Token':document.getElementById('adminToken').value||''}});if(!res.ok){alert('备份失败');return;}const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='infrared.db';a.click();URL.revokeObjectURL(url);});
document.getElementById('restore').addEventListener('click',async()=>{const f=document.getElementById('restoreFile').files[0];if(!f){alert('请选择文件');return;}const fd=new FormData();fd.append('file',f);const res=await fetch('/api/v1/admin/restore',{method:'POST',headers:{'X-Admin-Token':document.getElementById('adminToken').value||''},body:fd});if(res.ok){alert('还原成功');}else{alert('还原失败');}loadAdmin();});
(async()=>{await loadAdmin();})();
</script>
</body></html>
"""
    return HTMLResponse(content=html)

@app.get("/classification", response_class=HTMLResponse)
async def page_classification():
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>设备分类</title>
<link rel='stylesheet' href='/static/style.css'>
</head><body>
          <div class='sidebar'><h3>导航</h3><a class='nav-link' href='/dashboard'>数据看板</a><a class='nav-link' href='/history'>历史数据</a><a class='nav-link' href='/classification'>设备分类</a><a class='nav-link' href='/alerts'>告警中心</a></div>
<div class='main'>
  <h2>设备分类与名称管理</h2>
  <div class='toolbar'>
    <input id='regCategory' placeholder='分类'>
    <input id='regSearch' placeholder='搜索UUID/名称'>
    <input id='regToken' placeholder='Admin Token'>
    <button class='btn btn-primary' id='regQuery'>查询</button>
  </div>
  <div class='table-wrap'><table><thead><tr><th>UUID</th><th>名称</th><th>分类</th><th>操作</th></tr></thead><tbody id='regTbl'></tbody></table></div>
  <div class='toolbar'><button class='btn' id='regPrev'>上一页</button> <span id='regPageInfo'></span> <button class='btn' id='regNext'>下一页</button></div>
</div>
<div id='editModal' class='modal-backdrop'><div class='modal'><h3>编辑设备名称</h3><input id='editName' placeholder='显示名称(<=32)'><div class='toolbar'><button class='btn' id='editCancel'>取消</button><button class='btn btn-primary' id='editSave'>保存</button></div></div></div>
<div id='editCatModal' class='modal-backdrop'><div class='modal'><h3>编辑设备分类</h3><input id='editCategory' placeholder='设备分类(<=32)'><div class='toolbar'><button class='btn' id='editCatCancel'>取消</button><button class='btn btn-primary' id='editCatSave'>保存</button></div></div></div>
<div id='regToast' class='toast'></div>
<script>
document.querySelectorAll('.sidebar a').forEach(a=>{if(a.getAttribute('href')===location.pathname){a.classList.add('active');}});
const regTbl=document.getElementById('regTbl');const regCategory=document.getElementById('regCategory');const regSearch=document.getElementById('regSearch');const regToken=document.getElementById('regToken');const regPageInfo=document.getElementById('regPageInfo');let regPage=1,regPageSize=20;
async function loadRegistry(){const q=new URLSearchParams();if(regCategory.value)q.append('category',regCategory.value);if(regSearch.value)q.append('search',regSearch.value);q.append('page',regPage);q.append('page_size',regPageSize);const res=await fetch('/api/v1/admin/device/registry?'+q.toString(),{headers:{'X-Admin-Token':regToken.value||''}});const data=await res.json();regTbl.innerHTML='';for(const r of (data.items||[])){const tr=document.createElement('tr');tr.innerHTML=`<td>${r.uuid}</td><td>${r.name||''}</td><td>${r.category||''}</td><td><button class='btn btn-primary' data-act='editName' data-uuid='${r.uuid}' data-name='${r.name||''}'>修改名称</button> <button class='btn' data-act='editCategory' data-uuid='${r.uuid}' data-category='${r.category||''}'>修改分类</button></td>`;regTbl.appendChild(tr);}regPageInfo.textContent=`第 ${regPage} 页`;}
function toast(t){const el=document.getElementById('regToast');el.textContent=t;el.style.display='block';setTimeout(()=>el.style.display='none',1500)}
function validName(n){if(!n) return true; if(n.length>32) return false; return /^[\u4e00-\u9fa5A-Za-z0-9 _-]{0,32}$/.test(n)}
function validCategory(n){if(!n) return true; if(n.length>32) return false; return /^[\u4e00-\u9fa5A-Za-z0-9 _-]{0,32}$/.test(n)}
let editingUuid='', csrfToken='';
async function ensureCsrf(){if(csrfToken) return csrfToken; try{const r=await fetch('/api/v1/csrf'); const j=await r.json(); csrfToken=j.token||'';}catch(e){} return csrfToken}
function showModal(uuid,name){editingUuid=uuid;document.getElementById('editName').value=name||'';document.getElementById('editModal').style.display='flex'}
function hideModal(){document.getElementById('editModal').style.display='none'}
function showCatModal(uuid,cat){editingUuid=uuid;document.getElementById('editCategory').value=cat||'';document.getElementById('editCatModal').style.display='flex'}
function hideCatModal(){document.getElementById('editCatModal').style.display='none'}
document.getElementById('editCancel').addEventListener('click',hideModal)
document.getElementById('editSave').addEventListener('click',async()=>{const name=document.getElementById('editName').value.trim();if(!validName(name)){toast('名称不合法');return}await ensureCsrf();const ok=await fetch('/api/v1/admin/device/registry/'+editingUuid,{method:'PATCH',headers:{'Content-Type':'application/json','X-Admin-Token':regToken.value||'','X-CSRF-Token':csrfToken},body:JSON.stringify({name})});if(ok.ok){toast('保存成功');hideModal();loadRegistry();}else{toast('保存失败')}})
document.getElementById('editCatCancel').addEventListener('click',hideCatModal)
document.getElementById('editCatSave').addEventListener('click',async()=>{const category=document.getElementById('editCategory').value.trim();if(!validCategory(category)){toast('分类不合法');return}await ensureCsrf();const ok=await fetch('/api/v1/admin/device/registry/'+editingUuid,{method:'PATCH',headers:{'Content-Type':'application/json','X-Admin-Token':regToken.value||'','X-CSRF-Token':csrfToken},body:JSON.stringify({category})});if(ok.ok){toast('保存成功');hideCatModal();loadRegistry();}else{toast('保存失败')}})
document.getElementById('regQuery').addEventListener('click',()=>{regPage=1;loadRegistry();});document.getElementById('regPrev').addEventListener('click',()=>{if(regPage>1){regPage--;loadRegistry();}});document.getElementById('regNext').addEventListener('click',()=>{regPage++;loadRegistry();});
regTbl.addEventListener('click',(e)=>{const b=e.target.closest('button');if(!b)return; if(b.dataset.act==='editName'){showModal(b.dataset.uuid,b.dataset.name)}else if(b.dataset.act==='editCategory'){showCatModal(b.dataset.uuid,b.dataset.category)}})
(async()=>{await loadRegistry();})();
</script>
</body></html>
"""
    return HTMLResponse(content=html)

@app.get("/alerts", response_class=HTMLResponse)
async def page_alerts():
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>告警中心</title>
<link rel='stylesheet' href='/static/style.css'>
</head><body>
          <div class='sidebar'><h3>导航</h3><a class='nav-link' href='/dashboard'>数据看板</a><a class='nav-link' href='/history'>历史数据</a><a class='nav-link' href='/classification'>设备分类</a><a class='nav-link' href='/alerts'>告警中心</a></div>
<div class='main'>
  <h2>告警中心</h2>
  <div class='toolbar'>
    <input id='alertUuid' placeholder='设备UUID'>
    <input id='alertLimit' type='number' value='100'>
    <button class='btn' id='alertQuery'>查询</button>
  </div>
  <div class='table-wrap'><table><thead><tr><th>ID</th><th>UUID</th><th>类型</th><th>等级</th><th>信息</th><th>时间</th></tr></thead><tbody id='alertTbl'></tbody></table></div>
</div>
<script>
document.querySelectorAll('.sidebar a').forEach(a=>{if(a.getAttribute('href')===location.pathname){a.classList.add('active');}});
const alertTbl=document.getElementById('alertTbl');const alertUuid=document.getElementById('alertUuid');const alertLimit=document.getElementById('alertLimit');
async function loadAlerts(){const q=new URLSearchParams();if(alertUuid.value)q.append('uuid',alertUuid.value);q.append('limit',alertLimit.value||'100');const res=await fetch('/api/v1/alerts?'+q.toString());const data=await res.json();alertTbl.innerHTML='';for(const r of (data||[])){const tr=document.createElement('tr');tr.innerHTML=`<td>${r.id}</td><td>${r.uuid}</td><td>${r.type}</td><td>${r.level}</td><td>${r.info}</td><td>${r.time}</td>`;alertTbl.appendChild(tr);}}
document.getElementById('alertQuery').addEventListener('click',loadAlerts);
(async()=>{await loadAlerts();})();
</script>
</body></html>
"""
    return HTMLResponse(content=html)

@app.get("/recent", response_class=HTMLResponse)
async def page_recent():
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>最近记录</title>
<link rel='stylesheet' href='/static/style.css'>
<style>
body{margin:0}
.wrap{width:98vw;margin:0 auto;padding:8px}
h2{margin:8px 0 6px;font-size:18px}
.toolbar{margin:6px 0}
.table-wrap{min-height:calc(100vh - 70px);height:auto;overflow:visible;border-radius:10px}
</style>
</head><body>
<div class='wrap'>
  <h2>最近记录</h2>
  <div class='toolbar'>
    <input id='filterUuid' placeholder='设备UUID'>
    <input id='filterStart' type='datetime-local'>
    <input id='filterEnd' type='datetime-local'>
    <input id='filterWarn' type='number' placeholder='warn_status'>
    <input id='filterRecType' type='number' placeholder='rec_type'>
    <input id='filterBtxMin' type='number' placeholder='Tx电量最小'>
    <input id='filterBtxMax' type='number' placeholder='Tx电量最大'>
    <input id='adminToken' placeholder='Admin Token'>
    <button class='btn btn-primary' id='query'>查询</button>
    <button class='btn' id='reset'>重置</button>
    <button class='btn btn-danger' id='delRange'>删除区间</button>
  </div>
  <div class='table-wrap'><table style='width:100%'><thead><tr><th>ID</th><th>UUID</th><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>发射端是否在线</th><th>Tx电量</th><th>记录类型</th><th>操作</th></tr></thead><tbody id='adminTbl'></tbody></table></div>
  
</div>
<script>
const adminTbl=document.getElementById('adminTbl');const filterUuid=document.getElementById('filterUuid');const filterStart=document.getElementById('filterStart');const filterEnd=document.getElementById('filterEnd');const filterWarn=document.getElementById('filterWarn');const filterRecType=document.getElementById('filterRecType');const filterBtxMin=document.getElementById('filterBtxMin');const filterBtxMax=document.getElementById('filterBtxMax');let pageSize=100000;function fmtTxOnline(s){return (s===0||s==='0')?'在线':'离线'}function fmtRecType(t){return (t===1||t==='1')?'实时数据':(t===2||t==='2')?'历史数据':(t??'')}
async function loadAdmin(){const q=new URLSearchParams();if(filterUuid.value)q.append('uuid',filterUuid.value);if(filterStart.value)q.append('start',filterStart.value.replace('T',' '));if(filterEnd.value)q.append('end',filterEnd.value.replace('T',' '));if(filterWarn.value)q.append('warn_status',filterWarn.value);if(filterRecType.value)q.append('rec_type',filterRecType.value);if(filterBtxMin.value)q.append('batterytx_min',filterBtxMin.value);if(filterBtxMax.value)q.append('batterytx_max',filterBtxMax.value);q.append('page_size',pageSize);const res=await fetch('/api/v1/admin/records?'+q.toString(),{headers:{'X-Admin-Token':document.getElementById('adminToken').value||''}});const data=await res.json();adminTbl.innerHTML='';for(const r of (data.items||[])){const tr=document.createElement('tr');tr.innerHTML=`<td>${r.id}</td><td>${r.uuid||''}</td><td>${r.time||''}</td><td>${r.in_count??''}</td><td>${r.out_count??''}</td><td>${r.battery_level??''}</td><td>${fmtTxOnline(r.warn_status)}</td><td>${r.batterytx_level??''}</td><td>${fmtRecType(r.rec_type)}</td><td><button class='btn btn-primary' data-id='${r.id}' data-act='edit'>编辑</button> <button class='btn' data-id='${r.id}' data-act='del'>删除</button></td>`;adminTbl.appendChild(tr);} }
document.getElementById('query').addEventListener('click',()=>{loadAdmin();});
document.getElementById('reset').addEventListener('click',()=>{filterUuid.value='';filterStart.value='';filterEnd.value='';filterWarn.value='';filterRecType.value='';filterBtxMin.value='';filterBtxMax.value='';loadAdmin();});
adminTbl.addEventListener('click',async(e)=>{const btn=e.target.closest('button');if(!btn)return;const id=parseInt(btn.dataset.id);if(btn.dataset.act==='del'){if(confirm('确认删除?')){await fetch('/api/v1/admin/record/delete',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('adminToken').value||''},body:JSON.stringify({id})});loadAdmin();}}else if(btn.dataset.act==='edit'){const inc=prompt('IN');const outc=prompt('OUT');const bat=prompt('电量');const sig=prompt('信号');const time=prompt('时间 YYYY-MM-DD HH:MM:SS');const payload={id};if(inc)payload.in_count=parseInt(inc);if(outc)payload.out_count=parseInt(outc);if(bat)payload.battery_level=parseInt(bat);if(sig)payload.signal_status=parseInt(sig);if(time)payload.time=time;await fetch('/api/v1/admin/record/update',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('adminToken').value||''},body:JSON.stringify(payload)});loadAdmin();}});
document.getElementById('delRange').addEventListener('click',async()=>{const uuid=filterUuid.value.trim();const start=filterStart.value?filterStart.value.replace('T',' '):'';const end=filterEnd.value?filterEnd.value.replace('T',' '):'';if(!uuid||!start||!end){alert('请填写UUID、开始和结束时间');return}const ok=confirm(`确认删除区间 ${start} ~ ${end} 的记录?`);if(!ok)return;const res=await fetch('/api/v1/admin/records/delete-range',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('adminToken').value||''},body:JSON.stringify({uuid,start,end})});if(res.ok){alert('删除完成');page=1;loadAdmin();}else{alert('删除失败')}});
(async()=>{await loadAdmin();})();
</script>
</body></html>
"""
    return HTMLResponse(content=html)

@app.get("/api/v1/admin/records")
async def admin_records(request: Request, uuid: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None, page: int = 1, page_size: int = 20, warn_status: Optional[int] = None, rec_type: Optional[int] = None, batterytx_min: Optional[int] = None, batterytx_max: Optional[int] = None):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    if page < 1: page = 1
    if page_size < 1: page_size = 20
    total = await admin_count_records(uuid, start, end, warn_status, rec_type, batterytx_min, batterytx_max)
    offset = (page - 1) * page_size
    items = await admin_list_records(uuid, start, end, offset, page_size, warn_status, rec_type, batterytx_min, batterytx_max)
    return {"total": total, "items": items, "page": page, "page_size": page_size}

@app.post("/api/v1/admin/record/update")
async def admin_record_update(request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    rid = int(payload.get("id"))
    fields = {k: payload.get(k) for k in ["uuid","in_count","out_count","time","battery_level","signal_status","warn_status","batterytx_level","rec_type"] if k in payload}
    if "time" in fields and fields["time"]:
        # 尝试将时间格式化为纯数字格式 YYYYMMDDHHMMSS
        # 前端传来的是 YYYY-MM-DD HH:MM:SS，需要去除分隔符
        t = str(fields["time"]).strip()
        t = t.replace("-", "").replace(":", "").replace(" ", "")
        fields["time"] = t
    ok = await admin_update_record(rid, fields)
    return {"ok": ok}

@app.post("/api/v1/admin/record/delete")
async def admin_record_delete(request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    rid = int(payload.get("id"))
    ok = await admin_delete_record(rid)
    return {"ok": ok}

@app.post("/api/v1/admin/records/delete-range")
async def admin_records_delete_range(request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    uuid = str(payload.get("uuid", "") or "")
    start = str(payload.get("start", "") or "")
    end = str(payload.get("end", "") or "")
    if not uuid or not start or not end:
        return Response(status_code=400)
    cnt = await admin_delete_range(uuid, start, end)
    return {"ok": True, "deleted": cnt}

@app.post("/api/v1/admin/record/create")
async def admin_record_create(request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    rid = await admin_create_record(payload)
    return {"id": rid}

@app.get("/api/v1/admin/device/registry")
async def admin_device_registry(request: Request, category: Optional[str] = None, search: Optional[str] = None, page: int = 1, page_size: int = 20):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    if page < 1: page = 1
    if page_size < 1: page_size = 20
    offset = (page - 1) * page_size
    items = await admin_list_registry(category, search, offset, page_size)
    return {"items": items, "page": page, "page_size": page_size}

@app.post("/api/v1/admin/device/registry/upsert")
async def admin_device_registry_upsert(request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    if config.CSRF_ENABLE and not validate_csrf(request.headers.get("X-CSRF-Token", "")):
        return Response(status_code=403)
    uuid = payload.get("uuid")
    name = payload.get("name")
    category = payload.get("category")
    if name is not None:
        nm = str(name)
        if len(nm) > 32:
            return Response(status_code=400)
        import re
        if not re.match(r"^[\u4e00-\u9fa5A-Za-z0-9 _-]{0,32}$", nm):
            return Response(status_code=400)
    ok = await admin_upsert_registry(uuid, name, category)
    try:
        actor = request.headers.get("X-Admin-Token", "")
        await admin_write_op(actor, "registry_upsert", uuid, str(payload))
    except Exception:
        pass
    return {"ok": ok}

@app.get("/api/v1/csrf")
async def get_csrf():
    return {"token": issue_csrf()}

@app.put("/api/v1/admin/device/registry/{uuid}")
async def admin_device_registry_put(uuid: str, request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    if config.CSRF_ENABLE and not validate_csrf(request.headers.get("X-CSRF-Token", "")):
        return Response(status_code=403)
    name = payload.get("name")
    category = payload.get("category")
    if name is not None:
        nm = str(name)
        if len(nm) > 32:
            return Response(status_code=400)
        import re
        if not re.match(r"^[\u4e00-\u9fa5A-Za-z0-9 _-]{0,32}$", nm):
            return Response(status_code=400)
    ok = await admin_upsert_registry(uuid, name, category)
    try:
        actor = request.headers.get("X-Admin-Token", "")
        await admin_write_op(actor, "registry_put", uuid, str(payload))
    except Exception:
        pass
    return {"ok": ok}

@app.patch("/api/v1/admin/device/registry/{uuid}")
async def admin_device_registry_patch(uuid: str, request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    if config.CSRF_ENABLE and not validate_csrf(request.headers.get("X-CSRF-Token", "")):
        return Response(status_code=403)
    name = payload.get("name")
    category = payload.get("category")
    if name is not None:
        nm = str(name)
        if len(nm) > 32:
            return Response(status_code=400)
        import re
        if not re.match(r"^[\u4e00-\u9fa5A-Za-z0-9 _-]{0,32}$", nm):
            return Response(status_code=400)
    ok = await admin_upsert_registry(uuid, name, category)
    try:
        actor = request.headers.get("X-Admin-Token", "")
        await admin_write_op(actor, "registry_patch", uuid, str(payload))
    except Exception:
        pass
    return {"ok": ok}

@app.get("/api/v1/alerts")
async def alerts(uuid: Optional[str] = None, limit: int = 100):
    return await list_alerts(uuid, limit)

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    uuid = None
    q = None
    try:
        msg = await ws.receive_json()
        uuid = msg.get("uuid")
        q = await bus.subscribe(uuid)
        await ws.send_json({"type": "subscribed", "uuid": uuid})
        while True:
            item = await q.get()
            await ws.send_json(item)
    except Exception:
        pass
    finally:
        if uuid and q:
            await bus.unsubscribe(uuid, q)

# 导出CSV
def _csv_response(name: str, csv_text: str):
    return Response(content=csv_text, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={name}"})

@app.get("/api/v1/export/daily")
async def export_daily(uuid: str, start: Optional[str] = None, end: Optional[str] = None):
    rows = await db_stats_daily(uuid, start, end)
    csv = "day,in_total,out_total,net\n" + "\n".join([f"{r['day']},{r['in_total'] or 0},{r['out_total'] or 0},{(r['in_total'] or 0)-(r['out_total'] or 0)}" for r in rows])
    return _csv_response("daily.csv", csv)

@app.get("/api/v1/export/hourly")
async def export_hourly(uuid: str, date: str):
    rows = await db_stats_hourly(uuid, date)
    csv = "hour,in_total,out_total,net\n" + "\n".join([f"{r['hour']},{r['in_total'] or 0},{r['out_total'] or 0},{(r['in_total'] or 0)-(r['out_total'] or 0)}" for r in rows])
    return _csv_response("hourly.csv", csv)

@app.get("/api/v1/export/history")
async def export_history(uuid: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 10000):
    rows = await fetch_history(uuid, start, end, limit)
    def row_to_csv(r):
        t = r.get('time') if isinstance(r, dict) else r[3]
        inc = r.get('in_count') if isinstance(r, dict) else r[1]
        outc = r.get('out_count') if isinstance(r, dict) else r[2]
        bat = r.get('battery_level') if isinstance(r, dict) else r[4]
        sig = r.get('signal_status') if isinstance(r, dict) else r[5]
        warn = r.get('warn_status') if isinstance(r, dict) else (r[6] if len(r)>6 else '')
        btx = r.get('batterytx_level') if isinstance(r, dict) else (r[7] if len(r)>7 else '')
        rt = r.get('rec_type') if isinstance(r, dict) else (r[8] if len(r)>8 else '')
        return f"{t},{inc or ''},{outc or ''},{bat or ''},{sig or ''},{warn or ''},{btx or ''},{rt or ''}"
    csv = "time,in_count,out_count,battery_level,signal_status,warn_status,batterytx_level,rec_type\n" + "\n".join([row_to_csv(r) for r in rows])
    return _csv_response("history.csv", csv)

# Top榜统计
@app.get("/api/v1/stats/top")
async def stats_top(metric: str = "in", start: Optional[str] = None, end: Optional[str] = None, limit: int = 10):
    return await db_stats_top(metric, start, end, limit)

def _require_admin(req: Request):
    if config.ADMIN_TOKEN:
        t = req.headers.get("X-Admin-Token", "")
        return t == config.ADMIN_TOKEN
    return True

@app.get("/api/v1/admin/backup")
async def admin_backup(req: Request):
    if not _require_admin(req):
        return Response(status_code=403)
    if str(getattr(config, "DB_DRIVER", "sqlite")).lower() != "sqlite":
        return Response(status_code=400)
    p = config.DB_SQLITE_PATH
    if not os.path.exists(p):
        return Response(status_code=404)
    return FileResponse(path=p, filename="infrared.db", media_type="application/octet-stream")

@app.post("/api/v1/admin/restore")
async def admin_restore(req: Request, file: UploadFile):
    if not _require_admin(req):
        return Response(status_code=403)
    if str(getattr(config, "DB_DRIVER", "sqlite")).lower() != "sqlite":
        return Response(status_code=400)
    data = await file.read()
    from app.db import close_sqlite, init_sqlite
    await close_sqlite()
    os.makedirs(os.path.dirname(config.DB_SQLITE_PATH), exist_ok=True)
    with open(config.DB_SQLITE_PATH, "wb") as f:
        f.write(data)
    await init_sqlite()
    return {"ok": True}
@app.get("/device", response_class=HTMLResponse)
async def device_page():
    return RedirectResponse("/classification")
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>设备管理</title>
<link rel='stylesheet' href='/static/style.css'>
</head><body>
  <div class='sidebar'><h3>导航</h3><a class='nav-link' href='/dashboard'>数据看板</a><a class='nav-link' href='/history'>历史数据</a><a class='nav-link' href='/admin/db'>数据管理</a><a class='nav-link' href='/classification'>设备分类</a><a class='nav-link' href='/alerts'>告警中心</a><a class='nav-link' href='/device'>设备编辑</a></div>
  <div class='main'>
  <div class="card" style='max-width:920px'>
    <h2>设备名称自定义</h2>
    <div class="row">
      <input id="dev_uuid" placeholder="设备UUID">
      <input id="dev_name" placeholder="显示名称(<=32)">
      <input id="dev_category" placeholder="设备分类">
    </div>
    <div class="row">
      <button class="btn" id="dev_reset">重置</button>
      <button class="btn btn-primary" id="dev_save">保存</button>
      <span id="dev_loading" style="display:none">保存中...</span>
    </div>
    <div class="row">
      <input id="dev_adminToken" placeholder="Admin Token">
    </div>
    <div id="dev_toast" class="toast" style="display:none"></div>
  </div>
  <script>
    let csrfToken='';
    function toastMsg(t){const el=document.getElementById('dev_toast');el.textContent=t;el.style.display='block';setTimeout(()=>el.style.display='none',2000)}
    function validName(nm){if(!nm) return true; if(nm.length>32) return false; return /^[\u4e00-\u9fa5A-Za-z0-9 _-]{0,32}$/.test(nm)}
    async function fetchCsrf(){try{const r=await fetch('/api/v1/csrf');const j=await r.json();csrfToken=j.token||'';}catch(e){}}
    document.getElementById('dev_reset').addEventListener('click',()=>{document.getElementById('dev_name').value='';document.getElementById('dev_category').value='';});
    document.getElementById('dev_save').addEventListener('click',async()=>{
      const uuid=document.getElementById('dev_uuid').value.trim();
      const name=document.getElementById('dev_name').value.trim();
      const category=document.getElementById('dev_category').value.trim();
      const adminToken=document.getElementById('dev_adminToken').value||'';
      if(!uuid){toastMsg('请输入UUID');return}
      if(!validName(name)){toastMsg('名称不合法');return}
      document.getElementById('dev_loading').style.display='inline';
      try{
        const res=await fetch('/api/v1/admin/device/registry/upsert',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':adminToken,'X-CSRF-Token':csrfToken},body:JSON.stringify({uuid,name,category})});
        if(res.ok){toastMsg('保存成功'); await fetchCsrf()}else{toastMsg('保存失败')}
      }finally{document.getElementById('dev_loading').style.display='none'}
    });
    (async()=>{await fetchCsrf()})()
  </script>
</div>
<script>document.querySelectorAll('.sidebar a').forEach(a=>{if(a.getAttribute('href')===location.pathname){a.classList.add('active');}});</script>
</body></html>
"""
    return HTMLResponse(content=html)
@app.post("/api/v1/device/time-sync/request")
async def request_time_sync(payload: dict = Body(...)):
    uuid = str(payload.get("uuid", "")).strip()
    if not uuid:
        return {"ok": False}
    os.makedirs(os.path.join("data", "sync"), exist_ok=True)
    p = os.path.join("data", "sync", f"{uuid}.flag")
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write("1")
        return {"ok": True}
    except Exception:
        return {"ok": False}
