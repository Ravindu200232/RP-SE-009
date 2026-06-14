// Page-wise prototype audit — paste into preview_eval on <host>/<pid>/index.html.
// Returns {routes, results[], summary}. Checks per route:
//  render: text length, error/fallback card detection
//  images: every assets/*.jpg <img> loaded (naturalWidth>0)
//  overlap: visible text elements whose boxes intersect >40% (non ancestor pairs)
//  probes: dashboard bell toggle, notifications mark-all-read, FAQ toggle
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 60 && !window.AppDB; i++) await sleep(200);

  const html = document.documentElement.innerHTML;
  const routes = [...new Set([...html.matchAll(/path=["'`]([^"'`*]+)["'`]/g)].map(m => m[1]))]
    .filter(p => p && p.startsWith('/') && !p.includes(':'));

  // login as primary role with a name (mirrors the generated Login page)
  localStorage.setItem('session', JSON.stringify({ email: 'demo@demo.com', name: 'demo', role: 'Admin', roles: ['Admin'] }));
  const keys = [...new Set([...html.matchAll(/getRecords\(['"`]([^'"`]+)['"`]\)/g)].map(m => m[1]))];
  keys.forEach(k => { try { const r = (window.AppDB.getRecords(k) || []); if (r[0] && r[0].id) localStorage.setItem('__sel_' + k, r[0].id); } catch (e) {} });

  const root = document.getElementById('root');
  let jsErrors = [];
  const onErr = (e) => jsErrors.push(String((e && (e.message || e.reason)) || e).slice(0, 120));
  window.addEventListener('error', onErr);
  window.addEventListener('unhandledrejection', onErr);

  const textOverlaps = () => {
    const els = [...root.querySelectorAll('*')].filter(el => {
      if (!el.checkVisibility || !el.checkVisibility()) return false;
      return [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 2);
    }).slice(0, 250);
    const bad = [];
    for (let i = 0; i < els.length; i++) {
      const a = els[i].getBoundingClientRect();
      if (a.width < 8 || a.height < 8) continue;
      for (let j = i + 1; j < els.length; j++) {
        if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
        const b = els[j].getBoundingClientRect();
        const ix = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
        const iy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
        const inter = ix * iy, small = Math.min(a.width * a.height, b.width * b.height);
        if (small > 0 && inter / small > 0.4) {
          bad.push((els[i].textContent || '').trim().slice(0, 24) + ' <> ' + (els[j].textContent || '').trim().slice(0, 24));
          if (bad.length >= 3) return bad;
        }
      }
    }
    return bad;
  };

  const results = [];
  for (const p of routes) {
    jsErrors = [];
    location.hash = '#' + p;
    await sleep(450);
    const text = (root.innerText || '').replace(/\s+/g, ' ').trim();
    const fellback = /This section couldn't load|is being prepared|Something went wrong/i.test(text);
    const imgs = [...root.querySelectorAll('img')].filter(i => (i.getAttribute('src') || '').includes('assets/'));
    const impaths = imgs.map(i => (i.getAttribute('src') || '') + (i.complete && i.naturalWidth > 0 ? ':ok' : ':MISSING'));
    const overlaps = textOverlaps();

    let probe = null;
    try {
      if (p === '/dashboard') {
        const bell = [...root.querySelectorAll('button')].find(b => b.querySelector('svg') && /bell|notif/i.test(b.outerHTML));
        if (bell) { const before = root.innerHTML.length; bell.click(); await sleep(250); probe = 'bell:' + (root.innerHTML.length !== before ? 'works' : 'DEAD'); bell.click(); await sleep(120); }
      } else if (/notification/i.test(p)) {
        const mark = [...root.querySelectorAll('button')].find(b => /mark all/i.test(b.textContent));
        if (mark) { const before = root.innerHTML; mark.click(); await sleep(250); probe = 'markAll:' + (root.innerHTML !== before ? 'works' : 'DEAD'); }
        else probe = 'markAll:NOT_FOUND';
      } else if (p === '/') {
        const faqBtn = [...root.querySelectorAll('button')].find(b => /\?/.test(b.textContent) && b.textContent.length < 120);
        if (faqBtn) { const before = root.innerHTML.length; faqBtn.click(); await sleep(250); probe = 'faq:' + (root.innerHTML.length !== before ? 'works' : 'DEAD'); }
      }
    } catch (e) { probe = 'probe-error:' + String(e).slice(0, 60); }

    results.push({
      route: p, len: text.length,
      bad: text.length < 25 || fellback || jsErrors.length > 0,
      fellback, err: jsErrors[0] || null,
      images: impaths, overlaps, probe,
    });
  }
  const badRoutes = results.filter(r => r.bad);
  const missingImgs = results.flatMap(r => r.images.filter(i => i.includes(':MISSING')).map(i => r.route + ' ' + i));
  const overlapRoutes = results.filter(r => r.overlaps.length).map(r => r.route);
  const deadProbes = results.filter(r => r.probe && /DEAD|NOT_FOUND/.test(r.probe)).map(r => r.route + ' ' + r.probe);
  return {
    total: routes.length,
    summary: { badRoutes: badRoutes.length, missingImgs, overlapRoutes, deadProbes },
    bad: badRoutes.map(r => ({ route: r.route, len: r.len, err: r.err, fellback: r.fellback })),
    results,
  };
})()
