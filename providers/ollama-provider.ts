import type { LLMMessage, LLMResponse } from "@/types";

export class OllamaProvider {
  private baseUrl: string;
  private model: string;
  private resolvedModel?: string;
  private modelsPromise?: Promise<string[]>;

  constructor(baseUrl?: string, model?: string) {
    this.baseUrl = baseUrl || process.env.OLLAMA_BASE_URL || "http://localhost:11434";
    this.model = model || process.env.OLLAMA_MODEL || "llama3.2";
  }

  async chat(messages: LLMMessage[], systemPrompt?: string): Promise<LLMResponse> {
    const start = Date.now();
    const model = await this.resolveModel();
    const allMessages = systemPrompt
      ? [{ role: "system" as const, content: systemPrompt }, ...messages]
      : messages;

    try {
      const res = await fetch(`${this.baseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: allMessages,
          stream: false,
          options: { temperature: 0.1 },
        }),
        signal: AbortSignal.timeout(120000),
      });

      if (!res.ok) {
        throw new Error(`Ollama error: ${res.status} ${await res.text()}`);
      }

      const data = (await res.json()) as { message?: { content: string } };
      return {
        content: data.message?.content ?? "",
        provider: "ollama",
        model,
        latencyMs: Date.now() - start,
      };
    } catch (err) {
      throw new Error(`OllamaProvider: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async isAvailable(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/api/tags`, {
        signal: AbortSignal.timeout(5000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  private async resolveModel(): Promise<string> {
    if (this.resolvedModel) return this.resolvedModel;

    const models = await this.listModels();
    if (models.length === 0) {
      this.resolvedModel = this.model;
      return this.resolvedModel;
    }

    if (models.includes(this.model)) {
      this.resolvedModel = this.model;
      return this.resolvedModel;
    }

    const fallback = this.pickFallbackModel(models) || models[0];
    console.warn(
      `[OllamaProvider] Configured model "${this.model}" is not installed. Falling back to "${fallback}".`
    );
    this.resolvedModel = fallback;
    return this.resolvedModel;
  }

  private async listModels(): Promise<string[]> {
    if (!this.modelsPromise) {
      this.modelsPromise = (async () => {
        try {
          const res = await fetch(`${this.baseUrl}/api/tags`, {
            signal: AbortSignal.timeout(5000),
          });
          if (!res.ok) return [];

          const data = (await res.json()) as {
            models?: Array<{ name?: string; model?: string }>;
          };

          return (data.models || [])
            .map((entry) => entry.name || entry.model || "")
            .filter(Boolean);
        } catch {
          return [];
        }
      })();
    }

    return this.modelsPromise;
  }

  private pickFallbackModel(models: string[]): string | undefined {
    const rankedMatchers = [
      /qwen.*coder/i,
      /codellama/i,
      /deepseek/i,
      /qwen/i,
      /llama/i,
    ];

    for (const matcher of rankedMatchers) {
      const match = models.find((model) => matcher.test(model));
      if (match) return match;
    }

    return models[0];
  }
}
