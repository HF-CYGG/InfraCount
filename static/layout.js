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
    
    <div class="nav-group">
        <div class="nav-item nav-group-title" style="cursor:pointer; display:flex; justify-content:space-between; align-items:center">
            <span>历史数据</span>
            <span style="font-size:10px">▼</span>
        </div>
        <div class="nav-group-items" style="display:none; padding-left:16px; background:rgba(0,0,0,0.02)">
            <a href="/history/academy" class="nav-item" style="font-size:13px">
                书院数据
            </a>
            <a href="/history/device" class="nav-item" style="font-size:13px">
                设备数据
            </a>
        </div>
    </div>

    <a href="/alerts" class="nav-item">
        告警中心
    </a>
    <a href="/devices" class="nav-item">
        设备管理
    </a>
    <a href="/account" class="nav-item">
        账户管理
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

const PROFILE_MODAL_HTML = `
<div id="appProfileModal" class="modal-backdrop" style="z-index:9999">
    <div class="modal" style="width:500px">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <h2 style="margin:0;">我的账户</h2>
            <span id="closeProfileModal" style="cursor:pointer; font-size:24px;">&times;</span>
        </div>
        
        <div class="user-info" style="margin-bottom:20px; padding-bottom:20px; border-bottom:1px solid #eee;">
            <div style="display:flex; margin:10px 0; color:#666;">
                <span style="width:100px; font-weight:500;">用户名</span>
                <span id="profileUsername">加载中...</span>
            </div>
            <div style="display:flex; margin:10px 0; color:#666;">
                <span style="width:100px; font-weight:500;">角色</span>
                <span id="profileRole">加载中...</span>
            </div>
            <div style="display:flex; margin:10px 0; color:#666;">
                <span style="width:100px; font-weight:500;">上次登录</span>
                <span id="profileLastLogin">--</span>
            </div>
        </div>

        <h3>修改密码</h3>
        <form id="profileChangePwdForm">
            <div class="form-group" style="margin-bottom:15px;">
                <label class="form-label" style="display:block; margin-bottom:5px;">新密码</label>
                <input type="password" name="newPassword" class="form-control" style="width:100%; padding:8px; border:1px solid #ddd; border-radius:4px;" required minlength="6">
            </div>
            <div class="form-group" style="margin-bottom:15px;">
                <label class="form-label" style="display:block; margin-bottom:5px;">确认新密码</label>
                <input type="password" name="confirmPassword" class="form-control" style="width:100%; padding:8px; border:1px solid #ddd; border-radius:4px;" required minlength="6">
            </div>
            <button type="submit" class="btn btn-primary">更新密码</button>
        </form>
    </div>
</div>
`;


// Interval Tracking for SPA Cleanup
const _pageIntervals = new Set();
const _nativeSetInterval = window.setInterval;
const _nativeClearInterval = window.clearInterval;

const _SPA_MANAGED_ATTR = 'data-spa-managed';
const _SPA_GLOBAL_ATTR = 'data-spa-global';

function _isGlobalStylesheetHref(href) {
    if (!href) return false;
    const h = String(href);
    return h.includes('/static/style.css') || h.includes('/static/lib/fontawesome') || h.includes('/static/fonts/');
}

function _isGlobalScriptSrc(src) {
    if (!src) return false;
    const s = String(src);
    return s.includes('/static/layout.js');
}

function _markInitialHeadForSpa() {
    if (window.__spaHeadMarked) return;
    window.__spaHeadMarked = true;

    Array.from(document.head.querySelectorAll('style')).forEach(el => {
        el.setAttribute(_SPA_MANAGED_ATTR, '1');
    });

    Array.from(document.head.querySelectorAll('link[rel="stylesheet"]')).forEach(el => {
        const href = el.getAttribute('href') || '';
        if (_isGlobalStylesheetHref(href)) {
            el.setAttribute(_SPA_GLOBAL_ATTR, '1');
        } else {
            el.setAttribute(_SPA_MANAGED_ATTR, '1');
        }
    });

    Array.from(document.head.querySelectorAll('script[src]')).forEach(el => {
        const src = el.getAttribute('src') || '';
        if (_isGlobalScriptSrc(src)) {
            el.setAttribute(_SPA_GLOBAL_ATTR, '1');
        } else {
            el.setAttribute(_SPA_MANAGED_ATTR, '1');
        }
    });
}

function _replacePageHeadStyles(newDoc) {
    const head = document.head;
    Array.from(head.querySelectorAll('style')).forEach(el => {
        if (el.getAttribute(_SPA_GLOBAL_ATTR) === '1') return;
        el.remove();
    });
    Array.from(head.querySelectorAll('link[rel="stylesheet"]')).forEach(el => {
        const href = el.getAttribute('href') || '';
        if (_isGlobalStylesheetHref(href)) return;
        el.remove();
    });

    const newHead = newDoc.head;
    Array.from(newHead.querySelectorAll('link[rel="stylesheet"], style')).forEach(node => {
        if (node.tagName === 'LINK') {
            const href = node.getAttribute('href') || '';
            const exists = !!head.querySelector(`link[rel="stylesheet"][href="${href}"]`);
            if (exists) return;
            const clone = node.cloneNode(true);
            if (_isGlobalStylesheetHref(href)) {
                clone.setAttribute(_SPA_GLOBAL_ATTR, '1');
            } else {
                clone.setAttribute(_SPA_MANAGED_ATTR, '1');
            }
            head.appendChild(clone);
            return;
        }

        if (node.tagName === 'STYLE') {
            const clone = node.cloneNode(true);
            clone.setAttribute(_SPA_MANAGED_ATTR, '1');
            head.appendChild(clone);
        }
    });
}

function _replacePageHeadScripts(newDoc) {
    const head = document.head;
    Array.from(head.querySelectorAll('script')).forEach(el => {
        const src = el.getAttribute('src') || '';
        if (src && _isGlobalScriptSrc(src)) return;
        if (el.getAttribute(_SPA_GLOBAL_ATTR) === '1') return;
        el.remove();
    });

    const newHead = newDoc.head;
    const scripts = Array.from(newHead.querySelectorAll('script'));

    const tasks = [];
    for (const node of scripts) {
        const src = node.getAttribute('src') || '';
        if (src) {
            if (_isGlobalScriptSrc(src)) continue;
            const exists = !!head.querySelector(`script[src="${src}"]`);
            if (exists) continue;

            const scriptEl = document.createElement('script');
            scriptEl.src = src;
            scriptEl.setAttribute(_SPA_MANAGED_ATTR, '1');
            tasks.push(new Promise(resolve => {
                scriptEl.onload = () => resolve();
                scriptEl.onerror = () => resolve();
                head.appendChild(scriptEl);
            }));
            continue;
        }

        const inlineText = (node.textContent || '').trim();
        if (!inlineText) continue;
        const scriptEl = document.createElement('script');
        scriptEl.setAttribute(_SPA_MANAGED_ATTR, '1');
        scriptEl.textContent = inlineText;
        head.appendChild(scriptEl);
    }

    return Promise.all(tasks);
}

window.setInterval = function(fn, delay, ...args) {
    const id = _nativeSetInterval(fn, delay, ...args);
    _pageIntervals.add(id);
    return id;
};

window.clearInterval = function(id) {
    _nativeClearInterval(id);
    _pageIntervals.delete(id);
};

function clearPageIntervals() {
    for (const id of _pageIntervals) {
        _nativeClearInterval(id);
    }
    _pageIntervals.clear();
}

function initLayout(title, customContentId) {
    _markInitialHeadForSpa();

    // Auth Check
    if (window.location.pathname !== '/login') {
        fetch('/api/v1/auth/me').then(r => {
            if (r.status === 401) window.location.href = '/login';
            return r.json();
        }).then(data => {
            if (data && data.user) {
                const uEl = document.getElementById('headerUsername');
                if(uEl) uEl.textContent = data.user.username;
            }
        }).catch(e => console.error(e));
    }

    // Idempotency Check
    const existingLayout = document.querySelector('.app-layout');
    if (existingLayout) {
        const titleEl = document.querySelector('.page-title');
        if (titleEl) {
            titleEl.textContent = title;
        }
        updateActiveLink();
        return; 
    }

    const body = document.body;
    
    // Restore theme
    const savedTheme = localStorage.getItem('theme');
    const systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && systemDark)) {
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
            
            <div class="user-menu">
                <div id="userMenuTrigger" class="user-menu-trigger">
                    <div class="user-menu-avatar">
                         <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                            <circle cx="12" cy="7" r="4"></circle>
                         </svg>
                    </div>
                    <span id="headerUsername" class="user-menu-name">加载中...</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                </div>
                
                <div id="userDropdown" class="user-menu-dropdown">
                    <div id="openProfileBtn" class="user-menu-item">
                        <i class="fas fa-user-circle" style="width:16px;text-align:center"></i>
                        个人账户
                    </div>
                    <div style="height:1px; background:var(--border); margin:4px 8px;"></div>
                    <div id="doLogoutBtn" class="user-menu-item danger">
                        <i class="fas fa-sign-out-alt" style="width:16px;text-align:center"></i>
                        退出登录
                    </div>
                </div>
            </div>
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

    // Sidebar Dropdown Logic
    document.querySelectorAll('.nav-group-title').forEach(title => {
        title.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const group = title.parentElement;
            const items = group.querySelector('.nav-group-items');
            const arrow = title.querySelector('span:last-child');
            
            if(items.style.display === 'none') {
                items.style.display = 'block';
                arrow.style.transform = 'rotate(180deg)';
            } else {
                items.style.display = 'none';
                arrow.style.transform = 'rotate(0deg)';
            }
        });
    });

    // Active Link Logic
    updateActiveLink();
    
    // Time
    const clockId = setInterval(() => {
        const now = new Date();
        document.getElementById('currentTime').textContent = now.toLocaleString();
    }, 1000);
    // Protect clock interval from cleanup
    _pageIntervals.delete(clockId);

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

    // --- User Profile Logic ---
    
    // Add Profile Modal to Body
    const profileContainer = document.createElement('div');
    profileContainer.innerHTML = PROFILE_MODAL_HTML;
    document.body.appendChild(profileContainer);
    
    const userMenuTrigger = document.getElementById('userMenuTrigger');
    const userDropdown = document.getElementById('userDropdown');
    const openProfileBtn = document.getElementById('openProfileBtn');
    const doLogoutBtn = document.getElementById('doLogoutBtn');
    
    const profileModal = document.getElementById('appProfileModal');
    const closeProfileModal = document.getElementById('closeProfileModal');
    
    // Toggle Dropdown
    if (userMenuTrigger) {
        userMenuTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            userDropdown.classList.toggle('show');
            userMenuTrigger.classList.toggle('active');
        });
    }
    
    // Close dropdown on outside click
    document.addEventListener('click', () => {
        if(userDropdown) userDropdown.classList.remove('show');
        if(userMenuTrigger) userMenuTrigger.classList.remove('active');
    });
    
    // Open Profile Modal
    openProfileBtn.addEventListener('click', async () => {
        profileModal.classList.add('show');
        // Load User Info
        try {
            const res = await fetch('/api/v1/auth/me');
            if (res.ok) {
                const data = await res.json();
                if (data.user) {
                    document.getElementById('profileUsername').textContent = data.user.username;
                    document.getElementById('profileRole').textContent = data.user.role;
                    // Mock last login if not available
                    document.getElementById('profileLastLogin').textContent = data.user.last_login || new Date().toLocaleString(); 
                }
            }
        } catch(e) {
            console.error(e);
        }
    });
    
    closeProfileModal.addEventListener('click', () => {
        profileModal.classList.remove('show');
    });
    
    // Profile Change Password
    const profilePwdForm = document.getElementById('profileChangePwdForm');
    if (profilePwdForm) {
        profilePwdForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const form = e.target;
            const newPwd = form.newPassword.value;
            const confirmPwd = form.confirmPassword.value;

            if (newPwd !== confirmPwd) {
                window.showAlert('两次输入的密码不一致');
                return;
            }

            try {
                const res = await fetch('/api/v1/auth/password', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({new_password: newPwd})
                });

                if (res.ok) {
                    window.showAlert('密码修改成功');
                    form.reset();
                    profileModal.classList.remove('show');
                } else {
                    window.showAlert('修改失败，请重试');
                }
            } catch (e) {
                console.error(e);
                window.showAlert('发生错误');
            }
        });
    }

    // Logout
    doLogoutBtn.addEventListener('click', async () => {
        const confirmed = await window.showConfirm('确定要退出登录吗？');
        if(!confirmed) return;
        
        try {
            await fetch('/api/v1/auth/logout', {method: 'POST'});
            window.location.href = '/login';
        } catch (e) {
            console.error(e);
        }
    });

    // Initialize SPA Navigation
    setupSpaNavigation();

}

function updateActiveLink() {
    const path = location.pathname;
    document.querySelectorAll('.app-sidebar .nav-item').forEach(a => {
        a.classList.remove('active');
        if (a.getAttribute('href') === path) {
            a.classList.add('active');
            
            // Expand parent group if exists
            const group = a.closest('.nav-group');
            if (group) {
                const items = group.querySelector('.nav-group-items');
                const arrow = group.querySelector('.nav-group-title span:last-child');
                if(items) items.style.display = 'block';
                if(arrow) arrow.style.transform = 'rotate(180deg)';
            }
        }
    });
}

function setupSpaNavigation() {
    document.body.addEventListener('click', async (e) => {
        const link = e.target.closest('a.nav-item');
        if (link && link.getAttribute('href').startsWith('/')) {
            e.preventDefault();
            const url = link.getAttribute('href');
            await navigateTo(url);
        }
    });

    window.addEventListener('popstate', () => {
        navigateTo(location.pathname, false);
    });
}

async function navigateTo(url, push = true) {
    if (push) {
        history.pushState(null, '', url);
    }

    try {
        const res = await fetch(url);
        const html = await res.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // Clear existing page intervals
        clearPageIntervals();

        // Update Title
        document.title = doc.title

        _markInitialHeadForSpa();
        _replacePageHeadStyles(doc);
        await _replacePageHeadScripts(doc);
        
        // Update Content
        const content = document.querySelector('.app-content');
        const prevTransition = content.style.transition;
        const prevOpacity = content.style.opacity;
        content.style.transition = prevTransition || 'opacity 0.08s ease';
        content.style.opacity = '0';
        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        content.innerHTML = ''; // Clear current content

        // Extract body children from fetched doc
        // We need to be careful not to include the layout script itself if possible, 
        // or let initLayout handle the idempotency.
        const newBody = doc.body;
        
        // Move nodes
        const scriptsToRun = [];
        
        Array.from(newBody.childNodes).forEach(node => {
            if (node.tagName === 'SCRIPT') {
                scriptsToRun.push(node);
            } else {
                content.appendChild(node.cloneNode(true));
            }
        });

        // Run scripts sequentially
        await runScriptsSequentially(scriptsToRun, content);

        updateActiveLink();
        await new Promise(r => requestAnimationFrame(r));
        content.style.opacity = '1';
        setTimeout(() => {
            content.style.transition = prevTransition;
            content.style.opacity = prevOpacity;
        }, 200);

    } catch (err) {
        console.error('Navigation failed:', err);
        window.location.reload(); // Fallback
    }
}

async function runScriptsSequentially(scripts, contentEl) {
    for (const script of scripts) {
        // Skip layout.js as it is already loaded
        if (script.src && script.src.includes('layout.js')) {
            continue;
        }

        await new Promise((resolve, reject) => {
            const newScript = document.createElement('script');
            if (script.src) {
                // External Script
                newScript.src = script.src;
                newScript.onload = () => resolve();
                newScript.onerror = () => {
                    console.warn('Failed to load script:', script.src);
                    resolve(); // Continue anyway
                };
                contentEl.appendChild(newScript);
            } else {
                // Inline Script
                // Wrap in IIFE to avoid global variable collisions (e.g. const state)
                newScript.textContent = `(async function() { 
                    try {
                        ${script.textContent}
                    } catch(e) {
                        console.error('Inline script execution error:', e);
                    }
                })();`;
                contentEl.appendChild(newScript);
                resolve();
            }
        });
    }
}
