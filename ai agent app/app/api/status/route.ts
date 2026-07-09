import { checkOllama } from '@/lib/llm/ollama';
import { connectDB } from '@/lib/db/mongoose';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const ollama = await checkOllama();

  let db: { connected: boolean; error?: string } = { connected: false };
  try {
    await connectDB();
    db = { connected: true };
  } catch (e) {
    db = { connected: false, error: e instanceof Error ? e.message : String(e) };
  }

  return Response.json({ ollama, db });
}
