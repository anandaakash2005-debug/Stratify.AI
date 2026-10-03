import { chromium } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const root = path.resolve('frontend');
const report = JSON.parse(fs.readFileSync('qa/report-fixture.json', 'utf8'));
const server = http.createServer((req,res) => {
  const file=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));
  if (!file.startsWith(root+path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.html')?'text/html':'application/octet-stream');
  res.end(fs.readFileSync(file));
});
await new Promise(resolve=>server.listen(5517,'127.0.0.1',resolve));
let browser;
try {
  browser=await chromium.launch({channel:'chrome',headless:true});
  const page=await browser.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('survivaliq_auth',JSON.stringify({user:{id:'test-user',name:'Test'},token:'synthetic-test-token'})));
  await page.route('**/js/config.js',r=>r.fulfill({contentType:'text/javascript',body:'export const CONFIG={API_URL:"http://127.0.0.1:5517"};'}));
  await page.route('**/js/supabase.js',r=>r.fulfill({contentType:'text/javascript',body:'export const supabase={auth:{getSession:async()=>({data:{session:{user:{id:"test-user"},access_token:"synthetic-test-token"}}})}};'}));
  await page.route('**/api/v1/**',r=>r.fulfill({json:{data:[]}}));
  let count=0; let ids=[]; let fail=false;
  await page.route('**/api/v1/analyze/',async r=>{
    count++;ids.push(r.request().headers()['idempotency-key']);
    await new Promise(resolve=>setTimeout(resolve,300));
    await r.fulfill(fail?{status:502,json:{detail:'The AI report was incomplete. Please retry.',code:'AI_OUTPUT_INVALID',retryable:true}}:{json:report});
  });
  async function fill() {
    await page.goto('http://127.0.0.1:5517/analysis.html');
    await page.waitForFunction(()=>typeof window.nextPanel==='function');
    await page.fill('#startup-name','Inventory Pilot');
    await page.fill('#description','Inventory software for independent retailers');
    await page.selectOption('#industry',{index:1});
    await page.selectOption('#stage',{index:1});
  }
  await fill();
  fail=true;
  await page.evaluate(()=>{const b=document.getElementById('analysis-button'); b.click();b.dispatchEvent(new MouseEvent('click'));});
  await page.waitForFunction(()=>!document.getElementById('analysis-button').disabled);
  assert.equal(count,1,'double click must issue one request');
  assert.equal(await page.evaluate(()=>localStorage.getItem('latest_analysis')),null,'failed reports must not be stored');
  fail=false;
  await page.evaluate(()=>document.getElementById('analysis-button').click());
  await page.waitForURL('**/dashboard.html');
  await page.waitForTimeout(1000);
  assert.equal(count,2);
  assert.equal(ids[0],ids[1],'manual retry must reuse idempotency key');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('latest_analysis')).report_id),report.report_id);
  await page.goto('http://127.0.0.1:5517/report.html');
  await page.waitForTimeout(1000);
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS: duplicate click, retry ID reuse, failure cleanup, valid storage, dashboard redirect, dashboard and report rendering without JavaScript errors. Controlled API/auth responses.');
} finally {
  await browser?.close();
  await new Promise(resolve=>server.close(resolve));
}
