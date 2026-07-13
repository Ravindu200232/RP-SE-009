"use client";

import { useEffect, useMemo, useState } from "react";

type TabId =
    | "overview"
    | "pipeline"
    | "github"
    | "cicd"
    | "containers"
    | "aws"
    | "ecr"
    | "iam"
    | "logs"
    | "api"
    | "evidence";

type DevOpsCenterPrototypeProps = {
    jobId?: string;
    showIntroOverlay?: boolean;
};

type SidebarItem = { label: string; active?: boolean };
type AccessRequest = { title: string; host: string; description: string; scopes: string[] };
type Tab = { id: TabId; label: string };
type InputCandidate = {
    id: string;
    display_name: string;
    source_path: string;
    ready?: boolean;
    missing?: string[];
    updated_at?: string;
};

type JobValidationCheck = { name: string; success: boolean; details: string };
type JobSnapshot = {
    job_id: string;
    state: string;
    architecture: string;
    confidence: number;
    download_path?: string;
    package_dir?: string;
    evidence_path?: string;
    message?: string;
    artifacts?: string[];
    commit_preview?: Record<string, unknown>;
    validation?: { success: boolean; checks: JobValidationCheck[] };
    push_result?: { state: string; message: string; branch?: string; commit_sha?: string };
    strategy?: { deployment_profile?: string; packaging_supported?: boolean; release_strategy?: string; monitoring?: string[]; notes?: string[] };
};

const API_BASE = (process.env.NEXT_PUBLIC_AGENT4_API_BASE_URL || "http://127.0.0.1:8004").replace(/\/$/, "");

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
            "Content-Type": "application/json",
            ...(init?.headers || {}),
        },
    });

    if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Request failed with status ${response.status}`);
    }

    return response.json() as Promise<T>;
}

const sidebarItems: SidebarItem[] = [
    { label: "Dashboard" },
    { label: "New Project" },
    { label: "Analyser" },
    { label: "Design Selector" },
    { label: "Builder Studio" },
    { label: "QA Center" },
    { label: "DevOps Center", active: true },
    { label: "Artifacts & Exports" },
    { label: "Versions & Releases" },
    { label: "Memory & Logs" },
    { label: "LLM Model Ranking" },
    { label: "Project History" },
    { label: "Settings" },
];

const tabs: Tab[] = [
    { id: "overview", label: "Overview" },
    { id: "pipeline", label: "Pipeline" },
    { id: "github", label: "GitHub Repository" },
    { id: "cicd", label: "CI/CD" },
    { id: "containers", label: "Containers" },
    { id: "aws", label: "AWS ECS" },
    { id: "ecr", label: "ECR Images" },
    { id: "iam", label: "IAM & Security" },
    { id: "logs", label: "CloudWatch Logs" },
    { id: "api", label: "API Validation" },
    { id: "evidence", label: "Evidence" },
];

const accessRequests: AccessRequest[] = [
    {
        title: "Connect GitHub CLI",
        host: "github.com/login/device",
        description: "Authorize Agent 4 to push code, open PRs, and trigger GitHub Actions workflows on your behalf.",
        scopes: ["repo — read & write to repositories", "workflow — trigger CI/CD pipelines", "read:org — read organization data"],
    },
    {
        title: "Connect Snyk",
        host: "app.snyk.io/oauth/authorize",
        description: "Allow vulnerability scanning of dependencies, container images, and infrastructure-as-code.",
        scopes: ["scan:dependencies — Open Source / SCA", "scan:containers — image vulnerabilities", "scan:iac — Terraform / CloudFormation"],
    },
    {
        title: "Connect SonarCloud",
        host: "sonarcloud.io/account/security",
        description: "Run static analysis on every push — bugs, vulnerabilities, code smells, and coverage.",
        scopes: ["projects:write — create & analyze projects", "metrics:read — read quality gates", "issues:write — auto-resolve issues"],
    },
    {
        title: "Connect AWS",
        host: "console.aws.amazon.com/",
        description: "Provision ECS services, ECR images, and CloudWatch resources for deployment.",
        scopes: ["ecs:write — deploy services", "ecr:write — publish images", "logs:read — inspect CloudWatch logs"],
    },
    {
        title: "Connect Vercel",
        host: "vercel.com/oauth/authorize",
        description: "Authorize preview & production deployments for the client frontend on the Vercel edge network.",
        scopes: ["deployments:write — trigger builds", "project:read — read project config", "domains:read — verify custom domains"],
    },
];

const overviewCards = [
    { label: "Production Status", value: "Live", tone: "pass", note: "All services deployed." },
    { label: "ECS Services", value: "6 / 6", tone: "pass", note: "All microservices on Fargate." },
    { label: "CI/CD Workflows", value: "7", tone: "warn", note: "GitHub Actions workflows are green." },
    { label: "API Validation", value: "4 / 4", tone: "pass", note: "Live endpoints returned HTTP 200." },
    { label: "Security Gate", value: "Passed", tone: "pass", note: "Static analysis and IAM checks complete." },
    { label: "Evidence Report", value: "Ready", tone: "warn", note: "Screenshots and proof collected." },
];

const pipelineSteps = [
    ["Project intake", "Validate source path and enumerate files.", "1.2s"],
    ["Agent 3 report parsing", "Link previous QA/test reports.", "0.8s"],
    ["Service discovery", "Discover frontend, backend services, workflows, and AWS templates.", "3.4s"],
    ["Docker audit", "Inspect Dockerfiles and container hardening.", "4.1s"],
    ["Docker generation", "Generate improved Docker assets.", "5.6s"],
    ["Compose validation/generation", "Generate docker-compose.yml.", "2.3s"],
    ["Workflow generation", "Generate GitHub Actions workflows.", "3.8s"],
    ["Environment template generation", "Assemble .env.example and secret requirements.", "1.1s"],
    ["AWS template generation", "Generate ECS task definitions and service configs.", "6.2s"],
    ["Deployment gate evaluation", "Compute blockers, warnings, and readiness score.", "2.0s"],
    ["Cloud deployment", "Push images to ECR and deploy ECS services.", "14.3s"],
    ["API validation", "Test live endpoints using public IP.", "3.1s"],
    ["Evidence collection", "Collect GitHub, AWS, Postman, and Swagger screenshots.", "8.7s"],
    ["Docs generation", "Write deployment report and README.", "2.5s"],
    ["Final packaging", "Store generated artifacts and reports.", "1.8s"],
];

const repoChecklist = [
    ".github/workflows exists",
    ".aws folder exists",
    "client folder exists",
    "server folder exists",
    "docker-compose.yml exists",
    ".env.example exists",
    "README.md exists",
];

const workflowRows = [
    ["client.yml", "push main", "Success", "1m 10s", "N/A", "Success", "Success", "2 hrs ago"],
    ["user-service.yml", "push main", "Success", "1m 16s", "Snyk Passed", "ECR Pushed", "ECS Updated", "2 hrs ago"],
    ["restaurant-service.yml", "push main", "Success", "1m 33s", "Snyk Passed", "ECR Pushed", "ECS Updated", "2 hrs ago"],
    ["order-service.yml", "push main", "Success", "1m 29s", "Snyk Passed", "ECR Pushed", "ECS Updated", "2 hrs ago"],
    ["payment-service.yml", "push main", "Success", "1m 22s", "Snyk Passed", "ECR Pushed", "ECS Updated", "2 hrs ago"],
    ["delivery-service.yml", "push main", "Success", "1m 25s", "Snyk Passed", "ECR Pushed", "ECS Updated", "2 hrs ago"],
    ["notification-service.yml", "push main", "Success", "1m 22s", "Snyk Passed", "ECR Pushed", "ECS Updated", "2 hrs ago"],
];

const containerAudit = [
    "Dockerfile exists for all services",
    ".dockerignore exists",
    "Environment variables separated (.env)",
    "Ports mapped correctly",
    "Healthcheck configured",
    "Image names follow ECR naming",
    "Non-root user missing in 2 services",
    "Image size optimization recommended",
];

const ecsServices = [
    ["delivery-service", "1", "1", "Active", "delivery-service-task:8", "Success", "food-ordering-sg"],
    ["notification-service", "1", "1", "Active", "notification-service-task:8", "Success", "food-ordering-sg"],
    ["order-service", "1", "1", "Active", "order-service-task:8", "Success", "food-ordering-sg"],
    ["payment-service", "1", "1", "Active", "payment-service-task:8", "Success", "food-ordering-sg"],
    ["restaurant-service", "1", "1", "Active", "restaurant-service-task:8", "Success", "food-ordering-sg"],
    ["user-service", "1", "1", "Active", "user-service-task:8", "Success", "food-ordering-sg"],
];

const ecrRepos = [
    ["food-ordering/user-service", "latest", "AES-256", "Apr 24, 2026", "Success"],
    ["food-ordering/restaurant-service", "latest", "AES-256", "Apr 24, 2026", "Success"],
    ["food-ordering/order-service", "latest", "AES-256", "Apr 24, 2026", "Success"],
    ["food-ordering/payment-service", "latest", "AES-256", "Apr 24, 2026", "Success"],
    ["food-ordering/delivery-service", "latest", "AES-256", "Apr 24, 2026", "Success"],
    ["food-ordering/notification-service", "latest", "AES-256", "Apr 24, 2026", "Success"],
];

const securityRules = [
    ["3000", "frontend/client", "TCP"],
    ["3001", "user-service", "TCP"],
    ["3002", "restaurant-service", "TCP"],
    ["3003", "order-service", "TCP"],
    ["3004", "payment-service", "TCP"],
    ["3005", "delivery-service", "TCP"],
    ["3006", "notification-service", "TCP"],
];

const securityChecklist = [
    "No AWS keys committed to repository",
    ".env.example generated (no real values)",
    "GitHub Secrets used for credentials",
    "Bearer token API validation used",
    "Snyk security scan passed",
    "IAM role ecsTaskExecutionRole exists",
    "Security group should restrict source in production",
    "Public IP should use Load Balancer in production",
];

const cloudwatchLogs = [
    ["/ecs/food-ordering/user-service", "Server started on port 3001"],
    ["/ecs/food-ordering/restaurant-service", "MongoDB connection established"],
    ["/ecs/food-ordering/order-service", "Order API ready"],
    ["/ecs/food-ordering/payment-service", "Payment service connected"],
    ["/ecs/food-ordering/delivery-service", "Driver API ready"],
    ["/ecs/food-ordering/notification-service", "Notification service started"],
];

const apiValidationRows = [
    ["Driver API", "GET", "http://PUBLIC_IP:3005/api/v1/driver", "Bearer", "200 OK", "537ms", "Passed"],
    ["Orders API", "GET", "http://PUBLIC_IP:3003/api/v1/orders", "Bearer", "200 OK", "647ms", "Passed"],
    ["Payment API", "GET", "http://PUBLIC_IP:3004/api/payment", "Bearer", "200 OK", "518ms", "Passed"],
    ["Restaurant API", "GET", "http://PUBLIC_IP:3002/api/v1/restaurant", "Bearer", "200 OK", "606ms", "Passed"],
    ["Swagger Docs", "GET", "http://PUBLIC_IP:3000/api-docs", "Public", "200 OK", "300ms", "Passed"],
];

const evidenceCards = [
    ["ECS Cluster showing all 6 services Active", "Figure 1: ECS Cluster food-ordering-cluster with all services Active."],
    ["Each service showing 1/1 tasks running", "Figure 2: ECS service detail showing 1 desired, 1 running task."],
    ["Task detail — Public IP + Security Group", "Figure 3: Task networking showing public IP and security group."],
    ["Task network — Public IP + Subnet", "Figure 4: Task network section showing public IP and subnet."],
];

const statusPills = ["Deployment Complete — v1.0.0 is live", "Readiness: 92 / 100", "Services Active: 6 / 6", "Workflows: 7 successful", "Region: eu-north-1", "Cluster: food-ordering-cluster"];

function MetricCard({ label, value, note, tone }: { label: string; value: string; note: string; tone: string }) {
    return (
        <article className="studio-metric-card">
            <div className={`studio-metric-icon studio-metric-${tone}`}>{label.slice(0, 2)}</div>
            <div>
                <p className="studio-metric-label">{label}</p>
                <strong className="studio-metric-value">{value}</strong>
                <span className="studio-metric-note">{note}</span>
            </div>
        </article>
    );
}

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
    return (
        <div>
            <p className="section-kicker">Agent 4</p>
            <h2 className="section-title">{title}</h2>
            <p className="section-subtitle">{subtitle}</p>
        </div>
    );
}

export default function DevOpsCenterPrototype({ jobId, showIntroOverlay = false }: DevOpsCenterPrototypeProps) {
    const [activeTab, setActiveTab] = useState<TabId>("overview");
    const [introVisible, setIntroVisible] = useState(showIntroOverlay);
    const [inputCandidates, setInputCandidates] = useState<InputCandidate[]>([]);
    const [selectedSourcePath, setSelectedSourcePath] = useState("");
    const [dockerEnabled, setDockerEnabled] = useState(true);
    const [githubPushEnabled, setGithubPushEnabled] = useState(false);
    const [githubRepoUrl, setGithubRepoUrl] = useState("");
    const [githubBranch, setGithubBranch] = useState("main");
    const [commitMessage, setCommitMessage] = useState("Add packaged deployment output");
    const [loadingInputs, setLoadingInputs] = useState(false);
    const [runnerError, setRunnerError] = useState("");
    const [runnerMessage, setRunnerMessage] = useState("");
    const [runnerJob, setRunnerJob] = useState<JobSnapshot | null>(null);
    const [jobDetails, setJobDetails] = useState<JobSnapshot | null>(null);
    const [jobDetailsError, setJobDetailsError] = useState("");
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        let cancelled = false;

        async function loadInputs() {
            setLoadingInputs(true);
            setRunnerError("");
            try {
                const payload = await fetchJson<{ root: string; items: InputCandidate[] }>("/inputs");
                if (cancelled) {
                    return;
                }

                setInputCandidates(payload.items || []);
                setSelectedSourcePath((current) => current || payload.items?.[0]?.source_path || "");
            } catch (error) {
                if (!cancelled) {
                    setRunnerError(error instanceof Error ? error.message : "Failed to load input candidates.");
                }
            } finally {
                if (!cancelled) {
                    setLoadingInputs(false);
                }
            }
        }

        loadInputs();

        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        const currentJobId = jobId ?? "";

        if (!currentJobId) {
            setJobDetails(null);
            setJobDetailsError("");
            return;
        }

        let cancelled = false;

        async function loadJob() {
            setJobDetailsError("");
            try {
                const payload = await fetchJson<JobSnapshot>(`/jobs/${encodeURIComponent(currentJobId)}`);
                if (!cancelled) {
                    setJobDetails(payload);
                }
            } catch (error) {
                if (!cancelled) {
                    setJobDetails(null);
                    setJobDetailsError(error instanceof Error ? error.message : "Failed to load job details.");
                }
            }
        }

        loadJob();

        return () => {
            cancelled = true;
        };
    }, [jobId]);

    const liveJob = runnerJob || jobDetails;

    const downloadUrl = liveJob?.download_path ? `${API_BASE}${liveJob.download_path}` : "";

    async function handleRunPackage(options?: { githubPushEnabled?: boolean; sourcePath?: string; afterTab?: TabId }) {
        const sourcePath = options?.sourcePath || selectedSourcePath;
        const shouldPushToGithub = options?.githubPushEnabled ?? githubPushEnabled;

        if (!sourcePath) {
            setRunnerError("Select a source folder before running packaging.");
            return;
        }

        setSubmitting(true);
        setRunnerError("");
        setRunnerMessage("");

        try {
            const payload = await fetchJson<JobSnapshot>("/package", {
                method: "POST",
                body: JSON.stringify({
                    source_path: sourcePath,
                    job_id: crypto.randomUUID ? crypto.randomUUID().replace(/-/g, "") : `${Date.now()}`,
                    docker_enabled: dockerEnabled,
                    github_push_enabled: shouldPushToGithub,
                    github_repo_url: githubRepoUrl,
                    github_branch: githubBranch,
                    commit_message: commitMessage,
                }),
            });

            setRunnerJob(payload);
            setRunnerMessage(payload.message || "Packaging completed.");
            setActiveTab(options?.afterTab || "evidence");
        } catch (error) {
            setRunnerError(error instanceof Error ? error.message : "Packaging failed.");
        } finally {
            setSubmitting(false);
        }
    }

    function handleLoadLatestJob() {
        if (jobDetails) {
            setRunnerJob(jobDetails);
            setRunnerMessage(jobDetails.message || "Loaded job details.");
            setActiveTab("overview");
        }
    }

    async function handleCopyGithubRemote() {
        const remote = githubRepoUrl || "git@github.com:owner/repo.git";

        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(remote);
            }
            setRunnerMessage(`Copied GitHub remote: ${remote}`);
        } catch {
            setRunnerError("Unable to copy the GitHub remote in this browser session.");
        }
    }

    function handleEnableGithubAccess() {
        setIntroVisible(false);
        setGithubPushEnabled(true);
        if (!selectedSourcePath && inputCandidates[0]?.source_path) {
            setSelectedSourcePath(inputCandidates[0].source_path);
        }
        setRunnerMessage("GitHub access granted. GitHub push is enabled in the package runner.");
        setActiveTab("github");
    }

    function handleDeclineGithubAccess() {
        setIntroVisible(false);
        setGithubPushEnabled(false);
        setRunnerMessage("GitHub access skipped. Push actions remain available from the GitHub tab.");
    }

    const jobLabel = jobId ? `Job ${jobId}` : "Prototype Job";

    const tabPanels = useMemo(() => {
        switch (activeTab) {
            case "pipeline":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <SectionHeader title="Deployment Pipeline" subtitle="15-step automated DevOps pipeline — all steps completed." />
                            <div className="timeline-replay studio-timeline" style={{ marginTop: "1rem" }}>
                                {pipelineSteps.map(([title, summary, duration], index) => (
                                    <article key={title} className="timeline-step timeline-completed">
                                        <button type="button" className="timeline-head" disabled>
                                            <span className="timeline-dot" aria-hidden="true" />
                                            <span className="timeline-title-wrap">
                                                <strong>#{index + 1} {title}</strong>
                                                <span>{summary}</span>
                                            </span>
                                            <span className="badge badge-pass">{duration}</span>
                                        </button>
                                    </article>
                                ))}
                            </div>
                        </section>

                        <aside className="panel studio-panel">
                            <SectionHeader title="Pipeline Summary" subtitle="High-level delivery status." />
                            <div className="studio-summary-stack" style={{ marginTop: "1rem" }}>
                                <div className="studio-summary-card"><span>Total Steps</span><strong>15</strong></div>
                                <div className="studio-summary-card"><span>Completed</span><strong>14</strong></div>
                                <div className="studio-summary-card"><span>Warnings</span><strong>1</strong></div>
                                <div className="studio-summary-card"><span>Failures</span><strong>0</strong></div>
                                <div className="studio-summary-card"><span>Total Duration</span><strong>1m 02s</strong></div>
                            </div>

                            <div className="commit-preview-card tone-pass" style={{ marginTop: "1rem" }}>
                                <div className="commit-preview-head">
                                    <strong>Key Artifacts Generated</strong>
                                    <span className="badge badge-pass">READY</span>
                                </div>
                                <div className="commit-preview-items">
                                    {["docker-compose.yml", ".env.example", ".github/workflows/ (7)", "ECS task defs (6)", "deployment-report.md", "readiness-score.json"].map((item) => (
                                        <span key={item} className="pill mono commit-preview-pill">{item}</span>
                                    ))}
                                </div>
                            </div>
                        </aside>
                    </div>
                );
            case "github":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <SectionHeader title="GitHub Repository" subtitle="Repository checklist and deployment file structure." />
                            <div className="studio-checklist" style={{ marginTop: "1rem" }}>
                                {repoChecklist.map((item) => (
                                    <div className="studio-check-item" key={item}>
                                        <span className="badge badge-pass">✓</span>
                                        <span>{item}</span>
                                    </div>
                                ))}
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <SectionHeader title="Repository Stats" subtitle="Summary of repository contents." />
                            <div className="studio-summary-stack" style={{ marginTop: "1rem" }}>
                                <div className="studio-summary-card"><span>Workflows</span><strong>7</strong></div>
                                <div className="studio-summary-card"><span>AWS Configs</span><strong>6</strong></div>
                                <div className="studio-summary-card"><span>Services</span><strong>6</strong></div>
                                <div className="studio-summary-card"><span>Branches</span><strong>main</strong></div>
                                <div className="studio-summary-card"><span>Last Push</span><strong>2 hrs ago</strong></div>
                            </div>

                            <div className="code-view" style={{ marginTop: "1rem" }}>
                                <pre>{`/.github/workflows/
  client.yml
  user-service.yml
  restaurant-service.yml
  order-service.yml
  payment-service.yml
  delivery-service.yml
  notification-service.yml

/aws/
  user-service-task-definition.json
  restaurant-service-task-definition.json
  order-service-task-definition.json
  payment-service-task-definition.json`}</pre>
                            </div>
                        </aside>
                    </div>
                );
            case "cicd":
                return (
                    <section className="panel studio-panel">
                        <SectionHeader title="GitHub Actions Workflows" subtitle="7 workflows - all passing - push to main." />
                        <div className="studio-table-wrap" style={{ marginTop: "1rem" }}>
                            <table className="studio-table">
                                <thead>
                                    <tr>
                                        <th>Workflow</th>
                                        <th>Trigger</th>
                                        <th>Status</th>
                                        <th>Duration</th>
                                        <th>Security Scan</th>
                                        <th>Build & Push</th>
                                        <th>Deploy</th>
                                        <th>Last Run</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {workflowRows.map((row) => (
                                        <tr key={row[0]}>
                                            {row.map((cell, index) => (
                                                <td key={cell + index}>{cell}</td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <div className="studio-grid studio-grid-two" style={{ marginTop: "1rem" }}>
                            <div className="commit-preview-card tone-pass">
                                <div className="commit-preview-head">
                                    <strong>order-service.yml</strong>
                                    <span className="badge badge-pass">Success</span>
                                </div>
                                <div className="commit-preview-items">
                                    {["Security Scan (Snyk) — Passed", "Docker build — Passed", "ECR push — Passed", "ECS deploy — Passed"].map((item) => (
                                        <span key={item} className="pill mono commit-preview-pill">{item}</span>
                                    ))}
                                </div>
                            </div>
                            <div className="code-view">
                                <pre>{`name: order-service CI/CD
on:
  push:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Security scan
        run: snyk test`}</pre>
                            </div>
                        </div>
                    </section>
                );
            case "containers":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <SectionHeader title="docker-compose.yml" subtitle="Generated container orchestration for the prototype project." />
                            <div className="code-view" style={{ marginTop: "1rem" }}>
                                <pre>{`version: "3.9"
services:
  frontend:
    build: ./client
    ports: ["3000:3000"]
    env_file: .env
    depends_on:
      - user-service
  user-service:
    build: ./server/user-service
    ports: ["3001:3001"]
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "-O", "-", "http://localhost:3001/health"]`}</pre>
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <SectionHeader title="Docker Audit Checklist" subtitle="Container hardening assessment." />
                            <div className="studio-checklist" style={{ marginTop: "1rem" }}>
                                {containerAudit.map((item, index) => (
                                    <div className="studio-check-item" key={item}>
                                        <span className={index < 6 ? "badge badge-pass" : "badge badge-warn"}>{index < 6 ? "✓" : "!"}</span>
                                        <span>{item}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="studio-summary-note warning" style={{ marginTop: "1rem" }}>
                                2 Warnings — Non-Critical. Warnings do not block deployment. Address before production hardening review.
                            </div>
                        </aside>
                    </div>
                );
            case "aws":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <div className="studio-summary-row">
                                <div className="studio-summary-card"><span>Cluster</span><strong>food-ordering-cluster</strong></div>
                                <div className="studio-summary-card"><span>Status</span><strong>Active</strong></div>
                                <div className="studio-summary-card"><span>Launch Type</span><strong>Fargate</strong></div>
                                <div className="studio-summary-card"><span>Region</span><strong>eu-north-1</strong></div>
                                <div className="studio-summary-card"><span>Services</span><strong>6 / 6</strong></div>
                                <div className="studio-summary-card"><span>Tasks</span><strong>6 / 6</strong></div>
                            </div>
                            <div className="studio-table-wrap" style={{ marginTop: "1rem" }}>
                                <table className="studio-table">
                                    <thead>
                                        <tr>
                                            <th>Service</th>
                                            <th>Desired</th>
                                            <th>Running</th>
                                            <th>Status</th>
                                            <th>Task Definition</th>
                                            <th>Deployment</th>
                                            <th>Security Group</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {ecsServices.map((row) => (
                                            <tr key={row[0]}>
                                                {row.map((cell, index) => (
                                                    <td key={cell + index}>{cell}</td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <SectionHeader title="Task Detail" subtitle="Selected service network and runtime information." />
                            <div className="studio-summary-stack" style={{ marginTop: "1rem" }}>
                                <div className="studio-summary-card"><span>Public IP</span><strong>3.x.x.x13 (masked)</strong></div>
                                <div className="studio-summary-card"><span>Private IP</span><strong>10.0.1.xx (masked)</strong></div>
                                <div className="studio-summary-card"><span>Subnet</span><strong>subnet-8abc***masked***</strong></div>
                                <div className="studio-summary-card"><span>Security Group</span><strong>food-ordering-sg</strong></div>
                                <div className="studio-summary-card"><span>Exec Role</span><strong>ecsTaskExecutionRole</strong></div>
                                <div className="studio-summary-card"><span>Health</span><strong>HEALTHY</strong></div>
                            </div>
                            <div className="code-view" style={{ marginTop: "1rem" }}>
                                <pre>{`{
  "family": "order-service-task",
  "networkMode": "awsvpc",
  "launchType": "FARGATE",
  "desiredCount": 1
}`}</pre>
                            </div>
                        </aside>
                    </div>
                );
            case "ecr":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <div className="studio-summary-row">
                                <div className="studio-summary-card"><span>Encryption</span><strong>AES-256</strong></div>
                                <div className="studio-summary-card"><span>Tag Policy</span><strong>Mutable</strong></div>
                                <div className="studio-summary-card"><span>Image Tag</span><strong>latest</strong></div>
                                <div className="studio-summary-card"><span>Push Status</span><strong>All Success</strong></div>
                            </div>
                            <div className="studio-table-wrap" style={{ marginTop: "1rem" }}>
                                <table className="studio-table">
                                    <thead>
                                        <tr>
                                            <th>Repository Name</th>
                                            <th>Tag</th>
                                            <th>Encryption</th>
                                            <th>Created</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {ecrRepos.map((row) => (
                                            <tr key={row[0]}>
                                                {row.map((cell, index) => (
                                                    <td key={cell + index}>{cell}</td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <SectionHeader title="ECR Evidence" subtitle="Supporting screenshots and push commands are staged here." />
                            <div className="studio-evidence-grid" style={{ marginTop: "1rem" }}>
                                {Array.from({ length: 4 }).map((_, index) => (
                                    <div className="studio-evidence-card" key={`ecr-${index}`}>
                                        <span className="badge badge-warn">Required</span>
                                        <span className="badge badge-pass">AWS</span>
                                        <strong>Screenshot</strong>
                                    </div>
                                ))}
                            </div>
                        </aside>
                    </div>
                );
            case "iam":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <div className="studio-alert">Sensitive Values Policy. All AWS Account IDs, secret keys, tokens, emails, and phone numbers are masked in this report.</div>
                            <div className="studio-grid studio-grid-three" style={{ marginTop: "1rem" }}>
                                <div className="studio-split-card">
                                    <SectionHeader title="IAM Role" subtitle="Attached policies and role metadata." />
                                    <div className="studio-summary-card" style={{ marginTop: "0.85rem" }}><span>Role</span><strong>ecsTaskExecutionRole</strong></div>
                                    <div className="studio-checklist" style={{ marginTop: "0.85rem" }}>
                                        {["AmazonECSTaskExecutionRolePolicy", "CloudWatchFullAccess", "CloudWatchLogsFullAccess"].map((item) => (
                                            <div className="studio-check-item" key={item}>
                                                <span className="badge badge-pass">✓</span>
                                                <span>{item}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <div className="studio-split-card">
                                    <SectionHeader title="Security Group" subtitle="Inbound rules." />
                                    <div className="studio-rule-list" style={{ marginTop: "0.85rem" }}>
                                        {securityRules.map(([port, service, protocol]) => (
                                            <div className="studio-rule-item" key={`${port}-${service}`}>
                                                <strong>{port}</strong>
                                                <span>{service}</span>
                                                <span className="pill">{protocol}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <div className="studio-split-card">
                                    <SectionHeader title="Security Checklist" subtitle="Current readiness checks." />
                                    <div className="studio-checklist" style={{ marginTop: "0.85rem" }}>
                                        {securityChecklist.map((item, index) => (
                                            <div className="studio-check-item" key={item}>
                                                <span className={index < 6 ? "badge badge-pass" : "badge badge-warn"}>{index < 6 ? "✓" : "!"}</span>
                                                <span>{item}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <div className="studio-summary-note warning">Source: 0.0.0.0/0 — restrict in production.</div>
                            <div className="studio-summary-note warning">Public IP should use Load Balancer in production.</div>
                        </aside>
                    </div>
                );
            case "logs":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <SectionHeader title="CloudWatch Log Groups" subtitle="All log groups are active with standard class and never-expire retention." />
                            <div className="studio-table-wrap" style={{ marginTop: "1rem" }}>
                                <table className="studio-table">
                                    <thead>
                                        <tr>
                                            <th>Log Group</th>
                                            <th>Class</th>
                                            <th>Retention</th>
                                            <th>Status</th>
                                            <th>Sample Message</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {cloudwatchLogs.map(([group, message]) => (
                                            <tr key={group}>
                                                <td>{group}</td>
                                                <td>Standard</td>
                                                <td>Never expire</td>
                                                <td><span className="badge badge-pass">Active</span></td>
                                                <td>{message}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <SectionHeader title="Monitoring Summary" subtitle="Log volume and retention summary." />
                            <div className="studio-summary-stack" style={{ marginTop: "1rem" }}>
                                <div className="studio-summary-card"><span>Log Groups</span><strong>6</strong></div>
                                <div className="studio-summary-card"><span>Total Streams</span><strong>12</strong></div>
                                <div className="studio-summary-card"><span>Retention</span><strong>Never expire</strong></div>
                                <div className="studio-summary-card"><span>Log Class</span><strong>Standard</strong></div>
                            </div>
                            <div className="code-view" style={{ marginTop: "1rem" }}>
                                <pre>{`[order-service] Order API ready - connected to MongoDB
[order-service] GET /api/v1/orders 200 OK (24ms)`}</pre>
                            </div>
                        </aside>
                    </div>
                );
            case "api":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <div className="studio-banner success">All APIs Validated — 4 / 4 Passed</div>
                            <div className="studio-table-wrap" style={{ marginTop: "1rem" }}>
                                <table className="studio-table">
                                    <thead>
                                        <tr>
                                            <th>API Name</th>
                                            <th>Method</th>
                                            <th>URL</th>
                                            <th>Auth</th>
                                            <th>Status</th>
                                            <th>Response Time</th>
                                            <th>Result</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {apiValidationRows.map((row) => (
                                            <tr key={row[0]}>
                                                {row.map((cell, index) => (
                                                    <td key={cell + index}>{cell}</td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <SectionHeader title="Validation Checklist" subtitle="Live endpoint testing and bearer token validation." />
                            <div className="studio-checklist" style={{ marginTop: "1rem" }}>
                                {["Live public IP reachable", "Bearer token accepted", "JSON response received", "Swagger docs reachable"].map((item) => (
                                    <div className="studio-check-item" key={item}>
                                        <span className="badge badge-pass">✓</span>
                                        <span>{item}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="code-view" style={{ marginTop: "1rem" }}>
                                <pre>{`{
  "messages": [
    {
      "order_id": "***",
      "customer_name": "***",
      "phone": "***"
    }
  ]
}`}</pre>
                            </div>
                        </aside>
                    </div>
                );
            case "evidence":
                return (
                    <div className="studio-grid studio-grid-two">
                        <section className="panel studio-panel">
                            <div className="studio-summary-row">
                                <div className="studio-summary-card"><span>Total Evidence</span><strong>19</strong></div>
                                <div className="studio-summary-card"><span>Captured</span><strong>19</strong></div>
                                <div className="studio-summary-card"><span>AWS Screenshots</span><strong>9</strong></div>
                                <div className="studio-summary-card"><span>API Screenshots</span><strong>5</strong></div>
                            </div>
                            <div className="commit-preview-card tone-pass" style={{ marginTop: "1rem" }}>
                                <div className="commit-preview-head">
                                    <strong>Report Caption Generator</strong>
                                    <span className="badge badge-pass">AI Assistant</span>
                                </div>
                                <div className="commit-preview-items">
                                    <span className="pill mono commit-preview-pill">Figure 5: GitHub Actions workflow execution showing successful security scan, Docker image build, ECR push, and ECS deployment.</span>
                                </div>
                            </div>
                        </section>
                        <aside className="panel studio-panel">
                            <SectionHeader title="AWS Evidence" subtitle="Screenshot review cards and verification status." />
                            <div className="studio-evidence-grid" style={{ marginTop: "1rem" }}>
                                {evidenceCards.map(([title, caption]) => (
                                    <div className="studio-evidence-card" key={title}>
                                        <span className="badge badge-warn">Required</span>
                                        <span className="badge badge-pass">AWS</span>
                                        <strong>{title}</strong>
                                        <p>{caption}</p>
                                        <div className="button-stack">
                                            <button type="button" className="ghost-button" disabled>Captured</button>
                                            <button type="button" className="ghost-button" disabled>View</button>
                                            <button type="button" className="ghost-button" disabled>Replace</button>
                                            <button type="button" className="ghost-button" disabled>Verify</button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </aside>
                    </div>
                );
            case "overview":
            default:
                return (
                    <>
                        <section className="studio-grid studio-grid-requests">
                            {showIntroOverlay
                                ? accessRequests.map((request, index) => (
                                    <article className={`studio-request-card ${index === 0 ? "featured" : ""}`} key={request.title}>
                                        <div className="studio-request-head">
                                            <div>
                                                <p className="studio-request-step">Access Request {index + 1} of {accessRequests.length}</p>
                                                <h3>{request.title}</h3>
                                            </div>
                                            <span className="status-pill">Agent 4 — DevOps Center</span>
                                        </div>
                                        <p className="studio-request-host">{request.host}</p>
                                        <p className="studio-request-copy">{request.description}</p>
                                        <div className="studio-scope-list">
                                            {request.scopes.map((scope) => (
                                                <div className="studio-scope-item" key={scope}>✓ {scope}</div>
                                            ))}
                                        </div>
                                        <p className="studio-request-note">Prototype only. Access actions stay empty until the integration is implemented.</p>
                                        <div className="button-stack">
                                            <button type="button" className="ghost-button" disabled>Deny</button>
                                            <button type="button" className="primary-button" disabled>Allow Access</button>
                                        </div>
                                    </article>
                                ))
                                : null}
                        </section>

                        <section className="studio-grid studio-grid-cards">
                            {overviewCards.map((card) => (
                                <MetricCard key={card.label} {...card} />
                            ))}
                        </section>

                        <section className="studio-grid studio-grid-two">
                            <article className="panel studio-panel">
                                <SectionHeader title="Live Package Runner" subtitle="Use the real backend to generate Docker, validation, and GitHub push output." />
                                <div className="studio-runner-form" style={{ marginTop: "1rem" }}>
                                    <label className="studio-field">
                                        <span>Source folder</span>
                                        <select value={selectedSourcePath} onChange={(event) => setSelectedSourcePath(event.target.value)}>
                                            <option value="">{loadingInputs ? "Loading inputs..." : "Select a source folder"}</option>
                                            {inputCandidates.map((candidate) => (
                                                <option key={candidate.id} value={candidate.source_path}>
                                                    {candidate.display_name}
                                                </option>
                                            ))}
                                        </select>
                                    </label>

                                    <div className="studio-field-grid">
                                        <label className="studio-toggle">
                                            <input type="checkbox" checked={dockerEnabled} onChange={(event) => setDockerEnabled(event.target.checked)} />
                                            <span>Generate Docker assets</span>
                                        </label>
                                        <label className="studio-toggle">
                                            <input type="checkbox" checked={githubPushEnabled} onChange={(event) => setGithubPushEnabled(event.target.checked)} />
                                            <span>Push to GitHub</span>
                                        </label>
                                    </div>

                                    <label className="studio-field">
                                        <span>GitHub repository URL</span>
                                        <input type="text" value={githubRepoUrl} onChange={(event) => setGithubRepoUrl(event.target.value)} placeholder="https://github.com/owner/repo.git" />
                                    </label>

                                    <div className="studio-field-grid">
                                        <label className="studio-field">
                                            <span>Branch</span>
                                            <input type="text" value={githubBranch} onChange={(event) => setGithubBranch(event.target.value)} />
                                        </label>
                                        <label className="studio-field">
                                            <span>Commit message</span>
                                            <input type="text" value={commitMessage} onChange={(event) => setCommitMessage(event.target.value)} />
                                        </label>
                                    </div>

                                    <div className="button-stack">
                                        <button type="button" className="primary-button" onClick={handleRunPackage} disabled={submitting || !selectedSourcePath}>
                                            {submitting ? "Running..." : "Run Packaging"}
                                        </button>
                                        <button type="button" className="secondary-button" onClick={() => setSelectedSourcePath(inputCandidates[0]?.source_path || "")} disabled={!inputCandidates.length}>
                                            Load First Input
                                        </button>
                                        <button type="button" className="ghost-button" onClick={handleLoadLatestJob} disabled={!jobDetails}>
                                            Load Current Job
                                        </button>
                                    </div>

                                    {runnerError ? <div className="studio-summary-note warning">{runnerError}</div> : null}
                                    {runnerMessage ? <div className="studio-banner success">{runnerMessage}</div> : null}
                                </div>
                            </article>

                            <aside className="panel studio-panel">
                                <SectionHeader title="Live Job Output" subtitle="Backend response from the packaging service." />
                                <div className="studio-summary-stack" style={{ marginTop: "1rem" }}>
                                    <div className="studio-summary-card"><span>Job ID</span><strong>{liveJob?.job_id || jobId || "Not run yet"}</strong></div>
                                    <div className="studio-summary-card"><span>State</span><strong>{liveJob?.state || "Idle"}</strong></div>
                                    <div className="studio-summary-card"><span>Architecture</span><strong>{liveJob?.architecture || "Pending"}</strong></div>
                                    <div className="studio-summary-card"><span>Confidence</span><strong>{liveJob ? `${Math.round((liveJob.confidence || 0) * 100)}%` : "Pending"}</strong></div>
                                    <div className="studio-summary-card"><span>Docker</span><strong>{dockerEnabled ? "Enabled" : "Disabled"}</strong></div>
                                    <div className="studio-summary-card"><span>GitHub Push</span><strong>{githubPushEnabled ? "Enabled" : "Disabled"}</strong></div>
                                </div>

                                <div className="button-stack" style={{ marginTop: "1rem" }}>
                                    <a className={`secondary-button ${downloadUrl ? "" : "is-disabled"}`} href={downloadUrl || undefined} aria-disabled={!downloadUrl} onClick={(event) => { if (!downloadUrl) { event.preventDefault(); } }}>
                                        Download ZIP
                                    </a>
                                    <button type="button" className="ghost-button" disabled={!liveJob?.evidence_path}>
                                        Open Evidence
                                    </button>
                                </div>

                                {jobDetailsError ? <div className="studio-summary-note warning" style={{ marginTop: "1rem" }}>{jobDetailsError}</div> : null}
                                {liveJob?.push_result ? (
                                    <div className="studio-summary-note" style={{ marginTop: "1rem" }}>
                                        GitHub push: {liveJob.push_result.state} {liveJob.push_result.message ? `- ${liveJob.push_result.message}` : ""}
                                    </div>
                                ) : null}
                            </aside>
                        </section>

                        <section className="studio-grid studio-grid-two">
                            <article className="panel studio-panel">
                                <SectionHeader title="Production Readiness Score" subtitle="Overall deployment quality assessment." />
                                <div className="studio-score-wrap" style={{ marginTop: "1rem" }}>
                                    <div className="studio-score-ring">
                                        <strong>92</strong>
                                        <span>/ 100</span>
                                    </div>
                                    <div className="studio-score-bars">
                                        {[
                                            ["Docker", 95],
                                            ["CI/CD", 94],
                                            ["AWS", 90],
                                            ["Security", 88],
                                            ["Monitoring", 90],
                                            ["API", 96],
                                        ].map(([label, score]) => (
                                            <div className="studio-progress-row" key={label as string}>
                                                <div className="studio-progress-label">
                                                    <span>{label}</span>
                                                    <strong>{score}</strong>
                                                </div>
                                                <div className="studio-progress-track">
                                                    <div className="studio-progress-fill" style={{ width: `${score}%` }} />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </article>

                            <article className="panel studio-panel">
                                <SectionHeader title="Task Networking" subtitle="Selected service networking details." />
                                <div className="studio-summary-stack" style={{ marginTop: "1rem" }}>
                                    <div className="studio-summary-card"><span>Service</span><strong>order-service — eu-north-1</strong></div>
                                    <div className="studio-summary-card"><span>Public IP</span><strong>3.x.xx.x13 (masked)</strong></div>
                                    <div className="studio-summary-card"><span>Private IP</span><strong>10.0.1.xx (masked)</strong></div>
                                    <div className="studio-summary-card"><span>Subnet</span><strong>subnet-0abc***masked***</strong></div>
                                    <div className="studio-summary-card"><span>Security Group</span><strong>food-ordering-sg</strong></div>
                                    <div className="studio-summary-card"><span>Health Status</span><strong>HEALTHY</strong></div>
                                </div>
                            </article>
                        </section>

                        <section className="studio-grid studio-grid-two">
                            <article className="panel studio-panel">
                                <SectionHeader title="Export" subtitle="Download deployment artifacts." />
                                <div className="button-stack" style={{ marginTop: "1rem" }}>
                                    <button type="button" className="primary-button" disabled>Download PDF Report</button>
                                    <button type="button" className="secondary-button" disabled>Download Evidence ZIP</button>
                                    <button type="button" className="ghost-button" disabled>Copy Deployment Summary</button>
                                    <button type="button" className="ghost-button" disabled>Export Agent 4 Output</button>
                                    <button type="button" className="ghost-button" disabled>Generate Viva Summary</button>
                                </div>
                                <div className="studio-summary-note warning" style={{ marginTop: "1rem" }}>Functions are left empty in prototype mode until you implement them.</div>
                            </article>

                            <article className="panel studio-panel">
                                <SectionHeader title="Deployment Summary" subtitle="Current workspace context." />
                                <div className="studio-summary-stack" style={{ marginTop: "1rem" }}>
                                    <div className="studio-summary-card"><span>Workspace</span><strong>demo</strong></div>
                                    <div className="studio-summary-card"><span>Active user</span><strong>demo@gmail.com</strong></div>
                                    <div className="studio-summary-card"><span>Status</span><strong>Pipeline complete — DevOps Center is live.</strong></div>
                                    <div className="studio-summary-card"><span>Job</span><strong>{jobLabel}</strong></div>
                                </div>
                            </article>
                        </section>
                    </>
                );
        }
    }, [activeTab, introVisible, jobLabel, showIntroOverlay]);

    return (
        <main className="studio-app">
            <aside className="studio-sidebar">
                <div className="studio-sidebar-brand">
                    <div className="studio-avatar">AF</div>
                    <div>
                        <strong>AgentForge Studio</strong>
                        <span>AI Agent Workspace</span>
                    </div>
                </div>

                <div className="studio-workspace-box">
                    <span className="section-kicker">Workspace</span>
                    <strong>demo</strong>
                    <span>demo@gmail.com</span>
                </div>

                <nav className="studio-nav" aria-label="Primary">
                    {sidebarItems.map((item) => (
                        <button key={item.label} type="button" className={`studio-nav-item ${item.active ? "active" : ""}`}>
                            <span className="studio-nav-bullet" />
                            {item.label}
                        </button>
                    ))}
                </nav>

                <div className="studio-sidebar-footer">
                    <button type="button" className="studio-link-button">Help Center</button>
                    <button type="button" className="studio-link-button">Sign Out</button>
                </div>
            </aside>

            <section className="studio-content">
                <header className="studio-topbar topbar">
                    <div className="studio-search-shell">
                        <input className="studio-search" type="search" placeholder="Search projects, requirements, services, artifacts..." aria-label="Search" />
                    </div>

                    <div className="studio-toolbar-actions">
                        <button type="button" className="studio-icon-button" aria-label="Mute preview">◌</button>
                        <button type="button" className="studio-icon-button" aria-label="Notifications">◔</button>
                        <button type="button" className="studio-icon-button" aria-label="Downloads">⌁</button>
                        <button type="button" className="primary-button">+ New Project</button>
                    </div>
                </header>

                <div className="studio-header-copy">
                    <div>
                        <span className="section-kicker">AgentForge &gt; Agent 4 &gt; DevOps Center</span>
                        <h1>Agent 4 — DevOps Center</h1>
                        <p>Package, automate, deploy, validate, monitor, and export production evidence.</p>
                    </div>
                    <div className="button-stack">
                        <a
                            className={`secondary-button ${downloadUrl ? "" : "is-disabled"}`}
                            href={downloadUrl || undefined}
                            aria-disabled={!downloadUrl}
                            onClick={(event) => {
                                if (!downloadUrl) {
                                    event.preventDefault();
                                }
                            }}
                        >
                            Export ZIP
                        </a>
                        <button type="button" className="secondary-button" disabled>PDF Report</button>
                        <button type="button" className="ghost-button" onClick={handleRunPackage} disabled={submitting || !selectedSourcePath}>
                            Re-run
                        </button>
                    </div>
                </div>

                <section className="studio-status-strip">
                    {statusPills.map((pill) => (
                        <span className="studio-status-pill" key={pill}>● {pill}</span>
                    ))}
                </section>

                <nav className="studio-tabs" aria-label="DevOps Center sections">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            className={`studio-tab ${activeTab === tab.id ? "active" : ""}`}
                            onClick={() => setActiveTab(tab.id)}
                        >
                            {tab.label}
                        </button>
                    ))}
                </nav>

                <section className="studio-dashboard">
                    {tabPanels}
                </section>

                {introVisible ? (
                    <div className="studio-overlay" role="dialog" aria-modal="true" aria-label="Access requests preview">
                        <div className="studio-overlay-card panel">
                            <div className="studio-overlay-head">
                                <div>
                                    <p className="section-kicker">Access Request 1 of 5</p>
                                    <h3>Connect GitHub CLI</h3>
                                </div>
                                <span className="status-pill">Agent 4 — DevOps Center</span>
                            </div>
                            <p className="studio-request-host">github.com/login/device</p>
                            <p className="studio-request-copy">Authorize Agent 4 to push code, open PRs, and trigger GitHub Actions workflows on your behalf.</p>
                            <div className="studio-scope-list">
                                {accessRequests[0].scopes.map((scope) => (
                                    <div className="studio-scope-item" key={scope}>✓ {scope}</div>
                                ))}
                            </div>
                            <p className="studio-request-note">Prototype only. Controls are intentionally empty until the integration is implemented.</p>
                            <div className="button-stack">
                                <button type="button" className="ghost-button" disabled>Deny</button>
                                <button type="button" className="primary-button" disabled>Allow Access</button>
                                <button type="button" className="ghost-button" onClick={() => setIntroVisible(false)}>
                                    Continue to dashboard
                                </button>
                            </div>
                        </div>
                    </div>
                ) : null}
            </section>
        </main>
    );
}