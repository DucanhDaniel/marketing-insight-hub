/* ================================================================
   tiktok.js - TikTok tab: charts and task table
   API: GET /api/dashboard/tiktok
   ================================================================ */

window.initTiktok = function() {
    // No form setup needed for TikTok tab
};

window.renderTiktok = function(data) {
    const tasks       = data.task_logs || [];
    const apiTimeseries = data.api_timeseries || {};

    const tkTasks = tasks.filter(t =>
        ['product','creative','tiktok_product','tiktok_creative'].includes(t.task_type)
        || (t.api_total_counts && JSON.stringify(t.api_total_counts).includes('tiktok.com'))
    );

    const productTasks  = tkTasks.filter(t => t.task_type.includes('product')).length;
    const creativeTasks = tkTasks.filter(t => t.task_type.includes('creative')).length;

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('tiktok-total-tasks',    tkTasks.length);
    set('tiktok-product-tasks',  productTasks);
    set('tiktok-creative-tasks', creativeTasks);

    // Type Breakdown Chart
    const typeCounts = { 'Product':0, 'Creative':0, 'Other':0 };
    tkTasks.forEach(t => {
        const type = (t.task_type||'').toLowerCase();
        if (type.includes('product'))  typeCounts['Product']++;
        else if (type.includes('creative')) typeCounts['Creative']++;
        else typeCounts['Other']++;
    });
    const ctxType = document.getElementById('tiktokTypeChart')?.getContext('2d');
    if (ctxType) {
        if (window.app.charts.tiktokType) window.app.charts.tiktokType.destroy();
        window.app.charts.tiktokType = new Chart(ctxType, {
            type: 'pie',
            data: { labels: Object.keys(typeCounts), datasets: [{ data: Object.values(typeCounts), backgroundColor: ['#3498db','#e67e22','#95a5a6'] }] },
            options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{position:'bottom'} } }
        });
    }

    // Status Chart
    const statusCounts = { 'Success':0, 'Failed':0, 'Cancelled':0, 'Started':0 };
    tkTasks.forEach(t => {
        const s = (t.status||'').toUpperCase();
        if (s==='SUCCESS'||s==='COMPLETED')   statusCounts['Success']++;
        else if (s==='CANCELLED'||s==='REVOKED') statusCounts['Cancelled']++;
        else if (s==='STARTED'||s==='RUNNING')  statusCounts['Started']++;
        else statusCounts['Failed']++;
    });
    const ctxStatus = document.getElementById('tiktokStatusChart')?.getContext('2d');
    if (ctxStatus) {
        if (window.app.charts.tiktokStatus) window.app.charts.tiktokStatus.destroy();
        window.app.charts.tiktokStatus = new Chart(ctxStatus, {
            type: 'doughnut',
            data: { labels: ['Success','Failed','Cancelled','Started'], datasets: [{ data: Object.values(statusCounts), backgroundColor: ['#2ecc71','#e74c3c','#95a5a6','#3498db'], borderWidth:0 }] },
            options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{position:'bottom'} } }
        });
    }

    // API Timeline
    const tiktokEndpoints = {};
    for (const [url, series] of Object.entries(apiTimeseries)) {
        if (url.includes('tiktok.com')) {
            let name = url.split('/v1.3/')[1] || url;
            name = name.replace(/\/$/, '');
            tiktokEndpoints[name] = series;
        }
    }
    renderLineChart('tiktokApiChart', tiktokEndpoints, window.app.charts.tiktokApi, c => window.app.charts.tiktokApi = c);

    // API Totals Table
    const endpointCounts = {};
    for (const [ep, series] of Object.entries(tiktokEndpoints)) {
        endpointCounts[ep] = series.reduce((s, item) => s + (item.count||0), 0);
    }
    const totalsBody = document.getElementById('tiktok-api-totals-body');
    if (totalsBody) {
        totalsBody.innerHTML = Object.entries(endpointCounts)
            .sort((a,b) => b[1]-a[1])
            .map(([ep, count]) => `<tr><td>${ep}</td><td><strong>${count}</strong></td></tr>`)
            .join('');
    }

    // Recent Tasks Table
    window.renderTasksTable(tkTasks, 'tiktok-tasks-body', ['job_id','task_type','user_email','status','duration_seconds','message']);
};

function renderLineChart(canvasId, datasetMap, chartInstance, setChartInstance) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return;
    if (chartInstance) chartInstance.destroy();
    if (!datasetMap || Object.keys(datasetMap).length === 0) return;

    const colors = ['#1abc9c','#e74c3c','#3498db','#f1c40f','#9b59b6'];
    const datasets = Object.entries(datasetMap).map(([label, pts], i) => ({
        label, data: pts.map(d => d.count), borderColor: colors[i%colors.length], tension:0.3, fill:false
    }));
    const firstData = Object.values(datasetMap)[0];
    const labels = firstData.map(d => new Date(d.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}));

    setChartInstance(new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: { responsive:true, maintainAspectRatio:false, interaction:{mode:'index',intersect:false}, plugins:{legend:{position:'bottom'}}, scales:{y:{beginAtZero:true}} }
    }));
}
