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
from app.db import init_pool, close_pool, fetch_latest, fetch_history, list_devices as db_list_devices, stats_daily as db_stats_daily, stats_hourly as db_stats_hourly, stats_summary as db_stats_summary, stats_top as db_stats_top, stats_total as db_stats_total, admin_count_records, admin_list_records, admin_update_record, admin_delete_record, admin_create_record, list_alerts, admin_list_registry, admin_upsert_registry, admin_write_op, admin_delete_range, admin_get_categories, admin_get_uuids, get_device_mapping
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
    return await page_board()

@app.get("/board", response_class=HTMLResponse)
async def page_board():
    html = """
<!doctype html><html><head><meta charset='utf-8'><title>数据看板</title>
<link rel="stylesheet" href="/static/style.css">
<script src="/static/chart.umd.min.js"></script>
<script src="/static/dashboard.js" defer></script>

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
      <div class='filter-row' style='justify-content:space-between;margin-bottom:0'>
        <div style='display:flex;gap:12px;align-items:center;flex-wrap:wrap'>
          <label>设备</label>
          <select id='device' style='width:180px'></select>
          <div class="ant-picker ant-picker-range"><div class="ant-picker-input"><input id='start' type='date' placeholder='开始日期' size='12' autocomplete='off'></div><div class="ant-picker-range-separator"><span aria-label='to' class='ant-picker-separator'><span role='img' aria-label='swap-right' class='anticon anticon-swap-right'><svg focusable='false' data-icon='swap-right' width='1em' height='1em' fill='currentColor' aria-hidden='true' viewBox='0 0 1024 1024'><path d='M873.1 596.2l-164-208A32 32 0 00684 376h-64.8c-6.7 0-10.4 7.7-6.3 13l144.3 183H152c-4.4 0-8 3.6-8 8v60c0 4.4 3.6 8 8 8h695.9c26.8 0 41.7-30.8 25.2-51.8z'></path></svg></span></span></div><div class="ant-picker-input"><input id='end' type='date' placeholder='结束日期' size='12' autocomplete='off'></div></div>
          <button id='load' class='btn btn-primary'>加载数据</button>
          <button id='resetFilter' class='btn'>重置</button>
        </div>
        <div class='filter-actions' style='position:relative;gap:8px'>
          <button id='today' class='btn'>今天</button>
          <button id='last7' class='btn'>最近7天</button>
          <div style='display:flex;align-items:center;gap:6px;padding:0 8px;border:1px solid var(--border);border-radius:var(--radius);height:38px;background:var(--bg)'>
             <input type='checkbox' id='auto' style='margin:0;width:16px;height:16px'>
             <label for='auto' style='margin:0;cursor:pointer;font-size:0.85rem;user-select:none'>自动刷新</label>
          </div>
          <button id='refreshLatest' class='btn'>加载最新</button>
          <button id='toggleAdvanced' class='btn'>高级筛选</button>
          <button id='toggleActions' class='btn'>更多操作</button>
          <button id='themeToggle' class='btn'>主题</button>
          
          <div id='advancedPopup' class='popup-card' style='right:0;left:auto;width:320px;top:110%'>
             <div class='form-grid'>
               <div class='form-row'>
                 <label>告警状态</label>
                 <input id='filterWarn' type='number' class='input' placeholder='warn_status'>
               </div>
               <div class='form-row'>
                 <label>记录类型</label>
                 <input id='filterRecType' type='number' class='input' placeholder='rec_type'>
               </div>
               <div class='form-row full'>
                 <label>Tx电量范围</label>
                 <div style='display:flex;gap:8px'>
                   <input id='filterBtxMin' type='number' class='input' placeholder='Min' style='flex:1'>
                   <input id='filterBtxMax' type='number' class='input' placeholder='Max' style='flex:1'>
                 </div>
               </div>
             </div>
          </div>

          <div id='actionsPopup' class='popup-card' style='right:0;left:auto;width:240px;top:110%'>
             <div style='display:flex;flex-direction:column;gap:8px'>
                <button id='exportDaily' class='btn' style='width:100%;justify-content:flex-start'>📄 导出日统计CSV</button>
                <button id='exportHourly' class='btn' style='width:100%;justify-content:flex-start'>📄 导出小时统计CSV</button>
                <button id='exportHistory' class='btn' style='width:100%;justify-content:flex-start'>📄 导出历史CSV</button>
                <hr style='width:100%;border:0;border-top:1px solid var(--border);margin:4px 0'>
                <button id='runToastTests' class='btn' style='width:100%;justify-content:flex-start'>🧪 消息系统测试</button>
                <button id='runAnimPerf' class='btn' style='width:100%;justify-content:flex-start'>⚡ 动画性能测试</button>
             </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class='row'><div class='card'><canvas id='dailyChart' style='height:320px'></canvas></div><div class='card'><canvas id='hourChart' style='height:320px'></canvas></div></div>
  <div class='grid' style='margin-top:16px'><div class='mini' id='sum_in'>IN总计：</div><div class='mini' id='sum_out'>OUT总计：</div><div class='mini' id='sum_net'>净流量：</div><div class='mini' id='sum_last'>最近上报：</div></div>
  <div class='card' style='margin-top:16px'><h3><a href='/history' style='text-decoration:none;color:inherit'>设备记录</a></h3><div class='table-wrap'><table><thead><tr><th>时间</th><th>IN</th><th>OUT</th><th>电量</th><th>发射端是否在线</th><th>Tx电量</th><th>记录类型</th></tr></thead><tbody id='tbl'></tbody></table></div></div>
</div>




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
  <div class='filters'>
    <div class='filter-card'>
      <h4>查询</h4>
      <div class='filter-row'>
        <label>设备</label>
        <select id='device' style='min-width:200px'></select>
        <label>日期范围</label>
        <div class="ant-picker ant-picker-range">
          <div class="ant-picker-input"><input id='start' type='date' placeholder='开始' size='12'></div>
          <div class="ant-picker-range-separator"><span>-</span></div>
          <div class="ant-picker-input"><input id='end' type='date' placeholder='结束' size='12'></div>
        </div>
      </div>
      <div class='filter-actions' style='position:relative'>
        <button id='query' class='btn btn-primary'>查询</button>
        <button id='reset' class='btn'>重置</button>
        <button id='toggleAdvanced' class='btn'>高级筛选</button>
        <button id='dataCompletion' class='btn btn-primary' style='background-color:#0ca678;border-color:#0ca678'>数据补全</button>
        
        <div id='advancedPopup' class='popup-card'>
           <div class='form-grid'>
             <div class='form-row'>
               <label>告警状态 (0/1)</label>
               <input id='filterWarn' type='number' class='input' placeholder='warn_status'>
             </div>
             <div class='form-row'>
               <label>记录类型</label>
               <input id='filterRecType' type='number' class='input' placeholder='1:实时 2:历史'>
             </div>
             <div class='form-row full'>
               <label>Tx电量范围</label>
               <div style='display:flex;gap:8px'>
                 <input id='filterBtxMin' type='number' class='input' placeholder='Min' style='flex:1'>
                 <input id='filterBtxMax' type='number' class='input' placeholder='Max' style='flex:1'>
               </div>
             </div>
             <div class='form-row full'>
               <label>Admin Token</label>
               <input id='histAdminToken' class='input' placeholder='输入Token以进行管理操作'>
             </div>
           </div>
        </div>
      </div>
    </div>
  </div>
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
const toggleAdv=document.getElementById('toggleAdvanced');const advPopup=document.getElementById('advancedPopup');
if(toggleAdv && advPopup){
  toggleAdv.addEventListener('click',(e)=>{e.stopPropagation();advPopup.classList.toggle('show')});
  advPopup.addEventListener('click',(e)=>e.stopPropagation());
  document.addEventListener('click',()=>advPopup.classList.remove('show'));
}
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

  <div id='completionModal' class='modal-backdrop'>
    <div class='modal' style='width: min(90vw, 420px);'>
        <h3>数据补全</h3>
        <div style='margin-bottom:20px;color:var(--muted);font-size:14px;line-height:1.5'>请选择需要补全的时间段，系统将从设备拉取数据并与本地记录智能合并。</div>
        <div class='form-grid'>
            <div class='form-row'>
                <label style='font-weight:500;color:var(--text)'>起始时间</label>
                <input id='compStart' class='input' type='datetime-local' step='60'>
            </div>
            <div class='form-row'>
                <label style='font-weight:500;color:var(--text)'>结束时间</label>
                <input id='compEnd' class='input' type='datetime-local' step='60'>
            </div>
        </div>
        <div class='actions'>
            <button class='btn' id='compCancel'>取消</button>
            <button class='btn btn-primary' id='compConfirm'>获取数据</button>
        </div>
    </div>
  </div>

  <div id='mergeModal' class='modal-backdrop' style='z-index:2000;'>
    <div class='modal' style='width:80%;max-width:900px;display:flex;flex-direction:column;max-height:85vh'>
        <h3>合并预览</h3>
        <div class='toolbar' style='margin-bottom:10px'>
            <button class='btn' id='mergeSelectAll' style='padding:4px 10px;font-size:13px'>全选</button>
            <button class='btn' id='mergeDeselectAll' style='padding:4px 10px;font-size:13px'>反选</button>
        </div>
        <div class='table-wrap' style='flex:1;overflow-y:auto;border:1px solid var(--border);border-radius:8px;background:var(--bg)'>
            <table class='table' style='border:none'>
                <thead style='position:sticky;top:0;z-index:10;background:var(--card);box-shadow:0 1px 2px rgba(0,0,0,0.05)'>
                    <tr>
                        <th style='width:60px;text-align:center'>选择</th>
                        <th>时间</th>
                        <th style='width:100px'>IN</th>
                        <th style='width:100px'>OUT</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody id='mergeTbl'></tbody>
            </table>
        </div>
        <div class='actions' style='margin-top:16px;padding-top:16px;border-top:1px solid var(--border)'>
            <button class='btn' id='mergeCancel'>取消</button>
            <button class='btn btn-primary' id='mergeApply'>应用修改</button>
        </div>
    </div>
  </div>
<script>
const compModal=document.getElementById('completionModal');
const mergeModal=document.getElementById('mergeModal');
const compStart=document.getElementById('compStart');
const compEnd=document.getElementById('compEnd');
const mergeTbl=document.getElementById('mergeTbl');
let fetchedData = [];

document.getElementById('dataCompletion').addEventListener('click', ()=>{
    if(!deviceSel.value){ alert('请先选择设备'); return; }
    const now = new Date();
    const ymd = now.toISOString().slice(0,10);
    compStart.value = ymd + 'T00:00';
    compEnd.value = ymd + 'T23:59';
    compModal.classList.add('show');
});

document.getElementById('compCancel').addEventListener('click', ()=>compModal.classList.remove('show'));

document.getElementById('compConfirm').addEventListener('click', async ()=>{
    const uuid = deviceSel.value;
    if(!uuid) return;
    const s = compStart.value;
    const e = compEnd.value;
    if(!s || !e){ alert('请选择时间'); return; }
    
    const btn = document.getElementById('compConfirm');
    btn.disabled = true;
    btn.textContent = '获取中...';
    
    try {
        const resDev = await fetch('/api/v1/admin/device/fetch-history', {
            method: 'POST',
            headers: {'Content-Type':'application/json', 'X-Admin-Token': document.getElementById('histAdminToken').value||''},
            body: JSON.stringify({uuid, start: s.replace('T', ' ') + ':00', end: e.replace('T', ' ') + ':59'})
        });
        if(!resDev.ok) throw new Error('获取设备数据失败');
        const devData = await resDev.json();
        
        const q = new URLSearchParams();
        q.append('uuid', uuid);
        q.append('start', s.replace('T', ' ') + ':00');
        q.append('end', e.replace('T', ' ') + ':59');
        q.append('limit', 10000); 
        const resLoc = await fetch('/api/v1/data/history?' + q.toString());
        if(!resLoc.ok) throw new Error('获取本地数据失败');
        const locData = await resLoc.json();
        
        const locMap = new Map();
        locData.forEach(r => {
            locMap.set(r.time, r);
        });
        
        fetchedData = [];
        for(const d of devData) {
            const t = d.time;
            const loc = locMap.get(t);
            if(loc) {
                fetchedData.push({
                    ...d,
                    _status: 'exist',
                    _local: loc,
                    in_count: loc.in_count??loc.in,
                    out_count: loc.out_count??loc.out
                });
            } else {
                fetchedData.push({
                    ...d,
                    _status: 'new'
                });
            }
        }
        
        renderMergeTable();
        compModal.classList.remove('show');
        mergeModal.classList.add('show');
        
    } catch(err) {
        alert(err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '获取数据';
    }
});

function renderMergeTable() {
    mergeTbl.innerHTML = '';
    fetchedData.forEach((r, idx) => {
        const tr = document.createElement('tr');
        const isNew = r._status === 'new';
        const checked = isNew ? 'checked' : '';
        const statusText = isNew ? '<span style="color:green">新增</span>' : '<span style="color:gray">已存在(保留本地)</span>';
        
        tr.innerHTML = `
            <td><input type='checkbox' class='merge-chk' data-idx='${idx}' ${checked}></td>
            <td>${r.time}</td>
            <td><input type='number' class='input-mini' value='${r.in_count}' onchange='updateFetched(${idx}, "in_count", this.value)' style='width:60px'></td>
            <td><input type='number' class='input-mini' value='${r.out_count}' onchange='updateFetched(${idx}, "out_count", this.value)' style='width:60px'></td>
            <td>${statusText}</td>
        `;
        mergeTbl.appendChild(tr);
    });
}

window.updateFetched = function(idx, field, val) {
    fetchedData[idx][field] = parseInt(val);
};

document.getElementById('mergeSelectAll').addEventListener('click', ()=>{
    document.querySelectorAll('.merge-chk').forEach(c => c.checked = true);
});
document.getElementById('mergeDeselectAll').addEventListener('click', ()=>{
    document.querySelectorAll('.merge-chk').forEach(c => c.checked = !c.checked);
});
document.getElementById('mergeCancel').addEventListener('click', ()=>mergeModal.classList.remove('show'));

document.getElementById('mergeApply').addEventListener('click', async ()=>{
    const chks = document.querySelectorAll('.merge-chk:checked');
    if(chks.length === 0) { alert('未选择任何记录'); return; }
    
    const toMerge = [];
    chks.forEach(c => {
        const idx = parseInt(c.dataset.idx);
        const r = fetchedData[idx];
        const payload = {
            uuid: r.uuid,
            time: r.time,
            in_count: r.in_count,
            out_count: r.out_count,
            battery_level: r.battery_level,
            signal_status: r.signal_status,
            warn_status: r.warn_status,
            batterytx_level: r.batterytx_level,
            rec_type: r.rec_type
        };
        if(r._local && r._local.id) {
            payload.id = r._local.id;
        }
        toMerge.push(payload);
    });
    
    const btn = document.getElementById('mergeApply');
    btn.disabled = true;
    btn.textContent = '应用中...';
    
    try {
        const res = await fetch('/api/v1/admin/device/merge-history', {
            method: 'POST',
            headers: {'Content-Type':'application/json', 'X-Admin-Token': document.getElementById('histAdminToken').value||''},
            body: JSON.stringify({records: toMerge})
        });
        if(!res.ok) throw new Error('合并失败');
        const ret = await res.json();
        alert(`成功合并 ${ret.count} 条记录`);
        mergeModal.classList.remove('show');
        loadHistory();
    } catch(e) {
        alert(e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '应用修改';
    }
});
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
  <div class='filters'>
    <div class='filter-card'>
      <h4>查询与管理</h4>
      <div class='filter-row'>
        <select id='regCategory' style='width:160px;height:38px;border:1px solid var(--border);border-radius:var(--radius);padding:0 8px;outline:none'>
           <option value=''>全部分类</option>
        </select>
        <input id='regSearch' placeholder='搜索UUID/名称' style='width:200px'>
        <input id='regToken' placeholder='Admin Token' style='width:160px'>
        <button class='btn btn-primary' id='regQuery'>查询</button>
        <button class='btn' id='regAdd'>+ 新增/注册设备</button>
      </div>
    </div>
  </div>
  <div class='table-wrap'><table><thead><tr><th>UUID</th><th>名称</th><th>分类</th><th style='width:120px'>操作</th></tr></thead><tbody id='regTbl'></tbody></table></div>
  <div class='toolbar' style='margin-top:16px;justify-content:flex-end'>
    <button class='btn' id='regPrev'>上一页</button> 
    <span id='regPageInfo' style='display:flex;align-items:center;padding:0 8px;font-weight:500;color:var(--text-secondary)'></span> 
    <button class='btn' id='regNext'>下一页</button>
  </div>
</div>

<div id='deviceModal' class='modal-backdrop'>
  <div class='modal'>
    <h3 id='modalTitle'>编辑设备</h3>
    <div class='form-grid'>
      <div class='form-row'>
        <label>设备UUID</label>
        <select id='editUuid' class='input' style='height:38px;border:1px solid var(--border);border-radius:var(--radius);padding:0 8px;outline:none;background:var(--bg)'></select>
      </div>
      <div class='form-row'>
        <label>显示名称</label>
        <input id='editName' class='input' placeholder='显示名称(<=32)'>
      </div>
      <div class='form-row'>
        <label>设备分类</label>
        <input id='editCategory' class='input' list='catList' placeholder='选择或输入分类'>
        <datalist id='catList'></datalist>
      </div>
    </div>
    <div class='actions'>
      <button class='btn' id='editCancel'>取消</button>
      <button class='btn btn-primary' id='editSave'>保存</button>
    </div>
  </div>
</div>

<div id='regToast' class='toast'></div>
<script>
document.querySelectorAll('.sidebar a').forEach(a=>{if(a.getAttribute('href')===location.pathname){a.classList.add('active');}});
const regTbl=document.getElementById('regTbl');const regCategory=document.getElementById('regCategory');const regSearch=document.getElementById('regSearch');const regToken=document.getElementById('regToken');const regPageInfo=document.getElementById('regPageInfo');let regPage=1,regPageSize=20;

async function loadCategories(){
  try{
    const r=await fetch('/api/v1/admin/device/categories',{headers:{'X-Admin-Token':regToken.value||''}});
    if(r.ok){
      const d=await r.json();
      const cats=d.categories||[];
      const current=regCategory.value;
      regCategory.innerHTML="<option value=''>全部分类</option>"+cats.map(c=>`<option value='${c}'>${c}</option>`).join('');
      regCategory.value=current;
      const catList=document.getElementById('catList');
      catList.innerHTML=cats.map(c=>`<option value='${c}'>`).join('');
    }
  }catch(e){}
}

async function loadUuids(){
  try{
    const r=await fetch('/api/v1/admin/device/uuids',{headers:{'X-Admin-Token':regToken.value||''}});
    if(r.ok){
      const d=await r.json();
      const uuids=d.uuids||[];
      const current=editUuid.value;
      editUuid.innerHTML="<option value=''>请选择UUID</option>"+uuids.map(u=>`<option value='${u}'>${u}</option>`).join('');
      if(current) editUuid.value=current;
    }
  }catch(e){}
}

async function loadRegistry(){
  const q=new URLSearchParams();if(regCategory.value)q.append('category',regCategory.value);if(regSearch.value)q.append('search',regSearch.value);q.append('page',regPage);q.append('page_size',regPageSize);
  const res=await fetch('/api/v1/admin/device/registry?'+q.toString(),{headers:{'X-Admin-Token':regToken.value||''}});
  const data=await res.json();
  regTbl.innerHTML='';
  for(const r of (data.items||[])){const tr=document.createElement('tr');tr.innerHTML=`<td>${r.uuid}</td><td>${r.name||''}</td><td>${r.category||''}</td><td><button class='btn btn-primary' data-act='edit' data-uuid='${r.uuid}' data-name='${r.name||''}' data-cat='${r.category||''}'>✎ 编辑</button></td>`;regTbl.appendChild(tr);}
  regPageInfo.textContent=`第 ${regPage} 页`;
  loadCategories(); 
}
function toast(t){const el=document.getElementById('regToast');el.textContent=t;el.style.display='block';setTimeout(()=>el.style.display='none',1500)}
function validName(n){if(!n) return true; if(n.length>32) return false; return /^[\u4e00-\u9fa5A-Za-z0-9 _-]{0,32}$/.test(n)}

let csrfToken='';
async function ensureCsrf(){if(csrfToken) return csrfToken; try{const r=await fetch('/api/v1/csrf'); const j=await r.json(); csrfToken=j.token||'';}catch(e){} return csrfToken}

const modal=document.getElementById('deviceModal');
const editUuid=document.getElementById('editUuid');
const editName=document.getElementById('editName');
const editCategory=document.getElementById('editCategory');
const modalTitle=document.getElementById('modalTitle');

function showModal(uuid,name,cat,isAdd=false){
  editUuid.value=uuid||'';
  editName.value=name||'';
  editCategory.value=cat||'';
  editUuid.disabled=!isAdd;
  modalTitle.textContent=isAdd?'新增设备':'编辑设备';
  modal.classList.add('show');
}
function hideModal(){modal.classList.remove('show')}

document.getElementById('regAdd').addEventListener('click',async ()=>{await loadUuids();showModal('','','',true)});
document.getElementById('editCancel').addEventListener('click',hideModal);
modal.addEventListener('click',(e)=>{if(e.target===modal)hideModal()});

document.getElementById('editSave').addEventListener('click',async()=>{
  const uuid=editUuid.value.trim();
  const name=editName.value.trim();
  const category=editCategory.value.trim();
  
  if(!uuid){toast('请输入UUID');return}
  if(!validName(name)){toast('名称不合法');return}
  if(!validName(category)){toast('分类不合法');return}
  
  await ensureCsrf();
  const btn=document.getElementById('editSave');
  btn.disabled=true;
  btn.textContent='保存中...';
  try{
    const res=await fetch('/api/v1/admin/device/registry/upsert',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':regToken.value||'','X-CSRF-Token':csrfToken},body:JSON.stringify({uuid,name,category})});
    if(res.ok){
      toast('保存成功');
      hideModal();
      loadRegistry();
    }else{
      toast('保存失败');
    }
  }finally{
    btn.disabled=false;
    btn.textContent='保存';
  }
});

document.getElementById('regQuery').addEventListener('click',()=>{regPage=1;loadRegistry();});
document.getElementById('regPrev').addEventListener('click',()=>{if(regPage>1){regPage--;loadRegistry();}});
document.getElementById('regNext').addEventListener('click',()=>{regPage++;loadRegistry();});

regTbl.addEventListener('click',(e)=>{
  const b=e.target.closest('button');
  if(!b)return; 
  if(b.dataset.act==='edit'){
    showModal(b.dataset.uuid, b.dataset.name, b.dataset.cat, false);
  }
});

(async()=>{await loadRegistry();await loadUuids();})();
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
  <div class='filters'>
    <div class='filter-card'>
      <h4>查询</h4>
      <div class='filter-row'>
        <input id='alertUuid' placeholder='设备UUID' style='width:200px'>
        <input id='alertLimit' type='number' value='100' placeholder='数量' style='width:100px'>
        <button class='btn btn-primary' id='alertQuery'>查询</button>
      </div>
    </div>
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
</head><body>
<div class='main'>
  <h2>最近记录</h2>
  <div class='filters'>
    <div class='filter-card'>
      <h4>查询</h4>
      <div class='filter-row'>
        <input id='filterUuid' placeholder='设备UUID' style='width:160px'>
        <div class="ant-picker ant-picker-range" style='width:auto'>
          <div class="ant-picker-input"><input id='filterStart' type='date' placeholder='开始'></div>
          <div class="ant-picker-range-separator"><span>-</span></div>
          <div class="ant-picker-input"><input id='filterEnd' type='date' placeholder='结束'></div>
        </div>
        <input id='adminToken' placeholder='Admin Token' style='width:140px'>
        <button class='btn btn-primary' id='query'>查询</button>
        <button class='btn' id='reset'>重置</button>
        <button class='btn btn-danger' id='delRange'>删除区间</button>
      </div>
    </div>
    <details class='filter-card'>
      <summary><h4 style='display:inline'>高级过滤</h4></summary>
      <div class='filter-row' style='margin-top:8px'>
        <input id='filterWarn' type='number' placeholder='warn_status' style='width:120px'>
        <input id='filterRecType' type='number' placeholder='rec_type' style='width:120px'>
        <div class='ant-picker' style='padding:0 8px;width:auto'>
           <input id='filterBtxMin' type='number' placeholder='Tx Min' style='border:none;width:60px;text-align:center;outline:none'>
           <span style='color:var(--text-secondary);margin:0 2px'>-</span>
           <input id='filterBtxMax' type='number' placeholder='Tx Max' style='border:none;width:60px;text-align:center;outline:none'>
        </div>
      </div>
    </details>
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

@app.post("/api/v1/admin/device/fetch-history")
async def admin_device_fetch_history(request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    uuid = payload.get("uuid")
    start = payload.get("start") # YYYY-MM-DD HH:MM:SS
    end = payload.get("end")
    if not uuid or not start or not end:
        return Response(status_code=400)
    
    # 模拟从设备获取数据 (Simulation of fetching from device)
    # In real scenario, this would call the device API or Protocol.
    # Here we simulate returning data with some random values for testing.
    import random
    from datetime import datetime, timedelta
    
    try:
        s_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        e_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return Response(status_code=400)

    data = []
    curr = s_dt
    while curr <= e_dt:
        # Simulate a record every minute
        t_str = curr.strftime("%Y-%m-%d %H:%M:%S")
        # Simulate data: IN/OUT random
        data.append({
            "uuid": uuid,
            "in_count": random.randint(0, 5),
            "out_count": random.randint(0, 5),
            "time": t_str,
            "battery_level": 80,
            "signal_status": 1,
            "warn_status": 0,
            "batterytx_level": 80,
            "rec_type": 0
        })
        curr += timedelta(minutes=1) # Default 1 minute interval
    
    return data

@app.post("/api/v1/admin/device/merge-history")
async def admin_device_merge_history(request: Request, payload: dict = Body(...)):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    
    records = payload.get("records", [])
    if not records:
        return {"ok": True, "count": 0}
    
    # Format time if needed (frontend sends YYYY-MM-DD HH:MM:SS, we convert to compact for storage)
    for r in records:
        if "time" in r and r["time"]:
             t = str(r["time"]).strip()
             t = t.replace("-", "").replace(":", "").replace(" ", "")
             r["time"] = t
             
    cnt = await admin_batch_upsert(records)
    
    try:
        actor = request.headers.get("X-Admin-Token", "")
        await admin_write_op(actor, "merge_history", records[0].get("uuid") if records else "", f"count={cnt}")
    except Exception:
        pass
        
    return {"ok": True, "count": cnt}


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

@app.get("/api/v1/admin/device/uuids")
async def get_device_uuids(request: Request):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    uuids = await admin_get_uuids()
    return {"uuids": uuids}

@app.get("/api/v1/device/mapping")
async def device_mapping_endpoint():
    mapping = await get_device_mapping()
    return {"mapping": mapping}

@app.get("/api/v1/admin/device/categories")
async def get_device_categories(request: Request):
    if config.ADMIN_TOKEN and request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        return Response(status_code=403)
    cats = await admin_get_categories()
    return {"categories": cats}

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
