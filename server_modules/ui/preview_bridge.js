// Runs inside the generated document, after the shared picker/console helpers.
if (!window.__agentforgeBridge) {
  window.__agentforgeBridge = true;
  let parentOrigin = null;
  let detachPicker = null;
  let mode = 'desktop';
  let activityTimer = null;
  let lastSent = 0;
  const frame = () => ({ contentWindow: window, contentDocument: document,
                        clientWidth: innerWidth, clientHeight: innerHeight });
  const send = (kind, data = {}) => {
    if (parentOrigin && window.parent !== window) {
      window.parent.postMessage({ type: 'agentforge:preview', kind, ...data,
        project: config.project, runtimeId: config.runtimeId }, parentOrigin);
    }
  };
  const here = () => location.pathname + location.search + location.hash;
  const state = () => send('route', { route: here(), scroll: { x: scrollX, y: scrollY } });
  const touch = () => {
    lastSent = performance.now();
    activityTimer = null;
    fetch(config.path + '/activity', { method: 'POST', keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ runtimeId: config.runtimeId }) }).catch(() => {});
  };
  const activity = (event) => {
    if (!event.isTrusted) return;
    // Leading + trailing delivery; no heartbeat when the user stops acting.
    if (performance.now() - lastSent >= 1000) touch();
    else if (!activityTimer) activityTimer = setTimeout(touch, 1000);
  };
  for (const name of ['pointerdown', 'keydown', 'input', 'wheel', 'touchstart']) {
    document.addEventListener(name, activity, { capture: true, passive: true });
  }
  // Scroll also includes scrollbar drags and touch scrolling. Programmatic
  // route polling/HMR never calls touch.
  let recentInput = 0;
  for (const name of ['pointerdown', 'keydown', 'wheel', 'touchmove']) {
    document.addEventListener(name, e => { if (e.isTrusted) recentInput = performance.now(); },
                              { capture: true, passive: true });
  }
  window.addEventListener('scroll', e => {
    state();
    if (performance.now() - recentInput < 2000) activity(e);
  }, { passive: true });
  window.addEventListener('pagehide', () => { if (activityTimer) { clearTimeout(activityTimer); touch(); } });
  for (const method of ['pushState', 'replaceState']) {
    const original = history[method];
    history[method] = function (...args) { const result = original.apply(this, args); state(); return result; };
  }
  window.addEventListener('popstate', state);
  window.addEventListener('hashchange', state);
  captureFrameConsole(frame(), (kind, text) => send('console', { level: kind, text }));
  window.addEventListener('message', event => {
    const message = event.data;
    if (event.source !== window.parent || !config.parents.includes(event.origin) ||
        !message || message.type !== 'agentforge:command' || message.project !== config.project ||
        message.runtimeId !== config.runtimeId) return;
    parentOrigin = event.origin;
    if (message.kind === 'init') { state(); send('ready'); }
    if (message.kind === 'pick') {
      detachPicker?.(); detachPicker = null;
      mode = message.mode || 'desktop';
      if (message.enabled) detachPicker = attachPicker(frame(), el => {
        send('picked', { info: pickedFrom(frame(), el, mode) });
      });
    }
    if (message.kind === 'navigate' && typeof message.route === 'string') {
      const url = new URL(message.route, location.origin);
      if (url.origin === location.origin) location.href = url.href;
    }
  });
}
