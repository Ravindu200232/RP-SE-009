"use client";

import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_AGENT4_API_BASE_URL ?? "http://localhost:8004";

const workflowSteps = [
    {
        title: "Detect",
        description: "Analyze & Understand.",
    },
    {
        title: "Package",
        description: "Build Deployment-Ready Artifacts.",
    },
    {
        title: "Validate",
        description: "Ensure Production Quality.",
    },
    {
        title: "Publish",
        description: "Deploy or Share Instantly.",
    },
];

type ConversationStage =
    | "loadingInputs"
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

const stageTitles: Record<ConversationStage, string> = {
    loadingInputs: "Discover Inputs",
    askDocker: "Docker Validation",
    askGithub: "GitHub Delivery",
    askRepo: "Repository URL",
    askBranch: "Branch",
    askCommit: "Commit Message",
    confirm: "Final Review",
    submitting: "Submitting",
    blocked: "Action Needed",
};

export default function HomePage() {
    const router = useRouter();
    const conversationLogRef = useRef<HTMLDivElement | null>(null);
    const isTypingRef = useRef(false);
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            id: "welcome",
            role: "assistant",
            text: "Welcome! I detected Agent 3 output and will use the microservice input automatically for packaging.",
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

    function pickPreferredInput(items: InputCandidate[]) {
        const preferred = items.find((candidate) => {
            const haystack = `${candidate.display_name} ${candidate.name} ${candidate.source_path}`.toLowerCase();
            return haystack.includes("microservice");
        });

        return preferred ?? items.find((candidate) => candidate.ready) ?? items[0] ?? null;
    }

    function emitConversationEvent(
        eventName: string,
        detail: Record<string, unknown> = {},
    ) {
        if (typeof window === "undefined") {
            return;
        }

        window.dispatchEvent(
            new CustomEvent("agent4:conversation", {
                detail: {
                    source: "agent4",
                    event: eventName,
                    audioAutoplay: false,
                    timestamp: Date.now(),
                    ...detail,
                },
            }),
        );
    }

    function addMessage(role: ChatMessage["role"], text: string) {
        setMessages((previous) => [...previous, { id: `${Date.now()}-${previous.length}`, role, text }]);
        emitConversationEvent(role === "user" ? "message-sent" : "message-received", {
            role,
            text,
        });
    }

    async function loadInputs(active: boolean) {
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
        setError("");

        const preferredInput = pickPreferredInput(items);
        if (!preferredInput) {
            setStage((currentStage) => (currentStage === "blocked" ? currentStage : "blocked"));
            return;
        }

        setSelectedInput(preferredInput);

        setStage((currentStage) => {
            if (currentStage === "askDocker" || currentStage === "askGithub" || currentStage === "askRepo" || currentStage === "askBranch" || currentStage === "askCommit" || currentStage === "confirm" || currentStage === "submitting") {
                return currentStage;
            }
            return "askDocker";
        });

        setMessages((previous) => {
            const alreadyAnnounced = previous.some((message) => message.role === "assistant" && message.text.includes("candidate input packages"));
            if (alreadyAnnounced) {
                return previous;
            }
            return [
                ...previous,
                {
                    id: `${Date.now()}-${previous.length}`,
                    role: "assistant",
                    text: `Found ${items.length} candidate input packages. I selected the microservice input automatically.`,
                },
                {
                    id: `${Date.now()}-${previous.length + 1}`,
                    role: "assistant",
                    text: "Do you want Docker validation enabled for this run?",
                },
            ];

        });
    }

    useEffect(() => {
        let active = true;

        emitConversationEvent("ready", {
            availableEvents: [
                "ready",
                "message-sent",
                "message-received",
                "typing-start",
                "typing-stop",
                "submission-start",
                "submission-success",
                "submission-failed",
            ],
        });

        async function refreshInputs() {
            try {
                await loadInputs(active);
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

        refreshInputs();
        const interval = window.setInterval(refreshInputs, 5000);
        return () => {
            active = false;
            window.clearInterval(interval);
        };
    }, []);

    useEffect(() => {
        const container = conversationLogRef.current;
        if (!container) {
            return;
        }

        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const behavior = prefersReducedMotion || messages.length < 2 ? "auto" : "smooth";

        window.requestAnimationFrame(() => {
            container.scrollTo({
                top: container.scrollHeight,
                behavior,
            });
        });
    }, [messages, stage]);

    useEffect(() => {
        const isTyping = stage === "loadingInputs" || stage === "submitting";
        if (isTypingRef.current === isTyping) {
            return;
        }

        isTypingRef.current = isTyping;
        emitConversationEvent(isTyping ? "typing-start" : "typing-stop", { stage });
    }, [stage]);

    async function submitPackaging() {
        if (!selectedInput || !selectedInput.ready) {
            return;
        }

        setSubmitting(true);
        setStage("submitting");
        setError("");
        emitConversationEvent("submission-start", { selectedInput: selectedInput.display_name });

        const clientJobId =
            typeof crypto !== "undefined" && "randomUUID" in crypto
                ? crypto.randomUUID().replaceAll("-", "")
                : `${Date.now()}${Math.random().toString(16).slice(2)}`;

        addMessage("assistant", `Submission accepted. Opening live job ${clientJobId} now.`);
        emitConversationEvent("submission-success", { jobId: clientJobId });
        router.push(`/job/${clientJobId}`);

        try {
            const response = await fetch(`${apiBase}/package`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    job_id: clientJobId,
                    source_path: selectedInput.source_path,
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
        } catch (caught) {
            const message = caught instanceof Error ? caught.message : "Packaging request failed.";
            console.error("Packaging request failed after redirect:", message);
            emitConversationEvent("submission-failed", { error: message, jobId: clientJobId });
        } finally {
            setSubmitting(false);
        }
    }

    function resetConversation() {
        setDockerEnabled(true);
        setGithubEnabled(false);
        setGithubRepoUrl("");
        setGithubBranch("main");
        setCommitMessage(defaultCommitMessage);
        setDraftReply("");
        setError("");
        const preferredInput = pickPreferredInput(inputCandidates);
        if (!preferredInput) {
            setSelectedInput(null);
            setStage("blocked");
            addMessage("assistant", "Conversation reset. I could not find a valid microservice input to use automatically.");
            return;
        }

        setSelectedInput(preferredInput);
        setStage("askDocker");
        addMessage("assistant", `Conversation reset. I selected ${preferredInput.display_name} automatically. Do you want Docker validation enabled for this run?`);
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

    const stageProgress = useMemo(() => {
        if (stage === "loadingInputs") {
            return 8;
        }
        if (stage === "askDocker") {
            return 25;
        }
        if (stage === "askGithub") {
            return 45;
        }
        if (stage === "askRepo" || stage === "askBranch" || stage === "askCommit") {
            return 64;
        }
        if (stage === "confirm") {
            return 85;
        }
        if (stage === "submitting") {
            return 98;
        }
        return 0;
    }, [stage]);

    const stageHint = useMemo(() => {
        if (stage === "askDocker") {
            return "Choose whether to run local Docker checks before publishing artifacts.";
        }
        if (stage === "askGithub") {
            return "Choose whether this run should push packaged output to GitHub.";
        }
        if (stage === "askRepo") {
            return "Paste the destination repository URL where the packaged result should be pushed.";
        }
        if (stage === "askBranch") {
            return "Provide a target branch or send empty to keep main.";
        }
        if (stage === "askCommit") {
            return "Provide a commit message or send empty to use the default message.";
        }
        if (stage === "confirm") {
            return "Review the run summary and submit when everything looks correct.";
        }
        if (stage === "submitting") {
            return "Submitting your packaging request and preparing the live job page.";
        }
        if (stage === "blocked") {
            return "Input discovery is blocked. Refresh discovery to continue.";
        }
        return "Preparing your run context automatically.";
    }, [stage]);

    return (
        <main className="page-shell">
            <header className="topbar">
                <div className="brand">
                    <div className="brand-mark">A4</div>
                    <div className="brand-copy">
                        <strong>Agent 4 Packaging Console</strong>
                        <span>Built with awareness. Deployed with precision. Delivered with confidence</span>
                    </div>
                </div>

                <div className="topbar-actions">
                    <span className="chip">
                        <strong>Active mode</strong> Conversational
                    </span>
                    <span className="chip">Source: {selectedInput?.display_name ?? "Detecting input..."}</span>
                    <span className="chip">GitHub</span>
                </div>
            </header>

            <section className="hero-grid hero-grid-single">
                <section className="panel hero">
                    <div className="hero-content">
                        <p className="eyebrow">Agent 4 Deployment Studio</p>
                        <h1>
                            Experience a <span className="gradient-text">smarter workflow</span> with guided Q&A.
                        </h1>
                        <p className="lede hero-note">
                            Agent 4 automatically detects your validated outputs and guides you through a focused, decision-driven packaging flow — no unnecessary steps, just what matters.
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
            </section>

            <section className="panel form-panel" id="submission">
                <div className="form-header">
                    <div>
                        <p className="section-kicker">Conversational submission</p>
                        <h2 className="section-title">Guided Packaging Workflow</h2>
                        <p className="section-subtitle">
                            Agent 4 simplifies the process by asking only essential questions — you stay in control while we handle the complexity.
                        </p>
                    </div>
                    <span className="status-pill">Q&A mode</span>
                </div>

                <div className="conversation-shell">
                    <section className="conversation-command-center">
                        <div className="command-center-head">
                            <div>
                                <p className="section-kicker">Live orchestration</p>
                                <h3>Packaging Copilot</h3>
                            </div>
                            <span className="status-pill">{stageTitles[stage]}</span>
                        </div>

                        <div className="command-center-metrics">
                            <span className="pill">Progress {stageProgress}%</span>
                            <span className="pill">Input {selectedInput ? "Auto-selected" : "Pending"}</span>
                            <span className="pill">Validation {dockerEnabled ? "Enabled" : "Disabled"}</span>
                            <span className="pill">GitHub {githubEnabled ? "Enabled" : "Skipped"}</span>
                        </div>

                        <div className="stage-progress-track" aria-hidden="true">
                            <div className="stage-progress-fill" style={{ width: `${stageProgress}%` }} />
                        </div>

                        <p className="section-subtitle command-center-hint">{stageHint}</p>
                    </section>

                    <div className="conversation-log" role="log" aria-live="polite" ref={conversationLogRef}>
                        {messages.map((message, index) => (
                            <div
                                key={message.id}
                                className={`chat-row ${message.role === "assistant" ? "assistant" : "user"}`}
                                style={{ "--row-index": index } as CSSProperties}
                            >
                                <div className="chat-avatar">{message.role === "assistant" ? "A4" : "You"}</div>
                                <div className="chat-bubble-shell">
                                    <span className="chat-meta">{message.role === "assistant" ? "Agent 4" : "You"}</span>
                                    <div className="chat-bubble">{message.text}</div>
                                </div>
                            </div>
                        ))}

                        {(stage === "loadingInputs" || stage === "submitting") ? (
                            <div className="chat-row assistant typing-row">
                                <div className="chat-avatar">A4</div>
                                <div className="chat-bubble-shell">
                                    <span className="chat-meta">Agent 4</span>
                                    <div className="typing-indicator" aria-label="Agent is typing">
                                        <span />
                                        <span />
                                        <span />
                                    </div>
                                </div>
                            </div>
                        ) : null}
                    </div>

                    <div className="conversation-actions">
                        {stage === "askDocker" ? (
                            <div className="prompt-card">
                                <p className="prompt-title">Docker Validation</p>
                                <p className="prompt-copy">Do you want Docker validation enabled for this run?</p>
                                <div className="button-stack">
                                    <button type="button" className="secondary-button" onClick={() => answerDocker(true)}>
                                        Yes, enable Docker validation
                                    </button>
                                    <button type="button" className="ghost-button" onClick={() => answerDocker(false)}>
                                        No, skip Docker validation
                                    </button>
                                </div>
                            </div>
                        ) : null}

                        {stage === "askGithub" ? (
                            <div className="prompt-card">
                                <p className="prompt-title">GitHub Push</p>
                                <p className="prompt-copy">Do you want to push the packaged output to GitHub?</p>
                                <div className="button-stack">
                                    <button type="button" className="secondary-button" onClick={() => answerGithub(true)}>
                                        Yes, ask for repository and push
                                    </button>
                                    <button type="button" className="ghost-button" onClick={() => answerGithub(false)}>
                                        No GitHub push
                                    </button>
                                </div>
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
                                Reset Workflow
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
