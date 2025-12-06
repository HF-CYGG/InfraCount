// Theme initialization
document.body.setAttribute('data-theme', (localStorage.getItem('theme') || 'light'));

// Helper for alerts
const safeAlert = (msg) => {
    if (window.showAlert) return window.showAlert(msg);
    alert(msg);
};

document.querySelectorAll('.sidebar a').forEach(a => {
    if (a.getAttribute('href') === location.pathname) {
        a.classList.add('active');
    }
});

document.getElementById('themeToggle').addEventListener('click', () => {
    const cur = document.body.getAttribute('data-theme') || 'light';
    const nxt = cur === 'light' ? 'dark' : 'light';
    document.body.setAttribute('data-theme', nxt);
    localStorage.setItem('theme', nxt);
});

// Elements
const deviceSel = document.getElementById('device');
const startEl = document.getElementById('start');
const endEl = document.getElementById('end');
const autoEl = document.getElementById('auto');
const filterWarn = document.getElementById('filterWarn');
const filterRecType = document.getElementById('filterRecType');
const filterBtxMin = document.getElementById('filterBtxMin');
const filterBtxMax = document.getElementById('filterBtxMax');

let dailyChart, hourChart, timer;

// Formatters
function fmtTime(s) {
    if (!s) return '';
    const t = String(s).trim();
    if (/^[0-9]{14}$/.test(t)) {
        return t.slice(0, 4) + '-' + t.slice(4, 6) + '-' + t.slice(6, 8) + ' ' +
               t.slice(8, 10) + ':' + t.slice(10, 12) + ':' + t.slice(12, 14);
    }
    return t;
}

// Initialization
window.addEventListener('load', async () => {
    try {
        // Load Chart.js if needed
        if (typeof Chart === 'undefined') {
            await new Promise((resolve, reject) => {
                const s = document.createElement('script');
                s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
                s.onload = resolve;
                s.onerror = reject;
                document.head.appendChild(s);
            });
        }

        // Restore filters from LocalStorage
        try {
            const saved = localStorage.getItem('dashboardFilters');
            if (saved) {
                const v = JSON.parse(saved);
                if (v.start) startEl.value = v.start;
                if (v.end) endEl.value = v.end;
                if (v.warn) filterWarn.value = v.warn;
                if (v.rectype) filterRecType.value = v.rectype;
                if (v.btxmin) filterBtxMin.value = v.btxmin;
                if (v.btxmax) filterBtxMax.value = v.btxmax;
                if (v.auto) {
                    autoEl.checked = true;
                    // Trigger change event to start timer
                    autoEl.dispatchEvent(new Event('change'));
                }
            }
        } catch (e) {
            console.error('Failed to restore filters', e);
        }

        await loadDevices();
        
        // If we have a saved device and it exists in the list, select it
        try {
            const saved = localStorage.getItem('dashboardFilters');
            if (saved) {
                const v = JSON.parse(saved);
                if (v.device && document.querySelector(`#device option[value="${v.device}"]`)) {
                    deviceSel.value = v.device;
                }
            }
        } catch(e) {}

        // Force selection if empty
        if (!deviceSel.value && deviceSel.options.length > 0) {
            deviceSel.selectedIndex = 0;
        }

        await loadStats();
        await loadAllTotals();

    } catch (e) {
        console.error('Init failed', e);
    }
});

async function loadDevices() {
    try {
        const res = await fetch('/api/v1/devices');
        if (!res.ok) throw new Error('Failed to fetch devices');
        const list = await res.json();
        
        deviceSel.innerHTML = '';
        if (list.length === 0) {
            const opt = document.createElement('option');
            opt.text = "无设备";
            deviceSel.appendChild(opt);
            deviceSel.disabled = true;
            return;
        }
        
        deviceSel.disabled = false;
        for (const d of list) {
            const opt = document.createElement('option');
            opt.value = d.uuid;
            opt.textContent = (d.name ? `${d.name} (${d.uuid})` : d.uuid);
            deviceSel.appendChild(opt);
        }
    } catch (e) {
        console.error(e);
        deviceSel.innerHTML = '<option>加载失败</option>';
    }
}

async function loadAllTotals() {
    try {
        const r = await fetch('/api/v1/stats/total');
        if (!r.ok) return;
        const j = await r.json();
        document.getElementById('allTotals').textContent = '全部设备 IN: ' + (j.in_total || 0) + '  OUT: ' + (j.out_total || 0);
    } catch(e) {}
}

async function loadStats() {
    const uuid = deviceSel.value;
    if (!uuid) return;

    const today = new Date().toISOString().slice(0, 10);
    // Default to last 30 days if no date selected
    const startDate = startEl.value || (endEl.value ? '' : new Date(Date.now() - 29 * 24 * 3600 * 1000).toISOString().slice(0, 10));
    const endDate = endEl.value || today;

    const start = startDate ? startDate + ' 00:00:00' : '';
    const end = endDate ? endDate + ' 23:59:59' : '';

    const q = new URLSearchParams({ uuid });
    if (start) q.append('start', start);
    if (end) q.append('end', end);
    
    // Advanced filters
    if (filterWarn && filterWarn.value) q.append('warn_status', filterWarn.value);
    if (filterRecType && filterRecType.value) q.append('rec_type', filterRecType.value);
    if (filterBtxMin && filterBtxMin.value) q.append('batterytx_min', filterBtxMin.value);
    if (filterBtxMax && filterBtxMax.value) q.append('batterytx_max', filterBtxMax.value);

    try {
        // Summary
        const sumRes = await fetch('/api/v1/stats/summary?' + new URLSearchParams({ uuid }).toString());
        if (sumRes.ok) {
            const sum = await sumRes.json();
            document.getElementById('sum_in').innerText = 'IN总计：' + (sum.in_total || 0);
            document.getElementById('sum_out').innerText = 'OUT总计：' + (sum.out_total || 0);
            document.getElementById('sum_net').innerText = '净流量：' + ((sum.in_total || 0) - (sum.out_total || 0));
            document.getElementById('sum_last').innerText = '最近上报：' + fmtTime(sum.last_time || '') + ' IN=' + (sum.last_in ?? '') + ' OUT=' + (sum.last_out ?? '');
        }

        // Daily Chart
        const res = await fetch('/api/v1/stats/daily?' + q.toString());
        if (res.ok) {
            const daily = await res.json();
            const lab = daily.map(x => x.day);
            const inData = daily.map(x => x.in_total || 0);
            const outData = daily.map(x => x.out_total || 0);

            if (typeof Chart !== 'undefined') {
                const ctx = document.getElementById('dailyChart').getContext('2d');
                if (dailyChart) dailyChart.destroy();
                dailyChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: lab,
                        datasets: [
                            { label: 'IN', data: inData, borderColor: '#2b8a3e', tension: 0.1 },
                            { label: 'OUT', data: outData, borderColor: '#d9480f', tension: 0.1 }
                        ]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }
        }

        // Hourly Chart
        const hq = new URLSearchParams({ uuid, date: endDate });
        const hres = await fetch('/api/v1/stats/hourly?' + hq.toString());
        if (hres.ok) {
            const hourly = await hres.json();
            const hLab = hourly.map(x => x.hour);
            const hIn = hourly.map(x => x.in_total || 0);
            const hOut = hourly.map(x => x.out_total || 0);

            if (typeof Chart !== 'undefined') {
                const hctx = document.getElementById('hourChart').getContext('2d');
                if (hourChart) hourChart.destroy();
                hourChart = new Chart(hctx, {
                    type: 'bar',
                    data: {
                        labels: hLab,
                        datasets: [
                            { label: 'IN', data: hIn, backgroundColor: '#74c69d' },
                            { label: 'OUT', data: hOut, backgroundColor: '#ff8787' }
                        ]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }
        }
    } catch (e) {
        console.error("Load Stats Error", e);
    }
}

// Event Listeners
document.getElementById('load').addEventListener('click', async (e) => {
    const b = e.currentTarget;
    b.classList.add('loading');
    saveFilters();
    await loadStats();
    await loadAllTotals();
    b.classList.remove('loading');
});

document.getElementById('today').addEventListener('click', async (e) => {
    const b = e.currentTarget;
    const d = new Date().toISOString().slice(0, 10);
    startEl.value = d;
    endEl.value = d;
    saveFilters();
    b.classList.add('loading');
    await loadStats();
    await loadAllTotals();
    b.classList.remove('loading');
});

document.getElementById('last7').addEventListener('click', async (e) => {
    const b = e.currentTarget;
    const now = new Date();
    const end = now.toISOString().slice(0, 10);
    const start = new Date(now.getTime() - 6 * 24 * 3600 * 1000).toISOString().slice(0, 10);
    startEl.value = start;
    endEl.value = end;
    saveFilters();
    b.classList.add('loading');
    await loadStats();
    await loadAllTotals();
    b.classList.remove('loading');
});

document.getElementById('resetFilter').addEventListener('click', async (e) => {
    const b = e.currentTarget;
    deviceSel.selectedIndex = 0;
    startEl.value = '';
    endEl.value = '';
    if (filterWarn) filterWarn.value = '';
    if (filterRecType) filterRecType.value = '';
    if (filterBtxMin) filterBtxMin.value = '';
    if (filterBtxMax) filterBtxMax.value = '';
    autoEl.checked = false;
    if (timer) clearInterval(timer);
    localStorage.removeItem('dashboardFilters');
    b.classList.add('loading');
    await loadStats();
    await loadAllTotals();
    b.classList.remove('loading');
});

if (autoEl) {
    autoEl.addEventListener('change', () => {
        saveFilters();
        if (autoEl.checked) {
            timer = setInterval(() => { loadStats(); loadAllTotals() }, 10000);
        } else {
            clearInterval(timer);
        }
    });
}

function saveFilters() {
    const v = {
        device: deviceSel.value,
        start: startEl.value,
        end: endEl.value,
        warn: filterWarn ? filterWarn.value : '',
        rectype: filterRecType ? filterRecType.value : '',
        btxmin: filterBtxMin ? filterBtxMin.value : '',
        btxmax: filterBtxMax ? filterBtxMax.value : '',
        auto: autoEl ? autoEl.checked : false
    };
    localStorage.setItem('dashboardFilters', JSON.stringify(v));
}

// Popups
const toggleAdv = document.getElementById('toggleAdvanced');
const advPopup = document.getElementById('advancedPopup');
const toggleAct = document.getElementById('toggleActions');
const actPopup = document.getElementById('actionsPopup');

function setupPopup(btn, popup) {
    if (!btn || !popup) return;
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        document.querySelectorAll('.popup-card.show').forEach(el => {
            if (el !== popup) el.classList.remove('show');
        });
        popup.classList.toggle('show');
    });
    popup.addEventListener('click', (e) => e.stopPropagation());
}

setupPopup(toggleAdv, advPopup);
setupPopup(toggleAct, actPopup);

document.addEventListener('click', () => {
    document.querySelectorAll('.popup-card.show').forEach(el => el.classList.remove('show'));
});

// Exports
document.getElementById('exportDaily').addEventListener('click', () => {
    const uuid = deviceSel.value;
    if (!uuid) return safeAlert("请选择设备");
    const start = startEl.value ? startEl.value + ' 00:00:00' : '';
    const end = endEl.value ? endEl.value + ' 23:59:59' : '';
    const q = new URLSearchParams({ uuid });
    if (start) q.append('start', start);
    if (end) q.append('end', end);
    window.open('/api/v1/export/daily?' + q.toString(), '_blank');
});

document.getElementById('exportHourly').addEventListener('click', () => {
    const uuid = deviceSel.value;
    if (!uuid) return safeAlert("请选择设备");
    const date = endEl.value || new Date().toISOString().slice(0, 10);
    window.open('/api/v1/export/hourly?' + new URLSearchParams({ uuid, date }).toString(), '_blank');
});

document.getElementById('exportHistory').addEventListener('click', () => {
    const uuid = deviceSel.value;
    if (!uuid) return safeAlert("请选择设备");
    const start = startEl.value ? startEl.value + ' 00:00:00' : '';
    const end = endEl.value ? endEl.value + ' 23:59:59' : '';
    const q = new URLSearchParams({ uuid });
    if (start) q.append('start', start);
    if (end) q.append('end', end);
    window.open('/api/v1/export/history?' + q.toString(), '_blank');
});

document.getElementById('refreshLatest').addEventListener('click', async () => {
    await loadStats();
    await loadAllTotals();
});
