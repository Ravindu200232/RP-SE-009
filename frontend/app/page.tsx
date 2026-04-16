"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_AGENT4_API_BASE_URL ?? "http://localhost:8004";

const workflowSteps = [
    {
        title: "Detect",
        description: "Reads architecture from Agent 3 output and verifies packaging scope.",
    },
    {
        title: "Package",
        description: "Generates Docker-ready artifacts with architecture-aware strategies.",
    },
    {
        title: "Validate",
        description: "Runs validation checks before finalizing package output.",
    },
    {
        title: "Publish",
        description: "Optionally pushes to GitHub when you confirm repository details.",
    },
];

type ConversationStage =
    | "loadingInputs"
    | "chooseInput"
    | "askDocker"
    | "askGithub"
    | "askRepo"
    | "askBranch"
    | "askCommit"
    | "confirm"
    | "submitting"
    | "blocked";

type InputCandidate = {
    id: string;
    job_folder: string;
    name: string;
    display_name: string;
    source_path: string;
    review_report_path: string;
    srs_path: string;
    ready: boolean;
    missing: string[];
    updated_at: string;
};

type ChatMessage = {
    id: string;
    role: "assistant" | "user";
    text: string;
};

const defaultCommitMessage = "Add packaged deployment output";

export default function HomePage() {
    const router = useRouter();
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            id: "welcome",
            role: "assistant",
            text: "Welcome. I will package using your uploaded Agent 4 input folder and Agent 3 outputs. First, choose which detected input package you want to process.",
        },
    ]);
    const [stage, setStage] = useState<ConversationStage>("loadingInputs");
    const [inputCandidates, setInputCandidates] = useState<InputCandidate[]>([]);
    const [selectedInput, setSelectedInput] = useState<InputCandidate | null>(null);
    const [dockerEnabled, setDockerEnabled] = useState(true);
    const [githubEnabled, setGithubEnabled] = useState(false);
    const [githubRepoUrl, setGithubRepoUrl] = useState("");
    const [githubBranch, setGithubBranch] = useState("main");
    const [commitMessage, setCommitMessage] = useState(defaultCommitMessage);
    const [draftReply, setDraftReply] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    function addMessage(role: ChatMessage["role"], text: string) {
        setMessages((previous) => [...previous, { id: `${Date.now()}-${previous.length}`, role, text }]);
    }

    useEffect(() => {
        let active = true;

        async function loadInputs() {
            try {
                const response = await fetch(`${apiBase}/inputs`, { cache: "no-store" });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.detail ?? "Failed to load input candidates.");
                }

                const items = (payload.items ?? []) as InputCandidate[];
                if (!active) {
                    return;
                }

                setInputCandidates(items);
                if (!items.length) {
                    setStage("blocked");
                    addMessage(
                        "assistant",
                        "No input candidates were found. Upload Agent 3 output with SRS and review JSON inside the Agent 4 input folder, then refresh.",
                    );
                    return;
                }

                setStage("chooseInput");
                addMessage("assistant", `Found ${items.length} candidate input packages. Select one to continue.`);
            } catch (caught) {
                if (!active) {
                    return;
                }
                const message = caught instanceof Error ? caught.message : "Failed to load input candidates.";
                setError(message);
                setStage("blocked");
                addMessage("assistant", `I cannot continue right now: ${message}`);
            }
        }

        loadInputs();
        return () => {
            active = false;
        };
    }, []);

    async function submitPackaging() {
        if (!selectedInput || !selectedInput.ready) {
            return;
        }

        setSubmitting(true);
        setStage("submitting");
        setError("");

        try {
            const response = await fetch(`${apiBase}/package`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    source_path: selectedInput.source_path,
                    review_report_path: selectedInput.review_report_path,
                    srs_path: selectedInput.srs_path,
                    docker_enabled: dockerEnabled,
                    github_push_enabled: githubEnabled,
                    github_repo_url: githubEnabled ? githubRepoUrl : "",
                    github_branch: githubEnabled ? githubBranch : "main",
                    commit_message: githubEnabled ? commitMessage : defaultCommitMessage,
                }),
            });

            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail ?? "Packaging request failed.");
            }

            addMessage("assistant", `Packaging started successfully. Opening job ${payload.job_id}.`);
            router.push(`/job/${payload.job_id}`);
        } catch (caught) {
            const message = caught instanceof Error ? caught.message : "Packaging request failed.";
            setError(message);
            addMessage("assistant", `Submission failed: ${message}`);
            setStage("confirm");
        } finally {
            setSubmitting(false);
        }
    }

    function resetConversation() {
        setSelectedInput(null);
        setDockerEnabled(true);
        setGithubEnabled(false);
        setGithubRepoUrl("");
        setGithubBranch("main");
        setCommitMessage(defaultCommitMessage);
        setDraftReply("");
        setError("");
        setStage(inputCandidates.length ? "chooseInput" : "blocked");
        addMessage("assistant", "Conversation reset. Pick an input package to begin again.");
    }

    function chooseInput(candidate: InputCandidate) {
        setSelectedInput(candidate);
        addMessage("user", `Use ${candidate.display_name}.`);

        if (!candidate.ready) {
            addMessage(
                "assistant",
                `This input is missing: ${candidate.missing.join(", ")}. Add those files in the same input folder, then choose a ready package.`,
            );
            setStage("chooseInput");
            return;
        }

        setStage("askDocker");
        addMessage("assistant", "Do you want Docker validation enabled for this run?");
    }

    function answerDocker(value: boolean) {
        setDockerEnabled(value);
        addMessage("user", value ? "Yes, enable Docker validation." : "No, skip Docker validation.");
        setStage("askGithub");
        addMessage("assistant", "Do you want to push the packaged output to GitHub?");
    }

    function answerGithub(value: boolean) {
        setGithubEnabled(value);
        addMessage("user", value ? "Yes, push to GitHub." : "No GitHub push.");

        if (!value) {
            setStage("confirm");
            addMessage("assistant", "Great. I have enough details. Review and submit when ready.");
            return;
        }

        setStage("askRepo");
        addMessage("assistant", "Please provide the GitHub repository URL (for example: git@github.com:owner/repo.git).");
    }

    function submitReply() {
        const value = draftReply.trim();
        if (!value && stage !== "askBranch" && stage !== "askCommit") {
            return;
        }

        if (stage === "askRepo") {
            if (!value) {
                return;
            }
            setGithubRepoUrl(value);
            addMessage("user", value);
            setDraftReply("");
            setStage("askBranch");
            addMessage("assistant", "Which branch should I use? Press send with empty text to keep 'main'.");
            return;
        }

        if (stage === "askBranch") {
            const branchValue = value || "main";
            setGithubBranch(branchValue);
            addMessage("user", branchValue);
            setDraftReply("");
            setStage("askCommit");
            addMessage("assistant", "Any custom commit message? Press send with empty text to use the default message.");
            return;
        }

        if (stage === "askCommit") {
            const commitValue = value || defaultCommitMessage;
            setCommitMessage(commitValue);
            addMessage("user", commitValue);
            setDraftReply("");
            setStage("confirm");
            addMessage("assistant", "Perfect. I have everything needed. Review and submit when ready.");
        }
    }

    const summaryLines = useMemo(() => {
        const lines: string[] = [];
        if (selectedInput) {
            lines.push(`Input: ${selectedInput.display_name}`);
            lines.push(`Source: ${selectedInput.source_path}`);
            lines.push(`Review: ${selectedInput.review_report_path}`);
            lines.push(`SRS: ${selectedInput.srs_path}`);
        }
        lines.push(`Docker validation: ${dockerEnabled ? "enabled" : "disabled"}`);
        lines.push(`GitHub push: ${githubEnabled ? "enabled" : "disabled"}`);
        if (githubEnabled) {
            lines.push(`Repository: ${githubRepoUrl || "not set"}`);
            lines.push(`Branch: ${githubBranch || "main"}`);
            lines.push(`Commit message: ${commitMessage || defaultCommitMessage}`);
        }
        return lines;
    }, [selectedInput, dockerEnabled, githubEnabled, githubRepoUrl, githubBranch, commitMessage]);

    return (
        <main className="page-shell">
            <header className="topbar">
                <div className="brand">
                    <div className="brand-mark">A4</div>
                    <div className="brand-copy">
                        <strong>Agent 4 Packaging Console</strong>
                        <span>Architecture-aware deployment, validation, and repository handoff</span>
                    </div>
                </div>

                <div className="topbar-actions">
                    <span className="chip">
                        <strong>Active mode</strong> Conversational
                    </span>
                    <span className="chip">Agent 3 source</span>
                    <span className="chip">GitHub optional</span>
                </div>
            </header>

            <section className="hero-grid">
                <section className="panel hero">
                    <div className="hero-content">
                        <p className="eyebrow">Agent 4 Deployment Studio</p>
                        <h1>
                            Move from <span className="gradient-text">manual form fields</span> to guided Q&A.
                        </h1>
                        <p className="lede hero-note">
                            Agent 4 now discovers uploaded Agent 3 outputs and asks focused questions only. You choose
                            the input package, decide Docker validation, and optionally provide GitHub details.
                        </p>
                        <div className="workflow" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                            {workflowSteps.map((step, index) => (
                                <div className="workflow-step" key={step.title}>
                                    <strong>
                                        {String(index + 1).padStart(2, "0")} {step.title}
                                    </strong>
                                    <span>{step.description}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                <aside className="sidebar">
                    <div className="sidebar-card">
                        <p className="section-kicker">Conversation state</p>
                        <h2 className="section-title">{stage === "blocked" ? "Waiting for valid input" : "Ready for guided submission"}</h2>
                        <p className="section-subtitle">
                            {selectedInput
                                ? `Selected input: ${selectedInput.display_name}`
                                : "No input selected yet. Choose one of the discovered Agent 3 output packages."}
                        </p>
                    </div>
                    <div className="sidebar-card">
                        <p className="section-kicker">Detected inputs</p>
                        <h2 className="section-title">{inputCandidates.length}</h2>
                        <p className="section-subtitle">Packages discovered from your Agent 4 input folder.</p>
                    </div>
                </aside>
            </section>

            <section className="panel form-panel" id="submission">
                <div className="form-header">
                    <div>
                        <p className="section-kicker">Conversational submission</p>
                        <h2 className="section-title">Package through Q&A instead of filling a form</h2>
                        <p className="section-subtitle">
                            Manual job ID and path fields are removed. Agent 4 auto-uses discovered inputs and asks
                            only for decisions like Docker validation and optional GitHub push settings.
                        </p>
                    </div>
                    <span className="status-pill">Q&A mode</span>
                </div>

                <div className="conversation-shell">
                    <div className="conversation-log" role="log" aria-live="polite">
                        {messages.map((message) => (
                            <div key={message.id} className={`chat-row ${message.role === "assistant" ? "assistant" : "user"}`}>
                                <div className="chat-bubble">{message.text}</div>
                            </div>
                        ))}
                    </div>

                    <div className="conversation-actions">
                        {stage === "chooseInput" ? (
                            <div className="option-grid">
                                {inputCandidates.map((candidate) => (
                                    <button
                                        type="button"
                                        className={`option-card ${candidate.ready ? "option-ready" : "option-missing"}`}
                                        key={candidate.id}
                                        onClick={() => chooseInput(candidate)}
                                    >
                                        <strong>{candidate.display_name}</strong>
                                        <span>{candidate.ready ? "Ready to package" : `Missing: ${candidate.missing.join(", ")}`}</span>
                                    </button>
                                ))}
                            </div>
                        ) : null}

                        {stage === "askDocker" ? (
                            <div className="button-stack">
                                <button type="button" className="secondary-button" onClick={() => answerDocker(true)}>
                                    Yes, enable Docker validation
                                </button>
                                <button type="button" className="ghost-button" onClick={() => answerDocker(false)}>
                                    No, skip Docker validation
                                </button>
                            </div>
                        ) : null}

                        {stage === "askGithub" ? (
                            <div className="button-stack">
                                <button type="button" className="secondary-button" onClick={() => answerGithub(true)}>
                                    Yes, ask for repository and push
                                </button>
                                <button type="button" className="ghost-button" onClick={() => answerGithub(false)}>
                                    No GitHub push
                                </button>
                            </div>
                        ) : null}

                        {stage === "askRepo" || stage === "askBranch" || stage === "askCommit" ? (
                            <div className="reply-row">
                                <input
                                    value={draftReply}
                                    onChange={(event) => setDraftReply(event.target.value)}
                                    placeholder={
                                        stage === "askRepo"
                                            ? "git@github.com:owner/repo.git"
                                            : stage === "askBranch"
                                                ? "main"
                                                : "Add packaged deployment output"
                                    }
                                    onKeyDown={(event) => {
                                        if (event.key === "Enter") {
                                            event.preventDefault();
                                            submitReply();
                                        }
                                    }}
                                />
                                <button type="button" className="secondary-button" onClick={submitReply}>
                                    Send
                                </button>
                            </div>
                        ) : null}

                        {stage === "confirm" ? (
                            <div className="confirm-block">
                                <div className="summary-card">
                                    <p className="section-kicker">Submission summary</p>
                                    <ul className="summary-list">
                                        {summaryLines.map((line) => (
                                            <li key={line}>{line}</li>
                                        ))}
                                    </ul>
                                </div>

                                <div className="button-stack">
                                    <button type="button" className="primary-button" onClick={submitPackaging} disabled={submitting}>
                                        {submitting ? "Packaging..." : "Submit packaging job"}
                                    </button>
                                    <button type="button" className="ghost-button" onClick={resetConversation}>
                                        Restart Q&A
                                    </button>
                                </div>
                            </div>
                        ) : null}

                        {stage === "submitting" ? (
                            <p className="hint">Submitting job now. You will be redirected to the live job page shortly.</p>
                        ) : null}

                        {stage === "blocked" ? (
                            <button type="button" className="ghost-button" onClick={() => window.location.reload()}>
                                Refresh input discovery
                            </button>
                        ) : null}

                        <div className="button-stack">
                            <button className="ghost-button" type="button" onClick={resetConversation}>
                                Reset conversation
                            </button>
                        </div>
                    </div>

                    {selectedInput ? (
                        <div className="selected-input-card">
                            <p className="section-kicker">Using detected input</p>
                            <strong>{selectedInput.display_name}</strong>
                            <p className="mono">{selectedInput.source_path}</p>
                        </div>
                    ) : null}

                    {error ? <p className="error-text field-full">{error}</p> : null}
                </div>
            </section>
        </main>
    );
}
