/* ================================================================
   facebook.js - Facebook tab: charts and task table
   API: GET /api/dashboard/facebook
   ================================================================ */

window.initFacebook = function() {
    // No special init needed
};

window.renderFacebook = function(data) {
    const tasks   = data.task_logs || [];
    const fbTasks = tasks.filter(t => t.task_type && (t.task_type.includes('facebook') || t.task_type.includes('fb')));

    let totalBatches=0, successBatches=0, totalBackoff=0;
    fbTasks.forEach(t => {
        if (t.api_total_counts) {
            totalBackoff += (t.api_total_counts.total_backoff_sec||0);
            const summaries = t.api_total_counts.summaries||[];
            summaries.forEach(s => {
                totalBatches++;
                if (s.success_count>0 && s.error_count===0) successBatches++;
            });
        }
    });

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('fb-total-tasks',    fbTasks.length);
    set('fb-success-batches', successBatches);
    set('fb-total-backoff',  `${totalBackoff}s`);

    // Usage Chart
    const usageBuckets = { 'Safe (<75%)':0, 'Warning (75-95%)':0, 'Critical (>95%)':0 };
    fbTasks.forEach(t => {
        (t.api_total_counts?.summaries||[]).forEach(s => {
            const u = (s.rate_limits?.app_usage_pct||0)*100;
            if (u>=95) usageBuckets['Critical (>95%)']++;
            else if (u>=75) usageBuckets['Warning (75-95%)']++;
            else usageBuckets['Safe (<75%)']++;
        });
    });
    const ctxUsage = document.getElementById('fbUsageChart')?.getContext('2d');
    if (ctxUsage) {
        if (window.app.charts.fbUsage) window.app.charts.fbUsage.destroy();
        window.app.charts.fbUsage = new Chart(ctxUsage, {
            type: 'bar',
            data: { labels: Object.keys(usageBuckets), datasets: [{ label:'Batch Requests by Usage Load', data:Object.values(usageBuckets), backgroundColor:['#2ecc71','#f1c40f','#e74c3c'] }] },
            options: { responsive:true, maintainAspectRatio:false, scales:{ y:{ beginAtZero:true } } }
        });
    }

    // Type Chart
    const typeCounts = { 'Daily':0, 'Performance':0, 'Breakdown':0, 'Other':0 };
    fbTasks.forEach(t => {
        const n = (t.task_type||'').toLowerCase();
        if (n.includes('daily')) typeCounts['Daily']++;
        else if (n.includes('performance')) typeCounts['Performance']++;
        else if (n.includes('breakdown'))   typeCounts['Breakdown']++;
        else typeCounts['Other']++;
    });
    const ctxType = document.getElementById('fbTypeChart')?.getContext('2d');
    if (ctxType) {
        if (window.app.charts.fbType) window.app.charts.fbType.destroy();
        window.app.charts.fbType = new Chart(ctxType, {
            type: 'pie',
            data: { labels:Object.keys(typeCounts), datasets:[{ data:Object.values(typeCounts), backgroundColor:['#3498db','#9b59b6','#f1c40f','#95a5a6'] }] },
            options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'bottom'}} }
        });
    }

    // Status Chart
    const statusCounts = { 'Success':0, 'Failed':0, 'Cancelled':0, 'Started':0 };
    fbTasks.forEach(t => {
        const s = (t.status||'').toUpperCase();
        if (s==='SUCCESS'||s==='COMPLETED')   statusCounts['Success']++;
        else if (s==='CANCELLED'||s==='REVOKED') statusCounts['Cancelled']++;
        else if (s==='STARTED'||s==='RUNNING')  statusCounts['Started']++;
        else statusCounts['Failed']++;
    });
    const ctxStatus = document.getElementById('fbStatusChart')?.getContext('2d');
    if (ctxStatus) {
        if (window.app.charts.fbStatus) window.app.charts.fbStatus.destroy();
        window.app.charts.fbStatus = new Chart(ctxStatus, {
            type: 'doughnut',
            data: { labels:['Success','Failed','Cancelled','Started'], datasets:[{ data:Object.values(statusCounts), backgroundColor:['#2ecc71','#e74c3c','#95a5a6','#3498db'], borderWidth:0 }] },
            options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'bottom'}} }
        });
    }

    // FB Task Table
    const tbody = document.getElementById('fb-tasks-body');
    if (tbody) {
        tbody.innerHTML = fbTasks.slice(0,1000).map(t => {
            const template = t.template_name||'N/A';
            const batches  = t.api_total_counts?.batch_count||0;
            const backoff  = t.api_total_counts?.total_backoff_sec||0;
            return `<tr onclick="openTaskDetail('${t.job_id}')" title="Click to view details">
                <td><span class="job-id">${(t.job_id||'').substring(0,8)}...</span></td>
                <td>${template}</td>
                <td>${t.user_email}</td>
                <td class="status-${t.status}">${t.status}</td>
                <td>${backoff}s</td>
                <td>${batches}</td>
                <td class="task-message" style="max-width:300px;white-space:normal;word-wrap:break-word;">${t.message||''}</td>
            </tr>`;
        }).join('');
    }
};
