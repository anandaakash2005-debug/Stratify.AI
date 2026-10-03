/**
 * history.js
 * Satquery.AI — Analysis History Page
 *
 * Responsibilities:
 *  - Fetch GET /api/v1/reports/history
 *  - Render analysis cards dynamically
 *  - Search, filter, sort, paginate
 *  - Delete with confirmation modal
 *  - AI Insight panel + score distribution
 *  - Loading skeleton + empty + error states
 *  - View toggle (grid / list)
 *  - Toast notifications
 *  - Mobile nav toggle
 */

"use strict";

// ─────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────

const API_BASE        = "/api/v1";
const HISTORY_ENDPOINT = `${API_BASE}/reports/history`;
const DELETE_ENDPOINT  = (id) => `${API_BASE}/reports/${id}`;
const ITEMS_PER_PAGE   = 8;
const ANIMATION_STAGGER = 60; // ms between card animations

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────

const state = {
  all:         [],   // full dataset from API
  filtered:    [],   // after search + filter + sort
  currentPage: 1,
  viewMode:    "grid",  // "grid" | "list"
  filters: {
    search:   "",
    industry: "",
    stage:    "",
    sort:     "newest",
  },
  deletingId:      null,
  deletingName:    "",
  isLoading:       true,
  hasError:        false,
};

// ─────────────────────────────────────────────
// DOM REFS
// ─────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const DOM = {
  historyGrid:    $("history-grid"),
  skeletonGrid:   $("skeleton-grid"),
  emptyState:     $("empty-state"),
  errorState:     $("error-state"),
  errorMessage:   $("error-message"),
  resultsCount:   $("results-count"),
  pagination:     $("pagination"),
  filterChips:    $("filter-chips"),
  searchInput:    $("search-input"),
  searchClear:    $("search-clear"),
  filterIndustry: $("filter-industry"),
  filterStage:    $("filter-stage"),
  sortSelect:     $("sort-select"),
  filterReset:    $("filter-reset"),
  viewGrid:       $("view-grid"),
  viewList:       $("view-list"),
  retryBtn:       $("retry-btn"),
  exportAllBtn:   $("export-all-btn"),

  // Stats
  statTotal:      $("stat-total-val"),
  statAvg:        $("stat-avg-val"),
  statBest:       $("stat-best-val"),
  statLast:       $("stat-last-val"),

  // Insights
  insightList:    $("insight-list"),
  scoreDistBars:  $("score-dist-bars"),

  // Modal
  deleteModal:    $("delete-modal"),
  modalStartup:   $("modal-startup-name"),
  modalCancel:    $("modal-cancel"),
  modalConfirm:   $("modal-confirm"),

  // Toast
  toastContainer: $("toast-container"),

  // Nav
  hamburger:      document.querySelector(".nav-hamburger"),
  mobileMenu:     $("nav-mobile-menu"),
};

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initNav();
  initEventListeners();
  fetchHistory();
});

// ─────────────────────────────────────────────
// MOBILE NAV
// ─────────────────────────────────────────────

function initNav() {
  if (!DOM.hamburger || !DOM.mobileMenu) return;

  DOM.hamburger.addEventListener("click", () => {
    const isOpen = DOM.mobileMenu.classList.toggle("open");
    DOM.hamburger.setAttribute("aria-expanded", String(isOpen));
    DOM.mobileMenu.setAttribute("aria-hidden", String(!isOpen));
  });

  // Close on outside click
  document.addEventListener("click", (e) => {
    if (
      DOM.mobileMenu.classList.contains("open") &&
      !DOM.mobileMenu.contains(e.target) &&
      !DOM.hamburger.contains(e.target)
    ) {
      DOM.mobileMenu.classList.remove("open");
      DOM.hamburger.setAttribute("aria-expanded", "false");
      DOM.mobileMenu.setAttribute("aria-hidden", "true");
    }
  });
}

// ─────────────────────────────────────────────
// EVENT LISTENERS
// ─────────────────────────────────────────────

function initEventListeners() {
  // Search
  DOM.searchInput.addEventListener("input", debounce(() => {
    state.filters.search = DOM.searchInput.value.trim().toLowerCase();
    DOM.searchClear.hidden = !state.filters.search;
    state.currentPage = 1;
    applyFiltersAndRender();
  }, 250));

  DOM.searchClear.addEventListener("click", () => {
    DOM.searchInput.value = "";
    state.filters.search  = "";
    DOM.searchClear.hidden = true;
    state.currentPage = 1;
    applyFiltersAndRender();
  });

  // Filters
  DOM.filterIndustry.addEventListener("change", () => {
    state.filters.industry = DOM.filterIndustry.value;
    state.currentPage = 1;
    applyFiltersAndRender();
  });

  DOM.filterStage.addEventListener("change", () => {
    state.filters.stage = DOM.filterStage.value;
    state.currentPage = 1;
    applyFiltersAndRender();
  });

  DOM.sortSelect.addEventListener("change", () => {
    state.filters.sort = DOM.sortSelect.value;
    state.currentPage  = 1;
    applyFiltersAndRender();
  });

  // Reset
  DOM.filterReset.addEventListener("click", resetFilters);

  // View toggle
  DOM.viewGrid.addEventListener("click", () => setViewMode("grid"));
  DOM.viewList.addEventListener("click", () => setViewMode("list"));

  // Retry
  DOM.retryBtn.addEventListener("click", fetchHistory);

  // Export all
  DOM.exportAllBtn.addEventListener("click", handleExportAll);

  // Delete modal
  DOM.modalCancel.addEventListener("click",  closeDeleteModal);
  DOM.modalConfirm.addEventListener("click", confirmDelete);

  // Close modal on backdrop click
  DOM.deleteModal.addEventListener("click", (e) => {
    if (e.target === DOM.deleteModal) closeDeleteModal();
  });

  // Keyboard: close modal on Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !DOM.deleteModal.hidden) closeDeleteModal();
  });
}

// ─────────────────────────────────────────────
// FETCH
// ─────────────────────────────────────────────

async function fetchHistory() {
  setLoadingState(true);

  try {
    // Try real API first; fall back to localStorage for development
    let data;

    try {
      const res = await fetch(HISTORY_ENDPOINT, {
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(8000),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } catch (apiErr) {
      // Dev fallback: build mock history from localStorage
      console.warn("API unavailable, using localStorage fallback:", apiErr.message);
      data = buildLocalStorageFallback();
    }

    if (!Array.isArray(data)) throw new TypeError("Response is not an array");

    state.all     = data;
    state.filtered = [...data];
    state.hasError = false;

    setLoadingState(false);
    renderStats(data);
    renderInsightPanel(data);
    renderScoreDistribution(data);
    applyFiltersAndRender();

  } catch (err) {
    console.error("History fetch failed:", err);
    state.hasError = true;
    setLoadingState(false);
    showErrorState(err.message || "An unknown error occurred.");
  }
}

// ─────────────────────────────────────────────
// LOCALSTORAGE FALLBACK (development / offline)
// ─────────────────────────────────────────────

function buildLocalStorageFallback() {
  const analyses = [];

  // Check for latest_analysis
  const latest = localStorage.getItem("latest_analysis");
  if (latest) {
    try {
      const parsed = JSON.parse(latest);
      const metrics = parsed.metrics || {};
      const startup = parsed.startup || {};
      analyses.push({
        report_id:        parsed.report_id  || "local-" + Date.now(),
        startup_name:     startup.name      || parsed.startup_name || parsed.idea || "Startup",
        industry:         startup.industry  || parsed._form_data?.industry || "—",
        stage:            startup.stage     || parsed._form_data?.stage    || "—",
        survival_score:   metrics.survival_score   || parsed.health_score || 0,
        funding_readiness:metrics.funding_readiness || 0,
        risk_count:       metrics.risk_count       || (parsed.risks?.length || 0),
        competitor_count: parsed.competitors?.length || 0,
        created_at:       parsed.created_at || new Date().toISOString(),
      });
    } catch (_) {}
  }

  // Check for report history array
  const history = localStorage.getItem("report_history");
  if (history) {
    try {
      const parsed = JSON.parse(history);
      if (Array.isArray(parsed)) {
        parsed.forEach((item) => {
          if (!analyses.find((a) => a.report_id === item.report_id)) {
            analyses.push(item);
          }
        });
      }
    } catch (_) {}
  }

  // If truly empty, return empty array (empty state will show)
  return analyses;
}

// ─────────────────────────────────────────────
// FILTER + SORT
// ─────────────────────────────────────────────

function applyFiltersAndRender() {
  const { search, industry, stage, sort } = state.filters;

  let results = [...state.all];

  // Search by startup name
  if (search) {
    results = results.filter((r) =>
      (r.startup_name || "").toLowerCase().includes(search)
    );
  }

  // Industry filter
  if (industry) {
    results = results.filter((r) =>
      (r.industry || "").toLowerCase() === industry.toLowerCase()
    );
  }

  // Stage filter
  if (stage) {
    results = results.filter((r) =>
      (r.stage || "").toLowerCase() === stage.toLowerCase()
    );
  }

  // Sort
  results.sort((a, b) => {
    switch (sort) {
      case "oldest":     return new Date(a.created_at) - new Date(b.created_at);
      case "score-high": return (b.survival_score || 0) - (a.survival_score || 0);
      case "score-low":  return (a.survival_score || 0) - (b.survival_score || 0);
      case "newest":
      default:           return new Date(b.created_at) - new Date(a.created_at);
    }
  });

  state.filtered     = results;
  state.currentPage  = Math.min(state.currentPage, Math.max(1, Math.ceil(results.length / ITEMS_PER_PAGE)));

  renderFilterChips();
  renderResultsCount(results.length);
  renderPage();
  renderPagination();
}

// ─────────────────────────────────────────────
// RENDER: STATS
// ─────────────────────────────────────────────

function renderStats(data) {
  if (!data.length) {
    DOM.statTotal.textContent = "0";
    DOM.statAvg.textContent   = "—";
    DOM.statBest.textContent  = "—";
    DOM.statLast.textContent  = "—";
    return;
  }

  const scores = data.map((d) => d.survival_score || 0);
  const avg    = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  const best   = Math.max(...scores);

  // Relative date for latest
  const latestDate = data
    .map((d) => new Date(d.created_at))
    .sort((a, b) => b - a)[0];
  const relDate = relativeDate(latestDate);

  // Animate count up
  animateCount(DOM.statTotal, data.length);
  animateCount(DOM.statAvg,  avg,  "/100");
  animateCount(DOM.statBest, best, "/100");
  DOM.statLast.textContent = relDate;
}

// ─────────────────────────────────────────────
// RENDER: INSIGHT PANEL
// ─────────────────────────────────────────────

function renderInsightPanel(data) {
  if (!data.length) {
    DOM.insightList.innerHTML = `
      <div class="insight-item">
        <div class="insight-label">Status</div>
        <div class="insight-value" style="color:var(--text-muted);font-size:.85rem">No analyses yet</div>
      </div>
    `;
    return;
  }

  // Best startup
  const best = data.reduce((a, b) =>
    (a.survival_score || 0) >= (b.survival_score || 0) ? a : b
  );

  // Average funding readiness
  const avgFunding = Math.round(
    data.reduce((s, d) => s + (d.funding_readiness || 0), 0) / data.length
  );

  // Most common risk category (requires risk_categories field — fallback gracefully)
  const riskCounts = {};
  data.forEach((d) => {
    (d.risk_categories || []).forEach((cat) => {
      riskCounts[cat] = (riskCounts[cat] || 0) + 1;
    });
  });
  const topRisk = Object.entries(riskCounts).sort((a, b) => b[1] - a[1])[0];

  // Most recent industry
  const industryCounts = {};
  data.forEach((d) => {
    if (d.industry) industryCounts[d.industry] = (industryCounts[d.industry] || 0) + 1;
  });
  const topIndustry = Object.entries(industryCounts).sort((a, b) => b[1] - a[1])[0];

  DOM.insightList.innerHTML = `
    <div class="insight-item">
      <div class="insight-label">🏆 Best Startup</div>
      <div class="insight-value">${safe(best.startup_name || "—")}</div>
      <div class="insight-sub">${best.survival_score}/100 Survival Score</div>
    </div>
    <div class="insight-item">
      <div class="insight-label">📈 Avg Funding Readiness</div>
      <div class="insight-value gradient-text">${avgFunding}%</div>
      <div class="insight-sub">Across ${data.length} analys${data.length === 1 ? "is" : "es"}</div>
    </div>
    <div class="insight-item">
      <div class="insight-label">🏭 Top Industry</div>
      <div class="insight-value">${topIndustry ? safe(topIndustry[0]) : "—"}</div>
      <div class="insight-sub">${topIndustry ? `${topIndustry[1]} analys${topIndustry[1] === 1 ? "is" : "es"}` : "No data"}</div>
    </div>
    <div class="insight-item">
      <div class="insight-label">⚠️ Most Common Risk</div>
      <div class="insight-value" style="color:var(--amber)">${topRisk ? safe(topRisk[0]) : "—"}</div>
      <div class="insight-sub">${topRisk ? `Flagged ${topRisk[1]} time${topRisk[1] > 1 ? "s" : ""}` : "No risk data available"}</div>
    </div>
  `;
}

// ─────────────────────────────────────────────
// RENDER: SCORE DISTRIBUTION
// ─────────────────────────────────────────────

function renderScoreDistribution(data) {
  const buckets = { "80–100": 0, "60–79": 0, "40–59": 0, "0–39": 0 };

  data.forEach((d) => {
    const s = d.survival_score || 0;
    if (s >= 80)      buckets["80–100"]++;
    else if (s >= 60) buckets["60–79"]++;
    else if (s >= 40) buckets["40–59"]++;
    else              buckets["0–39"]++;
  });

  const max       = Math.max(...Object.values(buckets), 1);
  const fillClass = ["dist-fill-green", "dist-fill-blue", "dist-fill-amber", "dist-fill-red"];

  DOM.scoreDistBars.innerHTML = Object.entries(buckets).map(([label, count], i) => {
    const pct = Math.round((count / max) * 100);
    return `
      <div class="dist-bar-wrap">
        <div class="dist-label">${label}</div>
        <div class="dist-track">
          <div class="dist-fill ${fillClass[i]}" data-width="${pct}" style="width:0%"></div>
        </div>
        <div class="dist-count">${count}</div>
      </div>
    `;
  }).join("");

  // Animate bars
  setTimeout(() => {
    DOM.scoreDistBars.querySelectorAll(".dist-fill[data-width]").forEach((el) => {
      el.style.width = `${el.dataset.width}%`;
    });
  }, 400);
}

// ─────────────────────────────────────────────
// RENDER: FILTER CHIPS
// ─────────────────────────────────────────────

function renderFilterChips() {
  const chips = [];

  if (state.filters.search) {
    chips.push({ label: `"${state.filters.search}"`, key: "search" });
  }
  if (state.filters.industry) {
    chips.push({ label: state.filters.industry, key: "industry" });
  }
  if (state.filters.stage) {
    chips.push({ label: state.filters.stage, key: "stage" });
  }

  DOM.filterChips.hidden = chips.length === 0;

  DOM.filterChips.innerHTML = chips.map((c) => `
    <div class="filter-chip" role="listitem">
      ${safe(c.label)}
      <button class="chip-remove" data-key="${c.key}" aria-label="Remove ${safe(c.label)} filter">✕</button>
    </div>
  `).join("");

  DOM.filterChips.querySelectorAll(".chip-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.key;
      state.filters[key] = "";
      if (key === "search") {
        DOM.searchInput.value  = "";
        DOM.searchClear.hidden = true;
      } else if (key === "industry") {
        DOM.filterIndustry.value = "";
      } else if (key === "stage") {
        DOM.filterStage.value = "";
      }
      state.currentPage = 1;
      applyFiltersAndRender();
    });
  });
}

// ─────────────────────────────────────────────
// RENDER: RESULTS COUNT
// ─────────────────────────────────────────────

function renderResultsCount(count) {
  const total = state.all.length;
  if (count === total) {
    DOM.resultsCount.textContent = `${count} analys${count === 1 ? "is" : "es"}`;
  } else {
    DOM.resultsCount.textContent = `${count} of ${total} analys${total === 1 ? "is" : "es"}`;
  }
}

// ─────────────────────────────────────────────
// RENDER: PAGE (paginated cards)
// ─────────────────────────────────────────────

function renderPage() {
  const start = (state.currentPage - 1) * ITEMS_PER_PAGE;
  const end   = start + ITEMS_PER_PAGE;
  const page  = state.filtered.slice(start, end);

  if (state.filtered.length === 0) {
    DOM.historyGrid.hidden = true;
    showEmptyState();
    return;
  }

  hideEmptyState();
  DOM.historyGrid.hidden = false;
  DOM.historyGrid.className = `cards-grid${state.viewMode === "list" ? " list-view" : ""}`;
  DOM.historyGrid.innerHTML = page.map((item, i) => buildCard(item, i)).join("");

  // Wire up card buttons
  DOM.historyGrid.querySelectorAll(".card-btn-delete").forEach((btn) => {
    btn.addEventListener("click", () => {
      openDeleteModal(btn.dataset.id, btn.dataset.name);
    });
  });

  // Animate progress bars inside cards
  setTimeout(() => {
    DOM.historyGrid.querySelectorAll(".progress-fill[data-width]").forEach((el) => {
      el.style.width = `${el.dataset.width}%`;
    });
  }, 100);
}

// ─────────────────────────────────────────────
// BUILD: HISTORY CARD HTML
// ─────────────────────────────────────────────

function buildCard(item, animIndex) {
  const score     = Math.round(item.survival_score    || 0);
  const funding   = Math.round(item.funding_readiness || 0);
  const risks     = item.risk_count       || 0;
  const comps     = item.competitor_count || 0;
  const date      = item.created_at ? formatDate(new Date(item.created_at)) : "—";
  const relDate   = item.created_at ? relativeDate(new Date(item.created_at)) : "—";
  const id        = item.report_id || "";
  const name      = item.startup_name || "Unnamed Startup";
  const industry  = item.industry || "—";
  const stage     = item.stage    || "—";

  const scoreColor = score >= 70 ? "var(--emerald)" : score >= 50 ? "var(--indigo-light)" : "var(--amber)";
  const fundingFill = funding >= 65 ? "fill-emerald" : funding >= 45 ? "fill-indigo" : "fill-amber";
  const ringPct   = `${score}%`;
  const ringColor = scoreColor;
  const delay     = animIndex * ANIMATION_STAGGER;

  const dashUrl   = id ? `dashboard.html?id=${encodeURIComponent(id)}` : "dashboard.html";
  const reportUrl = id ? `report.html?id=${encodeURIComponent(id)}`    : "report.html";

  return `
    <article
      class="history-card"
      role="listitem"
      style="animation-delay:${delay}ms"
      data-id="${safe(id)}"
    >
      <div class="card-header">
        <div class="card-header-left">
          <div class="card-startup-name" title="${safe(name)}">${safe(name)}</div>
          <div class="card-badges">
            <span class="badge badge-industry">${safe(industry)}</span>
            <span class="badge badge-stage">${safe(stage)}</span>
          </div>
        </div>

        <div class="score-ring-wrap">
          <div
            class="score-ring"
            style="--ring-color:${ringColor};--ring-pct:${ringPct}"
            aria-label="Survival score ${score} out of 100"
            role="img"
          >
            <span class="score-ring-val">${score}</span>
          </div>
          <div class="score-ring-label">Survival<br/>Score</div>
        </div>
      </div>

      <div class="card-metrics">
        <div class="card-metric">
          <div class="card-metric-val" style="color:${funding >= 65 ? "var(--emerald)" : "var(--amber)"}">${funding}%</div>
          <div class="card-metric-label">Funding Ready</div>
        </div>
        <div class="card-metric">
          <div class="card-metric-val" style="color:${risks >= 3 ? "var(--rose)" : risks >= 1 ? "var(--amber)" : "var(--emerald)"}">${risks}</div>
          <div class="card-metric-label">${risks === 1 ? "Risk" : "Risks"}</div>
        </div>
        <div class="card-metric">
          <div class="card-metric-val" style="color:var(--cyan)">${comps}</div>
          <div class="card-metric-label">${comps === 1 ? "Competitor" : "Competitors"}</div>
        </div>
      </div>

      <div class="card-funding-bar">
        <div class="funding-bar-label">
          <span class="funding-bar-text">Funding Readiness</span>
          <span class="funding-bar-pct">${funding}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill ${fundingFill}" data-width="${funding}" style="width:0%"></div>
        </div>
      </div>

      <div class="card-date" title="${date}">
        🕐 ${relDate}
      </div>

      <div class="card-actions">
        <a
          href="${dashUrl}"
          class="card-btn card-btn-primary"
          aria-label="View dashboard for ${safe(name)}"
        >
          📊 Dashboard
        </a>
        <a
          href="${reportUrl}"
          class="card-btn"
          aria-label="View report for ${safe(name)}"
        >
          📄 Report
        </a>
        <button
          class="card-btn card-btn-delete"
          data-id="${safe(id)}"
          data-name="${safe(name)}"
          aria-label="Delete analysis for ${safe(name)}"
        >
          🗑️
        </button>
      </div>
    </article>
  `;
}

// ─────────────────────────────────────────────
// RENDER: PAGINATION
// ─────────────────────────────────────────────

function renderPagination() {
  const totalPages = Math.ceil(state.filtered.length / ITEMS_PER_PAGE);

  if (totalPages <= 1) {
    DOM.pagination.hidden = true;
    return;
  }

  DOM.pagination.hidden = false;
  const current = state.currentPage;

  let html = `
    <button class="page-btn" ${current === 1 ? "disabled" : ""} data-page="${current - 1}" aria-label="Previous page">‹</button>
  `;

  // Build page numbers with ellipsis
  const pages = getPaginationRange(current, totalPages);
  pages.forEach((p) => {
    if (p === "...") {
      html += `<span class="page-btn" style="cursor:default;pointer-events:none">…</span>`;
    } else {
      html += `
        <button
          class="page-btn ${p === current ? "active" : ""}"
          data-page="${p}"
          aria-label="Page ${p}"
          ${p === current ? 'aria-current="page"' : ""}
        >${p}</button>
      `;
    }
  });

  html += `
    <button class="page-btn" ${current === totalPages ? "disabled" : ""} data-page="${current + 1}" aria-label="Next page">›</button>
  `;

  DOM.pagination.innerHTML = html;

  DOM.pagination.querySelectorAll(".page-btn[data-page]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const page = parseInt(btn.dataset.page, 10);
      if (!isNaN(page) && page !== current) {
        state.currentPage = page;
        renderPage();
        renderPagination();
        DOM.historyGrid.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
}

function getPaginationRange(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const pages = [];
  pages.push(1);

  if (current > 3) pages.push("...");

  const start = Math.max(2, current - 1);
  const end   = Math.min(total - 1, current + 1);

  for (let i = start; i <= end; i++) pages.push(i);

  if (current < total - 2) pages.push("...");
  pages.push(total);

  return pages;
}

// ─────────────────────────────────────────────
// DELETE FLOW
// ─────────────────────────────────────────────

function openDeleteModal(id, name) {
  state.deletingId   = id;
  state.deletingName = name;
  DOM.modalStartup.textContent = name;
  DOM.deleteModal.hidden = false;
  DOM.modalConfirm.focus();
  document.body.style.overflow = "hidden";
}

function closeDeleteModal() {
  DOM.deleteModal.hidden = true;
  state.deletingId   = null;
  state.deletingName = "";
  document.body.style.overflow = "";
}

async function confirmDelete() {
  if (!state.deletingId) return;

  const id   = state.deletingId;
  const name = state.deletingName;

  DOM.modalConfirm.disabled    = true;
  DOM.modalConfirm.textContent = "Deleting...";

  try {
    // Try API delete
    let deleted = false;
    try {
      const res = await fetch(DELETE_ENDPOINT(id), {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(5000),
      });
      if (res.ok) deleted = true;
    } catch (_) {
      // Offline: remove from localStorage fallback
      deleted = deleteFromLocalStorage(id);
    }

    if (deleted) {
      // Remove from state
      state.all      = state.all.filter((r) => r.report_id !== id);
      state.filtered = state.filtered.filter((r) => r.report_id !== id);

      // Animate card out
      const card = DOM.historyGrid.querySelector(`[data-id="${id}"]`);
      if (card) {
        card.style.transition = "opacity 0.3s, transform 0.3s";
        card.style.opacity    = "0";
        card.style.transform  = "scale(0.95)";
        await sleep(320);
      }

      closeDeleteModal();
      renderStats(state.all);
      renderInsightPanel(state.all);
      renderScoreDistribution(state.all);
      applyFiltersAndRender();

      showToast("success", "Deleted", `"${name}" analysis removed.`);
    } else {
      throw new Error("Delete request failed");
    }

  } catch (err) {
    console.error("Delete error:", err);
    closeDeleteModal();
    showToast("error", "Error", "Could not delete the analysis. Please try again.");
  } finally {
    DOM.modalConfirm.disabled    = false;
    DOM.modalConfirm.textContent = "Delete";
  }
}

function deleteFromLocalStorage(id) {
  // Remove from latest_analysis if it matches
  try {
    const latest = localStorage.getItem("latest_analysis");
    if (latest) {
      const parsed = JSON.parse(latest);
      if (parsed.report_id === id) {
        localStorage.removeItem("latest_analysis");
      }
    }
  } catch (_) {}

  // Remove from history array
  try {
    const history = localStorage.getItem("report_history");
    if (history) {
      const parsed = JSON.parse(history);
      if (Array.isArray(parsed)) {
        const updated = parsed.filter((r) => r.report_id !== id);
        localStorage.setItem("report_history", JSON.stringify(updated));
      }
    }
  } catch (_) {}

  return true;
}

// ─────────────────────────────────────────────
// EXPORT ALL
// ─────────────────────────────────────────────

function handleExportAll() {
  if (!state.all.length) {
    showToast("info", "No Data", "No analyses to export.");
    return;
  }

  const blob = new Blob([JSON.stringify(state.all, null, 2)], {
    type: "application/json",
  });

  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `satquery-history-${dateSlug()}.json`;
  a.click();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
  showToast("success", "Exported", "All analysis history downloaded.");
}

// ─────────────────────────────────────────────
// VIEW TOGGLE
// ─────────────────────────────────────────────

function setViewMode(mode) {
  state.viewMode = mode;

  DOM.viewGrid.classList.toggle("active", mode === "grid");
  DOM.viewList.classList.toggle("active", mode === "list");
  DOM.viewGrid.setAttribute("aria-pressed", String(mode === "grid"));
  DOM.viewList.setAttribute("aria-pressed", String(mode === "list"));

  renderPage();
}

// ─────────────────────────────────────────────
// RESET FILTERS
// ─────────────────────────────────────────────

function resetFilters() {
  state.filters    = { search: "", industry: "", stage: "", sort: "newest" };
  state.currentPage = 1;

  DOM.searchInput.value    = "";
  DOM.filterIndustry.value = "";
  DOM.filterStage.value    = "";
  DOM.sortSelect.value     = "newest";
  DOM.searchClear.hidden   = true;

  applyFiltersAndRender();
  showToast("info", "Filters Reset", "Showing all analyses.");
}

// ─────────────────────────────────────────────
// LOADING / EMPTY / ERROR STATES
// ─────────────────────────────────────────────

function setLoadingState(loading) {
  state.isLoading = loading;

  DOM.skeletonGrid.hidden = !loading;
  DOM.skeletonGrid.setAttribute("aria-hidden", String(!loading));

  if (loading) {
    DOM.historyGrid.hidden = true;
    hideEmptyState();
    hideErrorState();
  }
}

function showEmptyState() {
  DOM.emptyState.hidden = false;
  DOM.errorState.hidden = true;
}

function hideEmptyState() {
  DOM.emptyState.hidden = true;
}

function showErrorState(msg) {
  DOM.skeletonGrid.hidden = true;
  DOM.historyGrid.hidden  = true;
  DOM.emptyState.hidden   = true;
  DOM.errorState.hidden   = false;
  DOM.errorMessage.textContent = msg || "An unknown error occurred.";
}

function hideErrorState() {
  DOM.errorState.hidden = true;
}

// ─────────────────────────────────────────────
// TOAST NOTIFICATIONS
// ─────────────────────────────────────────────

function showToast(type, title, message, duration = 3500) {
  const icons = { success: "✅", error: "❌", info: "ℹ️", warning: "⚠️" };

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || "ℹ️"}</span>
    <div class="toast-body">
      <div class="toast-title">${safe(title)}</div>
      ${message ? `<div class="toast-msg">${safe(message)}</div>` : ""}
    </div>
  `;

  DOM.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("out");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }, duration);
}

// ─────────────────────────────────────────────
// UTILITY: ANIMATE COUNT UP
// ─────────────────────────────────────────────

function animateCount(el, target, suffix = "", duration = 800) {
  if (!el) return;
  const start   = performance.now();
  const initial = 0;

  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased    = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(initial + eased * (target - initial)) + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }

  requestAnimationFrame(step);
}

// ─────────────────────────────────────────────
// UTILITY: DATES
// ─────────────────────────────────────────────

function formatDate(d) {
  if (!(d instanceof Date) || isNaN(d)) return "—";
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function relativeDate(d) {
  if (!(d instanceof Date) || isNaN(d)) return "—";

  const now   = Date.now();
  const delta = now - d.getTime();
  const secs  = Math.floor(delta / 1000);
  const mins  = Math.floor(secs / 60);
  const hours = Math.floor(mins / 60);
  const days  = Math.floor(hours / 24);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);

  if (secs  < 60)   return "Just now";
  if (mins  < 60)   return `${mins}m ago`;
  if (hours < 24)   return `${hours}h ago`;
  if (days  === 1)  return "Yesterday";
  if (days  < 7)    return `${days} days ago`;
  if (weeks === 1)  return "1 week ago";
  if (weeks < 4)    return `${weeks} weeks ago`;
  if (months === 1) return "1 month ago";
  if (months < 12)  return `${months} months ago`;
  return formatDate(d);
}

function dateSlug() {
  return new Date().toISOString().slice(0, 10);
}

// ─────────────────────────────────────────────
// UTILITY: XSS SAFE
// ─────────────────────────────────────────────

function safe(str) {
  const el = document.createElement("div");
  el.textContent = str ?? "";
  return el.innerHTML;
}

// ─────────────────────────────────────────────
// UTILITY: DEBOUNCE
// ─────────────────────────────────────────────

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// ─────────────────────────────────────────────
// UTILITY: SLEEP
// ─────────────────────────────────────────────

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
