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
    const conversationLogRef = useRef<HTMLDivElement | null>(null);
    const isTypingRef = useRef(false);
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            id: "welcome",
            role: "assistant",
            text: "Welcome! I’ve detected your Agent 3 outputs and prepared them for packaging. Let’s begin — select the package you’d like to process.",
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

        if (!items.length) {
            setStage((currentStage) => (currentStage === "blocked" ? currentStage : "blocked"));
            return;
        }

        setStage((currentStage) => {
            if (currentStage === "chooseInput" || currentStage === "askDocker" || currentStage === "askGithub" || currentStage === "askRepo" || currentStage === "askBranch" || currentStage === "askCommit" || currentStage === "confirm" || currentStage === "submitting") {
                return currentStage;
            }
            return "chooseInput";
        });

        setMessages((previous) => {
            const alreadyAnnounced = previous.some((message) => message.role === "assistant" && message.text.includes("candidate input packages"));
            if (alreadyAnnounced) {
                return previous;
            }
            return [...previous, { id: `${Date.now()}-${previous.length}`, role: "assistant", text: `Found ${items.length} candidate input packages. Select one to continue.` }];
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

        try {
            const response = await fetch(`${apiBase}/package`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
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

            addMessage("assistant", `Packaging started successfully. Opening job ${payload.job_id}.`);
            emitConversationEvent("submission-success", { jobId: payload.job_id });
            router.push(`/job/${payload.job_id}`);
        } catch (caught) {
            const message = caught instanceof Error ? caught.message : "Packaging request failed.";
            setError(message);
            addMessage("assistant", `Submission failed: ${message}`);
            emitConversationEvent("submission-failed", { error: message });
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
                        <span>Built with awareness. Deployed with precision. Delivered with confidence</span>
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
                        <p className="section-kicker">Detected Input Packages</p>
                        <h2 className="section-title">{inputCandidates.length}</h2>
                        <p className="section-subtitle">We found ready-to-process packages from Agent 3 workspace..</p>
                    </div>
                </aside>
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
