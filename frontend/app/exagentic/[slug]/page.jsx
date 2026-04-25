import { pageIdFromLegacySlug } from "@/components/agentforge/core/page-config";
import { SCREEN_COMPONENTS } from "@/components/agentforge/registry";

export default async function LegacyStudioPage({ params }) {
  const resolved = await params;
  const pageId = pageIdFromLegacySlug(resolved?.slug);
  const Screen = SCREEN_COMPONENTS[pageId] || SCREEN_COMPONENTS.dashboard;

  return <Screen />;
}
