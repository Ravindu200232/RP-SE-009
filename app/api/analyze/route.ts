import { NextRequest, NextResponse } from "next/server";
import { createRun } from "@/store/run-store";
import { runAnalysis } from "@/server/orchestrator";
import type { RunConfig } from "@/types";

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<RunConfig>;

    if (!body.projectPath) {
      return NextResponse.json({ error: "projectPath is required" }, { status: 400 });
    }
    if (!body.srsPath) {
      return NextResponse.json({ error: "srsPath is required" }, { status: 400 });
    }

    const config: RunConfig = {
      projectPath: body.projectPath,
      srsPath: body.srsPath,
      runName: body.runName,
      enableSecurity: body.enableSecurity ?? Boolean(process.env.ENABLE_SEMGREP === "true"),
      enablePerformance: body.enablePerformance ?? Boolean(process.env.ENABLE_K6 === "true"),
      enablePlaywright: body.enablePlaywright ?? Boolean(process.env.ENABLE_PLAYWRIGHT === "true"),
      ollamaBaseUrl: body.ollamaBaseUrl || process.env.OLLAMA_BASE_URL || "http://localhost:11434",
      ollamaModel: body.ollamaModel || process.env.OLLAMA_MODEL || "llama3.2",
      glmApiKey: body.glmApiKey || process.env.GLM_API_KEY,
      glmModel: body.glmModel || process.env.GLM_MODEL || "glm-4-flash",
    };

    const run = createRun(config);

    // Start analysis in background (do NOT await)
    runAnalysis(run.id).catch((err) => {
      console.error(`[Orchestrator] Run ${run.id} failed:`, err);
    });

    return NextResponse.json({ runId: run.id, outputPath: run.outputPath });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
