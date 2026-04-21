import { NextRequest, NextResponse } from "next/server";
import { getRun } from "@/store/run-store";
import fs from "fs";
import path from "path";
import archiver from "archiver";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;
  const { searchParams } = new URL(request.url);
  const type = searchParams.get("type") || "json";

  const run = getRun(runId);
  if (!run) {
    return NextResponse.json({ error: "Run not found" }, { status: 404 });
  }

  if (type === "zip") {
    const zipBuffer = await createZip(run.outputPath);
    return new Response(new Uint8Array(zipBuffer), {
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="agent3-report-${runId.substring(0, 8)}.zip"`,
      },
    });
  }

  const reportFile = resolveReportFile(run.outputPath, type);
  if (!reportFile || !fs.existsSync(reportFile.path)) {
    return NextResponse.json({ error: "Requested report is not available yet" }, { status: 404 });
  }

  const content = fs.readFileSync(reportFile.path);
  return new Response(new Uint8Array(content), {
    headers: {
      "Content-Type": reportFile.contentType,
      "Content-Disposition": `attachment; filename="agent3-report-${runId.substring(0, 8)}.${reportFile.extension}"`,
    },
  });
}

function resolveReportFile(outputPath: string, type: string): {
  path: string;
  contentType: string;
  extension: string;
} | null {
  switch (type) {
    case "json":
      return {
        path: path.join(outputPath, "reports", "final_agent3_report.json"),
        contentType: "application/json; charset=utf-8",
        extension: "json",
      };
    case "pdf":
      return {
        path: path.join(outputPath, "pdf", "agent3_report.pdf"),
        contentType: "application/pdf",
        extension: "pdf",
      };
    case "html":
      return {
        path: path.join(outputPath, "html", "report.html"),
        contentType: "text/html; charset=utf-8",
        extension: "html",
      };
    default:
      return null;
  }
}

async function createZip(outputPath: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    const archive = archiver("zip", { zlib: { level: 6 } });
    archive.on("data", (chunk: Buffer) => chunks.push(chunk));
    archive.on("end", () => resolve(Buffer.concat(chunks)));
    archive.on("error", reject);
    archive.directory(outputPath, false);
    archive.finalize();
  });
}
