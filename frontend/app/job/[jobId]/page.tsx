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
  commit_preview?: {
    title: string;
    sections: Array<{
      id: string;
      title: string;
      tone: "pass" | "warn" | "fail";
      items: string[];
    }>;
  };
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
  const [expandedCheckpoint, setExpandedCheckpoint] = useState("detect");
  const [diffQuery, setDiffQuery] = useState("");
  const [copiedDiff, setCopiedDiff] = useState(false);

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

  const timeline = useMemo(() => {
    if (!payload) {
      return [] as Array<{
        id: string;
        title: string;
        state: "completed" | "active" | "failed" | "pending";
        summary: string;
        snapshot: string[];
      }>;
    }

    const validationFailed = payload.validation.checks.length > 0 && !payload.validation.success;
    const pushFailed = /fail|error|reject|auth_required/i.test(payload.push_result.state);
    const pushSucceeded = /pushed|success|done|complete/i.test(payload.push_result.state);
    const sanitizeFailed = /sensitive token patterns|blocked|secret/i.test(payload.push_result.message || "");

    return [
      {
        id: "detect",
        title: "Detect",
        state: "completed" as const,
        summary: "Architecture and strategy inference complete.",
        snapshot: [
          `Architecture: ${payload.architecture}`,
          `Confidence: ${Math.round(payload.confidence * 100)}%`,
          `Profile: ${payload.strategy.deployment_profile}`,
        ],
      },
      {
        id: "validate",
        title: "Validate",
        state: validationFailed ? ("failed" as const) : ("completed" as const),
        summary: validationFailed
          ? "Some validation checks failed."
          : "Validation checks are healthy.",
        snapshot: [
          `Checks passed: ${validationSummary.passed}`,
          `Checks failed: ${validationSummary.failed}`,
          `Validator result: ${payload.validation.success ? "PASS" : "FAIL"}`,
        ],
      },
      {
        id: "sanitize",
        title: "Sanitize",
        state: sanitizeFailed ? ("failed" as const) : ("completed" as const),
        summary: sanitizeFailed
          ? "Sanitization gate blocked sensitive content."
          : "Artifacts and secrets sanitization completed.",
        snapshot: [
          `Artifacts generated: ${payload.artifacts.length}`,
          `Evidence file ready: ${payload.evidence_path ? "Yes" : "No"}`,
          `Secret gate: ${sanitizeFailed ? "Blocked" : "Clear"}`,
        ],
      },
      {
        id: "push",
        title: "Push",
        state: pushFailed ? ("failed" as const) : pushSucceeded ? ("completed" as const) : ("pending" as const),
        summary: pushSucceeded
          ? "Repository update delivered successfully."
          : pushFailed
            ? "Push blocked or rejected."
            : "Push skipped or awaiting action.",
        snapshot: [
          `State: ${payload.push_result.state}`,
          `Branch: ${payload.push_result.branch || "—"}`,
          `Commit: ${payload.push_result.commit_sha || "—"}`,
        ],
      },
    ];
  }, [payload, validationSummary.failed, validationSummary.passed]);

  const smartDiffPreview = useMemo(() => {
    if (!payload) {
      return null;
    }

    if (payload.commit_preview) {
      return payload.commit_preview;
    }

    const workflowArtifacts = payload.artifacts.filter(
      (artifact) => artifact.startsWith(".github/workflows/") && artifact.endsWith((".yml")),
    );

    return {
      title: "What will be committed",
      sections: [
        {
          id: "generated-workflows",
          title: "Generated workflows",
          tone: "pass" as const,
          items: workflowArtifacts.length ? workflowArtifacts : ["No workflow artifacts detected yet."],
        },
      ],
    };
  }, [payload]);

  const smartDiffGridClass = useMemo(() => {
    const count = smartDiffPreview?.sections.length ?? 0;
    if (count <= 1) {
      return "commit-preview-grid cols-1";
    }
    if (count === 2) {
      return "commit-preview-grid cols-2";
    }
    return "commit-preview-grid cols-3";
  }, [smartDiffPreview]);

  const diffEntries = useMemo(() => {
    if (!smartDiffPreview) {
      return [] as Array<{
        sectionId: string;
        sectionTitle: string;
        sectionTone: "pass" | "warn" | "fail";
        text: string;
        kind: "generated" | "redacted" | "removed" | "note";
      }>;
    }

    return smartDiffPreview.sections.flatMap((section) =>
      section.items.map((item) => {
        const lower = item.toLowerCase();
        let kind: "generated" | "redacted" | "removed" | "note" = "note";

        if (section.id.includes("workflow") || lower.includes(".github/workflows/")) {
          kind = "generated";
        } else if (section.id.includes("redacted") || lower.includes("redacted")) {
          kind = "redacted";
        } else if (section.id.includes("removed") || lower.includes("removed")) {
          kind = "removed";
        }

        if (lower.includes("unavailable") || lower.includes("no ")) {
          kind = "note";
        }

        return {
          sectionId: section.id,
          sectionTitle: section.title,
          sectionTone: section.tone,
          text: item,
          kind,
        };
      }),
    );
  }, [smartDiffPreview]);

  const filteredDiffEntries = useMemo(() => {
    const query = diffQuery.trim().toLowerCase();
    if (!query) {
      return diffEntries;
    }
    return diffEntries.filter((entry) =>
      `${entry.sectionTitle} ${entry.text} ${entry.kind}`.toLowerCase().includes(query),
    );
  }, [diffEntries, diffQuery]);

  const diffStats = useMemo(() => {
    const generated = filteredDiffEntries.filter((entry) => entry.kind === "generated").length;
    const redacted = filteredDiffEntries.filter((entry) => entry.kind === "redacted").length;
    const removed = filteredDiffEntries.filter((entry) => entry.kind === "removed").length;
    const notes = filteredDiffEntries.filter((entry) => entry.kind === "note").length;
    return {
      total: filteredDiffEntries.length,
      generated,
      redacted,
      removed,
      notes,
    };
  }, [filteredDiffEntries]);

  async function copyVisibleDiff() {
    const text = filteredDiffEntries
      .map((entry) => `[${entry.sectionTitle}] ${entry.text}`)
      .join("\n");

    try {
      await navigator.clipboard.writeText(text || "No visible diff entries.");
      setCopiedDiff(true);
      window.setTimeout(() => setCopiedDiff(false), 1200);
    } catch {
      setCopiedDiff(false);
    }
  }

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
            <p className="section-kicker">Timeline Replay</p>
            <h2 className="section-title" style={{ fontSize: "1.4rem" }}>
              Cinematic Packaging Journey
            </h2>
            <p className="section-subtitle">Detect → Validate → Sanitize → Push with expandable checkpoints.</p>

            <div className="timeline-replay" style={{ marginTop: "1rem" }}>
              {timeline.map((checkpoint) => {
                const expanded = expandedCheckpoint === checkpoint.id;
                return (
                  <article
                    key={checkpoint.id}
                    className={`timeline-step timeline-${checkpoint.state} ${expanded ? "is-expanded" : ""}`}
                  >
                    <button
                      type="button"
                      className="timeline-head"
                      onClick={() => setExpandedCheckpoint(expanded ? "" : checkpoint.id)}
                    >
                      <span className="timeline-dot" aria-hidden="true" />
                      <span className="timeline-title-wrap">
                        <strong>{checkpoint.title}</strong>
                        <span>{checkpoint.summary}</span>
                      </span>
                      <span className={`badge ${checkpoint.state === "completed" ? "badge-pass" : checkpoint.state === "failed" ? "badge-fail" : "badge-warn"}`}>
                        {checkpoint.state.toUpperCase()}
                      </span>
                    </button>

                    {expanded ? (
                      <div className="timeline-body">
                        <div className="timeline-snapshot">
                          {checkpoint.snapshot.map((item) => (
                            <span className="pill" key={`${checkpoint.id}-${item}`}>
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </section>

          {smartDiffPreview ? (
            <section className="panel">
              <p className="section-kicker">Smart Diff Preview</p>
              <h2 className="section-title" style={{ fontSize: "1.4rem" }}>
                {smartDiffPreview.title}
              </h2>
              <p className="section-subtitle">See what will be committed before the push is made.</p>

              <div className="diff-toolbar" style={{ marginTop: "1rem" }}>
                <label className="diff-search" htmlFor="diff-search-input">
                  <span>Search changes</span>
                  <input
                    id="diff-search-input"
                    value={diffQuery}
                    onChange={(event) => setDiffQuery(event.target.value)}
                    placeholder="Filter by file, section, or change type"
                  />
                </label>
                <button type="button" className="secondary-button" onClick={copyVisibleDiff}>
                  {copiedDiff ? "Copied" : "Copy visible diff"}
                </button>
              </div>

              <div className="diff-metrics" style={{ marginTop: "0.85rem" }}>
                <span className="pill">Total {diffStats.total}</span>
                <span className="pill">Generated {diffStats.generated}</span>
                <span className="pill">Redacted {diffStats.redacted}</span>
                <span className="pill">Removed {diffStats.removed}</span>
                {diffStats.notes ? <span className="pill">Notes {diffStats.notes}</span> : null}
              </div>

              <div className={smartDiffGridClass} style={{ marginTop: "1rem" }}>
                {smartDiffPreview.sections.map((section) => (
                  <article className={`commit-preview-card tone-${section.tone}`} key={section.id}>
                    <div className="commit-preview-head">
                      <strong>{section.title}</strong>
                      <span className={`badge badge-${section.tone}`}>{section.tone.toUpperCase()}</span>
                    </div>
                    {section.items.length ? (
                      <div className="commit-preview-items">
                        {section.items.map((item) => (
                          <span className="pill mono commit-preview-pill" key={`${section.id}-${item}`}>
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="empty-state" style={{ padding: "0.8rem" }}>
                        <strong>None detected</strong>
                        <span>No entries in this category for the current package.</span>
                      </div>
                    )}
                  </article>
                ))}
              </div>

              <div className="diff-console" style={{ marginTop: "1rem" }}>
                {filteredDiffEntries.length ? (
                  <ul className="diff-list">
                    {filteredDiffEntries.map((entry) => (
                      <li className={`diff-row diff-${entry.kind}`} key={`${entry.sectionId}-${entry.text}`}>
                        <span className="diff-mark" aria-hidden="true">
                          {entry.kind === "generated" ? "+" : entry.kind === "removed" ? "-" : entry.kind === "redacted" ? "~" : "·"}
                        </span>
                        <span className="diff-path mono">{entry.text}</span>
                        <span className={`badge ${entry.sectionTone === "pass" ? "badge-pass" : entry.sectionTone === "fail" ? "badge-fail" : "badge-warn"}`}>
                          {entry.sectionTitle}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="empty-state" style={{ padding: "0.8rem" }}>
                    <strong>No matching changes</strong>
                    <span>Adjust your search query to inspect other diff entries.</span>
                  </div>
                )}
              </div>
            </section>
          ) : null}

          <section className="section-grid">
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
