import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const root = path.resolve('frontend');
const port = 5518;
const hostileReport = JSON.parse(fs.readFileSync('qa/report-fixture.json', 'utf8'));
const attributePayload = 'var(--amber)" onmouseover="window.__xss=4';
hostileReport.financial_health.rows[0].color = attributePayload;
hostileReport.market_analysis.stats[0].color = attributePayload;
hostileReport.funding_readiness.bars[0].color = 'success" onmouseover="window.__xss=5';
if (hostileReport.risks.length) {
  hostileReport.risks[0].severity = 'medium" onmouseover="window.__xss=6';
} else {
  hostileReport.risks.push({
    category: 'Test risk',
    description: 'Synthetic QA fixture',
    severity: 'medium" onmouseover="window.__xss=6',
  });
}
const server = http.createServer((req, res) => {
  const file = path.resolve(root, `.${decodeURIComponent(req.url.split('?')[0])}`);
  if (!file.startsWith(`${root}${path.sep}`) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404);
    res.end();
    return;
  }
  res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html');
  res.end(fs.readFileSync(file));
});

await new Promise(resolve => server.listen(port, '127.0.0.1', resolve));
let browser;

try {
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage();
  const payload = '<img src=x onerror="window.__xss=1">';
  await page.addInitScript((untrustedName) => {
    window.__xss = 0;
    if (!sessionStorage.getItem('xss-qa-fixture-ready')) {
      localStorage.setItem('latest_analysis', JSON.stringify({ startup: { name: '<img src=x onerror="window.__xss=2">' } }));
      sessionStorage.setItem('xss-qa-fixture-ready', 'true');
    }
    localStorage.setItem('survivaliq_auth', JSON.stringify({
      user: { id: 'synthetic-user', user_metadata: { full_name: untrustedName } },
      token: 'synthetic-test-token',
    }));
  }, payload);
  await page.route('**/js/config.js', route => route.fulfill({
    contentType: 'text/javascript',
    body: `export const CONFIG={API_URL:"http://127.0.0.1:${port}"};window.CONFIG=CONFIG;`,
  }));
  await page.route('**/js/supabase.js', route => route.fulfill({
    contentType: 'text/javascript',
    body: 'export const supabase={auth:{getSession:async()=>({data:{session:{access_token:"synthetic-test-token"}}})}};',
  }));
  await page.route('**/api/v1/chatbot/history', route => route.fulfill({
    json: { history: [{ title: payload, message_count: payload, report_id: null }] },
  }));
  await page.route('**/api/v1/mentor/chat', route => route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: `data: ${JSON.stringify({
      type: 'structured',
      data: { reply: payload, headline: payload, intent: payload, suggested_questions: [`">${payload}`] },
    })}\n\n`,
  }));

  await page.goto(`http://127.0.0.1:${port}/chatbot.html`);
  await page.waitForSelector('.chat-history-item');
  await page.waitForSelector('.nav-user-info');
  await page.evaluate(() => window.ChatBot.send('<img src=x onerror="window.__xss=3">'));
  await page.waitForSelector('.mentor-deep-content', { state: 'attached' });
  await page.waitForSelector('.mentor-suggestions button', { state: 'attached' });

  const result = await page.evaluate(() => ({
    injectedImages: document.querySelectorAll('#chat-messages img, #recent-chats img, #analysis-badge img').length,
    navbarImages: document.querySelectorAll('.nav-user-info img').length,
    handlers: [...document.querySelectorAll('.mentor-suggestions button')].filter(button => button.hasAttribute('onclick')).length,
    badgeText: document.getElementById('analysis-badge').textContent,
    navbarText: document.querySelector('.nav-user-info').textContent,
    historyText: document.querySelector('.chat-history-item').textContent,
    messageText: document.querySelector('.msg.user').textContent,
    replyText: document.querySelector('.mentor-deep-content').textContent,
    questionText: document.querySelector('.mentor-suggestions button').textContent,
    xss: window.__xss,
  }));

  assert.equal(result.injectedImages, 0, 'untrusted content must not create image elements');
  assert.equal(result.navbarImages, 0, 'untrusted account names must not create image elements');
  assert.equal(result.handlers, 0, 'suggestion buttons must not use inline event handlers');
  assert.match(result.badgeText, /<img/);
  assert.match(result.navbarText, /<img/);
  assert.match(result.historyText, /<img/);
  assert.match(result.messageText, /<img/);
  assert.match(result.replyText, /<img/);
  assert.match(result.questionText, /<img/);
  assert.equal(result.xss, 0, 'untrusted event-handler text must never execute');

  await page.evaluate(report => localStorage.setItem('latest_analysis', JSON.stringify(report)), hostileReport);
  await page.goto(`http://127.0.0.1:${port}/report.html`);
  await page.waitForSelector('#financialTableBody tr');
  const reportResult = await page.evaluate(() => ({
    injectedHandlers: document.querySelectorAll('#financialTableBody [onmouseover], #marketStatCards [onmouseover], #riskList [onmouseover], #fundingBarsContainer [onmouseover]').length,
    riskClass: document.querySelector('#riskList .risk-item')?.className || '',
    fundingClass: document.querySelector('#fundingBarsContainer .progress-fill')?.className || '',
    xss: window.__xss,
  }));
  assert.equal(reportResult.injectedHandlers, 0, 'untrusted report colors and severity must not create event handlers');
  assert.doesNotMatch(reportResult.riskClass, /onmouseover/);
  assert.match(reportResult.fundingClass, /fill-danger/);
  assert.equal(reportResult.xss, 0, 'untrusted report attributes must never execute');
  console.log('PASS: chatbot, navbar, and report views render untrusted content safely and reject injected attributes.');
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
