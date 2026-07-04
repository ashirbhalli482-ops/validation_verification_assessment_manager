// Initializes progress bars and renders the KPI chart on the employee progress list page
(function(){
  function initProgressBars() {
    document.querySelectorAll('.progress-bar[data-width]').forEach(function (el) {
      var v = parseFloat(el.getAttribute('data-width')) || 0;
      el.style.width = v + '%';
    });
  }

  function renderScoresByKpiChart() {
    var rawNode = document.getElementById('tasksPeriodData');
    if (!rawNode) return;
    var raw = rawNode.textContent || '[]';
    var data = [];
    try { data = JSON.parse(raw); } catch (e) { data = []; }
    var perKpi = {};
    data.forEach(function(t){
      var k = (t.kpi && t.kpi.name) ? t.kpi.name : 'Unassigned';
      if(!perKpi[k]) perKpi[k] = [];
      if (typeof t.final_score === 'number') perKpi[k].push(t.final_score);
    });
    var labels = Object.keys(perKpi);
    var avgs = labels.map(function(k){
      var arr = perKpi[k];
      if (!arr.length) return 0;
      var s = arr.reduce(function(a,b){return a+b;},0);
      return Math.round((s/arr.length)*100)/100;
    });

    var palette = ['#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f','#edc949','#af7aa1','#ff9da7','#9c755f','#bab0ac'];
    var canvas = document.getElementById('scoresByKPIChart');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    if (!ctx || !window.Chart) return;

    if (window.ChartDataLabels) { Chart.register(ChartDataLabels); }

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Average Final Score by KPI',
          data: avgs,
          backgroundColor: labels.map(function(_,i){return palette[i % palette.length] + 'CC';}),
          borderColor: labels.map(function(_,i){return palette[i % palette.length];}),
          borderWidth: 1.5,
          borderRadius: 6,
          barThickness: 'flex',
          maxBarThickness: 48
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 16, right: 12, bottom: 8, left: 12 } },
        plugins: {
          legend: { display: true, position: 'bottom' },
          title: { display: true, text: 'Average Final Score by KPI' },
          tooltip: {
            callbacks: { label: function(ctx){ return (ctx.parsed.y || 0) + '%'; } }
          },
          datalabels: {
            anchor: 'end', align: 'end',
            formatter: function(v){ return v + '%'; },
            color: '#333', font: { weight: 'bold', size: 11 },
            clip: true
          }
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, max: 100, grid: { color: '#eee' }, ticks: { callback: function(v){ return v + '%'; } } }
        },
        animation: { duration: 800, easing: 'easeOutQuart' }
      }
    });
  }

  function renderEmployeesProgressChart() {
    var rawNode = document.getElementById('employeesSummaryData');
    if (!rawNode) return;
    var raw = rawNode.textContent || '[]';
    var rows = [];
    try { rows = JSON.parse(raw); } catch (e) { rows = []; }
    if (!rows.length) return;

    var labels = rows.map(function(r){ return r.name; });
    var data = rows.map(function(r){ return r.score; });

    var palette = ['#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f','#edc949','#af7aa1','#ff9da7','#9c755f','#bab0ac'];
    var canvas = document.getElementById('employeesProgressChart');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    if (!ctx || !window.Chart) return;

    if (window.ChartDataLabels) { Chart.register(ChartDataLabels); }

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Employee Progress Score',
          data: data,
          backgroundColor: labels.map(function(_,i){return palette[i % palette.length] + 'CC';}),
          borderColor: labels.map(function(_,i){return palette[i % palette.length];}),
          borderWidth: 1.5,
          borderRadius: 6,
          barThickness: 'flex',
          maxBarThickness: 48
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 16, right: 12, bottom: 8, left: 12 } },
        plugins: {
          legend: { display: true, position: 'bottom' },
          title: { display: true, text: 'Employee Progress Scores' },
          tooltip: { callbacks: { label: function(ctx){ return (ctx.parsed.y || 0) + '%'; } } },
          datalabels: {
            anchor: 'end', align: 'end',
            formatter: function(v){ return v + '%'; },
            color: '#333', font: { weight: 'bold', size: 11 },
            clip: true
          }
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, max: 100, grid: { color: '#eee' }, ticks: { callback: function(v){ return v + '%'; } } }
        },
        animation: { duration: 800, easing: 'easeOutQuart' }
      }
    });
  }

  function onReady(fn){
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else { fn(); }
  }

  onReady(function(){
    initProgressBars();
    renderScoresByKpiChart();
    renderEmployeesProgressChart();
  });
})();


