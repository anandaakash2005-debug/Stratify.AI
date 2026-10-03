function scrollToSection(id, event) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  if (event && event.currentTarget) event.currentTarget.classList.add('active');
  return false;
}

function safe(str) { const d = document.createElement("div"); d.textContent = str || ""; return d.innerHTML; }

document.addEventListener('DOMContentLoaded', () => {
  document.body.classList.add('dashboard-loading');

  document
    .getElementById('refreshBtn')
    ?.addEventListener('click', () => {
      location.reload();
    });

  document
    .getElementById('fullReportBtn')
    ?.addEventListener('click', () => {
      const data = localStorage.getItem('latest_analysis');
      if (!data) {
        alert("No report data found. Run an analysis first.");
        return;
      }

      const blob = new Blob([data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'startup-report.json';
      a.click();
      URL.revokeObjectURL(url);
    });

  // ─── Load from API (by ?id=) or localStorage ─────────────────────────────────
  let d = null;

  async function loadById(reportId) {
    const token = typeof Auth !== 'undefined' ? Auth.getToken() : null;
    const res = await fetch(
      (window.CONFIG?.API_URL || "http://localhost:8000") + "/api/v1/reports/" + reportId,
      { headers: token ? { Authorization: "Bearer " + token } : {} }
    );
    if (!res.ok) throw new Error("API returned " + res.status);
    const json = await res.json();
    const payload = json.data || {};
    const fullResponse = payload.report?.raw_ai_response || {};
    return { ...fullResponse, startup: fullResponse.startup || payload.startup || {} };
  }

  async function init() {
    const params = new URLSearchParams(window.location.search);
    const reportId = params.get("id");

    if (reportId) {
      try {
        d = await loadById(reportId);
        console.log("DASHBOARD DATA (from API):", d);
      } catch (err) {
        console.warn("Failed to load report by ID, falling back to localStorage:", err);
      }
    }

    if (!d) {
      try {
        const stored = localStorage.getItem("latest_analysis");
        if (stored) {
          const parsed = JSON.parse(stored);
          d = parsed.data || parsed;
          console.log("DASHBOARD DATA (from localStorage):", d);
          console.log("SWOT:", d.swot || d.swot_analysis);
          console.log("RISKS:", d.risks || d.risk_analysis);
          console.log("COMPETITORS:", d.competitors || d.competitor_analysis);
        }
      } catch (err) {
        console.warn("Failed to parse latest_analysis:", err);
      }
    }

    if (!d) {
      console.warn("NO analysis data found — redirecting to empty state");
      document.body.innerHTML = `
      <div style="
        min-height:100vh;
        background:#020617;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        color:white;
        font-family:sans-serif;
        gap:20px;
      ">
        <h1>No Analysis Data Found</h1>
        <p>Run a startup analysis first.</p>
        <a href="analysis.html" style="
          background:#6366f1;
          color:white;
          padding:12px 20px;
          border-radius:10px;
          text-decoration:none;
          font-weight:bold;
        ">Go To Analysis</a>
      </div>`;
      return; // use return instead of throw to avoid unhandled rejection noise
    }

    try {
      renderDashboard(d);
    } catch (err) {
      console.error("Dashboard render failed:", err);
      document.body.innerHTML = `<div style="min-height:100vh;background:#020617;display:flex;flex-direction:column;align-items:center;justify-content:center;color:white;font-family:sans-serif;gap:20px;padding:40px"><h1>Dashboard Render Error</h1><p style="color:rgba(255,255,255,0.6)">${safe(err.message)}</p><a href="analysis.html" style="background:#6366f1;color:white;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:bold">Run New Analysis</a></div>`;
    }
  }

  function renderDashboard(analysis) {
    const metrics = analysis.metrics || {};
    const charts = analysis.charts || {};
    const signals = analysis.financial_signals || [];
    const risks = analysis.risks || [];
    const swot = analysis.swot || {};
    const recs = analysis.recommendations || [];
    const comps = analysis.competitors || [];
    const funding = analysis.funding_readiness || {};
    const startup = analysis.startup || {};
    const bd = analysis.score_breakdown || [];

    const score = metrics.survival_score || 0;
    const probability = metrics.survival_probability || 0;
    const fundingReady = metrics.funding_readiness || 0;
    const runway = Number(metrics.runway_months || 0);
    const teamScore = metrics.team_score || 0;
    const marketScore = metrics.market_score || 0;
    const riskCount = metrics.risk_count || risks.length;
    const breakEven = metrics.break_even_month || '—';
    const name = startup.name || analysis.idea || 'Startup';
    const industry = startup.industry || '—';

    console.log('DASHBOARD METRICS:', metrics);
    console.log('DASHBOARD CHARTS:', charts);
    console.log('Revenue trend:', charts.revenue_trend);
    console.log('Burn trend:', charts.burn_trend);

    function scoreColor(v) {
      if (v >= 75) return 'var(--emerald)';
      if (v >= 55) return 'var(--amber)';
      return 'var(--rose)';
    }
    function plural(n, s, p) { return n === 1 ? s : p; }

    function setText(id, txt) { const el = document.getElementById(id); if (el) el.textContent = txt; }
    function setHTML(id, html) { const el = document.getElementById(id); if (el) el.innerHTML = html; }
    function setStyle(id, prop, val) { const el = document.getElementById(id); if (el) el.style[prop] = val; }

    function animCount(id, target, suffix = '', prefix = '', duration = 1200) {
      const el = document.getElementById(id);
      if (!el) return;
      const start = Date.now();
      const tick = () => {
        const p = Math.min((Date.now() - start) / duration, 1);
        const e = 1 - Math.pow(1 - p, 3);
        el.textContent = prefix + Math.round(target * e) + suffix;
        if (p < 1) requestAnimationFrame(tick);
        else el.textContent = prefix + target + suffix;
      };
      requestAnimationFrame(tick);
    }

    function setBar(id, pct, delay = 300) {
      setTimeout(() => {
        const el = document.getElementById(id);
        if (el) el.style.width = Math.min(100, Math.max(0, pct)) + '%';
      }, delay);
    }

    /** Funding bars: set width + data-width (main.js observer reads data-width) + color tier */
    function setFundingBar(fillId, pct) {
      const el = document.getElementById(fillId);
      if (!el) {
        console.warn('Funding bar element not found:', fillId);
        return;
      }
      const clamped = Math.min(100, Math.max(0, Math.round(Number(pct) || 0)));
      console.log('Funding bar:', fillId, clamped);

      el.dataset.width = String(clamped);
      el.classList.remove('fill-success', 'fill-warning', 'fill-danger', 'fill-info');
      if (clamped >= 70) el.classList.add('fill-success');
      else if (clamped >= 40) el.classList.add('fill-warning');
      else el.classList.add('fill-danger');

      el.style.width = '0%';
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.style.width = clamped + '%';
        });
      });
    }

    function sliceChartPoints(points, windowMode) {
      const hist12 = points.length >= 12 ? points.slice(0, 12) : points;
      if (windowMode === '6m') {
        return hist12.length >= 6 ? hist12.slice(-6) : hist12;
      }
      return hist12;
    }

    // ─── Chart.js defaults ────────────────────────────────────────────────────────
    Chart.defaults.color = '#cbd5e1';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';

    const revCtx = document.getElementById('revenueChart');
    let revenueChart = null;
    const revenuePoints = charts.revenue_trend || [];
    const burnPoints = charts.burn_trend || [];
    console.log('Burn chart data:', burnPoints);

    if (revCtx && revenuePoints.length > 0) {
      const ctx = revCtx.getContext('2d');
      const grad = ctx.createLinearGradient(0, 0, 0, 200);
      grad.addColorStop(0, 'rgba(99,102,241,0.35)');
      grad.addColorStop(1, 'rgba(99,102,241,0)');

      const rev6 = sliceChartPoints(revenuePoints, '6m');
      const rev12 = sliceChartPoints(revenuePoints, '1y');
      const burn6 = sliceChartPoints(burnPoints, '6m');
      const burn12 = sliceChartPoints(burnPoints, '1y');

      const labels6 = rev6.map(p => p.label);
      const revenue6 = rev6.map(p => p.value);
      const burn6Data = burn6.map(p => p.value);

      console.log('Revenue trend 6M:', labels6, 'Burn 6M:', burn6Data);

      const chartDatasets = [
        {
          label: 'Revenue',
          data: revenue6,
          borderColor: '#6366f1',
          backgroundColor: grad,
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#6366f1',
          pointRadius: 4,
          yAxisID: 'yRevenue',
        },
      ];
      if (burnPoints.length > 0) {
        chartDatasets.push({
          label: 'Burn',
          data: burn6Data,
          borderColor: '#f43f5e',
          backgroundColor: 'rgba(244,63,94,0.08)',
          borderWidth: 2,
          fill: false,
          borderDash: [4, 4],
          tension: 0.4,
          pointBackgroundColor: '#f43f5e',
          pointRadius: 4,
          yAxisID: 'yBurn',
        });
      }

      revenueChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels6,
          datasets: chartDatasets,
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 1200, easing: 'easeOutQuart' },
          plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
          scales: {
            yRevenue: {
              type: 'linear',
              position: 'left',
              grid: { color: 'rgba(255,255,255,0.04)' },
              ticks: { callback: v => (v >= 1000 ? '$' + v / 1000 + 'K' : '$' + v) },
            },
            yBurn: {
              type: 'linear',
              position: 'right',
              grid: { display: false },
              ticks: { callback: v => (v >= 1000 ? '$' + v / 1000 + 'K' : '$' + v) },
            },
            x: { grid: { display: false }, ticks: { maxRotation: 0, minRotation: 0 } },
          },
        },
      });

      function applyRevenueWindow(mode) {
        const rev = sliceChartPoints(revenuePoints, mode);
        const burn = sliceChartPoints(burnPoints, mode);
        revenueChart.data.labels = rev.map(p => p.label);
        revenueChart.data.datasets[0].data = rev.map(p => p.value);
        if (revenueChart.data.datasets[1] && burn.length > 0) {
          revenueChart.data.datasets[1].data = burn.map(p => p.value);
        }
        revenueChart.update();
      }

      document.getElementById('trend6m')?.addEventListener('click', () => {
        applyRevenueWindow('6m');
        document.getElementById('trend6m')?.classList.add('active');
        document.getElementById('trend1y')?.classList.remove('active');
      });
      document.getElementById('trend1y')?.addEventListener('click', () => {
        applyRevenueWindow('1y');
        document.getElementById('trend1y')?.classList.add('active');
        document.getElementById('trend6m')?.classList.remove('active');
      });
    }

    const chartSubtitle = document.getElementById('revenueChartSubtitle');
    if (chartSubtitle && charts.analysis_month) {
      chartSubtitle.textContent = `Based on analysis generated ${charts.analysis_month}`;
    }

    const cashCtx = document.getElementById('cashChart');
    if (cashCtx && Array.isArray(charts.cash_projection) && charts.cash_projection.length > 0) {
      new Chart(cashCtx.getContext('2d'), {
        type: 'line',
        data: {
          labels: charts.cash_projection.map(p => p.label),
          datasets: [{
            label: 'Cash Balance', data: charts.cash_projection.map(p => p.value),
            borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.2)',
            borderWidth: 2, fill: true, tension: 0.4,
            pointBackgroundColor: '#10b981', pointRadius: 3,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          animation: { duration: 1200, easing: 'easeOutQuart' },
          plugins: { legend: { display: false } },
          scales: {
            y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: v => v >= 1000 ? '$' + v / 1000 + 'K' : '$' + v } },
            x: { grid: { display: false }, ticks: { maxRotation: 0, minRotation: 0 } },
          },
        },
      });
    }

    const radCtx = document.getElementById('radarChart');
    if (radCtx && charts.health_radar && Object.keys(charts.health_radar).length > 0) {
      const radarKeys = Object.keys(charts.health_radar);
      const radarValues = Object.values(charts.health_radar);
      new Chart(radCtx.getContext('2d'), {
        type: 'radar',
        data: {
          labels: radarKeys,
          datasets: [{ label: 'Health', data: radarValues, borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.15)', pointBackgroundColor: '#6366f1', borderWidth: 2, pointRadius: 4 }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          animation: { duration: 1200, easing: 'easeOutQuart' },
          plugins: { legend: { display: false } },
          scales: { r: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.06)' }, angleLines: { color: 'rgba(255,255,255,0.06)' }, ticks: { display: false }, pointLabels: { font: { size: 10 }, color: '#cbd5e1' } } },
        },
      });
    }

    // ─── Risk counts ──────────────────────────────────────────────────────────────
    const crit = risks.filter(r => (r.severity || '').toLowerCase() === 'critical').length;
    const high = risks.filter(r => (r.severity || '').toLowerCase() === 'high').length;
    const med = risks.filter(r => (r.severity || '').toLowerCase() === 'medium').length;
    const low = risks.filter(r => (r.severity || '').toLowerCase() === 'low').length;

    const riskCtx = document.getElementById('riskChart');
    console.log('RISKS:', risks);
    console.log('Risk counts:', { critical: crit, high: high, medium: med, low: low });

    if (riskCtx && Array.isArray(risks) && typeof Chart !== 'undefined') {
      let riskCounts = [crit, high, med, low];
      const riskSum = riskCounts.reduce((a, b) => a + b, 0);
      if (riskSum === 0 && risks.length > 0) {
        console.warn('Risk severities did not match buckets — grouping', risks.length, 'as medium');
        riskCounts = [0, 0, risks.length, 0];
      }
      const riskParent = riskCtx.parentElement;
      if (riskParent && riskParent.clientHeight < 10) {
        riskParent.style.minHeight = '260px';
      }
      try {
        const riskCtx2d = riskCtx.getContext('2d');
        if (riskCtx2d) {
          console.log('Risk chart data:', { crit, high, med, low, total: riskSum, risks: risks.length });
          new Chart(riskCtx2d, {
            type: 'doughnut',
            data: {
              labels: ['Critical', 'High', 'Medium', 'Low'],
              datasets: [{
                data: riskCounts,
                backgroundColor: ['#f43f5e', '#f59e0b', '#06b6d4', '#10b981'],
                borderWidth: 0,
                hoverOffset: 6,
              }],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: '72%',
              plugins: { legend: { display: false } },
            },
          });
        } else {
          console.warn('Could not get 2d context for risk chart');
        }
      } catch (err) {
        console.warn('Risk chart initialization failed:', err);
      }
    } else {
      if (!riskCtx) console.warn('Risk chart canvas missing (#riskChart)');
      if (!Array.isArray(risks)) console.warn('Invalid risks array:', risks);
      if (typeof Chart === 'undefined') console.warn('Chart.js not loaded — risk donut skipped');
    }

    // ─── Survival Gauge ───────────────────────────────────────────────────────────
    const gaugeCtx = document.getElementById('survivalGauge');
    if (gaugeCtx) {
      const col = score >= 75 ? '#10b981' : score >= 50 ? '#6366f1' : score >= 30 ? '#f59e0b' : '#f43f5e';
      new Chart(gaugeCtx.getContext('2d'), {
        type: 'doughnut',
        data: { datasets: [{ data: [score, 100 - score], backgroundColor: [col, 'rgba(255,255,255,0.04)'], borderColor: 'transparent', circumference: 270, rotation: 225 }] },
        options: { responsive: false, animation: { duration: 1200, easing: 'easeOutQuart' }, plugins: { legend: { display: false }, tooltip: { enabled: false } }, cutout: '80%' },
      });
    }

    // ─── Page header ──────────────────────────────────────────────────────────────
    setText('pageTitle', `${name} — Survival Dashboard`);
    setText('pageSubtitle', `Last analyzed: ${new Date().toLocaleDateString()} · ${riskCount} risks · ${comps.length} competitors`);
    setText('industryBadge', industry);

    // ─── Gauge ────────────────────────────────────────────────────────────────────
    animCount('gaugeScoreText', score);
    setText('gaugeCardTitle', name);
    setText('gaugeCardDesc', `Survival probability: ${probability}%`);
    const survivalLabel = score >= 75 ? 'Strong' : score >= 50 ? 'Moderate' : score >= 30 ? 'At Risk' : 'Critical';
    setText('survivalBadge', survivalLabel);
    setStyle('survivalBadge', 'background', score >= 75 ? 'rgba(16,185,129,.15)' : score >= 50 ? 'rgba(99,102,241,.15)' : score >= 30 ? 'rgba(245,158,11,.15)' : 'rgba(244,63,94,.15)');
    setStyle('survivalBadge', 'color', scoreColor(score));

    const mrrDisplay = startup.monthly_revenue || analysis.financial_health?.mrr || '—';
    setText('monthlyRevenue', mrrDisplay);
    console.log('Monthly revenue card:', { mrrDisplay, growth: startup.revenue_growth });

    const revChangeEl = document.getElementById('revenueChange');
    if (revChangeEl) {
      const growthRaw = startup.revenue_growth || analysis.financial_health?.growth || '';
      const growthNum = parseFloat(String(growthRaw).replace(/[%$,]/g, ''));
      const growthLabel = growthRaw ? String(growthRaw).includes('%') ? growthRaw : `${growthNum}%` : '';
      if (!isNaN(growthNum) && growthNum > 0) {
        revChangeEl.className = 'stat-change up';
        revChangeEl.textContent = `▲ ${growthLabel} MoM growth`;
      } else if (!isNaN(growthNum) && growthNum < 0) {
        revChangeEl.className = 'stat-change down';
        revChangeEl.textContent = `▼ ${growthLabel} MoM decline`;
      } else {
        revChangeEl.className = 'stat-change';
        revChangeEl.textContent = growthRaw ? `▲ ${growthLabel} MoM` : '— Growth rate not provided';
      }
    }

    const revCaptionEl = document.getElementById('revenueCaption');
    if (revCaptionEl) {
      revCaptionEl.textContent =
        breakEven !== '—'
          ? `Break-even projected: ${breakEven}`
          : startup.monthly_burn && startup.monthly_burn !== '—'
            ? `Monthly burn: ${startup.monthly_burn}`
            : '—';
    }

    const growthRaw = startup.revenue_growth || analysis.financial_health?.growth || '';
    const growthNum = parseFloat(String(growthRaw).replace(/[%$,]/g, ''));
    const growthPct = Number.isFinite(growthNum) ? Math.min(100, Math.max(0, growthNum)) : 0;
    console.log('Revenue progress:', growthPct);

    const revenueFill = document.getElementById('revenueFill');
    if (revenueFill) {
      revenueFill.style.transition = 'width 1.2s ease';
      revenueFill.style.width = '0%';
      revenueFill.className = 'progress-fill ' +
        (growthPct >= 70 ? 'fill-success' : growthPct >= 40 ? 'fill-warning' : 'fill-danger');
      requestAnimationFrame(() => {
        revenueFill.style.width = `${growthPct}%`;
      });
    }

    setText('breakEvenForecast',
      breakEven !== '—' ? `Break-even projected: ${breakEven}` : 'Break-even not projected in current window');

    const runwayEl = document.getElementById('runwayRemaining');
    if (runwayEl) {
      if (metrics.runway_unbounded === true) { runwayEl.textContent = '∞ Profitable'; runwayEl.style.color = 'var(--emerald)'; }
      else { animCount('runwayRemaining', Math.round(runway), ' mo'); runwayEl.style.color = scoreColor(runway >= 14 ? 80 : runway >= 9 ? 55 : 30); }
    }
    const runwayChangeEl = document.getElementById('runwayChange');
    if (runwayChangeEl) {
      if (metrics.runway_unbounded === true) {
        runwayChangeEl.className = 'stat-change up';
        runwayChangeEl.textContent = 'Revenue covers expenses';
      } else if (runway <= 3) {
        runwayChangeEl.className = 'stat-change down';
        runwayChangeEl.textContent = '🚨 Critical runway';
      } else if (runway <= 6) {
        runwayChangeEl.className = 'stat-change down';
        runwayChangeEl.textContent = '⚠️ Fundraising required';
      } else {
        runwayChangeEl.className = 'stat-change up';
        runwayChangeEl.textContent = 'Healthy runway';
      }
    }
    setBar('runwayFill', Math.min(100, Math.round((runway / 24) * 100)));
    setText('runwayCaption',
      runway >= 36 ? 'Business is cash-flow positive'
        : runway <= 3 ? '🚨 Critical — raise or cut costs immediately'
          : runway <= 6 ? '⚠️ Fundraise within 2 months'
            : runway <= 12 ? 'Start fundraising process now'
              : `${Math.round(runway)} months of runway — healthy position`);

    animCount('teamHealth', teamScore, '%');
    setStyle('teamHealth', 'color', scoreColor(teamScore));
    const teamChangeEl = document.getElementById('teamChange');
    if (teamChangeEl) {
      teamChangeEl.className = 'stat-change ' + (teamScore >= 60 ? 'up' : 'down');
      teamChangeEl.textContent = teamScore >= 75 ? '▲ Strong team foundation' : teamScore >= 50 ? '→ Team needs development' : '▼ Team gaps identified';
    }
    setBar('teamFill', teamScore);
    setText('teamCaption',
      startup.team_size && startup.team_size !== '—'
        ? `Team of ${startup.team_size} · Score: ${teamScore}/100`
        : `Score: ${teamScore}/100`);

    animCount('fundingReadiness', fundingReady, '%');
    setStyle('fundingReadiness', 'color', scoreColor(fundingReady));
    const fundReadChangeEl = document.getElementById('fundingReadinessChange');
    if (fundReadChangeEl) {
      const lbl = fundingReady >= 80 ? 'Investor Ready' : fundingReady >= 60 ? 'Series Seed-ready' : fundingReady >= 40 ? 'Approaching Seed' : 'Pre-Seed stage';
      fundReadChangeEl.className = 'stat-change ' + (fundingReady >= 60 ? 'up' : 'down');
      fundReadChangeEl.textContent = '▲ ' + lbl;
    }
    setBar('fundingReadinessFill', fundingReady);
    const gaps = metrics.funding_gaps || 0;
    setText('fundingReadinessCaption', gaps > 0 ? `${gaps} key gap${gaps > 1 ? 's' : ''} to address first` : 'Ready for investor conversations');

    animCount('marketOpportunity', marketScore);
    setText('marketOpportunity', marketScore + '/100');
    const marketChangeEl = document.getElementById('marketChange');
    if (marketChangeEl) {
      marketChangeEl.className = 'stat-change ' + (marketScore >= 60 ? 'up' : 'down');
      marketChangeEl.textContent = marketScore >= 70 ? `▲ Strong market — ${marketScore}/100` : `→ Market score: ${marketScore}/100`;
    }
    setBar('marketFill', marketScore);
    setText('marketCaption', marketScore >= 80 ? 'Excellent timing & market size' : marketScore >= 60 ? 'Good market conditions' : 'Market opportunity needs validation');

    setHTML('financialSignalsList',
      signals.length > 0
        ? signals.map(s => `
            <div class="signal-card ${safe(s.status)}">
              <div class="signal-title">${safe(s.label)}</div>
              <div class="signal-desc">${safe(s.value)} · ${safe(s.benchmark || '')}</div>
            </div>`).join('')
        : '<p style="color:var(--text-muted);padding:1rem">No financial signals available.</p>'
    );

    // ─── Activity Log ─────────────────────────────────────────────────────────────
    const logEl = document.getElementById('activityLog');
    if (logEl) {
      const entries = [
        { dot: 'var(--emerald,#10b981)', title: 'Analysis completed', meta: `${riskCount} risk signals processed · Score: ${score}/100`, time: 'Just now' },
      ];
      if (runway > 0 && runway < 12) entries.push({ dot: runway < 6 ? 'var(--rose,#f43f5e)' : 'var(--amber,#f59e0b)', title: 'Runway alert', meta: `${runway} months of runway at current burn rate`, time: 'Just now' });
      if (crit > 0) entries.push({ dot: 'var(--rose,#f43f5e)', title: `${crit} critical risk${crit > 1 ? 's' : ''} identified`, meta: risks.find(r => (r.severity || '').toLowerCase() === 'critical')?.description || '', time: 'Just now' });
      if (comps.length > 0) entries.push({ dot: 'var(--indigo,#6366f1)', title: `${comps.length} competitor${comps.length > 1 ? 's' : ''} mapped`, meta: comps.map(c => c.name).join(', '), time: 'Just now' });
      if (recs.length > 0) entries.push({ dot: 'var(--cyan,#06b6d4)', title: `${recs.length} AI recommendations generated`, meta: (recs[0]?.title || '').slice(0, 80), time: 'Just now' });

      logEl.innerHTML = entries.map(e => `
      <div class="timeline-item">
        <div class="timeline-dot" style="background:${e.dot}"></div>
        <div class="timeline-content">
          <div class="timeline-title">${safe(e.title)}</div>
          <div class="timeline-meta">${safe(e.meta)}</div>
        </div>
        <div class="timeline-time">${safe(e.time)}</div>
      </div>`).join('');
    }

    // ─── Risks ────────────────────────────────────────────────────────────────────
    const sevColor = { critical: '#f43f5e', high: '#f59e0b', medium: '#06b6d4', low: '#10b981' };
    setHTML('riskList', risks.length
      ? risks.map(r => {
          const sev = (r.severity || 'medium').toLowerCase();
          return `
        <div class="risk-item">
          <div class="risk-level-bar" style="background:${sevColor[sev] || '#cbd5e1'}"></div>
          <div class="risk-content">
            <div class="risk-name">${safe(r.category) || 'Risk'}</div>
            <div class="risk-desc">${safe(r.description) || ''}</div>
          </div>
          <div class="risk-pct" style="color:${sevColor[sev] || '#cbd5e1'}">${sev.toUpperCase()}</div>
        </div>`;
        }).join('')
      : '<p style="color:var(--text-muted);padding:1rem">No risks detected.</p>');

    // ─── SWOT ─────────────────────────────────────────────────────────────────────
    [['swotStrengths', swot.strengths], ['swotWeaknesses', swot.weaknesses], ['swotOpportunities', swot.opportunities], ['swotThreats', swot.threats]].forEach(([id, items]) => {
      setHTML(id, (items || []).length ? (items || []).map(i => `<li>${safe(i)}</li>`).join('') : '<li class="empty">No insights generated yet.</li>');
    });

    // ─── Competitors ──────────────────────────────────────────────────────────────
    setHTML('competitorGrid', comps.length
      ? comps.map(c => `
        <div class="glass-card competitor-card">
          <div class="competitor-name">${safe(c.name) || '—'}</div>
          <div class="competitor-niche">${safe(c.stage) || '—'}</div>
          <div class="competitor-diff">${safe(c.differentiator) || '—'}</div>
          <div class="competitor-threat">${safe(c.threat) || '—'}</div>
        </div>`).join('')
      : '<p style="color:var(--text-muted);padding:1rem">No competitors detected.</p>');

    setHTML('recommendationList', recs.length
      ? recs.map((r, i) => `
        <div class="rec-card">
          <div class="rec-header">
            <div class="rec-number">${String(i + 1).padStart(2, '0')}</div>
            <div class="rec-title">${safe(r.title) || safe(r)}</div>
          </div>
          ${r.description ? `<div class="rec-body">${safe(r.description)}</div>` : ''}
        </div>`).join('')
      : '<p style="color:var(--text-muted);padding:1rem">No recommendations yet.</p>');

    const fundingBars = funding.bars || [];
    [
      ['fundingPctTraction', 'fundingFillTraction', fundingBars[0]?.pct ?? (funding.traction_pct ?? 0)],
      ['fundingPctTeam', 'fundingFillTeam', fundingBars[1]?.pct ?? (funding.team_pct ?? 0)],
      ['fundingPctMarket', 'fundingFillMarket', fundingBars[2]?.pct ?? (funding.market_pct ?? 0)],
      ['fundingPctEconomics', 'fundingFillEconomics', fundingBars[3]?.pct ?? (funding.econ_pct ?? 0)],
      ['fundingPctInvestors', 'fundingFillInvestors', fundingBars[4]?.pct ?? (funding.materials_pct ?? 0)],
      ['fundingPctSocial', 'fundingFillSocial', fundingBars[5]?.pct ?? (funding.social_pct ?? 0)],
    ].forEach(([pctId, fillId, val]) => {
      const pct = Math.min(Math.max(Math.round(val), 0), 100);
      setText(pctId, `${pct}%`);
      setStyle(pctId, 'color', scoreColor(pct));
      setFundingBar(fillId, pct);
    });

    setText('riskCountBadge', `${riskCount} Active ${plural(riskCount, 'Risk', 'Risks')}`);
    setText('riskSidebarCount', riskCount);
    setText('recommendationSidebarCount', recs.length);
    setText('recommendationsBadge', `${recs.length} Action Item${recs.length === 1 ? '' : 's'}`);
    setText('competitorThreatBadge', `${comps.length} Competitor${comps.length === 1 ? '' : 's'} Detected`);
    setText('criticalRiskCount', `${crit} ${plural(crit, 'risk', 'risks')}`);
    setText('highRiskCount', `${high} ${plural(high, 'risk', 'risks')}`);
    setText('mediumRiskCount', `${med}  ${plural(med, 'risk', 'risks')}`);
    setText('lowRiskCount', `${low}  ${plural(low, 'risk', 'risks')}`);

    animCount('fundingScoreValue', fundingReady);
    setText('fundingStatusBadge', fundingReady >= 80 ? 'Investor Ready' : fundingReady >= 60 ? 'Seed Ready' : fundingReady >= 40 ? 'Needs Work' : 'Pre-Seed');
    setText('fundingTagline',
      fundingReady >= 80 ? 'Strong investor momentum and readiness.'
        : fundingReady >= 60 ? 'Close to Seed readiness with a few gaps.'
          : 'Strengthen business model and materials before approaching investors.');

    const scoreGrid = document.getElementById('scoreBreakdownGrid');
    if (scoreGrid && Array.isArray(bd) && bd.length > 0) {
      scoreGrid.innerHTML = bd.map(item => {
        const val = Math.round(item.score || 0);
        return `
          <div class="score-pill">
            <div class="score-pill-val" style="color:${scoreColor(val)}">${val}</div>
            <div class="score-pill-label">${safe(item.label) || '—'}</div>
          </div>`;
      }).join('');
    }

    // ── Timeline (score progress) ──────────────────────────────────────────────
    window.__timelineRequest ||= (async () => {
      const timelineWidget = document.getElementById('timelineWidget');
      if (!timelineWidget) return;

      try {
        const token = typeof window.getValidAccessToken === 'function'
          ? await window.getValidAccessToken()
          : null;
        if (!token) {
          timelineWidget.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem">Sign in to see score history.</p>`;
          return;
        }
        const res = await fetch(
          (window.CONFIG?.API_URL || "http://localhost:8000") + "/api/v1/reports/timeline",
          { headers: { Authorization: "Bearer " + token, Accept: "application/json" } }
        );

        // Handle auth errors silently — token may be stale
        if (res.status === 401) {
          timelineWidget.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem">Session expired. Please sign in again to see score history.</p>`;
          return;
        }
        if (res.status === 403) {
          timelineWidget.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem">Access denied to timeline.</p>`;
          return;
        }
        if (!res.ok) {
          timelineWidget.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem">Could not load score history.</p>`;
          return;
        }

        const json = await res.json();
        const points = json.data || [];
        if (points.length < 2) {
          timelineWidget.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem">Run 2+ analyses to see your score progress here.</p>`;
          return;
        }
        const first = points[0]?.score || 0;
        const last = points[points.length - 1]?.score || 0;
        const improvement = last - first;
        const deltaClass = improvement >= 0 ? 'var(--emerald)' : 'var(--rose)';
        const deltaSign = improvement >= 0 ? '+' : '';
        timelineWidget.innerHTML = `
          <div class="timeline-score" style="font-size:1.4rem;font-weight:700;letter-spacing:-.02em;margin-bottom:.5rem">
            ${points.map(p => `<span style="color:${p.score >= 75 ? 'var(--emerald)' : p.score >= 55 ? 'var(--amber)' : 'var(--rose)'}">${p.score}</span>`).join(' <span style="color:var(--text-muted)">→</span> ')}
          </div>
          <div class="timeline-delta" style="font-size:.9rem;color:${deltaClass}">
            ${deltaSign}${improvement} points
          </div>`;
      } catch (err) {
        if (err?.refreshFailed) {
          if (typeof Auth !== 'undefined') Auth.clearAuth();
          window.location.href = 'signin.html?redirect=dashboard.html';
          return;
        }
        timelineWidget.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem">Score history unavailable.</p>`;
      }
    })();

    if (typeof Toast !== 'undefined') {
      Toast.info('Dashboard Loaded', `${name} · Score ${score}/100 · ${riskCount} risks`);
    }

    // ─── Score card → AI Mentor ──────────────
    const mentorQ = {
      "Funding Readiness": "How can I improve funding readiness?",
      "Team Health": "How can I improve team health?",
      "Market Opportunity": "How can I strengthen my market position?",
      "Survival Score": "How can I improve survival probability?",
      "Monthly Revenue": "How can I grow monthly revenue?",
      "Runway Remaining": "How can I extend my runway?",
    };
    document.querySelectorAll('.stat-card').forEach(function (card) {
      card.style.cursor = 'pointer';
      card.addEventListener('click', function () {
        const label = this.querySelector('.stat-label');
        if (!label) return;
        const text = label.textContent.trim();
        const q = mentorQ[text] || ("How can I improve " + text + "?");
        if (window.openMentor) window.openMentor(q);
      });
    });

    // Gauge card click
    const gaugeCard = document.querySelector('.score-gauge-card');
    if (gaugeCard) {
      gaugeCard.style.cursor = 'pointer';
      gaugeCard.addEventListener('click', function () {
        if (window.openMentor) window.openMentor("How can I improve my survival score?");
      });
    }

    setTimeout(() => {
      document.body.classList.remove('dashboard-loading');
    }, 300);
  } // end renderDashboard

  init();
}); // end DOMContentLoaded