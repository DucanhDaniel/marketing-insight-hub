/* ================================================================
   main.js - Shell router: tab switching, date range, refresh
   Loads view HTML fragments + page-specific JS modules dynamically.
   ================================================================ */

const BASE_URL = window.location.origin;

// Global state shared across modules
window.app = {
    rawData: null,
    currentTab: 'overview',
    charts: {}
};

// Page titles mapping
const TITLE_MAP = {
    overview: 'Dashboard Overview',
    tiktok:   'TikTok Dashboard',
    facebook: 'Facebook Dashboard',
    jobs:     'Job Manager'
};

// Track loaded modules to avoid re-loading
const loadedModules = new Set();

// ================================================================
// ROUTER – Load a view fragment + its JS module
// ================================================================
async function navigateTo(tabId) {
    const container = document.getElementById('app-content');
    if (!container) return;

    // Update sidebar active state
    document.querySelectorAll('.tab-link').forEach(l => l.classList.toggle('active', l.getAttribute('data-tab') === tabId));

    // Update page title
    const pageTitle = document.getElementById('page-title');
    if (pageTitle) pageTitle.textContent = TITLE_MAP[tabId] || tabId;

    window.app.currentTab = tabId;

    // Persist current tab in URL hash (survives refresh)
    history.replaceState(null, '', `#${tabId}`);

    // Stop any active jobs polling if leaving jobs tab
    if (tabId !== 'jobs' && window.stopPollingActiveJobs) window.stopPollingActiveJobs();

    // Show loading state
    container.innerHTML = '<div class="loading-view"><i class="fas fa-spinner fa-spin"></i>&nbsp; Loading...</div>';

    try {
        // 1. Fetch HTML view fragment
        const htmlRes = await fetch(`/static/views/${tabId}.html`);
        if (!htmlRes.ok) throw new Error(`Cannot load view: ${tabId}`);
        container.innerHTML = await htmlRes.text();

        // 2. Dynamically load the page JS module (once)
        if (!loadedModules.has(tabId)) {
            await loadScript(`/static/js/${tabId}.js`);
            loadedModules.add(tabId);
        }

        // 3. Call page init function
        const initFn = window[`init${capitalize(tabId)}`];
        if (typeof initFn === 'function') await initFn();

        // 4. Fetch data for this tab
        await fetchPageData(tabId);

    } catch (err) {
        container.innerHTML = `<div class="loading-view" style="color:#e74c3c;">⚠ Error loading page: ${err.message}</div>`;
        console.error(err);
    }
}

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = () => reject(new Error(`Failed to load script: ${src}`));
        document.body.appendChild(s);
    });
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// ================================================================
// DATA FETCH – per-page endpoints
// ================================================================
async function fetchPageData(tabId) {
    const range = document.getElementById('date-range')?.value || '24h';
    try {
        let url;
        if (tabId === 'overview') {
            url = `${BASE_URL}/api/dashboard/overview?time_range=${range}`;
        } else if (tabId === 'tiktok') {
            url = `${BASE_URL}/api/dashboard/tiktok?time_range=${range}`;
        } else if (tabId === 'facebook') {
            url = `${BASE_URL}/api/dashboard/facebook?time_range=${range}`;
        } else {
            // Jobs tab: no data fetch needed (uses active-jobs polling)
            return;
        }

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // Store in global state and call page render function
        window.app.rawData = data;
        const renderFn = window[`render${capitalize(tabId)}`];
        if (typeof renderFn === 'function') renderFn(data);

    } catch (err) {
        console.error(`Failed to fetch data for tab [${tabId}]:`, err);
    }
}

// Refresh current tab
async function fetchAndRender() {
    await fetchPageData(window.app.currentTab);
}

// ================================================================
// INIT
// ================================================================
document.addEventListener('DOMContentLoaded', () => {

    // Tab click listeners
    document.querySelectorAll('.tab-link').forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            navigateTo(link.getAttribute('data-tab'));
        });
    });

    // Date range change
    document.getElementById('date-range')?.addEventListener('change', fetchAndRender);

    // Refresh button
    document.getElementById('refresh-btn')?.addEventListener('click', () => {
        fetchAndRender();
        const btn = document.getElementById('refresh-btn');
        btn.style.transform = 'rotate(360deg)';
        setTimeout(() => btn.style.transform = 'none', 500);
    });

    // Auto refresh every 30s
    setInterval(fetchAndRender, 30000);

    // Restore tab from URL hash (e.g. /dashboard#tiktok), fallback to 'overview'
    const validTabs = new Set(['overview', 'tiktok', 'facebook', 'jobs']);
    const hashTab = window.location.hash.replace('#', '');
    const initialTab = validTabs.has(hashTab) ? hashTab : 'overview';
    navigateTo(initialTab);
});

// ================================================================
// SHARED UTILS (available to all page modules)
// ================================================================
window.formatDateSafe = function(dateString) {
    if (!dateString) return '';
    try {
        const cleaned = dateString.replace('+00:00', '');
        const date = new Date(cleaned);
        if (isNaN(date.getTime())) return '';
        return date.toLocaleString();
    } catch (e) {
        return '';
    }
};

window.cancelJob = async function(jobId) {
    if (!confirm(`Are you sure you want to cancel job ${jobId}?`)) return;
    try {
        const res = await fetch(`${BASE_URL}/reports/${jobId}/cancel`, { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        alert('Cancel request sent successfully!');
        fetchAndRender();
    } catch (e) {
        alert('Failed to cancel job: ' + e.message);
    }
};

window.hexToRgba = function(hex, alpha) {
    const r = parseInt(hex.slice(1,3), 16);
    const g = parseInt(hex.slice(3,5), 16);
    const b = parseInt(hex.slice(5,7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
};

window.renderTasksTable = function(tasks, containerId, columns = null) {
    const tbody = document.getElementById(containerId);
    if (!tbody) return;
    if (!columns) {
        columns = ['job_id','task_type','user_email','status','start_time','end_time','duration_seconds','message','action'];
        if (containerId === 'tasks-table-body') columns.unshift('checkbox');
    }
    tbody.innerHTML = tasks.slice(0, 1000).map(t => {
        const cells = columns.map(col => {
            const content = t[col];
            if (col === 'checkbox') return `<td onclick="event.stopPropagation();"><input type="checkbox" class="row-checkbox" value="${t.job_id}"></td>`;
            if (col === 'job_id')   return `<td><span class="job-id">${(content||'').substring(0,8)}...</span></td>`;
            if (col === 'status')   return `<td class="status-${content}">${content}</td>`;
            if (col === 'start_time' || col === 'end_time') return `<td>${window.formatDateSafe(content)}</td>`;
            if (col === 'duration_seconds') return `<td>${content ? parseFloat(content).toFixed(2)+'s' : ''}</td>`;
            if (col === 'message')  return `<td class="task-message" style="max-width:300px;white-space:normal;word-wrap:break-word;">${content||''}</td>`;
            if (col === 'action') {
                if (t.status === 'STARTED' || t.status === 'RUNNING')
                    return `<td><button class="btn btn-danger" style="padding:4px 8px;font-size:0.8rem;" onclick="event.stopPropagation();cancelJob('${t.job_id}')">Cancel</button></td>`;
                return '<td></td>';
            }
            return `<td>${content||''}</td>`;
        }).join('');
        return `<tr onclick="openTaskDetail('${t.job_id}')" title="Click to view details">${cells}</tr>`;
    }).join('');
};
