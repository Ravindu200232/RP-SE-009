import { NextRequest, NextResponse } from "next/server";
import { getRun } from "@/store/run-store";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;
  const { searchParams } = new URL(request.url);
  const file = searchParams.get("file");

  const run = getRun(runId);
  if (!run) {
    return NextResponse.json({ error: "Run not found" }, { status: 404 });
  }

  if (file) {
    const outputRoot = path.resolve(run.outputPath);
    const safePath = path.resolve(outputRoot, file.replace(/\.\./g, ""));
    if (!(safePath === outputRoot || safePath.startsWith(`${outputRoot}${path.sep}`))) {
      return NextResponse.json({ error: "Invalid path" }, { status: 400 });
    }
    if (!fs.existsSync(safePath)) {
      return NextResponse.json({ error: "File not found" }, { status: 404 });
    }

    const content = fs.readFileSync(safePath);
    return new Response(new Uint8Array(content), {
      headers: {
        "Content-Type": getContentType(safePath),
        "Content-Disposition": `inline; filename="${path.basename(safePath)}"`,
        "X-Content-Type-Options": "nosniff",
      },
    });
  }

  // List all artifacts
  const listFiles = (dir: string, rel = ""): string[] => {
    const result: string[] = [];
    if (!fs.existsSync(dir)) return result;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const relPath = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        result.push(...listFiles(path.join(dir, entry.name), relPath));
      } else {
        result.push(relPath);
      }
    }
    return result;
  };

  const files = listFiles(run.outputPath);
  return NextResponse.json({ files, outputPath: run.outputPath });
}

function getContentType(filePath: string): string {
  switch (path.extname(filePath).toLowerCase()) {
    case ".json":
      return "application/json; charset=utf-8";
    case ".html":
      return "text/html; charset=utf-8";
    case ".pdf":
      return "application/pdf";
    case ".txt":
    case ".log":
    case ".js":
    case ".ts":
    case ".tsx":
      return "text/plain; charset=utf-8";
    default:
      return "application/octet-stream";
  }
}
