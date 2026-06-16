'use client';
// SECTION 4: cross-frame "Select Element" inspector (Google-AI-Studio style).
// While active we highlight the exact element under the cursor and show a small
// floating tag badge (h1 / Image / div). On click we capture the element's tag,
// text and image src plus the nearest [data-component-id] (its source file), and
// post VISUAL_ELEMENT_SELECTED to the studio for a targeted edit. Inert until on.
import * as React from 'react';
import { selectedComponentId } from '../lib/componentId';

export default function Inspector() {
  React.useEffect(() => {
    let active = false;
    let box = null;
    let badge = null;

    const ensure = () => {
      if (!box) {
        box = document.createElement('div');
        box.style.cssText =
          'position:fixed;z-index:2147483646;pointer-events:none;border:2px solid #7c3aed;' +
          'background:rgba(124,58,237,.10);border-radius:8px;transition:all .04s ease;display:none';
        badge = document.createElement('div');
        badge.style.cssText =
          'position:fixed;z-index:2147483647;pointer-events:none;display:none;font:600 11px/1.4 system-ui,sans-serif;' +
          'color:#fff;background:#7c3aed;padding:2px 8px;border-radius:7px;white-space:nowrap;' +
          'box-shadow:0 2px 8px rgba(0,0,0,.25)';
        document.body.appendChild(box);
        document.body.appendChild(badge);
      }
      return box;
    };

    // ignore our own overlay; pick the real element under the cursor
    const pick = (e) => {
      const el = e.target;
      if (!el || el === box || el === badge || el === document.body) return null;
      return el;
    };

    const tagName = (el) => {
      const t = (el.tagName || '').toLowerCase();
      if (t === 'img') return 'Image';
      if (t === 'svg' || el.closest('button')) return el.closest('button') ? 'button' : t;
      return t || 'element';
    };

    const onMove = (e) => {
      if (!active) return;
      const el = pick(e);
      ensure();
      if (!el) { box.style.display = 'none'; badge.style.display = 'none'; return; }
      const r = el.getBoundingClientRect();
      box.style.display = 'block';
      box.style.left = r.left + 'px'; box.style.top = r.top + 'px';
      box.style.width = r.width + 'px'; box.style.height = r.height + 'px';
      badge.textContent = tagName(el);
      badge.style.display = 'block';
      badge.style.left = r.left + 'px';
      badge.style.top = Math.max(2, r.top - 22) + 'px';
    };

    const setActive = (v) => {
      active = v;
      document.body.style.cursor = v ? 'crosshair' : '';
      ensure();
      if (!v) { box.style.display = 'none'; badge.style.display = 'none'; }
      try { window.parent.postMessage({ type: 'INSPECTOR_STATE', active: v }, '*'); } catch (err) { /* noop */ }
    };

    const onClick = (e) => {
      if (!active) return;
      const el = pick(e);
      if (!el) return;
      e.preventDefault();
      e.stopPropagation();
      const container = el.closest('[data-component-id]');
      const imgEl = el.tagName === 'IMG' ? el : el.querySelector && el.querySelector('img');
      const tag = (el.tagName || '').toLowerCase();
      const text = (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200);
      try {
        window.parent.postMessage({
          type: 'VISUAL_ELEMENT_SELECTED',
          componentId: selectedComponentId(el, window.location.pathname),  // never null/undefined
          label: (container && container.getAttribute('data-component-label')) || tagName(el),
          tag,
          className: typeof el.className === 'string' ? el.className.slice(0, 200) : '',
          isImage: !!imgEl,
          src: imgEl ? imgEl.getAttribute('src') : null,
          text,
        }, '*');
      } catch (err) { /* noop */ }
      setActive(false);
    };

    const onMsg = (e) => {
      const d = e.data || {};
      if (d.type === 'SET_INSPECTOR_STATE') setActive(!!d.active);
    };

    window.addEventListener('mousemove', onMove, true);
    window.addEventListener('click', onClick, true);
    window.addEventListener('message', onMsg);
    return () => {
      window.removeEventListener('mousemove', onMove, true);
      window.removeEventListener('click', onClick, true);
      window.removeEventListener('message', onMsg);
      if (box) box.remove();
      if (badge) badge.remove();
    };
  }, []);

  return null;
}
