/* ================================================================
   overview.js - Overview tab: charts, stats, task log table
   API: GET /api/dashboard/overview
   ================================================================ */

window.initOverview = function() {
    // Setup status filter listener (runs each time view is loaded)
    const statusFilter = document.getElementById('task-status-filter');
    if (statusFilter) {
        statusFilter.addEventListener('change', () => {
            if (window.app.rawData) renderOverview(window.app.rawData);
        });
    }

    // Delete task logs UI
    initDeleteTasksOverview();
};

window.renderOverview = function(data) {
    const tasks = data.task_logs || [];

    // Summary Cards
    const totalTasks      = tasks.length;
    const successfulTasks = tasks.filter(t => t.status === 'SUCCESS').length;
    const successRate     = totalTasks > 0 ? ((successfulTasks / totalTasks) * 100).toFixed(1) : 0;
    const completedTasks  = tasks.filter(t => t.duration_seconds && t.duration_seconds > 0);
    const avgDuration     = completedTasks.length > 0
        ? (completedTasks.reduce((s,t) => s + t.duration_seconds, 0) / completedTasks.length).toFixed(1)
        : 0;
    const uniqueEmails = new Set(tasks.map(t => t.user_email).filter(e => e && e.includes('@')));

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('total-tasks',      totalTasks);
    set('successful-tasks', successfulTasks);
    set('success-rate',     `${successRate}%`);
    set('avg-duration',     `${avgDuration}s`);
    set('total-emails',     uniqueEmails.size);

    // Charts
    renderStatusChart(tasks);
    renderEndpointChart(tasks);
    renderUserStats(tasks);

    // Top failed users table
    const failedUsers = {};
    tasks.forEach(t => {
        if (t.status === 'FAILED' || t.status === 'FAILURE') {
            const email = t.user_email || 'Unknown';
            failedUsers[email] = (failedUsers[email] || 0) + 1;
        }
    });
    const sortedFailed = Object.entries(failedUsers).sort((a,b) => b[1]-a[1]).slice(0,10);
    const failedBody = document.getElementById('top-failed-users-body');
    if (failedBody) {
        failedBody.innerHTML = sortedFailed.length === 0
            ? '<tr><td colspan="2" style="text-align:center;color:#999;">No failed tasks</td></tr>'
            : sortedFailed.map(([email, count]) => `
                <tr class="clickable-row" onclick="openEmailFailedModal('${email.replace(/'/g,"&apos;")}')" style="cursor:pointer;">
                    <td style="color:#3498db;text-decoration:underline;">${email}</td>
                    <td><strong style="color:#e74c3c;">${count}</strong></td>
                </tr>`).join('');
    }

    // Recent task table
    const statusFilter = document.getElementById('task-status-filter')?.value || 'all';
    const tasksForTable = statusFilter === 'all'
        ? tasks
        : tasks.filter(t => (t.status||'').toUpperCase() === statusFilter.toUpperCase());
    window.renderTasksTable(tasksForTable, 'tasks-table-body');
};

function renderStatusChart(tasks) {
    const counts = tasks.reduce((acc, t) => { acc[t.status] = (acc[t.status]||0)+1; return acc; }, {});
    const colorMap = {
        'SUCCESS':'#2ecc71','COMPLETED':'#2ecc71','FAILED':'#e74c3c','FAILURE':'#e74c3c',
        'STARTED':'#3498db','RUNNING':'#3498db','PENDING':'#f1c40f','REVOKED':'#95a5a6',
        'CANCELLED':'#7f8c8d','TIMED_OUT':'#e67e22'
    };
    const labels = Object.keys(counts);
    const ctx = document.getElementById('statusChart')?.getContext('2d');
    if (!ctx) return;
    if (window.app.charts.status) window.app.charts.status.destroy();
    window.app.charts.status = new Chart(ctx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data: Object.values(counts), backgroundColor: labels.map(s => colorMap[s]||'#bdc3c7'), borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
    });
}

function renderEndpointChart(tasks) {
    const counts = tasks.reduce((acc, t) => { const k = t.task_type||'Unknown'; acc[k]=(acc[k]||0)+1; return acc; }, {});
    const ctx = document.getElementById('endpointChart')?.getContext('2d');
    if (!ctx) return;
    if (window.app.charts.endpoint) window.app.charts.endpoint.destroy();
    window.app.charts.endpoint = new Chart(ctx, {
        type: 'pie',
        data: { labels: Object.keys(counts), datasets: [{ data: Object.values(counts), backgroundColor: ['#3498db','#9b59b6','#1abc9c','#e67e22','#34495e'], borderWidth: 1 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
    });
}

function renderUserStats(tasks) {
    const userCounts = {};
    tasks.forEach(t => { if (t.user_email) userCounts[t.user_email] = (userCounts[t.user_email]||0)+1; });
    const sorted = Object.entries(userCounts).sort((a,b) => b[1]-a[1]).slice(0,5);

    const tbody = document.getElementById('top-users-body');
    if (tbody) {
        tbody.innerHTML = sorted.map(([email, count]) => `<tr><td>${email}</td><td><strong>${count}</strong></td></tr>`).join('');
    }

    const ctx = document.getElementById('userChart')?.getContext('2d');
    if (!ctx) return;
    if (window.app.charts.user) window.app.charts.user.destroy();
    window.app.charts.user = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(u => u[0].split('@')[0]),
            datasets: [{ label: 'Tasks Count', data: sorted.map(u => u[1]), backgroundColor: '#3498db', borderRadius: 4 }]
        },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
    });
}

// ================================================================
// TASK DETAIL MODAL (also used by Facebook tab)
// ================================================================
let currentTaskData = null;

window.openTaskDetail = function(jobId) {
    const rawData = window.app.rawData;
    const tasks = rawData?.task_logs || [];
    const task = tasks.find(t => t.job_id === jobId);
    if (!task) return;

    document.getElementById('modal-task-id').textContent = `Task: ${jobId}`;
    document.getElementById('modal-task-meta').innerHTML = `
        <span class="status-${task.status}">${task.status}</span> | 
        ${task.user_email} | ${window.formatDateSafe(task.start_time)}`;

    const summaries = task.api_total_counts?.summaries || [];
    currentTaskData = { timestamps: [], appUsage: [], globalMaxCpu: [], globalMaxTotalTime: [], accounts: {} };

    summaries.forEach((s, idx) => {
        const label = s.timestamp ? window.formatDateSafe(s.timestamp) : `Batch ${idx+1}`;
        currentTaskData.timestamps.push(label);
        currentTaskData.appUsage.push((s.rate_limits?.app_usage_pct||0)*100);

        let maxCpu = 0, maxTime = 0;
        if (s.rate_limits?.account_details) {
            s.rate_limits.account_details.forEach(acc => {
                const id = acc.account_id;
                if (!currentTaskData.accounts[id]) {
                    currentTaskData.accounts[id] = { insightsUsage:[], eta:[], cpuTime:[], totalTime:[], tier:'N/A', call_count:0, max_insights:0, max_eta:0 };
                    for (let i=0; i<currentTaskData.timestamps.length-1; i++) {
                        currentTaskData.accounts[id].insightsUsage.push(0);
                        currentTaskData.accounts[id].eta.push(0);
                        currentTaskData.accounts[id].cpuTime.push(0);
                        currentTaskData.accounts[id].totalTime.push(0);
                    }
                }
                currentTaskData.accounts[id].insightsUsage.push(acc.insights_usage_pct||0);
                currentTaskData.accounts[id].eta.push(acc.eta_seconds||0);
                let cpu=0, tTime=0;
                (acc.business_use_cases||[]).forEach(uc => {
                    cpu += uc.total_cputime||0;
                    tTime += uc.total_time||0;
                    if (uc.type==='ads_insights') currentTaskData.accounts[id].tier = uc.ads_api_access_tier;
                });
                currentTaskData.accounts[id].cpuTime.push(cpu);
                currentTaskData.accounts[id].totalTime.push(tTime);
                currentTaskData.accounts[id].max_insights = Math.max(currentTaskData.accounts[id].max_insights, acc.insights_usage_pct||0);
                currentTaskData.accounts[id].max_eta = Math.max(currentTaskData.accounts[id].max_eta, acc.eta_seconds||0);
                currentTaskData.accounts[id].call_count++;
                maxCpu = Math.max(maxCpu, cpu);
                maxTime = Math.max(maxTime, tTime);
            });
        }
        currentTaskData.globalMaxCpu.push(maxCpu);
        currentTaskData.globalMaxTotalTime.push(maxTime);

        Object.values(currentTaskData.accounts).forEach(a => {
            while (a.insightsUsage.length < currentTaskData.timestamps.length) { a.insightsUsage.push(0); a.eta.push(0); a.cpuTime.push(0); a.totalTime.push(0); }
        });
    });

    const accSelect = document.getElementById('account-selector');
    const metricSelect = document.getElementById('metric-selector');
    metricSelect.disabled = false;
    accSelect.innerHTML = '<option value="all">All Accounts</option>';
    Object.keys(currentTaskData.accounts).forEach(id => { accSelect.innerHTML += `<option value="${id}">${id}</option>`; });
    accSelect.onchange = () => {
        const isAll = accSelect.value === 'all';
        if (isAll && (metricSelect.value==='insights_usage' || metricSelect.value==='eta')) metricSelect.value = 'app_usage';
        updateDetailChart();
    };
    metricSelect.onchange = updateDetailChart;
    updateDetailChart();

    const sortedAccounts = Object.entries(currentTaskData.accounts).sort((a,b) => b[1].call_count - a[1].call_count);
    document.getElementById('modal-account-list').innerHTML = sortedAccounts.map(([id, d]) => `
        <tr onclick="selectAccount('${id}')" style="cursor:pointer;">
            <td>${id}</td><td>${d.max_insights}%</td>
            <td>${d.max_eta>0 ? `<strong style="color:red">${d.max_eta}</strong>` : '0'}</td>
            <td>${d.tier}</td><td><strong>${d.call_count}</strong></td>
        </tr>`).join('');

    const modal = document.getElementById('task-detail-modal');
    modal.style.display = 'block';

    const logContainer = document.getElementById('log-container');
    const logContent   = document.getElementById('log-content');
    const btnViewLogs  = document.getElementById('btn-view-logs');
    if (logContainer) logContainer.style.display = 'none';
    if (logContent) logContent.textContent = '';
    if (btnViewLogs) {
        btnViewLogs.textContent = 'View Full Logs';
        const newBtn = btnViewLogs.cloneNode(true);
        btnViewLogs.parentNode.replaceChild(newBtn, btnViewLogs);
        newBtn.addEventListener('click', () => {
            if (logContainer.style.display === 'none') {
                fetchTaskLogs(jobId);
                logContainer.style.display = 'block';
                newBtn.textContent = 'Hide Logs';
            } else {
                logContainer.style.display = 'none';
                newBtn.textContent = 'View Full Logs';
            }
        });
    }

    const closeBtn = modal.querySelector('.close-modal');
    if (closeBtn) closeBtn.onclick = () => modal.style.display = 'none';
    window.onclick = e => { if (e.target === modal) modal.style.display = 'none'; };
};

async function fetchTaskLogs(jobId) {
    const logContent = document.getElementById('log-content');
    logContent.textContent = 'Loading logs...';
    try {
        const res = await fetch(`/api/dashboard/logs/${jobId}`);
        if (!res.ok) throw new Error('Failed to fetch logs');
        const data = await res.json();
        logContent.textContent = data.logs || 'No logs found.';
    } catch (err) {
        logContent.textContent = `Error loading logs: ${err.message}`;
    }
}

window.selectAccount = function(accountId) {
    const accSelect = document.getElementById('account-selector');
    if (accSelect) { accSelect.value = accountId; accSelect.dispatchEvent(new Event('change')); }
};

function updateDetailChart() {
    if (!currentTaskData) return;
    const accSelect    = document.getElementById('account-selector');
    const metricSelect = document.getElementById('metric-selector');
    const accountId    = accSelect.value;
    const metric       = metricSelect.value;

    Array.from(metricSelect.options).forEach(opt => {
        opt.disabled = accountId==='all' && (opt.value==='insights_usage' || opt.value==='eta');
    });

    const labels = currentTaskData.timestamps;
    let datasets = [], yMax = 100;

    if (accountId === 'all') {
        if (metric === 'app_usage') {
            datasets.push({ label:'App Usage PCT (Global)', data:currentTaskData.appUsage, borderColor:'#e74c3c', backgroundColor:window.hexToRgba('#e74c3c',0.1), fill:true, tension:0.3, pointRadius:2 });
        } else if (metric === 'time_stats') {
            datasets.push({ label:'Max CPU Time', data:currentTaskData.globalMaxCpu, borderColor:'#9b59b6', fill:false, tension:0.3, pointRadius:2 });
            datasets.push({ label:'Max Process Time', data:currentTaskData.globalMaxTotalTime, borderColor:'#2c3e50', fill:false, tension:0.3, pointRadius:2 });
            yMax = null;
        }
    } else {
        const accData = currentTaskData.accounts[accountId];
        if (!accData) return;
        switch (metric) {
            case 'app_usage':    datasets.push({ label:'App Usage PCT (Global)', data:currentTaskData.appUsage, borderColor:'#e74c3c', backgroundColor:window.hexToRgba('#e74c3c',0.1), fill:true, tension:0.3, pointRadius:2 }); break;
            case 'insights_usage': datasets.push({ label:`Insights Usage (${accountId})`, data:accData.insightsUsage, borderColor:'#3498db', backgroundColor:window.hexToRgba('#3498db',0.1), fill:true, tension:0.3, pointRadius:2 }); break;
            case 'eta':          datasets.push({ label:`ETA (${accountId})`, data:accData.eta, borderColor:'#f39c12', backgroundColor:window.hexToRgba('#f39c12',0.1), fill:true, tension:0.3, pointRadius:2 }); yMax=null; break;
            case 'time_stats':
                datasets.push({ label:`CPU Time (${accountId})`, data:accData.cpuTime, borderColor:'#9b59b6', fill:false, tension:0.3, pointRadius:2 });
                datasets.push({ label:`Process Time (${accountId})`, data:accData.totalTime, borderColor:'#2c3e50', fill:false, tension:0.3, pointRadius:2 });
                yMax=null; break;
        }
    }

    const ctx = document.getElementById('detailUsageChart')?.getContext('2d');
    if (!ctx) return;
    if (window.app.charts.detailUsage) window.app.charts.detailUsage.destroy();
    window.app.charts.detailUsage = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: { responsive:true, maintainAspectRatio:false, scales: { y: { beginAtZero:true, max:yMax, title:{ display:true, text:'Value' } } }, plugins: {} }
    });
}

// ================================================================
// EMAIL FAILED MODAL
// ================================================================
window.openEmailFailedModal = function(email) {
    const rawData = window.app.rawData;
    const tasks   = rawData?.task_logs || [];
    const failed  = tasks.filter(t => t.user_email===email && (t.status==='FAILED'||t.status==='FAILURE'));

    document.getElementById('email-failed-title').textContent = `Failed Tasks: ${email}`;
    document.getElementById('email-failed-meta').innerHTML = `<span style="color:#e74c3c;font-weight:600;">${failed.length} failed task${failed.length!==1?'s':''}</span>`;

    const tbody = document.getElementById('email-failed-tasks-body');
    tbody.innerHTML = failed.length===0
        ? '<tr><td colspan="6" style="text-align:center;color:#999;padding:20px;">No failed tasks found</td></tr>'
        : failed.map(t => `
            <tr onclick="openTaskDetailFromEmailModal('${t.job_id}')" style="cursor:pointer;">
                <td><span class="job-id">${(t.job_id||'').substring(0,8)}...</span></td>
                <td>${t.task_type||'N/A'}</td>
                <td class="status-${t.status}">${t.status}</td>
                <td>${window.formatDateSafe(t.start_time)}</td>
                <td>${t.duration_seconds ? parseFloat(t.duration_seconds).toFixed(2)+'s' : 'N/A'}</td>
                <td class="task-message" style="max-width:300px;white-space:normal;word-wrap:break-word;">${t.message||''}</td>
            </tr>`).join('');

    const modal = document.getElementById('email-failed-modal');
    modal.style.display = 'block';
    document.getElementById('email-failed-close').onclick = () => modal.style.display = 'none';
    window.addEventListener('click', function handler(e) {
        if (e.target === modal) { modal.style.display='none'; window.removeEventListener('click', handler); }
    });
};

window.openTaskDetailFromEmailModal = function(jobId) {
    document.getElementById('email-failed-modal').style.display = 'none';
    window.openTaskDetail(jobId);
};

// ================================================================
// DELETE TASK LOGS
// ================================================================
function initDeleteTasksOverview() {
    const masterCheckbox   = document.getElementById('master-checkbox');
    const deleteSelectedBtn = document.getElementById('btn-delete-selected');
    const deleteAllBtn     = document.getElementById('btn-delete-all');
    const tbody            = document.getElementById('tasks-table-body');
    if (!masterCheckbox || !deleteSelectedBtn || !deleteAllBtn || !tbody) return;

    const updateBtn = () => {
        deleteSelectedBtn.disabled = document.querySelectorAll('.row-checkbox:checked').length === 0;
    };

    masterCheckbox.addEventListener('change', e => {
        document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = e.target.checked);
        updateBtn();
    });

    tbody.addEventListener('change', e => {
        if (!e.target.classList.contains('row-checkbox')) return;
        updateBtn();
        const all = Array.from(document.querySelectorAll('.row-checkbox'));
        masterCheckbox.checked = all.length>0 && all.every(c=>c.checked);
        masterCheckbox.indeterminate = all.some(c=>c.checked) && !all.every(c=>c.checked);
    });

    deleteSelectedBtn.addEventListener('click', async () => {
        const ids = Array.from(document.querySelectorAll('.row-checkbox:checked')).map(c=>c.value);
        if (!ids.length || !confirm(`Delete ${ids.length} selected task logs?`)) return;
        try {
            const res = await fetch(window.location.origin+'/api/tasks', { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({job_ids:ids}) });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            masterCheckbox.checked = masterCheckbox.indeterminate = false;
            updateBtn();
            fetchAndRender();
        } catch (e) { alert('Failed to delete: '+e.message); }
    });

    deleteAllBtn.addEventListener('click', async () => {
        if (!confirm('DELETE ALL task logs? This cannot be undone.')) return;
        try {
            const res = await fetch(window.location.origin+'/api/tasks', { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({delete_all:true}) });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            masterCheckbox.checked = masterCheckbox.indeterminate = false;
            updateBtn();
            fetchAndRender();
        } catch (e) { alert('Failed to delete: '+e.message); }
    });
}
