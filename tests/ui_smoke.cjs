// Run against the local server. Set PLAYWRIGHT_MODULE when Playwright is bundled elsewhere.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function smoke() {
  const url = process.env.HIRELOOP_URL || 'http://127.0.0.1:8000';
  assert.ok(['localhost', '127.0.0.1', '::1', '[::1]'].includes(new URL(url).hostname), 'Use a local development server.');
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [], modelRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      const path = new URL(request.url()).pathname;
      if (request.method() === 'POST' && /^\/api\/(chat|jobs\/match|resumes(?:\/|$))/.test(path)) modelRequests.push(path);
    });
    await page.goto(url);
    await page.locator('#auth-view').waitFor({ state: 'visible' });
    await page.locator('#register-tab').click();
    await page.locator('#auth-name').fill('بررسی رابط');
    const email = `ui-smoke-${Date.now()}-${process.pid}@example.com`;
    await page.locator('#auth-email').fill(email);
    await page.locator('#auth-password').fill('LocalSmokeCheck123!');
    await page.locator('#auth-submit').click();
    await page.locator('#workspace').waitFor({ state: 'visible' });
    if (await page.locator('#config-banner').isVisible()) assert.equal(await page.locator('#chat-submit').isDisabled(), true);

    await page.locator('#chat-actions [data-go="profile"]').click();
    await page.locator('#view-profile').waitFor({state:'visible'});
    assert.equal(await page.locator('#profile-submit').textContent(),'ذخیره و تأیید پروفایل');
    await page.locator('[name="full_name"]').fill('بررسی رابط');
    await page.locator('[name="city"]').fill('تهران');
    await page.locator('[name="skills"]').fill('HTML، CSS، HTML');
    await page.locator('[data-add-entry="projects"]').click();
    const project = page.locator('[data-profile-entry="projects"]').first();
    const description = 'Built React UI | accessible\nAdded keyboard access';
    await project.locator('[data-entry-field="name"]').fill('پروژه بررسی | واقعی');
    await project.locator('[data-entry-field="description"]').fill(description);
    await project.locator('[data-entry-field="url"]').fill('https://example.com');
    await page.locator('#profile-submit').click();
    await page.locator('#notice').filter({ hasText: 'ذخیره و تأیید شد' }).waitFor();
    await page.reload();
    await page.locator('#workspace').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#dossier-name').textContent(), 'بررسی رابط');
    assert.equal(await page.locator('#dossier-skills .chip').count(), 2);
    assert.match(await page.locator('#profile-status').textContent(), /تأیید شده/);
    await page.locator('[data-view="profile"]').click();
    assert.equal(await project.locator('[data-entry-field="description"]').inputValue(), description);
    assert.equal(await project.locator('[data-entry-field="url"]').inputValue(), 'https://example.com');
    await page.locator('#profile-submit').click();
    await page.locator('#notice').filter({ hasText: 'ذخیره و تأیید شد' }).waitFor();
    const saved = await page.evaluate(async () => (await fetch('/api/me')).json());
    assert.equal(saved.profile.projects.length, 1);
    assert.equal(saved.profile.projects[0].description, description);
    assert.equal(saved.profile.projects[0].name, 'پروژه بررسی | واقعی');
    const summary = await page.evaluate(() => {
      state.search = {query:'Python',city:'زنجان',remote:true,jobs:[],sources:[
        {id:'jobinja',name:'جابینجا',status:'empty',count:0},
        {id:'jobvision',name:'جاب‌ویژن',status:'error',count:0,error:'دریافت صفحه ناموفق'}]};
      renderChatActions();
      const text = document.querySelector('#chat-actions').textContent;
      state.search = null; renderChatActions();
      return text;
    });
    assert.match(summary,/زنجان یا دورکاری/);
    assert.match(summary,/جابینجا: بدون نتیجه/);
    assert.match(summary,/جاب‌ویژن: دسترسی ناموفق/);

    // Offline transport fixture: even an abort-ignoring response cannot cross a session change.
    const stale = await page.evaluate(async () => {
      const originalFetch = window.fetch;
      let resolve;
      window.fetch = () => new Promise(done => { resolve = done; });
      const request = api('/api/offline-stale-check').then(() => 'accepted', error => error.name);
      document.querySelector('#chat-input').disabled = true;
      showAuth();
      resolve(new Response(JSON.stringify({profile:{full_name:'Previous account'}}), {status:200}));
      const result = await request;
      window.fetch = originalFetch;
      return {result, disabled:document.querySelector('#chat-input').disabled};
    });
    assert.equal(stale.result, 'SessionChanged');
    assert.equal(stale.disabled, false);
    await page.reload();
    await page.locator('#workspace').waitFor({ state: 'visible' });

    await page.locator('[data-view="jobs"]').click();
    assert.equal(await page.locator('#source-filters input:checked').count(), 4);
    if (process.env.LIVE_SEARCH === '1') {
      await page.locator('#job-query').fill('Python');
      const response = page.waitForResponse(response => new URL(response.url()).pathname === '/api/jobs/search', { timeout: 120000 });
      await page.locator('#search-submit').click();
      assert.equal((await response).status(), 200);
      await page.locator('#source-status .source-result').first().waitFor();
      assert.equal(await page.locator('#source-status .source-result').count(), 4);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('[data-view="interview"]').click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Mobile layout must not overflow horizontally.');
    assert.equal(await page.locator('#logout').isVisible(), true);
    await page.locator('#logout').click();
    await page.locator('#auth-view').waitFor({ state: 'visible' });
    assert.equal(await page.locator('[name="full_name"]').inputValue(), '');
    assert.equal(await page.locator('#dossier-name').textContent(), 'نام شما');
    assert.equal(await page.locator('#dossier-skills .chip').count(), 0);

    await page.locator('#login-tab').click();
    await page.locator('#auth-email').fill(email);
    await page.locator('#auth-password').fill('LocalSmokeCheck123!');
    await page.locator('#auth-submit').click();
    await page.locator('#workspace').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#dossier-name').textContent(), 'بررسی رابط');
    await page.locator('#logout').click();
    await page.locator('#auth-view').waitFor({ state: 'visible' });
    assert.deepEqual(errors, [], 'No JavaScript errors.');
    assert.deepEqual(modelRequests, [], 'The smoke check must not make model requests.');
    console.log(`PASS: auth, lossless profile, stale response guard, mobile, logout privacy; no model calls. Disposable local account: ${email}`);
  } finally { await browser.close(); }
}

smoke().catch(error => { console.error(error); process.exitCode = 1; });
