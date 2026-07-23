"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type ProviderId = "github" | "snyk" | "sonarcloud" | "aws" | "vercel";

type IntegrationStatus = {
    provider: ProviderId;
    connected: boolean;
    state: string;
    message: string;
    setup_url: string;
    required_environment: string[];
    command?: string;
};

type IntegrationResponse = { items: IntegrationStatus[] };

type ProviderDefinition = {
    id: ProviderId;
    title: string;
    description: string;
    scopes: string[];
};

const API_BASE = (process.env.NEXT_PUBLIC_AGENT4_API_BASE_URL || "http://127.0.0.1:8004").replace(/\/$/, "");

const providers: ProviderDefinition[] = [
    {
        id: "github",
        title: "Connect GitHub CLI",
        description: "Authenticate the backend machine so Agent 4 can push code and work with GitHub repositories.",
        scopes: ["Repository read/write", "Workflow access", "Organization metadata"],
    },
    {
        id: "snyk",
        title: "Connect Snyk",
        description: "Enable dependency, source-code, container, and infrastructure security scanning.",
        scopes: ["Open-source dependencies", "Snyk Code", "Container and IaC scanning"],
    },
    {
        id: "sonarcloud",
        title: "Connect SonarCloud",
        description: "Enable quality-gate analysis for bugs, vulnerabilities, maintainability, duplication, and coverage.",
        scopes: ["Project analysis", "Quality gates", "Metrics and issues"],
    },
    {
        id: "aws",
        title: "Connect AWS",
        description: "Configure credentials and region for ECS, ECR, and CloudWatch deployment operations.",
        scopes: ["ECS deployment", "ECR publishing", "CloudWatch logs"],
    },
    {
        id: "vercel",
        title: "Connect Vercel",
        description: "Configure a Vercel token for frontend preview and production deployments.",
        scopes: ["Deployments", "Project configuration", "Domain verification"],
    },
];

async function fetchStatuses(): Promise<IntegrationResponse> {
    const response = await fetch(`${API_BASE}/integrations/status`, { cache: "no-store" });
    if (!response.ok) {
        throw new Error(await response.text() || `Status request failed (${response.status})`);
    }
    return response.json() as Promise<IntegrationResponse>;
}

export default function IntegrationAccessCenter() {
    const [statuses, setStatuses] = useState<IntegrationStatus[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [copiedProvider, setCopiedProvider] = useState<ProviderId | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const payload = await fetchStatuses();
            setStatuses(payload.items || []);
        } catch (caught) {
            setError(caught instanceof Error ? caught.message : "Unable to check integrations.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
    }, [refresh]);

    const byProvider = useMemo(
        () => new Map(statuses.map((status) => [status.provider, status])),
        [statuses],
    );

    async function copyCommand(provider: ProviderId, command: string) {
        try {
            await navigator.clipboard.writeText(command);
            setCopiedProvider(provider);
            window.setTimeout(() => setCopiedProvider(null), 1800);
        } catch {
            setError("The browser could not copy the command. Select and copy it manually.");
        }
    }

    function openSetup(status: IntegrationStatus | undefined, fallback: string) {
        const target = status?.setup_url || fallback;
        window.open(target, "_blank", "noopener,noreferrer");
    }

    return (
        <section className="studio-integration-shell">
            <div className="studio-integration-heading">
                <div>
                    <p className="section-kicker">Agent 4 integrations</p>
                    <h2 className="section-title">Connect deployment services</h2>
                    <p className="section-subtitle">
                        These controls now open real setup pages and verify the backend configuration without exposing credentials.
                    </p>
                </div>
                <button type="button" className="secondary-button" onClick={refresh} disabled={loading}>
                    {loading ? "Checking..." : "Recheck connections"}
                </button>
            </div>

            {error ? <div className="studio-summary-note warning">{error}</div> : null}

            <div className="studio-grid studio-grid-requests">
                {providers.map((provider, index) => {
                    const status = byProvider.get(provider.id);
                    const connected = status?.connected === true;
                    const fallbackUrl = provider.id === "github"
                        ? "https://github.com/login/device"
                        : provider.id === "snyk"
                            ? "https://app.snyk.io/account"
                            : provider.id === "sonarcloud"
                                ? "https://sonarcloud.io/account/security"
                                : provider.id === "aws"
                                    ? "https://console.aws.amazon.com/iam/home#/roles"
                                    : "https://vercel.com/account/tokens";

                    return (
                        <article className={`studio-request-card ${connected ? "connected" : index === 0 ? "featured" : ""}`} key={provider.id}>
                            <div className="studio-request-head">
                                <div>
                                    <p className="studio-request-step">Access Request {index + 1} of {providers.length}</p>
                                    <h3>{provider.title}</h3>
                                </div>
                                <span className={`badge ${connected ? "badge-pass" : "badge-warn"}`}>
                                    {loading && !status ? "CHECKING" : connected ? "CONNECTED" : status?.state || "SETUP REQUIRED"}
                                </span>
                            </div>

                            <p className="studio-request-host">{status?.setup_url || fallbackUrl}</p>
                            <p className="studio-request-copy">{provider.description}</p>

                            <div className="studio-scope-list">
                                {provider.scopes.map((scope) => (
                                    <div className="studio-scope-item" key={scope}>✓ {scope}</div>
                                ))}
                            </div>

                            <p className="studio-request-note">
                                {status?.message || "Open the provider setup page, configure credentials, then recheck the connection."}
                            </p>

                            {status?.required_environment?.length ? (
                                <div className="code-view">
                                    <pre>{status.required_environment.join("\n")}</pre>
                                </div>
                            ) : null}

                            {status?.command ? (
                                <div className="code-view">
                                    <pre>{status.command}</pre>
                                </div>
                            ) : null}

                            <div className="button-stack">
                                <button
                                    type="button"
                                    className="primary-button"
                                    onClick={() => openSetup(status, fallbackUrl)}
                                >
                                    {connected ? "Open provider" : "Allow Access / Setup"}
                                </button>

                                {status?.command ? (
                                    <button
                                        type="button"
                                        className="ghost-button"
                                        onClick={() => copyCommand(provider.id, status.command || "")}
                                    >
                                        {copiedProvider === provider.id ? "Copied" : "Copy CLI command"}
                                    </button>
                                ) : null}

                                <button type="button" className="secondary-button" onClick={refresh} disabled={loading}>
                                    Verify
                                </button>
                            </div>
                        </article>
                    );
                })}
            </div>
        </section>
    );
}
