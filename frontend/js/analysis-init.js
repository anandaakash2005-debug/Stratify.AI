// analysis-init.js — Transport only: collect form → POST → store → redirect

import { supabase } from './supabase.js';
import { CONFIG } from './config.js';

const analysisAuthGuard = (typeof Auth !== 'undefined') ? Auth.requireAuth('analysis.html') : true;

let currentPanel = 1;

function nextPanel(from) {
  if (!analysisAuthGuard) return;
  if (from === 1) {
    const name = document.getElementById('startup-name')?.value.trim();
    const industry = document.getElementById('industry')?.value;
    const stage = document.getElementById('stage')?.value;
    if (!name || !industry || !stage) {
      Toast.warning('Required Fields', 'Please fill in the required fields before continuing.');
      return;
    }
  }
  goToPanel(from + 1);
}

function prevPanel(from) {
  goToPanel(from - 1);
}

function goToPanel(n) {
  document.getElementById(`panel-${currentPanel}`)?.classList.remove('active');
  currentPanel = n;
  document.getElementById(`panel-${n}`)?.classList.add('active');

  document.querySelectorAll('[data-step-indicator]').forEach(el => {
    const s = parseInt(el.dataset.stepIndicator);
    el.classList.remove('active', 'done');
    if (s === n) el.classList.add('active');
    else if (s < n) el.classList.add('done');
  });

  updateSummary();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateSummary() {
  const getVal = id => document.getElementById(id)?.value || '—';
  const getNum = id => parseFloat(document.getElementById(id)?.value) || 0;
  const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

  const name = getVal('startup-name');
  const industry = getVal('industry');
  const stage = getVal('stage');
  const burn = getNum('burn');
  const revenue = getNum('revenue');
  const cash = getNum('cash');
  const growth = getVal('growth');

  setText('sum-name', name.length > 12 ? name.slice(0, 12) + '…' : name);
  setText('sum-industry', industry.split('/')[0].trim().slice(0, 12));
  setText('sum-stage', stage.split('/')[0].trim().slice(0, 12));
  setText('sum-burn', burn ? '$' + formatNumber(burn) : '—');
  setText('sum-revenue', revenue ? '$' + formatNumber(revenue) : '—');
  setText('sum-growth', growth ? growth + '%' : '—');
  setText('sum-runway', 'Calculated after analysis');

  const fields = [name !== '—', industry !== '—', stage !== '—', burn > 0, revenue > 0, cash > 0];
  const pct = Math.round((fields.filter(Boolean).length / fields.length) * 100);
  setText('readiness-pct', pct);
  const bar = document.getElementById('readiness-bar');
  if (bar) bar.style.width = pct + '%';
}

document.querySelectorAll('.form-control').forEach(el => {
  el.addEventListener('input', updateSummary);
  el.addEventListener('change', updateSummary);
});

document.querySelectorAll('.checkbox-item input[type="checkbox"]').forEach(cb => {
  cb.addEventListener('change', () => {
    cb.closest('.checkbox-item')?.classList.toggle('checked', cb.checked);
  });
});

function collectFormData() {
  const getVal = id => document.getElementById(id)?.value.trim() || '';
  const getNum = id => parseFloat(getVal(id)) || 0;
  const getBool = id => {
    const el = document.getElementById(id);
    return el ? (el.checked || el.value === 'yes' || el.value === 'true') : false;
  };
  const getCheckboxGroup = selector =>
    Array.from(document.querySelectorAll(`${selector}:checked`))
      .map(cb => cb.value || cb.closest('.checkbox-item')?.querySelector('label')?.textContent?.trim() || cb.id);
  const location = getVal('location');
  const currency = /india|\bindia\b|\bin\b/i.test(location) ? 'INR' : 'USD';
  const riskCategories = getCheckboxGroup('#risks-group input');

  return {
    startup_name: getVal('startup-name'),
    industry: getVal('industry'),
    stage: getVal('stage'),
    country_region: location,
    currency,
    description: getVal('description'),
    website: getVal('website'),
    location: getVal('location'),
    founded: getVal('founded'),
    monthly_burn: getNum('burn'),
    monthly_revenue: getNum('revenue'),
    cash_in_bank: getNum('cash'),
    revenue_growth: getNum('growth'),
    total_raised: getNum('funding-raised') || getNum('funding'),
    valuation: getNum('valuation'),
    team_size: getNum('team-size') || getNum('team'),
    founders: getNum('founders') || 2,
    has_cto: getBool('tech-cofounder'),
    product_stage: getVal('product-stage'),
    customers: getNum('customers') || getNum('customer-count'),
    nps_score: getNum('nps'),
    churn_rate: getNum('churn'),
    risk_categories: riskCategories,
    founder_experience: getVal('founder-experience'),
    market_size: getVal('tam') || getVal('market-size'),
    differentiator: getVal('advantages') || getVal('moat'),
    go_to_market: getVal('gtm') || getVal('go-to-market'),
    challenges: getVal('challenges'),
    goals: getVal('goals'),
    additional_context: [getVal('challenges'), getVal('goals')].filter(Boolean).join('\n'),
    competitors_known: getVal('competitors') || getVal('known-competitors'),
    business_model: getVal('business-model') || 'Subscription',
    last_round: getVal('last-round'),
    gross_margin: getNum('gross-margin'),
    revenue_streams: getCheckboxGroup('.revenue-stream input'),
    tech_stack: getCheckboxGroup('.tech-stack input'),
    target_market: getCheckboxGroup('.target-market input'),
  };
}

let analysisInProgress = false;
let activeController = null;

function validReport(a) {
  const sections = ['startup', 'metrics', 'charts', 'executive_summary', 'financial_health', 'market_analysis', 'funding_readiness'];
  const scores = ['survival_score','survival_probability','funding_readiness','financial_score','market_score','team_score','product_score','traction_score','risk_score'];
  return a && typeof a.report_id === 'string' && sections.every(k => a[k] && typeof a[k] === 'object') &&
    scores.every(k => Number.isFinite(a.metrics[k])) &&
    ['strengths','weaknesses','opportunities','threats'].every(k => Array.isArray(a.swot?.[k]) && a.swot[k].length === 3) &&
    Array.isArray(a.risks) && a.risks.length === 3 && Array.isArray(a.competitors) && a.competitors.length === 3 &&
    Array.isArray(a.recommendations) && a.recommendations.length === 4 &&
    ['revenue_trend','burn_trend','cash_projection'].every(k => Array.isArray(a.charts[k]) && a.charts[k].length > 0);
}

async function runAnalysis(event) {
  event?.preventDefault();
  if (analysisInProgress) return;
  analysisInProgress = true;
  const button = document.getElementById('analysis-button');
  const original = button.innerHTML;
  let timer;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  button.textContent = 'Analyzing... This can take up to 120 seconds';
  activeController = new AbortController();
  timer = setTimeout(() => activeController?.abort(), 120000);
  try {
    const { data, error } = await supabase.auth.getSession();
    if (error || !data?.session) {
      throw Object.assign(new Error('Please sign in again to run analysis.'), { status: 401 });
    }
    const formData = collectFormData();
    if (!formData.startup_name || !formData.description) {
      throw new Error('Please fill in startup name and description.');
    }
    const body = JSON.stringify(formData);
    // Keep only a hash and UUID, not private form data, for retry recovery across reloads.
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body))))
      .map(b => b.toString(16).padStart(2, '0')).join('');
    const key = `analysis-request:${data.session.user.id}`;
    let previous;
    try { previous = JSON.parse(sessionStorage.getItem(key)); } catch { previous = null; }
    const requestId = previous?.hash === hash ? previous.id : crypto.randomUUID();
    sessionStorage.setItem(key, JSON.stringify({ hash, id: requestId }));
    Loader.show();
    const response = await fetch(`${CONFIG.API_URL.replace(/\/+$/, '')}/api/v1/analyze/`, {
      method: 'POST', signal: activeController.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}`,
                 'Idempotency-Key': requestId }, body,
    });
    const text = await response.text();
    let result;
    try { result = JSON.parse(text); } catch { result = null; }
    if (!response.ok) {
      console.error('ANALYSIS FAILED', response.status, text);
      const message = typeof result?.detail === 'string' ? result.detail : text || 'Backend returned an error.';
      throw Object.assign(new Error(message), { status: response.status, retryable: result?.retryable });
    }
    if (!validReport(result)) throw new Error('The server returned an incomplete report. Please retry.');
    localStorage.setItem('latest_analysis', JSON.stringify(result));
    localStorage.setItem('report_id', result.report_id);
    sessionStorage.removeItem(key);
    Toast.success('Analysis Complete', 'Opening dashboard...');
    window.location.assign('dashboard.html');
  } catch (err) {
    const message = err.name === 'AbortError' ? 'Analysis was cancelled or timed out. You can retry safely.' :
      err instanceof TypeError ? 'Could not reach the server. Check your connection and retry.' : err.message;
    Toast.error(err.status === 401 ? 'Authentication Required' : 'Analysis Failed', message);
  } finally {
    clearTimeout(timer);
    activeController = null;
    analysisInProgress = false;
    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.innerHTML = original;
    Loader.hide();
  }
}

document.getElementById('analysis-button')?.addEventListener('click', runAnalysis);
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', event => event.preventDefault()));
window.addEventListener('pagehide', () => activeController?.abort());
if (analysisAuthGuard) updateSummary();
window.nextPanel = nextPanel;
window.prevPanel = prevPanel;
