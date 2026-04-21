import type { LLMMessage, LLMResponse } from "@/types";

export class GLMCloudProvider {
  private apiKey: string;
  private baseUrl: string;
  private model: string;

  constructor(apiKey?: string, baseUrl?: string, model?: string) {
    this.apiKey = apiKey || process.env.GLM_API_KEY || "";
    this.baseUrl = baseUrl || process.env.GLM_BASE_URL || "https://open.bigmodel.cn/api/paas/v4";
    this.model = model || process.env.GLM_MODEL || "glm-4-flash";
  }

  async chat(messages: LLMMessage[], systemPrompt?: string): Promise<LLMResponse> {
    if (!this.apiKey) throw new Error("GLM_API_KEY not configured");
    const start = Date.now();

    const allMessages = systemPrompt
      ? [{ role: "system" as const, content: systemPrompt }, ...messages]
      : messages;

    try {
      const res = await fetch(`${this.baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          model: this.model,
          messages: allMessages,
          temperature: 0.1,
          max_tokens: 4096,
          stream: false,
        }),
        signal: AbortSignal.timeout(120000),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`GLM error: ${res.status} ${errText}`);
      }

      const data = (await res.json()) as {
        choices?: Array<{ message?: { content: string } }>;
        usage?: { total_tokens: number };
      };

      return {
        content: data.choices?.[0]?.message?.content ?? "",
        provider: "glm_cloud",
        model: this.model,
        tokensUsed: data.usage?.total_tokens,
        latencyMs: Date.now() - start,
      };
    } catch (err) {
      throw new Error(`GLMCloudProvider: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  isAvailable(): boolean {
    return Boolean(this.apiKey);
  }
}
