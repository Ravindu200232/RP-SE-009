/**
 * Design direction for generated apps.
 *
 * There is NO permanent design template and NO seeded palette here. The model
 * acts as the product designer for each app: it invents its OWN cohesive visual
 * identity (colors, fonts, radius, vibe) and implements it directly in
 * app/globals.css (Tailwind v4 @theme tokens) + consistent usage on every page.
 * This direction text is injected into every build step's system prompt, so the
 * app-to-app variety comes from the model's own choices, not anything we hardcode.
 */
export function designDirection(): string {
  return `DESIGN — act as the product designer for THIS app. Invent a cohesive, distinctive visual identity that suits the app's domain and audience, and IMPLEMENT it yourself (do not ask; do NOT default to generic gray/blue):
- app/globals.css: keep \`@import "tailwindcss";\` as the FIRST line, then add a \`@theme { … }\` block defining YOUR OWN tokens — a deliberate --color-primary / --color-accent / --color-bg / --color-surface / --color-fg / --color-border, plus --font-* and --radius-* — and any base body/heading styles.
- Use those tokens consistently on EVERY page via Tailwind utilities (bg-*, text-*, border-*, rounded-*), with tasteful spacing, clear hierarchy and hover/focus states.
Make it look like ONE intentional, branded product. Two different apps must look clearly different.`;
}
