"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_AGENT4_API_BASE_URL ?? "http://localhost:8004";

const initialForm = {
  job_id: "",
  source_path: "",
  review_report_path: "",
  srs_path: "",
  docker_enabled: true,
  github_push_enabled: false,
  github_repo_url: "",
  github_branch: "main",
  commit_message: "Add packaged deployment output",
};

export default function HomePage() {
  const router = useRouter();
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch(`${apiBase}/package`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Packaging request failed.");
      }

      router.push(`/job/${payload.job_id}`);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Packaging request failed.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="panel hero">
        <p className="eyebrow">Agent 4</p>
        <h1>Deployment packaging with Docker and optional GitHub push</h1>
        <p className="lede">
          Submit Agent 3 approved output, choose whether Docker deployment artifacts should be
          generated and validated, and optionally push the packaged result to an existing GitHub
          repository after validation succeeds.
        </p>
      </section>

      <section className="panel">
        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            <span>Job ID</span>
            <input
              value={form.job_id}
              onChange={(event) => setForm({ ...form, job_id: event.target.value })}
              placeholder="optional-job-id"
            />
          </label>

          <label>
            <span>Source Path</span>
            <input
              required
              value={form.source_path}
              onChange={(event) => setForm({ ...form, source_path: event.target.value })}
              placeholder="/absolute/path/to/agent3/output"
            />
          </label>

          <label>
            <span>Review Report Path</span>
            <input
              required
              value={form.review_report_path}
              onChange={(event) => setForm({ ...form, review_report_path: event.target.value })}
              placeholder="/absolute/path/to/review_report.json"
            />
          </label>

          <label>
            <span>SRS Path</span>
            <input
              required
              value={form.srs_path}
              onChange={(event) => setForm({ ...form, srs_path: event.target.value })}
              placeholder="/absolute/path/to/srs.json"
            />
          </label>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.docker_enabled}
              onChange={(event) => setForm({ ...form, docker_enabled: event.target.checked })}
            />
            <span>Prepare Docker deployment</span>
          </label>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.github_push_enabled}
              onChange={(event) => setForm({ ...form, github_push_enabled: event.target.checked })}
            />
            <span>Push packaged result to GitHub</span>
          </label>

          <label>
            <span>GitHub Repository URL</span>
            <input
              value={form.github_repo_url}
              onChange={(event) => setForm({ ...form, github_repo_url: event.target.value })}
              placeholder="git@github.com:owner/repo.git"
              disabled={!form.github_push_enabled}
            />
          </label>

          <label>
            <span>GitHub Branch</span>
            <input
              value={form.github_branch}
              onChange={(event) => setForm({ ...form, github_branch: event.target.value })}
              disabled={!form.github_push_enabled}
            />
          </label>

          <label className="full-span">
            <span>Commit Message</span>
            <input
              value={form.commit_message}
              onChange={(event) => setForm({ ...form, commit_message: event.target.value })}
              disabled={!form.github_push_enabled}
            />
          </label>

          <div className="full-span action-row">
            <button type="submit" disabled={submitting}>
              {submitting ? "Packaging..." : "Start Packaging"}
            </button>
          </div>

          {error ? <p className="error-text full-span">{error}</p> : null}
        </form>
      </section>
    </main>
  );
}

