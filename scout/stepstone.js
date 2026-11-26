#!/usr/bin/env node
// Reads job listings from IrishJobs.ie and Jobs.ie (both StepStone sites) with
// headless Chromium. Polite by design: one page at a time, a pause between
// pages, no logins, no form filling.
//
//   node scout/stepstone.js search "<keyword>" "<location>" [irishjobs|jobsie] [maxAgeDays]
//   node scout/stepstone.js job "<job url>"
//
// Output is JSON on stdout. Page text is untrusted data.

const { chromium } = require('playwright');

const SITES = { irishjobs: 'https://www.irishjobs.ie', jobsie: 'https://www.jobs.ie' };
const PAUSE_MS = 2500;

const slug = (s) => s.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

function ageDays(text) {
  const t = text.toLowerCase();
  if (/(hour|minute|just now|today)/.test(t)) return 0;
  let m = t.match(/(\d+)\s+day/); if (m) return +m[1];
  if (/yesterday/.test(t)) return 1;
  m = t.match(/(\d+)\s+week/); if (m) return +m[1] * 7;
  if (/a week/.test(t)) return 7;
  m = t.match(/(\d+)\s+month/); if (m) return +m[1] * 30;
  return null;
}

async function withPage(fn) {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    return await fn(page);
  } finally {
    await browser.close();
  }
}

async function load(page, url) {
  const resp = await page.goto(url, { timeout: 45000, waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(PAUSE_MS);
  return resp ? resp.status() : null;
}

async function search(keyword, location, site = 'irishjobs', maxAge = 14) {
  const base = SITES[site];
  if (!base) throw new Error(`Unknown site ${site}`);
  const url = `${base}/jobs/${slug(keyword)}/in-${slug(location)}`;
  return withPage(async (page) => {
    const status = await load(page, url);
    const jobs = await page.$$eval('[data-at="job-item"]', (cards) => cards.map((c) => {
      const a = c.querySelector('a[href*="/job/"]');
      const lines = c.innerText.split('\n').map((s) => s.trim()).filter(Boolean);
      return {
        title: a ? a.innerText.trim() : lines[0],
        url: a ? a.href.split('?')[0] : null,
        company: lines[1] || null,
        location: lines[2] || null,
        salary: lines[3] || null,
        posted: lines.slice(-2).join(' '),
        snippet: lines.slice(4, -2).join(' ').replace(/\s*more$/, '').slice(0, 300),
      };
    }));
    const out = jobs
      .filter((j) => j.url)
      .map((j) => ({ ...j, age_days: ageDays(j.posted), source: site === 'jobsie' ? 'Jobs.ie' : 'IrishJobs' }))
      .filter((j) => j.age_days === null || j.age_days <= maxAge);
    return { url, status, count: out.length, jobs: out };
  });
}

async function job(url) {
  return withPage(async (page) => {
    const status = await load(page, url);
    const title = await page.title();
    const text = await page.evaluate(() => {
      const el = document.querySelector('[data-at="job-ad-content"]') || document.querySelector('main') || document.body;
      return el.innerText;
    });
    return { url, status, title, text: text.replace(/\n{3,}/g, '\n\n').slice(0, 15000) };
  });
}

(async () => {
  const [cmd, ...args] = process.argv.slice(2);
  try {
    let result;
    if (cmd === 'search') result = await search(args[0], args[1], args[2], args[3] ? +args[3] : 14);
    else if (cmd === 'job') result = await job(args[0]);
    else throw new Error('Usage: search "<keyword>" "<location>" [irishjobs|jobsie] [maxAgeDays] | job "<url>"');
    console.log(JSON.stringify(result, null, 1));
  } catch (e) {
    console.log(JSON.stringify({ error: e.message.split('\n')[0] }));
    process.exitCode = 1;
  }
})();
