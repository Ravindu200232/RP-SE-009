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

  return (
    <main className="page-shell">
      <section className="panel">
        <p className="eyebrow">Job Status</p>
        <h1>{jobId || "Loading..."}</h1>
        <p className="lede">Track architecture detection, validation, and optional GitHub push results.</p>
        <p>
          <Link href="/">Back to input form</Link>
        </p>
      </section>

      {error ? (
        <section className="panel">
          <p className="error-text">{error}</p>
        </section>
      ) : null}

      {payload ? (
        <>
          <section className="panel metrics">
            <article>
              <h2>State</h2>
              <p>{payload.state}</p>
            </article>
            <article>
              <h2>Architecture</h2>
              <p>{payload.architecture}</p>
            </article>
            <article>
              <h2>Confidence</h2>
              <p>{payload.confidence}</p>
            </article>
          </section>

          <section className="panel">
            <h2>Strategy</h2>
            <p>{payload.strategy.deployment_profile}</p>
            <ul>
              {payload.strategy.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>Validation</h2>
            <ul>
              {payload.validation.checks.map((check) => (
                <li key={check.name}>
                  <strong>{check.success ? "PASS" : "FAIL"}</strong> {check.name}: {check.details}
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>GitHub Push</h2>
            <p>{payload.push_result.state}</p>
            <p>{payload.push_result.message}</p>
            {payload.push_result.commit_sha ? <p>Commit: {payload.push_result.commit_sha}</p> : null}
          </section>

          <section className="panel">
            <h2>Artifacts</h2>
            <ul>
              {payload.artifacts.map((artifact) => (
                <li key={artifact}>{artifact}</li>
              ))}
            </ul>
            {downloadUrl ? (
              <p>
                <a href={downloadUrl}>Download packaged ZIP</a>
              </p>
            ) : null}
            <p>Evidence file: {payload.evidence_path}</p>
          </section>
        </>
      ) : null}
    </main>
  );
}
