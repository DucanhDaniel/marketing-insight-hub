/* ================================================================
   jobs.js - Job Manager tab: create/cancel job forms + active jobs polling
   ================================================================ */

const FB_TEMPLATES = {
    facebook_performance: ['Campaign Overview Report', 'Ad Set Performance Report', 'Ad Performance Report', 'Ad Creative Report'],
    facebook_breakdown:   ['Campaign Performance by AGE & GENDER', 'Campaign Performance by Age', 'Campaign Performance by Gender', 'Campaign Performance by Platform', 'Campaign Performance by Region'],
    facebook_daily:       ['Account Daily Report', 'Campaign Daily Report', 'Ad Set Daily Report', 'Ad Daily Report', 'Ad Creative Daily Report', 'LOCATION_DETAILED_REPORT', 'AGE & GENDER_DETAILED_REPORT', 'Campaign Performance by Hour (Audience Time)']
};

window.initJobs = function() {
    // Template selector
    const templateSelect = document.getElementById('job-template-name');
    const taskTypeSelect = document.getElementById('job-task-type');
    const templateGroup  = document.getElementById('fb-template-group');

    function updateTemplates() {
        if (!templateSelect || !taskTypeSelect) return;
        const type = taskTypeSelect.value;
        templateSelect.innerHTML = '';
        if (FB_TEMPLATES[type]) {
            FB_TEMPLATES[type].forEach(tmpl => {
                const opt = document.createElement('option');
                opt.value = opt.textContent = tmpl;
                templateSelect.appendChild(opt);
            });
            if (templateGroup) templateGroup.style.display = 'flex';
        } else {
            if (templateGroup) templateGroup.style.display = 'none';
        }
    }
    taskTypeSelect?.addEventListener('change', updateTemplates);
    updateTemplates();

    // Load saved access token
    const tokenInput    = document.getElementById('job-access-token');
    const saveTokenCheck = document.getElementById('job-save-token');
    if (tokenInput && saveTokenCheck) {
        const saved = localStorage.getItem('mih_access_token');
        if (saved) { tokenInput.value = saved; saveTokenCheck.checked = true; }
    }

    // Default dates (yesterday → today)
    const startInput = document.getElementById('job-start-date');
    const endInput   = document.getElementById('job-end-date');
    if (startInput && endInput) {
        const today    = new Date();
        const lastDay  = new Date(today);
        lastDay.setDate(lastDay.getDate() - 1);
        endInput.value   = today.toISOString().split('T')[0];
        startInput.value = lastDay.toISOString().split('T')[0];
    }

    // Create Job form
    document.getElementById('create-job-form')?.addEventListener('submit', async e => {
        e.preventDefault();
        const statusDiv  = document.getElementById('create-job-status');
        statusDiv.textContent = 'Submitting job...';
        statusDiv.style.color = '#3498db';

        const taskType = document.getElementById('job-task-type').value;
        const token    = document.getElementById('job-access-token').value;
        if (document.getElementById('job-save-token').checked) localStorage.setItem('mih_access_token', token);
        else localStorage.removeItem('mih_access_token');

        const payload = {
            task_type:   taskType,
            job_id:      `job_${Date.now()}`,
            task_id:     `task_${Date.now()}`,
            access_token: token,
            start_date:  document.getElementById('job-start-date').value,
            end_date:    document.getElementById('job-end-date').value,
            user_email:  document.getElementById('job-user-email').value,
            destination: 'clickhouse',
            selected_fields: []
        };
        const accountsStr = document.getElementById('job-accounts').value.trim();
        if (accountsStr) payload.accounts = accountsStr.split(',').map(a => a.trim()).filter(a => a);
        if (taskType.startsWith('facebook_')) payload.template_name = document.getElementById('job-template-name').value;

        try {
            const res = await fetch(`${window.location.origin}/reports/create-job`, {
                method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
            const data = await res.json();
            statusDiv.textContent = `✅ Job Created! ID: ${data.job_id}`;
            statusDiv.style.color = '#2ecc71';
        } catch (err) {
            statusDiv.textContent = `❌ Failed: ${err.message}`;
            statusDiv.style.color = '#e74c3c';
        }
    });

    // Cancel Job form
    document.getElementById('cancel-job-form')?.addEventListener('submit', async e => {
        e.preventDefault();
        const jobId    = document.getElementById('cancel-job-id').value.trim();
        const statusDiv = document.getElementById('cancel-job-status');
        if (!jobId) return;
        statusDiv.textContent = 'Sending cancel request...';
        statusDiv.style.color = '#e67e22';
        try {
            const res = await fetch(`${window.location.origin}/reports/${jobId}/cancel`, { method:'POST' });
            if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
            statusDiv.textContent = `✅ Cancel request sent for: ${jobId}`;
            statusDiv.style.color = '#2ecc71';
            document.getElementById('cancel-job-id').value = '';
        } catch (err) {
            statusDiv.textContent = `❌ Failed: ${err.message}`;
            statusDiv.style.color = '#e74c3c';
        }
    });

    // Start active jobs polling
    startPollingActiveJobs();
};

// ================================================================
// ACTIVE JOBS POLLING
// ================================================================
let _pollInterval = null;

window.startPollingActiveJobs = function() {
    if (_pollInterval) clearInterval(_pollInterval);
    fetchActiveJobs();
    _pollInterval = setInterval(fetchActiveJobs, 3000);
};

window.stopPollingActiveJobs = function() {
    if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
};

async function fetchActiveJobs() {
    try {
        const res = await fetch(`${window.location.origin}/api/active-jobs`);
        if (!res.ok) return;
        renderActiveJobsTable(await res.json());
    } catch (e) {
        console.error('Polling error:', e);
    }
}

function renderActiveJobsTable(tasks) {
    const tbody = document.getElementById('active-jobs-table-body');
    if (!tbody) return;
    if (tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#777;padding:20px;">No active jobs at the moment.</td></tr>';
        return;
    }
    tbody.innerHTML = tasks.map(t => {
        const progress = t.progress || 0;
        const bar = `<div style="display:flex;align-items:center;gap:10px;">
            <div style="flex:1;background:#f3f3f3;border-radius:4px;overflow:hidden;height:10px;">
                <div style="width:${progress}%;background:#3498db;height:100%;transition:width 0.5s;"></div>
            </div>
            <span style="font-size:0.8rem;color:#666;width:30px;">${progress}%</span>
        </div>`;
        return `<tr onclick="openTaskDetail && openTaskDetail('${t.job_id}')" style="cursor:pointer;">
            <td><span class="job-id">${(t.job_id||'').substring(0,8)}...</span></td>
            <td>${t.task_type||''}</td>
            <td style="width:200px;">${bar}</td>
            <td class="status-${t.status}">${t.status}</td>
            <td class="task-message" style="max-width:250px;white-space:normal;word-wrap:break-word;font-size:0.85rem;">${t.last_message||t.message||''}</td>
            <td><button class="btn btn-danger" style="padding:4px 8px;font-size:0.8rem;" onclick="event.stopPropagation();cancelJob('${t.job_id}')">Cancel</button></td>
        </tr>`;
    }).join('');
}
