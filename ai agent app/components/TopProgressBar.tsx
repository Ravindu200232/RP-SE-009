'use client';

import { useEffect, useRef, useState } from 'react';
import { useBuilder } from '@/lib/store';
import { stagesFor } from '@/lib/llm/planPrompts';

/** Count route rows in the Pages Plan markdown table (lines like "| `/foo` | …"). */
function countPlannedPages(pagesPlan: string): number {
  if (!pagesPlan) return 0;
  return pagesPlan
    .split('\n')
    .filter((l) => /^\s*\|\s*`?\/[A-Za-z0-9[\]]/.test(l)).length;
}

/** Count distinct METHOD /api/… endpoints named in the Backend Plan. */
function countPlannedApis(backendPlan: string): number {
  if (!backendPlan) return 0;
  const m = backendPlan.match(/\b(?:GET|POST|PUT|PATCH|DELETE)\s+\/api\//g);
  return m ? m.length : 0;
}

/**
 * Top-of-app progress bar that fills LIVE toward completion during a run.
 * Phases: analyze → plan (stages done) → build (pages + API routes on disk vs
 * planned) → repair → done. The fill is monotonic within one run so it never
 * jumps backward, and snaps to 100% with a "Done" flash before fading out.
 */
export function TopProgressBar() {
  const isStreaming = useBuilder((s) => s.isStreaming);
  const isPlanning = useBuilder((s) => s.isPlanning);
  const isBuilding = useBuilder((s) => s.isBuilding);
  const hasBackend = useBuilder((s) => s.hasBackend);
  const plans = useBuilder((s) => s.plans);
  const files = useBuilder((s) => s.files);
  const buildCoverage = useBuilder((s) => s.buildCoverage);

  const active = isStreaming || isPlanning || isBuilding;

  // Target percentage for the current phase.
  let target = 0;
  let label = '';
  if (isBuilding) {
    const plannedPages = countPlannedPages(plans.pages || '');
    const plannedApis = hasBackend ? countPlannedApis(plans.backend || '') : 0;
    const builtPages = files.filter((f) => /^app\/.*page\.tsx$/.test(f.path)).length;
    const builtApis = files.filter((f) => /^app\/api\/.*route\.ts$/.test(f.path)).length;
    const total = Math.max(1, plannedPages + plannedApis);
    const built =
      Math.min(builtPages, plannedPages || builtPages) +
      Math.min(builtApis, plannedApis || builtApis);
    const frac =
      buildCoverage && buildCoverage.planned > 0
        ? buildCoverage.built / buildCoverage.planned
        : built / total;
    target = 35 + 60 * Math.max(0, Math.min(1, frac));
    label =
      `Building · ${builtPages}/${plannedPages || '?'} pages` +
      (hasBackend ? ` · ${builtApis}/${plannedApis || '?'} APIs` : '');
  } else if (isPlanning) {
    const planStages = stagesFor(hasBackend).length || 9;
    const planDone = Object.values(plans).filter((v) => (v || '').trim().length > 40).length;
    target = 8 + 26 * Math.min(1, planDone / planStages);
    label = `Planning · ${planDone}/${planStages} stages`;
  } else if (isStreaming) {
    target = 5;
    label = 'Analyzing request';
  }

  const maxRef = useRef(0);
  const wasActive = useRef(false);
  const [display, setDisplay] = useState(0);
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    if (active) {
      setComplete(false);
      maxRef.current = Math.max(maxRef.current, target);
      setDisplay(maxRef.current);
      wasActive.current = true;
    } else if (wasActive.current) {
      // Finished a run: snap to 100%, flash "Done", then reset + hide.
      setDisplay(100);
      setComplete(true);
      const t = setTimeout(() => {
        setComplete(false);
        wasActive.current = false;
        maxRef.current = 0;
        setDisplay(0);
      }, 1600);
      return () => clearTimeout(t);
    }
  }, [active, target]);

  if (!active && !complete) return null;

  const width = `${Math.max(2, Math.min(100, display))}%`;

  return (
    <div className="relative h-6 w-full shrink-0 overflow-hidden border-b border-border bg-bg-soft">
      {/* translucent fill region */}
      <div
        className="absolute inset-y-0 left-0 bg-gradient-to-r from-accent/20 to-accent-soft/25 transition-[width] duration-500 ease-out"
        style={{ width }}
      />
      {/* phase label + percentage */}
      <div className="absolute inset-0 flex items-center justify-between px-3 text-[11px] font-medium">
        <span className="truncate text-text">{complete ? '✓ Done' : label}</span>
        <span className="tabular-nums text-text-muted">{Math.round(display)}%</span>
      </div>
      {/* solid leading edge line */}
      <div
        className="absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-accent to-accent-soft transition-[width] duration-500 ease-out"
        style={{ width }}
      />
    </div>
  );
}
