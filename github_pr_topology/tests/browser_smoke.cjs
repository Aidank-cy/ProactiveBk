const { chromium } = require('../frontend/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.stack || error.message));
  try {
    await page.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle' });
    await page.locator('.graph-stage canvas').first().waitFor({ timeout: 30000 });
    if (await page.locator('html').getAttribute('lang') !== 'zh-CN') throw new Error('Page language is not zh-CN');
    await page.getByRole('button', { name: '关系图探索', exact: true }).waitFor();
    await page.waitForFunction(() => window.__topologyCy && window.__topologyCy.nodes().length > 0);
    const out = path.resolve('screenshots'); fs.mkdirSync(out, { recursive: true });
    await page.screenshot({ path: path.join(out, 'graph_explorer.png') });
    const initialRepo = await page.locator('#repo-select').inputValue();
    const repos = await page.locator('#repo-select option').count();
    if (repos < 2) throw new Error('Expected at least two repositories');
    const second = await page.locator('#repo-select option').nth(1).getAttribute('value');
    await page.locator('#repo-select').selectOption(second);
    await page.waitForFunction(name => document.querySelector('.workspace-head h2')?.textContent === name, second);
    await page.locator('#repo-select').selectOption(initialRepo);
    await page.waitForFunction(() => window.__topologyCy?.nodes().length > 0);
    await page.evaluate(() => { const n = window.__topologyCy.nodes('[kind = "PULL_REQUEST"]').first(); if (n.length) n.emit('tap'); });
    await page.locator('.details-panel .detail-tabs').waitFor({ timeout: 10000 });
    await page.getByRole('button', { name: '时间线', exact: true }).click();
    await page.locator('.timeline').waitFor();
    await page.getByRole('button', { name: '证据', exact: true }).click();
    await page.locator('.evidence-list').waitFor();
    await page.getByRole('button', { name: '拓扑统计' }).click();
    await page.getByRole('heading', { name: '拓扑统计' }).waitFor();
    await page.screenshot({ path: path.join(out, 'topology_statistics.png') });
    await page.getByRole('button', { name: '案例研究' }).click();
    await page.locator('.case-card').first().waitFor();
    await page.locator('.case-card').first().click();
    await page.locator('.details-panel .detail-tabs').waitFor();
    await page.locator('input[type="date"]').last().fill('2026-10-20');
    await page.locator('.time-banner').waitFor();
    await page.waitForFunction(() => window.__topologyCy && window.__topologyCy.nodes().length > 0);
    await page.waitForFunction(() => document.querySelector('.details-panel h2')?.textContent?.startsWith('PR #'));
    await page.waitForFunction(() => { const rows = [...document.querySelectorAll('.details-panel .related-node')]; return rows.length > 0 && rows.every(row => /^(Issue|PR) #\d+/.test(row.textContent.trim())); });
    await page.screenshot({ path: path.join(out, 'historical_slice.png') });
    await page.getByRole('button', { name: '清除历史快照' }).click();
    if (errors.length) throw new Error('Browser console errors: ' + errors.join(' | '));
    console.log(JSON.stringify({ status: 'passed', initialRepo, repositories: repos, screenshots: ['graph_explorer.png', 'topology_statistics.png', 'historical_slice.png'] }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
