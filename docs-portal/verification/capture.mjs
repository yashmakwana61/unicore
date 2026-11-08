#!/usr/bin/env node
/**
 * Read-only Playwright screenshot capture for a disposable Edicai demo.
 * Does not log in, click workflow buttons, submit forms, or modify any Odoo records.
 *
 * Setup:
 *   npm install --no-save playwright
 *   npx playwright install chromium
 *   EDICAI_DEMO_ORIGIN=https://demo.example.test \
 *   EDICAI_DEMO_OK=I_CONFIRM_SYNTHETIC_ISOLATED_ENV \
 *   EDICAI_STORAGE_STATE=/secure/location/test-session.json \
 *   node docs-portal/verification/capture.mjs
 *
 * The storage state is optional and must never be committed or published.
 */
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const confirmation='I_CONFIRM_SYNTHETIC_ISOLATED_ENV';
const rawOrigin=process.env.EDICAI_DEMO_ORIGIN;
if (process.env.EDICAI_DEMO_OK !== confirmation) {
  throw new Error('Explicit disposable synthetic-environment confirmation is required');
}
if (!rawOrigin) throw new Error('EDICAI_DEMO_ORIGIN must be explicitly configured');
const target=new URL(rawOrigin);
if (target.protocol!=='https:' && !(target.protocol==='http:' && ['127.0.0.1','localhost'].includes(target.hostname))) {
  throw new Error('HTTPS is required except for localhost');
}
if (target.pathname!=='/' || target.search || target.hash || target.username || target.password) {
  throw new Error('Origin must not contain credentials, paths or queries');
}
const host=target.hostname.toLowerCase();
if (host==='app.edicai.com' || host==='edicai.com' || host==='docs.edicai.com' ||
    host==='app.clasflow.io' || host==='clasflow.io' ||
    host.endsWith('.edicai.com') || host.endsWith('.clasflow.io') ||
    host.includes('prod') || host.includes('production')) {
  throw new Error('Protected or production-like hostname. Use isolated nonproduction origin');
}
const origin=target.origin;
const storagePath=process.env.EDICAI_STORAGE_STATE;
if (storagePath && !fs.existsSync(storagePath)) throw new Error('Storage state does not exist');
const destination=path.resolve('docs-portal/verification/output');
fs.mkdirSync(destination,{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({
  ...(storagePath?{storageState:storagePath}:{}),
  viewport:{width:1440,height:900},
  acceptDownloads:false,
  serviceWorkers:'block'
});
// Reject cross-origin traffic to prevent accidental contact with production ERP.
// Fonts and third-party analytics are also blocked; screenshots may look different.
await context.route('**/*',async route=>{
  const req=route.request();
  const url=new URL(req.url());
  if(url.origin!==origin) return route.abort();
  if(!['GET','HEAD'].includes(req.method())) return route.abort();
  if(['/web/dataset/call_kw','/web/dataset/call_button','/web/session/logout'].some(s=>url.pathname.startsWith(s))) return route.abort();
  return route.continue();
});
const screens=[
  {name:'login-page',url:'/web/login',selector:'body'},
  {name:'odoo-shell',url:'/web',selector:'body'}
];
const manifest=[];
try {
  for(const s of screens){
    const page=await context.newPage();
    await page.goto(origin+s.url,{waitUntil:'domcontentloaded',timeout:30000});
    await page.locator(s.selector).waitFor({timeout:10000});
    const output=path.join(destination,s.name+'.png');
    await page.screenshot({path:output,fullPage:true,animations:'disabled'});
    manifest.push({id:s.name,path:output,source_url:origin+s.url,review_status:'pending-human-review'});
    await page.close();
  }
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(destination,'capture-manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log('Captured '+manifest.length+' read-only screenshots. Do NOT publish without privacy review.');
