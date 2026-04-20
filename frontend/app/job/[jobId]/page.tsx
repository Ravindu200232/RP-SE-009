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
  const [artifactQuery, setArtifactQuery] = useState("");
  const [copiedArtifacts, setCopiedArtifacts] = useState(false);

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


  const artifactEntries = useMemo(() => {
    if (!payload) {
      return [] as Array<{
        path: string;
        kind: "workflow" | "container" | "api" | "evidence" | "script" | "source";
        label: string;
      }>;
    }

    return payload.artifacts.map((artifact) => {
      const lower = artifact.toLowerCase();

      if (lower.startsWith(".github/workflows/")) {
        return { path: artifact, kind: "workflow" as const, label: "Workflow" };
      }
      if (lower.includes("docker") || lower.includes("compose")) {
        return { path: artifact, kind: "container" as const, label: "Container" };
      }
      if (lower.includes("postman") || lower.endsWith(".http")) {
        return { path: artifact, kind: "api" as const, label: "API" };
      }
      if (
        lower.includes("evidence") ||
        lower.includes("analysis") ||
        lower.endsWith("strategy.json") ||
        lower.endsWith("result.json")
      ) {
        return { path: artifact, kind: "evidence" as const, label: "Evidence" };
      }
      if (lower.endsWith(".sh") || lower.endsWith("readme.md") || lower.endsWith(".md")) {
        return { path: artifact, kind: "script" as const, label: "Docs/Script" };
      }

      return { path: artifact, kind: "source" as const, label: "Source" };
    });
  }, [payload]);

  const filteredArtifactEntries = useMemo(() => {
    const query = artifactQuery.trim().toLowerCase();
    if (!query) {
      return artifactEntries;
    }

    return artifactEntries.filter((entry) => `${entry.path} ${entry.label} ${entry.kind}`.toLowerCase().includes(query));
  }, [artifactEntries, artifactQuery]);

  const visibleArtifactEntries = useMemo(
    () => filteredArtifactEntries.filter((entry) => entry.kind !== "workflow" && entry.kind !== "container"),
    [filteredArtifactEntries],
  );

  const artifactStats = useMemo(() => {
    const api = visibleArtifactEntries.filter((entry) => entry.kind === "api").length;
    const evidence = visibleArtifactEntries.filter((entry) => entry.kind === "evidence").length;
    const docs = visibleArtifactEntries.filter((entry) => entry.kind === "script").length;
    const source = visibleArtifactEntries.filter((entry) => entry.kind === "source").length;

    return {
      total: visibleArtifactEntries.length,
      api,
      evidence,
      docs,
      source,
    };
  }, [visibleArtifactEntries]);

  const artifactBuckets = useMemo(() => {
    const byKind: Record<string, { title: string; tone: "pass" | "warn" | "fail"; items: string[] }> = {
      api: { title: "API collections", tone: "warn", items: [] },
      evidence: { title: "Evidence and analysis", tone: "warn", items: [] },
      script: { title: "Scripts and docs", tone: "warn", items: [] },
      source: { title: "Source artifacts", tone: "pass", items: [] },
    };

    visibleArtifactEntries.forEach((entry) => {
      byKind[entry.kind].items.push(entry.path);
    });

    return Object.entries(byKind)
      .filter(([, bucket]) => bucket.items.length > 0)
      .map(([id, bucket]) => ({ id, ...bucket }));
  }, [visibleArtifactEntries]);

  async function copyVisibleArtifacts() {
    const text = visibleArtifactEntries.map((entry) => entry.path).join("\n");

    try {
      await navigator.clipboard.writeText(text || "No visible artifacts.");
      setCopiedArtifacts(true);
      window.setTimeout(() => setCopiedArtifacts(false), 1200);
    } catch {
      setCopiedArtifacts(false);
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

        <div className="status-layout status-layout-full" style={{ marginTop: "1rem" }}>
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

          <section className="panel">
              <div className="panel-title-row">
                <div>
                  <p className="section-kicker">Artifacts</p>
                  <h2 className="section-title" style={{ fontSize: "1.4rem" }}>
                    What will be packaged
                  </h2>
                  <p className="section-subtitle">
                    Review generated deliverables before download and push.
                  </p>
                </div>

                {downloadUrl ? (
                  <a className="primary-button download-cta" href={downloadUrl}>
                    Download packaged ZIP
                  </a>
                ) : null}
              </div>

              <div className="diff-toolbar" style={{ marginTop: "1rem" }}>
                <label className="artifact-search" htmlFor="artifact-search-input">
                  <span>Filter artifacts</span>
                  <input
                    id="artifact-search-input"
                    value={artifactQuery}
                    onChange={(event) => setArtifactQuery(event.target.value)}
                    placeholder="Search by path, type, or filename"
                  />
                </label>
                <button type="button" className="secondary-button" onClick={copyVisibleArtifacts}>
                  {copiedArtifacts ? "Copied" : "Copy visible artifacts"}
                </button>
              </div>

              <div className="diff-metrics" style={{ marginTop: "0.85rem" }}>
                <span className="pill">Total {artifactStats.total}</span>
                <span className="pill">API {artifactStats.api}</span>
                <span className="pill">Evidence {artifactStats.evidence}</span>
                <span className="pill">Docs {artifactStats.docs}</span>
                <span className="pill">Source {artifactStats.source}</span>
              </div>

              <div className="artifact-landscape-lane" style={{ marginTop: "1rem" }}>
                {artifactBuckets.length ? (
                  artifactBuckets.map((bucket) => (
                    <article className={`commit-preview-card tone-${bucket.tone}`} key={bucket.id}>
                      <div className="commit-preview-head">
                        <strong>{bucket.title}</strong>
                        <span className={`badge badge-${bucket.tone}`}>{bucket.tone.toUpperCase()}</span>
                      </div>
                      <div className="commit-preview-items">
                        {bucket.items.map((item) => (
                          <span className="pill mono commit-preview-pill" key={`${bucket.id}-${item}`}>
                            {item}
                          </span>
                        ))}
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="empty-state" style={{ padding: "0.85rem" }}>
                    <strong>No matching artifacts</strong>
                    <span>Try a different keyword to locate a generated file.</span>
                  </div>
                )}
              </div>

              <p className="section-subtitle evidence-line" style={{ marginTop: "1rem" }}>
                Evidence file: <span className="mono path-value">{payload.evidence_path}</span>
              </p>
          </section>
        </>
      ) : null}
    </main>
  );
}
