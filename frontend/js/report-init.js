// ─────────────────────────────────────────────
// report-init.js
// Full dynamic report renderer + PDF export
// + persistent report_id + share link
// ─────────────────────────────────────────────

// ✅ jsPDF alias (loaded via CDN in report.html)
// PDF dependencies are optional until export is requested.

let analysis = null;

async function loadReport() {
  const reportId = new URLSearchParams(location.search).get("id");

  if (!reportId) return loadLocalStorageFallback();

  try {
    const token = (typeof Auth !== 'undefined' && Auth.getToken()) ? Auth.getToken() : null;
    const res = await fetch(
      (window.CONFIG?.API_URL || "http://localhost:8000") + "/api/v1/reports/" + reportId,
      { headers: token ? { Authorization: "Bearer " + token } : {} }
    );
    if (!res.ok) throw new Error("Report not found");
    const payload = await res.json();
    analysis = { ...payload.data.report.raw_ai_response, startup: payload.data.report.raw_ai_response.startup || payload.data.startup };
    console.log("REPORT DATA (from API):", analysis);
    renderReport();
  } catch (err) {
    console.error("API load failed, falling back to localStorage:", err);
    loadLocalStorageFallback();
  }
}

function loadLocalStorageFallback() {
  const stored = localStorage.getItem("latest_analysis");
  if (!stored) {
    window.location.href = "analysis.html";
    return;
  }
  const parsed = JSON.parse(stored);
  analysis = parsed.data || parsed;
  console.log("REPORT DATA (from localStorage):", analysis);
  renderReport();
}

function renderReport() {

const metrics = analysis.metrics || {};
const runwayMonths = metrics.runway_months || 0;
const execSummary = analysis.executive_summary || {};
const finHealth = analysis.financial_health || {};
const marketData = analysis.market_analysis || {};
const funding = analysis.funding_readiness || {};
const risks = analysis.risks || [];
const swot = analysis.swot || {};
const competitors = analysis.competitors || [];
const recs = analysis.recommendations || [];
const startup = analysis.startup || {};
const bd = analysis.score_breakdown || analysis.charts?.score_breakdown || [];

const score = metrics.survival_score || 0;
const probability = metrics.survival_probability || 0;
const fundingReady = metrics.funding_readiness || 0;
const percentile = metrics.percentile || 0;
const riskCount = metrics.risk_count || risks.length;
const reportId = analysis.report_id || null;

const startupName = startup.name || analysis.idea || "Startup";
const industry = startup.industry || "—";
const survivalProbability = `${probability}%`;

// Clone to avoid mutating the original analysis object
const data = structuredClone(analysis);
data.health_score = score;
data.survival_probability = survivalProbability;

// ─────────────────────────────────────────────
// HELPER — safe text (prevents XSS)
// ─────────────────────────────────────────────

function safe(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}

const REPORT_COLORS = new Set([
  "var(--amber)",
  "var(--cyan)",
  "var(--emerald)",
  "var(--indigo)",
  "var(--rose)",
  "var(--text-muted)",
]);

function safeReportColor(value) {
  return typeof value === "string" && REPORT_COLORS.has(value.trim())
    ? value.trim()
    : "var(--text-muted)";
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = value;
  }
}

// ─────────────────────────────────────────────
// HELPER — score color
// ─────────────────────────────────────────────

function scoreColor(val) {
  if (val >= 75) return "var(--emerald)";
  if (val >= 55) return "var(--amber)";
  return "var(--rose)";
}

// ─────────────────────────────────────────────
// HELPER — threat badge
// ─────────────────────────────────────────────

function threatBadge(level) {
  const map = {
    critical: "badge-danger",
    high:     "badge-warning",
    medium:   "badge-info",
    low:      "badge-success",
  };
  const cls = map[(level || "medium").toLowerCase()] || "badge-info";
  return `<div class="badge ${cls}">${safe(level || "Medium")}</div>`;
}

// ─────────────────────────────────────────────
// HELPER — callout builder
// ─────────────────────────────────────────────

function buildCallout(type, icon, title, text) {
  // type: critical | success | warning | info
  const classMap = {
    critical: "callout-critical",
    success:  "callout-success",
    warning:  "callout-warning",
    info:     "callout-info",
  };
  const cls = classMap[type] || "callout-info";
  return `
    <div class="callout ${cls}">
      <div class="callout-icon">${icon}</div>
      <div class="callout-body">
        <div class="callout-title">${safe(title)}</div>
        <div class="callout-text">${safe(text)}</div>
      </div>
    </div>
  `;
}

// ─────────────────────────────────────────────
// 1. HEADER — startup name, score, industry
// ─────────────────────────────────────────────

setText("reportStartupName", startupName);
setText("reportIndustry", industry);
setText("reportScore", `${score} / 100`);
setText("reportScoreLarge", score);

setText(
  "reportSurvivalProbability",
  `${survivalProbability} Survival Probability`
);

// Dynamic report date — today or from data
const reportDateRaw = analysis.created_at || null;
const reportDateFormatted = reportDateRaw
  ? new Date(reportDateRaw).toLocaleDateString("en-US", {
      year: "numeric", month: "long", day: "numeric"
    })
  : new Date().toLocaleDateString("en-US", {
      year: "numeric", month: "long", day: "numeric"
    });
setText("reportDate", reportDateFormatted);

// Cohort from data if available
if (data.cohort) {
  setText("reportCohort", data.cohort);
}

// Column header = startup name
setText("colStartupName", startupName);

// Score fill progress bar (sidebar)
const scoreFill = document.getElementById("scoreFill");
if (scoreFill) {
  scoreFill.setAttribute("data-width", score);
}

// ─────────────────────────────────────────────
// 2. REPORT ID — show if present
// ─────────────────────────────────────────────

if (reportId) {
  const idRow = document.getElementById("reportIdRow");
  const idDisplay = document.getElementById("reportIdDisplay");
  if (idRow) idRow.style.display = "";
  if (idDisplay) idDisplay.textContent = reportId;

  // Store in localStorage so share links can open it
  localStorage.setItem("current_report_id", reportId);
}

// ─────────────────────────────────────────────
// 3. EXEC SUMMARY — dynamic paragraphs + callouts
// ─────────────────────────────────────────────

setText("execSummaryP1", execSummary.overview || "");
setText("execSummaryP2", execSummary.positioning || "");
const p3El = document.getElementById("execSummaryP3");
if (p3El) p3El.textContent = execSummary.risks_headline || "";

// Exec callouts — from data or smart defaults
const execCalloutsEl = document.getElementById("execCallouts");
let calloutsHTML = "";

if (execSummary.critical_callout) {
  const criticalCalloutText = execSummary.critical_callout;
  calloutsHTML += buildCallout(
    "critical",
    "🚨",
    "Critical Action Required",
    criticalCalloutText
  );
}

if (execSummary.success_callout) {
  calloutsHTML += buildCallout(
    "success",
    "✅",
    "Strong Advantage Confirmed",
    execSummary.success_callout
  );
}

execCalloutsEl.innerHTML = calloutsHTML;

// Badge label driven by score
const execBadge = document.getElementById("execSummaryBadge");
if (execBadge) {
  if (score >= 75) {
    execBadge.textContent = "Strong";
    execBadge.className = "badge badge-success";
  } else if (score >= 55) {
    execBadge.textContent = "Moderate";
    execBadge.className = "badge badge-warning";
  } else {
    execBadge.textContent = "At Risk";
    execBadge.className = "badge badge-danger";
  }
}

// ─────────────────────────────────────────────
// 4. SCORE BREAKDOWN — dynamic pills
// ─────────────────────────────────────────────

const scoreBreakdown =
  analysis.score_breakdown || [];

const scoreGrid = document.getElementById("scoreBreakdownGrid");

if (scoreGrid && Array.isArray(scoreBreakdown) && scoreBreakdown.length > 0) {

  scoreGrid.innerHTML = scoreBreakdown.map(item => {
    const val = Math.round(item.score || item.value || 0);
    return `
      <div class="score-pill">
        <div class="score-pill-val" style="color:${scoreColor(val)}">${val}</div>
        <div class="score-pill-label">${safe(item.label || item.category || "—")}</div>
      </div>
    `;
  }).join("");

} else {
  // Fallback: derive from top-level fields if breakdown array is absent
  const fallbackScores = [
    { label: "Financial Health",    score: data.financial_score    || 0 },
    { label: "Team Strength",       score: data.team_score         || 0 },
    { label: "Market Opportunity",  score: data.market_score       || 0 },
    { label: "Product / IP",        score: data.product_score      || 0 },
    { label: "Traction",            score: data.traction_score     || 0 },
    { label: "Risk Exposure",       score: data.risk_score         || 0 },
  ].filter(s => s.score > 0);

  if (fallbackScores.length > 0 && scoreGrid) {
    scoreGrid.innerHTML = fallbackScores.map(item => `
      <div class="score-pill">
        <div class="score-pill-val" style="color:${scoreColor(item.score)}">${Math.round(item.score)}</div>
        <div class="score-pill-label">${safe(item.label)}</div>
      </div>
    `).join("");
  } else if (scoreGrid) {
    scoreGrid.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem">Score breakdown not available for this analysis.</p>`;
  }
}

// ─────────────────────────────────────────────
// 5. FINANCIAL HEALTH — dynamic table rows
// ─────────────────────────────────────────────

const tableBody = document.getElementById("financialTableBody");
if (tableBody) {
  const rows = finHealth.rows || [];
  if (rows.length > 0) {
    tableBody.innerHTML = rows.map(row => `
    <tr>
      <td>${safe(row.metric || "—")}</td>
      <td class="font-mono">${safe(row.value || "—")}</td>
      <td class="font-mono text-muted">${safe(row.median || "—")}</td>
      <td><span class="metric-status" style="color:${safeReportColor(row.color)}">${safe(row.status || "—")}</span></td>
    </tr>`).join("");
  } else {
    tableBody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:1.5rem">Financial data not available.</td></tr>`;
  }
}

const financialCalloutEl = document.getElementById("financialCallout");
if (financialCalloutEl && finHealth.callout) {
  financialCalloutEl.innerHTML = buildCallout("warning", "⚠️", "Financial Alert", finHealth.callout);
}

const financialBadge = document.getElementById("financialBadge");
const financialScore = metrics.financial_score || 0;
if (financialBadge) {
  if (financialScore >= 70) {
    financialBadge.textContent = "Healthy";
    financialBadge.className = "badge badge-success";
  } else if (financialScore >= 50) {
    financialBadge.textContent = "Needs Attention";
    financialBadge.className = "badge badge-warning";
  } else {
    financialBadge.textContent = "Critical";
    financialBadge.className = "badge badge-danger";
  }
}

// ─────────────────────────────────────────────
// 5B. RUNWAY ANALYSIS
// ─────────────────────────────────────────────

const runwayValueEl = document.getElementById("reportRunwayValue");
const runwayStatusEl = document.getElementById("reportRunwayStatus");
const runwayDescEl = document.getElementById("reportRunwayDescription");
const runwayBadgeEl = document.getElementById("runwayBadge");

if (runwayValueEl) {
  if (metrics.runway_unbounded === true) {
    runwayValueEl.textContent = "∞ Profitable";
    runwayStatusEl.textContent = "Revenue covers expenses";
    runwayDescEl.textContent = "Business is cash-flow positive and does not currently consume capital.";
    runwayBadgeEl.textContent = "No net burn";
    runwayBadgeEl.className = "badge badge-success";
  } else {
    runwayValueEl.textContent = `${Math.round(runwayMonths)} mo`;
    runwayStatusEl.textContent = "Runway Remaining";
    runwayDescEl.textContent = `Estimated cash runway: ${Math.round(runwayMonths)} months`;
    if (runwayMonths <= 3) {
      runwayBadgeEl.textContent = "Critical";
      runwayBadgeEl.className = "badge badge-danger";
    }
    else if (runwayMonths <= 6) {
      runwayBadgeEl.textContent = "Warning";
      runwayBadgeEl.className = "badge badge-warning";
    }
    else {
      runwayBadgeEl.textContent = "Healthy";
      runwayBadgeEl.className = "badge badge-success";
    }
  }
}

// ─────────────────────────────────────────────
// 6. MARKET ANALYSIS — dynamic stat cards + paragraph
// ─────────────────────────────────────────────

const market = marketData;

const marketStats = market.stats || [];

const marketStatCards = document.getElementById("marketStatCards");
if (marketStatCards && marketStats.length > 0) {
  marketStatCards.innerHTML = marketStats.map((s, i) => `
    <div class="glass-card col-4 stat-card anim-fade-up ${i > 0 ? `delay-${i}` : ""}">
      <div class="stat-label">${safe(s.label)}</div>
      <div class="stat-value ${s.color === "gradient-text" ? "gradient-text" : ""}"
           style="color:${s.color === "gradient-text" ? "var(--indigo)" : safeReportColor(s.color)}">
        ${safe(s.value)}
      </div>
      <div class="stat-change up">${safe(s.change)}</div>
    </div>
  `).join("");
}

// Market paragraph
const marketPara = document.getElementById("marketAnalysisPara");
if (marketPara && market.analysis) {
  marketPara.textContent = market.analysis || "";
}

// Market callout
const marketCalloutEl = document.getElementById("marketCallout");
if (marketCalloutEl) {
  const marketCalloutText = market.callout || market.timing_note || null;
  if (marketCalloutText) {
    marketCalloutEl.innerHTML = buildCallout("info", "💡", "Market Insight", marketCalloutText);
  }
}

// ─────────────────────────────────────────────
// 7. RISK ASSESSMENT — dynamic risk cards
// ─────────────────────────────────────────────

const riskCountBadge = document.getElementById("riskCountBadge");
if (riskCountBadge) {
  riskCountBadge.textContent =
    riskCount > 0 ? `${riskCount} Active Risk${riskCount > 1 ? "s" : ""}` : "No Risks Found";
}

const riskContainer = document.getElementById("riskList");

if (riskContainer) {
  if (risks.length === 0) {
    riskContainer.innerHTML = `
      <div class="callout callout-success">
        <div class="callout-icon">✅</div>
        <div class="callout-body">
          <div class="callout-title">No Critical Risks Detected</div>
          <div class="callout-text">The analysis did not identify any flagged risks for this startup profile. Continue monitoring key metrics monthly.</div>
        </div>
      </div>
    `;
  } else {
    riskContainer.innerHTML = risks.map(risk => {
      const severity = String(risk.severity || "medium").toLowerCase();
      const severityClass = ["critical", "high", "medium", "low"].includes(severity)
        ? severity
        : "medium";
      return `
        <div class="risk-item risk-${severityClass}">
          <div class="risk-level-bar"></div>
          <div class="risk-content">
            <div class="risk-name">${safe(risk.category || risk.title || "Risk")}</div>
            <div class="risk-desc">${safe(risk.description || "")}</div>
          </div>
          <div class="risk-pct">${safe(severity.toUpperCase())}</div>
        </div>
      `;
    }).join("");
  }
}

// ─────────────────────────────────────────────
// 8. SWOT — dynamic four quadrants
// ─────────────────────────────────────────────

const swotConfig = [
  {
    key:       "strengths",
    icon:      "💪",
    title:     "Strengths",
    cssClass:  "swot-strengths",
    fallback:  ["Strong founding team", "Early traction demonstrated", "Technical differentiation"],
  },
  {
    key:       "weaknesses",
    icon:      "⚡",
    title:     "Weaknesses",
    cssClass:  "swot-weaknesses",
    fallback:  ["Limited runway", "Small team", "Early-stage brand recognition"],
  },
  {
    key:       "opportunities",
    icon:      "🚀",
    title:     "Opportunities",
    cssClass:  "swot-opportunities",
    fallback:  ["Growing market", "Potential strategic partnerships", "Regulatory tailwinds"],
  },
  {
    key:       "threats",
    icon:      "🛡️",
    title:     "Threats",
    cssClass:  "swot-threats",
    fallback:  ["Competitive intensity increasing", "Macro environment pressuring valuations", "Talent market competition"],
  },
];

const swotGrid = document.getElementById("swotGrid");
if (swotGrid) {
  swotGrid.innerHTML = swotConfig.map(q => {
    const items = swot[q.key] || q.fallback;
    const listItems = (Array.isArray(items) ? items : [items])
      .map(item => `<li>${safe(item)}</li>`)
      .join("");

    return `
      <div class="glass-card swot-card ${q.cssClass}">
        <div class="swot-header">
          <div class="swot-icon">${q.icon}</div>
          <div class="swot-title">${q.title}</div>
        </div>
        <ul class="swot-list">${listItems}</ul>
      </div>
    `;
  }).join("");
}

// ─────────────────────────────────────────────
// 9. COMPETITIVE INTEL — dynamic table rows
// ─────────────────────────────────────────────

// competitors loaded from analysis at top

const competitorCountBadge = document.getElementById("competitorCountBadge");
const highThreats = competitors.filter(c => ["critical","high"].includes((c.threat || "").toLowerCase())).length;
if (competitorCountBadge) {
  competitorCountBadge.textContent =
    competitors.length > 0
      ? `${highThreats} Threat${highThreats !== 1 ? "s" : ""}`
      : "— Threats";
}

const competitorTable = document.getElementById("competitorTableBody");
if (competitorTable) {
  if (competitors.length === 0) {
    competitorTable.innerHTML = `
      <tr>
        <td colspan="5" style="text-align:center;color:var(--text-muted);font-size:.85rem;padding:1.5rem">
          No competitor data available for this analysis.
        </td>
      </tr>
    `;
  } else {
    competitorTable.innerHTML = competitors.map(c => `
      <tr>
        <td><strong>${safe(c.name || c.competitor || "—")}</strong></td>
        <td>${safe(c.stage || "—")}</td>
        <td class="font-mono">${safe(c.funding || "—")}</td>
        <td>${safe(c.differentiator || c.key_differentiator || "—")}</td>
        <td>${threatBadge(c.threat || c.threat_level || "Medium")}</td>
      </tr>
    `).join("");
  }
}

// Competitive callout
const competitiveCalloutEl = document.getElementById("competitiveCallout");
if (competitiveCalloutEl) {
  const competitiveCalloutText =
    data.competitive_callout ||
    data.differentiation_note ||
    null;

  if (competitiveCalloutText) {
    competitiveCalloutEl.innerHTML = buildCallout(
      "info", "🎯", "Differentiation Recommendation", competitiveCalloutText
    );
  } else if (competitors.length > 0) {
    competitiveCalloutEl.innerHTML = buildCallout(
      "info",
      "🎯",
      "Competitive Positioning",
      `${safe(startupName)} is operating in a competitive landscape with ${competitors.length} identified ` +
      `players. Focus on your unique differentiators and build a moat through customer success and IP protection.`
    );
  }
}

// ─────────────────────────────────────────────
// 10. FUNDING READINESS — dynamic bars
// ─────────────────────────────────────────────

// Overall readiness % (funding from analysis at top)
const overallReadiness = metrics.funding_readiness || 0;

const fundingBadge = document.getElementById("fundingReadinessBadge");
if (fundingBadge) {
  fundingBadge.textContent = `${overallReadiness}% Ready`;
  if (overallReadiness >= 75) fundingBadge.className = "badge badge-success";
  else if (overallReadiness >= 55) fundingBadge.className = "badge badge-warning";
  else fundingBadge.className = "badge badge-danger";
}

const fundingReadinessSummary = document.getElementById("fundingReadinessSummary");
if (fundingReadinessSummary) {
  if (funding.summary) {
    fundingReadinessSummary.textContent = funding.summary;
  } else {
    fundingReadinessSummary.textContent =
      `${startupName} is ${overallReadiness}% funding-ready based on traction, team, ` +
      `market timing, unit economics, and investor materials. Improving the lowest-scoring areas will ` +
      `increase readiness the fastest.`;
  }
}

const fundingBars = funding.bars || [];

const fundingBarsContainer = document.getElementById("fundingBarsContainer");
if (fundingBarsContainer) {
  fundingBarsContainer.innerHTML = fundingBars.map(bar => {
    const pct = Math.min(Math.max(Math.round(bar.pct || 0), 0), 100);
    const colorName = ["success", "warning", "danger"].includes(bar.color)
      ? bar.color
      : "danger";
    const colorVar =
      colorName === "success" ? "var(--emerald)"
      : colorName === "warning" ? "var(--amber)"
      : "var(--rose)";

    return `
      <div class="funding-bar-row">
        <div class="funding-bar-header">
          <div class="funding-bar-name">
            ${safe(bar.name)} —
            <span style="color:${colorVar};font-size:.8rem">${safe(bar.detail)}</span>
          </div>
          <div class="funding-bar-pct" style="color:${colorVar}">${pct}%</div>
        </div>
        <div class="progress-track">
          <div class="progress-fill fill-${colorName}" data-width="${pct}" style="width:0%"></div>
        </div>
      </div>
    `;
  }).join("");
}

// ─────────────────────────────────────────────
// 11. ACTION PLAN — dynamic rec cards
// ─────────────────────────────────────────────

const actions = analysis.recommendations || [];

const actionCountBadge = document.getElementById("actionCountBadge");
if (actionCountBadge) {
  actionCountBadge.textContent =
    actions.length > 0 ? `${actions.length} Action${actions.length > 1 ? "s" : ""}` : "—";
}

const actionContainer = document.getElementById("actionPlanContainer");

if (actionContainer) {
  if (actions.length === 0) {
    actionContainer.innerHTML = `
      <div class="callout callout-info">
        <div class="callout-icon">ℹ️</div>
        <div class="callout-body">
          <div class="callout-title">No Action Plan Data</div>
          <div class="callout-text">Action plan data was not returned for this analysis. Run a new analysis to generate priority recommendations.</div>
        </div>
      </div>
    `;
  } else {
    actionContainer.innerHTML = actions.map((action, i) => {
      const urgency   = action.urgency   || action.priority || "Medium";
      const impact    = action.impact    || action.est_impact || "";
      const badgeCls  =
        urgency.toLowerCase().includes("critical") ? "badge-danger"
        : urgency.toLowerCase().includes("high")     ? "badge-warning"
        : "badge-indigo";

      return `
        <div class="rec-card">
          <div class="rec-header">
            <div class="rec-number">${String(i + 1).padStart(2, "0")}</div>
            <div class="rec-title">${safe(action.title || action.action || "—")}</div>
          </div>
          <div class="rec-body">${safe(action.description || action.body || "")}</div>
          <div style="margin-top:.75rem;display:flex;align-items:center;gap:.75rem">
            <div class="badge ${badgeCls}">${safe(urgency)}</div>
            ${impact ? `<span class="text-xs text-muted">${safe(impact)}</span>` : ""}
          </div>
        </div>
      `;
    }).join("");
  }
}

// ─────────────────────────────────────────────
// 12. APPENDIX — dynamic grid from _form_data
// ─────────────────────────────────────────────

const formData = data._form_data || {};
const appendixGrid = document.getElementById("appendixGrid");

// Build appendix from form data fields + core fields
const appendixItems = [
  { key: "Company Name",         val: startupName },
  { key: "Industry",             val: industry },
  { key: "Stage",                val: formData.stage              || data.stage              || "—" },
  { key: "Founded",              val: formData.founded            || data.founded            || "—" },
  { key: "Team Size",            val: formData.team_size          || data.team_size          || "—" },
  { key: "Monthly Burn",         val: formData.monthly_burn       || finHealth.burn          || "—" },
  { key: "Monthly Revenue",      val: formData.monthly_revenue    || finHealth.mrr           || "—" },
  { key: "Total Raised",         val: formData.total_raised       || data.total_raised       || "—" },
  { key: "Cash in Bank",         val: formData.cash_in_bank       || data.cash_in_bank       || "—" },
  { key: "Revenue Growth",       val: formData.revenue_growth     || finHealth.growth        || "—" },
  { key: "Last Round",           val: formData.last_round         || data.last_round         || "—" },
  { key: "Market Size",          val: formData.market_size        || market.tam              || "—" },
  { key: "Differentiator",       val: formData.differentiator     || data.differentiator     || "—" },
  { key: "Founder Experience",   val: formData.founder_experience || data.founder_experience || "—" },
  { key: "Technical Co-Founder", val: formData.has_cto            || data.has_cto            || "—" },
  { key: "Analysis Date",        val: reportDateFormatted },
  ...(reportId ? [{ key: "Report ID", val: reportId }] : []),
];

// Also include any extra fields from _form_data not already listed
const knownKeys = new Set([
  "startup_name","industry","stage","founded","team_size","monthly_burn",
  "monthly_revenue","total_raised","cash_in_bank","revenue_growth","last_round",
  "market_size","differentiator","founder_experience","has_cto",
]);
Object.entries(formData).forEach(([k, v]) => {
  if (!knownKeys.has(k) && v) {
    appendixItems.push({
      key: k.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
      val: v,
    });
  }
});

if (appendixGrid) {
  appendixGrid.innerHTML = appendixItems
    .filter(item => item.val && item.val !== "—" && item.val !== "")
    .map(item => `
      <div class="appendix-item">
        <div class="appendix-key">${safe(item.key)}</div>
        <div class="appendix-val">${safe(String(item.val))}</div>
      </div>
    `).join("");
}

// ─────────────────────────────────────────────
// 13. TOC — active section on scroll
// ─────────────────────────────────────────────

const sections  = document.querySelectorAll(".report-section");
const tocLinks  = document.querySelectorAll(".toc-list a");

const tocObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      tocLinks.forEach(link => link.classList.remove("active"));
      const active = document.querySelector(
        `.toc-list a[href="#${e.target.id}"]`
      );
      if (active) active.classList.add("active");
    }
  });
}, { threshold: 0.3 });

sections.forEach(section => tocObserver.observe(section));

// ─────────────────────────────────────────────
// 14. ANIMATE ALL PROGRESS BARS
// ─────────────────────────────────────────────

setTimeout(() => {
  document.querySelectorAll(".progress-fill").forEach(bar => {
    const width = bar.dataset.width || 0;
    bar.style.width = `${width}%`;
  });
}, 300);

// ─────────────────────────────────────────────
// 15. SHARE LINK — copy report URL with id param
// ─────────────────────────────────────────────

function getShareURL() {
  const base = window.location.href.split("?")[0];
  return reportId ? `${base}?id=${reportId}` : base;
}

function handleShareLink() {
  const url = getShareURL();
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(url).then(() => {
      Toast.success("Copied!", "Report link copied to clipboard.");
    }).catch(() => {
      prompt("Copy this link:", url);
    });
  } else {
    prompt("Copy this link:", url);
  }
}

// Wire both share buttons
const shareLinkBtn    = document.getElementById("shareLinkBtn");
const copyShareLinkBtn = document.getElementById("copyShareLinkBtn");

if (shareLinkBtn)     shareLinkBtn.addEventListener("click", handleShareLink);
if (copyShareLinkBtn) copyShareLinkBtn.addEventListener("click", handleShareLink);

// ─────────────────────────────────────────────
// 16. PDF EXPORT — real multi-page PDF via jsPDF + html2canvas
// ─────────────────────────────────────────────

async function exportPDF() {
  const jsPDF = window.jspdf?.jsPDF;
  if (!jsPDF || typeof html2canvas !== "function") {
    Toast.error("Export Unavailable", "PDF tools could not load. Please use your browser print command.");
    return;
  }
  const exportBtn = document.getElementById("exportPDFBtn");

  try {
    // Disable button + show loading state
    if (exportBtn) {
      exportBtn.disabled = true;
      exportBtn.textContent = "⏳ Generating...";
    }

    Toast.info("Preparing PDF...", "Capturing full report. This may take a few seconds.");

    // Target the full report container
    const reportEl = document.getElementById("report-container") || document.querySelector(".page-content");

    if (!reportEl) {
      throw new Error("Report container not found in DOM");
    }

    const canvas = await html2canvas(reportEl, {
      scale:       2,         // 2× for retina-quality PDF
      useCORS:     true,      // allow cross-origin images
      logging:     false,
      backgroundColor: getComputedStyle(document.body).backgroundColor || "#0f0f1a",
      windowWidth: document.documentElement.scrollWidth,
      scrollY:     -window.scrollY,
    });

    const imgData = canvas.toDataURL("image/png");

    const pdf       = new jsPDF("p", "mm", "a4");
    const pdfWidth  = 210;       // A4 width in mm
    const pageHeight = 295;      // A4 height in mm

    const imgWidth  = pdfWidth;
    const imgHeight = (canvas.height * imgWidth) / canvas.width;

    let heightLeft = imgHeight;
    let position   = 0;

    // First page
    pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
    heightLeft -= pageHeight;

    // Additional pages
    while (heightLeft > 0) {
      position   = heightLeft - imgHeight;
      pdf.addPage();
      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
    }

    // Filename: startup-name-survival-report.pdf
    const filename = `${startupName.replace(/\s+/g, "-").toLowerCase()}-survival-report.pdf`;
    pdf.save(filename);

    Toast.success("PDF Exported", `${filename} downloaded successfully.`);

  } catch (error) {
    console.error("PDF EXPORT ERROR:", error);
    Toast.error("Export Failed", "Could not generate PDF. Please try printing instead.");
  } finally {
    // Restore button
    if (exportBtn) {
      exportBtn.disabled  = false;
      exportBtn.textContent = "📄 Export PDF";
    }
  }
}

// Wire export button
const exportPDFBtn = document.getElementById("exportPDFBtn");
if (exportPDFBtn) {
  exportPDFBtn.addEventListener("click", exportPDF);
}

// ─────────────────────────────────────────────
// 17. SUCCESS TOAST on load
// ─────────────────────────────────────────────

Toast.success(
  "Report Ready",
  `${startupName} survival report loaded successfully.`
);

} // end renderReport

document.addEventListener("DOMContentLoaded", loadReport);