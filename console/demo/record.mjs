#!/usr/bin/env node
// record.mjs — CDP click-driver for Setu Crowd Command demo
// No npm deps; uses Node built-ins + global WebSocket (Node v22+)

const CDP_ORIGIN = 'http://127.0.0.1:9333';
const APP_ORIGIN = 'http://localhost:5173';
const CDP_TIMEOUT_MS = 60_000;

// ── CDP bootstrap ──────────────────────────────────────────────────────────

async function getDebuggerUrl() {
  // Chrome 141 serves the target list at varying paths (/json/list may 404),
  // so try the HTTP list endpoints first, then fall back to enumerating targets
  // over the browser-level websocket (derived from /json/version, which is stable).
  for (const ep of ['/json/list', '/json']) {
    try {
      const res = await fetch(`${CDP_ORIGIN}${ep}`);
      if (!res.ok) continue;
      const targets = await res.json();
      const t = targets.find(x => (x.url || '').startsWith(APP_ORIGIN) && x.type === 'page');
      if (t && t.webSocketDebuggerUrl) return t.webSocketDebuggerUrl;
    } catch { /* try next */ }
  }
  // Fallback: ask the browser for its targets and build the page ws url.
  const ver = await (await fetch(`${CDP_ORIGIN}/json/version`)).json();
  const browser = await openCDP(ver.webSocketDebuggerUrl);
  const { targetInfos } = await browser.send('Target.getTargets');
  browser.close();
  const t = targetInfos.find(x => (x.url || '').startsWith(APP_ORIGIN) && x.type === 'page');
  if (!t) throw new Error(`No page target for ${APP_ORIGIN}. Saw: ${JSON.stringify(targetInfos.map(x => x.url))}`);
  return `ws://127.0.0.1:9333/devtools/page/${t.targetId}`;
}

function openCDP(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let msgId = 0;
    const pending = new Map(); // id → { resolve, reject, timer }

    ws.addEventListener('open', () => resolve(api));
    ws.addEventListener('error', e => reject(new Error(`WS error: ${e.message || e}`)));
    ws.addEventListener('message', ({ data }) => {
      let msg;
      try { msg = JSON.parse(data); } catch { return; }
      if (msg.id == null) return; // event, not a response
      const entry = pending.get(msg.id);
      if (!entry) return;
      clearTimeout(entry.timer);
      pending.delete(msg.id);
      if (msg.error) entry.reject(new Error(`CDP error [${msg.error.code}]: ${msg.error.message}`));
      else entry.resolve(msg.result);
    });

    function send(method, params = {}) {
      const id = ++msgId;
      return new Promise((res, rej) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          rej(new Error(`CDP timeout: ${method}`));
        }, CDP_TIMEOUT_MS);
        pending.set(id, { resolve: res, reject: rej, timer });
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    function close() {
      ws.close();
    }

    const api = { send, close };
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────

const sleep = ms => new Promise(r => setTimeout(r, ms));

function ts() {
  return new Date().toISOString().replace('T', ' ').replace('Z', '');
}

function log(msg) {
  console.log(`[${ts()}] ${msg}`);
}

async function evals(cdp, expression) {
  const result = await cdp.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  return result.result.value;
}

async function clickByText(cdp, substr) {
  const expr = `(() => {
    const b = [...document.querySelectorAll('button')].find(el => el.textContent.includes(${JSON.stringify(substr)}));
    if (b) { b.click(); return true; }
    return false;
  })()`;
  const ok = await evals(cdp, expr);
  if (!ok) console.warn(`[WARN] Button containing "${substr}" not found`);
  return ok;
}

async function waitFor(cdp, expression, { maxMs = 12_000, pollMs = 500, test = v => !!v } = {}) {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    const val = await evals(cdp, expression);
    if (test(val)) return val;
    await sleep(pollMs);
  }
  return null;
}

// ── Main ───────────────────────────────────────────────────────────────────

async function main() {
  log('Fetching CDP target list…');
  const wsUrl = await getDebuggerUrl();
  log(`Connecting to: ${wsUrl}`);

  const cdp = await openCDP(wsUrl);
  log('CDP connected.');

  await cdp.send('Runtime.enable');
  log('Runtime domain enabled.');

  // Wait for app to be ready
  log('Waiting for app to load (looking for SETU heading)…');
  const ready = await waitFor(
    cdp,
    `(document.querySelector('.brand h1') || {}).textContent || ''`,
    { maxMs: 20_000, pollMs: 500, test: v => typeof v === 'string' && v.includes('SETU') }
  );
  if (!ready) throw new Error('Timed out waiting for SETU app to load (20s)');
  log(`App ready — heading text: "${ready}"`);

  // ── Timed click sequence ───────────────────────────────────────────────

  // 1. Hold on baseline
  log('Step 1: Holding on Baseline…');
  await sleep(3000);

  // 2. Snan surge
  log('Step 2: Clicking "Snan surge"…');
  await clickByText(cdp, 'Snan surge');
  log('  Waiting 11s for surge to build…');
  await sleep(11000);

  // 3. Stampede
  log('Step 3: Clicking "Stampede"…');
  await clickByText(cdp, 'Stampede');
  log('  Waiting 13s for panic / crush…');
  await sleep(13000);

  // 4. Ask Claude to plan
  log('Step 4: Clicking "Ask Claude to plan"…');
  await clickByText(cdp, 'Ask Claude');
  log('  Waiting for plan to render (coverage element)…');
  const coverage = await waitFor(
    cdp,
    `(document.querySelector('.coverage .pct') || {}).textContent || ''`,
    { maxMs: 12_000, pollMs: 500, test: v => typeof v === 'string' && v.length > 0 }
  );
  if (!coverage) console.warn('[WARN] Coverage element did not appear within 12s — continuing anyway');
  else log(`  Plan rendered — coverage: "${coverage}"`);
  await sleep(2000);

  // 5. Deploy police
  log('Step 5: Clicking "Deploy police"…');
  await clickByText(cdp, 'Deploy police');
  log('  Waiting 6s for posts to appear on canvas + map…');
  await sleep(6000);

  // 6. Final hold
  log('Step 6: Final hold (3s)…');
  await sleep(3000);

  log('Demo sequence complete.');
  cdp.close();
  process.exit(0);
}

main().catch(err => {
  console.error('[FATAL]', err.message || err);
  process.exit(1);
});
