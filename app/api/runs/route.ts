import { NextResponse } from "next/server";
import { listRuns } from "@/store/run-store";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const runs = listRuns(50);
    return NextResponse.json({ runs });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg, runs: [] }, { status: 500 });
  }
}
