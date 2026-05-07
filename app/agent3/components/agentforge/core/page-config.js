export const PAGE_ROUTES = {
  dashboard: "/dashboard",
  "new-project": "/new-project",
  agent1: "/agent1",
  "design-selector": "/design-selector",
  agent2: "/agent2",
  agent3: "/agent3",
  agent4: "/agent4",
  artifacts: "/artifacts",
  versions: "/versions",
  memory: "/memory",
  settings: "/settings",
  "project-history": "/project-history",
};

export const VALID_PAGE_IDS = new Set(Object.keys(PAGE_ROUTES));

export function pageIdFromLegacySlug(slug) {
  const value = decodeURIComponent(Array.isArray(slug) ? slug.join("/") : slug || "").trim();
  if (!value || value === "AgentForge Studio.html") return "dashboard";

  const normalized = value.replace(/\.html$/i, "").replace(/\s+/g, "-").toLowerCase();
  return VALID_PAGE_IDS.has(normalized) ? normalized : "dashboard";
}
