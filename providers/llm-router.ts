import type { LLMMessage, LLMProvider, LLMResponse, RunConfig } from "@/types";
import { OllamaProvider } from "./ollama-provider";
import { GLMCloudProvider } from "./glm-provider";

type TaskComplexity = "simple" | "complex";

const COMPLEX_TASKS = new Set([
  "traceability",
  "missing_feature_detection",
  "gap_reasoning",
  "root_cause",
  "report_synthesis",
  "security_reasoning",
  "integration_reasoning",
]);

export class LLMRouter {
  private ollama: OllamaProvider;
  private glm: GLMCloudProvider;
  private providerLog: Array<{ task: string; provider: LLMProvider; latencyMs: number }> = [];

  constructor(config: Pick<RunConfig, "ollamaBaseUrl" | "ollamaModel" | "glmApiKey" | "glmModel">) {
    this.ollama = new OllamaProvider(config.ollamaBaseUrl, config.ollamaModel);
    this.glm = new GLMCloudProvider(config.glmApiKey, undefined, config.glmModel);
  }

  async chat(
    task: string,
    messages: LLMMessage[],
    systemPrompt?: string
  ): Promise<LLMResponse> {
    const complexity = this.resolveComplexity(task);
    let result: LLMResponse;

    if (complexity === "complex" && this.glm.isAvailable()) {
      try {
        result = await this.glm.chat(messages, systemPrompt);
        this.log(task, "glm_cloud", result.latencyMs);
        return result;
      } catch (err) {
        console.warn(`[LLMRouter] GLM failed for task "${task}", falling back to Ollama:`, err);
      }
    }

    result = await this.ollama.chat(messages, systemPrompt);
    this.log(task, "ollama", result.latencyMs);
    return result;
  }

  async simplePrompt(task: string, prompt: string): Promise<string> {
    const result = await this.chat(task, [{ role: "user", content: prompt }]);
    return result.content;
  }

  private resolveComplexity(task: string): TaskComplexity {
    const taskLower = task.toLowerCase();
    for (const complexTask of COMPLEX_TASKS) {
      if (taskLower.includes(complexTask)) return "complex";
    }
    return "simple";
  }

  private log(task: string, provider: LLMProvider, latencyMs: number): void {
    this.providerLog.push({ task, provider, latencyMs });
  }

  getProviderLog() {
    return [...this.providerLog];
  }
}
