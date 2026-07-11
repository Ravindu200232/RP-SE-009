import { AnalyzerClient } from "@/components/analyzer/analyzer-client";

export default async function AnalyzerPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  return <AnalyzerClient id={id} initialTab={sp.tab || "srs"} />;
}
