"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_AGENT4_API_BASE_URL ?? "http://localhost:8004";

type JobPayload = {
  job_id: string;
  state: string;
  architecture: string;
  confidence: number;
  message: string;
  download_path: string;
  evidence_path: string;
  artifacts: string[];
  validation: {
    success: boolean;
    checks: Array<{ name: string; success: boolean; details: string }>;
  };
  push_result: {
    state: string;
    message: string;
    branch: string;
    commit_sha: string;
  };
  strategy: {
    deployment_profile: string;
    notes: string[];
  };
};

export default function JobPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params?.jobId ?? "";
  const [payload, setPayload] = useState<JobPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let active = true;

    async function load() {
      try {
        const response = await fetch(`${apiBase}/jobs/${jobId}`, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail ?? "Failed to load job.");
        }
        if (active) {
          setPayload(data);
        }
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "Failed to load job.";
        if (active) {
          setError(message);
        }
      }
    }

    load();
    const interval = window.setInterval(load, 3000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [jobId]);

  const downloadUrl = useMemo(() => {
    if (!payload?.download_path) {
      return "";
    }
    return `${apiBase}${payload.download_path}`;
  }, [payload]);

  const progressValue = useMemo(() => {
    if (!payload) {
      return 0;
    }

    const state = payload.state.toLowerCase();
    if (state.includes("fail") || state.includes("error")) {
      return 20;
    }
    if (state.includes("review")) {
      return 60;
    }
    if (state.includes("done") || state.includes("complete")) {
      return 100;
    }
    return 80;
  }, [payload]);

  const validationSummary = useMemo(() => {
    if (!payload) {
      return { passed: 0, failed: 0 };
    }

    return payload.validation.checks.reduce(
      (summary, check) => {
        if (check.success) {
          summary.passed += 1;
        } else {
          summary.failed += 1;
        }
        return summary;
      },
      { passed: 0, failed: 0 },
    );
  }, [payload]);

  const pushState = payload?.push_result.state ?? "Pending";
  const pushTone = /success|done|complete/i.test(pushState)
    ? "badge-pass"
    : /fail|error|reject/i.test(pushState)
      ? "badge-fail"
      : "badge-warn";

  return (
    <main className="page-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">A4</div>
          <div className="brand-copy">
            <strong>Agent 4 Job Console</strong>
            <span>Track every step live — from packaging to validation to push</span>
          </div>
        </div>

        <div className="topbar-actions">
          <Link className="link-button" href="/">
            New submission
          </Link>
        </div>
      </header>

      <section className="panel">
        <div className="job-toolbar">
          <div>
            <p className="section-kicker">Job Status</p>
            <h1>{jobId || "Loading..."}</h1>
            <p>Stay in sync with architecture insights, validation progress, and delivery results.</p>
          </div>

          <div className="pill-row">
            <span className="pill">
              <span className="status-dot" /> Live polling
            </span>
            <span className="pill">Refreshes every 3s</span>
          </div>
        </div>

        <div className="shell-divider" />

        <div className="status-layout" style={{ marginTop: "1rem" }}>
          <div className="status-card">
            <div className="status-banner">
              <div>
                <p className="status-heading">Delivery snapshot</p>
                <p className="status-copy">Current progress across the job lifecycle.</p>
              </div>
              <span className="status-pill">{payload?.state ?? "Waiting"}</span>
            </div>

            <div className="progress-track" aria-label="job progress">
              <div className="progress-bar" style={{ width: `${progressValue}%` }} />
            </div>

            <div className="status-metrics" style={{ marginTop: "1rem" }}>
              <div className="status-metric">
                <span>Architecture</span>
                <strong>{payload?.architecture ?? "—"}</strong>
              </div>
              <div className="status-metric">
                <span>Confidence</span>
                <strong>{payload ? `${Math.round(payload.confidence * 100)}%` : "—"}</strong>
              </div>
              <div className="status-metric">
                <span>Validation</span>
                <strong>
                  {payload ? `${validationSummary.passed}/${payload.validation.checks.length}` : "—"}
                </strong>
              </div>
            </div>

            {payload ? (
              <div style={{ marginTop: "1rem" }}>
                <p className="section-kicker">Strategy</p>
                <h2 className="section-title" style={{ fontSize: "1.4rem" }}>
                  {payload.strategy.deployment_profile}
                </h2>
                <p className="status-copy" style={{ marginTop: "0.45rem" }}>
                  The deployment profile is chosen from the detected architecture and validation outcome.
                </p>
              </div>
            ) : null}
          </div>

          <div className="status-card">
            <div className="status-banner">
              <div>
                <p className="status-heading">Execution log</p>
                <p className="status-copy">A compact view of the latest checks and repository actions.</p>
              </div>
              <span className={pushTone}>{pushState}</span>
            </div>

            {error ? (
              <div className="empty-state" style={{ marginBottom: "1rem" }}>
                <strong>Unable to load job</strong>
                <span>{error}</span>
              </div>
            ) : null}

            {payload ? (
              <ul className="status-list">
                {payload.validation.checks.map((check) => (
                  <li className="status-list-item" key={check.name}>
                    <span className={`badge ${check.success ? "badge-pass" : "badge-fail"}`}>
                      {check.success ? "PASS" : "FAIL"}
                    </span>
                    <div className="stacked-copy">
                      <strong>{check.name}</strong>
                      <span>{check.details}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <strong>Waiting for job data</strong>
                <span>The page is polling the backend and will populate automatically once the job exists.</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {payload ? (
        <>
          <section className="panel">
            <p className="section-kicker">Strategy notes</p>
            <h2 className="section-title" style={{ fontSize: "1.4rem" }}>
              What the package engine decided
            </h2>
            <ul className="feature-list" style={{ marginTop: "1rem" }}>
              {payload.strategy.notes.map((note) => (
                <li className="feature-item" key={note}>
                  <div className="feature-icon">•</div>
                  <div>
                    <strong>{note}</strong>
                    <p>Included in the generated execution plan and preserved with the job output.</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="section-grid">
            <div className="panel">
              <p className="section-kicker">GitHub push</p>
              <h2 className="section-title" style={{ fontSize: "1.4rem" }}>
                {payload.push_result.state}
              </h2>
              <p className="section-subtitle">{payload.push_result.message}</p>
              {payload.push_result.commit_sha ? (
                <div className="pill-row" style={{ marginTop: "0.9rem" }}>
                  <span className="pill mono">Commit {payload.push_result.commit_sha}</span>
                  {payload.push_result.branch ? <span className="pill">Branch {payload.push_result.branch}</span> : null}
                </div>
              ) : null}
            </div>

            <div className="panel">
              <p className="section-kicker">Artifacts</p>
              <h2 className="section-title" style={{ fontSize: "1.4rem" }}>
                Deliverables and evidence
              </h2>
              <div className="artifacts-row" style={{ margin: "1rem 0" }}>
                {payload.artifacts.map((artifact) => (
                  <span className="pill mono artifact-pill" key={artifact}>
                    {artifact}
                  </span>
                ))}
              </div>

              <div className="button-stack">
                {downloadUrl ? (
                  <a className="primary-button" href={downloadUrl}>
                    Download packaged ZIP
                  </a>
                ) : null}
                <Link className="secondary-button" href="/">
                  Create another job
                </Link>
              </div>

              <p className="section-subtitle evidence-line" style={{ marginTop: "1rem" }}>
                Evidence file: <span className="mono path-value">{payload.evidence_path}</span>
              </p>
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
