/* Monthly Employee Stats charts (ApexCharts) — improved readability and styling */
(function () {
  try {
    if (!window.ApexCharts) return;

    function parseJSONScript(id) {
      var el = document.getElementById(id);
      if (!el) return null;
      try { return JSON.parse(el.textContent || el.innerText || 'null'); } catch (e) { return null; }
    }

    // Translation function for Arabic support
    function tr(text) {
      var lang = (function(){ try { return localStorage.getItem('ui.lang') || 'en'; } catch(e){ return 'en'; } })();
      if (lang !== 'ar') return text;
      
      var translations = {
        // Chart titles
        'Monthly Task Status': 'حالة المهام شهريا',
        'Task Priority Distribution': 'توزيع أولويات المهام',
        'Tasks by Employee': 'المهام حسب الموظف',
        'Monthly Task Creation Trend': 'تطور إنشاء المهام شهريا',
        // Axis labels
        'Status': 'الحالة',
        'Number of Tasks': 'عدد المهام',
        'Employees': 'الموظفون',
        'Month': 'الشهر',
        'Tasks': 'المهام',
        // Statuses
        'Open': 'مفتوح',
        'Closed': 'مغلق',
        'Due': 'مستحق',
        // Priorities
        'High': 'عالي',
        'Medium': 'متوسط',
        'Low': 'منخفض',
        // Other dataset labels
        'Assigned': 'مسند',
        'Completed': 'منجز',
        // Months (if abbreviated from backend)
        'Jan': 'يناير',
        'Feb': 'فبراير',
        'Mar': 'مارس',
        'Apr': 'أبريل',
        'May': 'مايو',
        'Jun': 'يونيو',
        'Jul': 'يوليو',
        'Aug': 'أغسطس',
        'Sep': 'سبتمبر',
        'Oct': 'أكتوبر',
        'Nov': 'نوفمبر',
        'Dec': 'ديسمبر'
      };
      
      return translations[text] || text;
    }

    // Function to translate chart data labels and categories
    function translateChartData(data) {
      var lang = (function(){ try { return localStorage.getItem('ui.lang') || 'en'; } catch(e){ return 'en'; } })();
      if (lang !== 'ar' || !data) return data;
      
      // Create a deep copy to avoid modifying original data
      var translatedData = JSON.parse(JSON.stringify(data));
      
      // Translate labels array (statuses, priorities, months)
      if (translatedData.labels && Array.isArray(translatedData.labels)) {
        translatedData.labels = translatedData.labels.map(function(label) {
          return tr(label);
        });
      }
      
      // Translate dataset labels (e.g., 'Assigned' -> 'مسؤول')
      if (translatedData.datasets && Array.isArray(translatedData.datasets)) {
        translatedData.datasets = translatedData.datasets.map(function(dataset) {
          if (dataset.label) {
            dataset.label = tr(dataset.label);
          }
          return dataset;
        });
      }
      
      return translatedData;
    }

    function baseGrid() {
      return {
        strokeDashArray: 3,
        xaxis: { lines: { show: true } },
        yaxis: { lines: { show: true } }
      };
    }

    function baseLegend() {
      var lang = (function(){ try { return localStorage.getItem('ui.lang') || 'en'; } catch(e){ return 'en'; } })();
      return { 
        position: 'bottom', 
        markers: { radius: 3, width: 12, height: 12 },
        fontSize: '12px',
        fontFamily: lang === 'ar' ? 'Arial, sans-serif' : 'Arial, sans-serif',
        itemMargin: { horizontal: 8, vertical: 4 }
      };
    }

    function baseTooltip() { return { theme: 'dark' }; }

    function renderStatusBar(containerId, data) {
      var el = document.getElementById(containerId);
      if (!el || !data || !data.datasets || !data.datasets.length) return;
      
      // Translate chart data before rendering
      var translatedData = translateChartData(data);
      
      var options = {
        chart: { type: 'bar', height: 280, toolbar: { show: false } },
        title: { text: tr('Monthly Task Status'), align: 'center' },
        series: [{ name: translatedData.datasets[0].label || tr('Tasks'), data: translatedData.datasets[0].data }],
        xaxis: { categories: translatedData.labels, labels: { style: { fontSize: '12px' } }, title: { text: tr('Status') } },
        yaxis: { title: { text: tr('Number of Tasks') } },
        plotOptions: { bar: { borderRadius: 6, columnWidth: '45%', distributed: true, dataLabels: { position: 'center' } } },
        dataLabels: { 
          enabled: true, 
          style: { fontSize: '12px', colors: ['#111'] },
          offsetY: 0,
          formatter: function (val) { return (val === 0 || val === null) ? '' : val; }
        },
        colors: ['#ffc107', '#198754', '#dc3545'],
        tooltip: baseTooltip(),
        grid: baseGrid(),
        legend: {
          position: 'bottom',
          horizontalAlign: 'center',
          markers: { 
            radius: 3, 
            width: 12, 
            height: 12,
            offsetX: -5,
            offsetY: 0
          },
          fontSize: '12px',
          fontFamily: 'Arial, sans-serif',
          itemMargin: { horizontal: 8, vertical: 4 },
          onItemClick: { toggleDataSeries: false },
          onItemHover: { highlightDataSeries: true }
        }
      };
      new ApexCharts(el, options).render();
    }

    function renderPriorityDonut(containerId, data) {
      var el = document.getElementById(containerId);
      if (!el || !data || !data.datasets || !data.datasets.length) return;
      
      // Translate chart data before rendering
      var translatedData = translateChartData(data);
      
      var options = {
        chart: { type: 'donut', height: 280 },
        title: { text: tr('Task Priority Distribution'), align: 'center' },
        series: translatedData.datasets[0].data,
        labels: translatedData.labels,
        colors: translatedData.datasets[0].backgroundColor,
        legend: {
          position: 'bottom',
          horizontalAlign: 'center',
          markers: { 
            radius: 3, 
            width: 12, 
            height: 12,
            offsetX: -5,
            offsetY: 0
          },
          fontSize: '12px',
          fontFamily: 'Arial, sans-serif',
          itemMargin: { horizontal: 8, vertical: 4 },
          onItemClick: { toggleDataSeries: false },
          onItemHover: { highlightDataSeries: true }
        },
        dataLabels: { 
          enabled: true,
          style: { fontSize: '12px', fontWeight: 'bold', colors: ['#ffffff'] },
          dropShadow: { enabled: true, top: 0, left: 0, blur: 1, opacity: 0.35 },
          formatter: function (percent, opts) {
            var value = opts.w.config.series[opts.seriesIndex] || 0;
            return value + '\n' + percent.toFixed(0) + '%';
          },
          offsetY: 0
        },
        stroke: { width: 1 },
        plotOptions: {
          pie: {
            donut: {
              size: '65%',
              labels: {
                show: true,
                name: { show: true, fontSize: '14px', fontWeight: 'bold', color: '#495057' },
                value: { show: true, fontSize: '12px', color: '#6c757d' },
                total: { show: false }
              }
            }
          }
        }
      };
      new ApexCharts(el, options).render();
    }

    function renderEmployeeStacked(containerId, data) {
      var el = document.getElementById(containerId);
      if (!el || !data) return;
      
      // Translate chart data before rendering
      var translatedData = translateChartData(data);
      var series = (translatedData.datasets || []).map(function (ds) { return { name: ds.label, data: ds.data }; });
      
      var options = {
        chart: { type: 'bar', stacked: true, height: 340, toolbar: { show: false } },
        title: { text: tr('Tasks by Employee'), align: 'center' },
        series: series,
        xaxis: { categories: translatedData.labels, labels: { rotateAlways: false, trim: true, style: { fontSize: '12px' } }, title: { text: tr('Employees') } },
        yaxis: { title: { text: tr('Number of Tasks') } },
        plotOptions: { 
          bar: { 
            borderRadius: 6, 
            columnWidth: (translatedData.meta && translatedData.meta.xaxis === 'months') ? '35%' : '50%',
            dataLabels: { position: 'center' }
          } 
        },
        dataLabels: { 
          enabled: true,
          style: { fontSize: '11px', colors: ['#ffffff'] },
          dropShadow: { enabled: true, blur: 1, opacity: 0.35 },
          formatter: function (val) { return (!val || val < 1) ? '' : val; }
        },
        colors: ['#6c757d', '#ffc107', '#198754', '#dc3545'],
        grid: baseGrid(),
        tooltip: baseTooltip(),
        legend: {
          position: 'bottom',
          horizontalAlign: 'center',
          markers: { 
            radius: 3, 
            width: 12, 
            height: 12,
            offsetX: -5,
            offsetY: 0
          },
          fontSize: '12px',
          fontFamily: 'Arial, sans-serif',
          itemMargin: { horizontal: 8, vertical: 4 },
          onItemClick: { toggleDataSeries: false },
          onItemHover: { highlightDataSeries: true }
        }
      };
      new ApexCharts(el, options).render();
    }

    function renderMonthlyTrend(containerId, data) {
      var el = document.getElementById(containerId);
      if (!el || !data) return;
      
      // Translate chart data before rendering
      var translatedData = translateChartData(data);
      var series = (translatedData.datasets || []).map(function (ds) { return { name: ds.label, data: ds.data }; });
      
      var options = {
        chart: { type: 'line', height: 340, toolbar: { show: false } },
        title: { text: tr('Monthly Task Creation Trend'), align: 'center' },
        series: series,
        xaxis: { categories: translatedData.labels, tickPlacement: 'on', labels: { style: { fontSize: '12px' } }, title: { text: tr('Month') } },
        yaxis: { title: { text: tr('Number of Tasks') } },
        dataLabels: { enabled: false },
        stroke: { width: 2, curve: 'smooth' },
        legend: {
          position: 'bottom',
          markers: { 
            radius: 3, 
            width: 12, 
            height: 12,
            offsetX: -5,
            offsetY: 0
          },
          fontSize: '12px',
          fontFamily: 'Arial, sans-serif',
          itemMargin: { horizontal: 8, vertical: 4 },
          onItemClick: { toggleDataSeries: false },
          onItemHover: { highlightDataSeries: true }
        },
        tooltip: baseTooltip(),
        grid: baseGrid()
      };
      new ApexCharts(el, options).render();
    }

    var statusData = parseJSONScript('monthly-status-data');
    var priorityData = parseJSONScript('priority-data');
    var employeeData = parseJSONScript('employee-status-data');
    var trendData = parseJSONScript('monthly-trend-data');

    renderStatusBar('apex-monthlyStatus', statusData);
    renderPriorityDonut('apex-priority', priorityData);
    renderEmployeeStacked('apex-employeeStatus', employeeData);
    renderMonthlyTrend('apex-monthlyTrend', trendData);
  } catch (e) { /* no-op */ }
})();


