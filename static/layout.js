const SIDEBAR_HTML = `
<div class="app-sidebar-header">
    InfraCount
</div>
<div class="app-sidebar-nav">
    <a href="/activity-dashboard" class="nav-item">
        书院看板
    </a>
    <a href="/dashboard" class="nav-item">
        数据看板
    </a>
    <a href="/history" class="nav-item">
        历史数据
    </a>
    <a href="/alerts" class="nav-item">
        告警中心
    </a>
    <a href="/devices" class="nav-item">
        设备管理
    </a>
</div>
<div style="padding:16px;border-top:1px solid #e9ecef;font-size:12px;color:#868e96;text-align:center">
    v1.0 by_夜喵cats
</div>
`;

const ALERT_HTML = `
<div id="appAlertModal" class="modal-backdrop" style="z-index:9999">
    <div class="modal" style="width:400px">
        <h3 id="appAlertTitle">提示</h3>
        <p id="appAlertMsg"></p>
        <div class="actions">
            <button class="btn btn-primary" id="appAlertOk">确定</button>
        </div>
    </div>
</div>
<div id="appConfirmModal" class="modal-backdrop" style="z-index:9999">
    <div class="modal" style="width:400px">
        <h3 id="appConfirmTitle">确认</h3>
        <p id="appConfirmMsg"></p>
        <div class="actions">
            <button class="btn" id="appConfirmCancel">取消</button>
            <button class="btn btn-primary" id="appConfirmOk">确定</button>
        </div>
    </div>
</div>
`;

function initLayout(title, customContentId) {
    const body = document.body;
    
    // Restore theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        body.classList.add('dark-mode');
    }

    // Strategy: Create layout structure and move body children into content area.
    const layout = document.createElement('div');
    layout.className = 'app-layout';
    
    const sidebar = document.createElement('div');
    sidebar.className = 'app-sidebar';
    sidebar.innerHTML = SIDEBAR_HTML;
    
    const main = document.createElement('div');
    main.className = 'app-main';
    
    const header = document.createElement('div');
    header.className = 'app-header';
    header.innerHTML = `
        <div class="page-title">${title}</div>
        <div class="flex items-center gap-4">
            <span id="currentTime" class="text-sm text-muted"></span>
            <button id="themeToggle" class="btn btn-sm">
                ${body.classList.contains('dark-mode') ? '亮色模式' : '暗色模式'}
            </button>
            <div style="width:32px;height:32px;background:#e9ecef;border-radius:50%;display:flex;align-items:center;justify-content:center"></div>
        </div>
    `;
    
    const content = document.createElement('div');
    content.className = 'app-content';
    
    // Move existing nodes
    while (body.firstChild) {
        content.appendChild(body.firstChild);
    }
    
    main.appendChild(header);
    main.appendChild(content);
    layout.appendChild(sidebar);
    layout.appendChild(main);
    body.appendChild(layout);
    
    // Theme Toggle Logic
    const themeBtn = document.getElementById('themeToggle');
    themeBtn.addEventListener('click', () => {
        body.classList.toggle('dark-mode');
        const isDark = body.classList.contains('dark-mode');
        themeBtn.textContent = isDark ? '亮色模式' : '暗色模式';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    });

    // Active Link Logic
    const path = location.pathname;
    sidebar.querySelectorAll('.nav-item').forEach(a => {
        if (a.getAttribute('href') === path) {
            a.classList.add('active');
        }
    });
    
    // Time
    setInterval(() => {
        const now = new Date();
        document.getElementById('currentTime').textContent = now.toLocaleString();
    }, 1000);

    // Alert & Confirm Logic
    const alertContainer = document.createElement('div');
    alertContainer.innerHTML = ALERT_HTML;
    document.body.appendChild(alertContainer);

    const alertModal = document.getElementById('appAlertModal');
    const alertTitle = document.getElementById('appAlertTitle');
    const alertMsg = document.getElementById('appAlertMsg');
    const alertOk = document.getElementById('appAlertOk');
    
    let alertResolve = null;
    
    window.showAlert = (msg, title='提示') => {
        return new Promise(resolve => {
            alertTitle.textContent = title;
            alertMsg.textContent = msg;
            alertModal.classList.add('show');
            alertResolve = resolve;
        });
    };
    
    alertOk.addEventListener('click', () => {
        alertModal.classList.remove('show');
        if(alertResolve) alertResolve();
    });

    const confirmModal = document.getElementById('appConfirmModal');
    const confirmTitle = document.getElementById('appConfirmTitle');
    const confirmMsg = document.getElementById('appConfirmMsg');
    const confirmOk = document.getElementById('appConfirmOk');
    const confirmCancel = document.getElementById('appConfirmCancel');
    
    let confirmResolve = null;

    window.showConfirm = (msg, title='确认') => {
        return new Promise(resolve => {
            confirmTitle.textContent = title;
            confirmMsg.textContent = msg;
            confirmModal.classList.add('show');
            confirmResolve = resolve;
        });
    };
    
    confirmOk.addEventListener('click', () => {
        confirmModal.classList.remove('show');
        if(confirmResolve) confirmResolve(true);
    });
    
    confirmCancel.addEventListener('click', () => {
        confirmModal.classList.remove('show');
        if(confirmResolve) confirmResolve(false);
    });
}
