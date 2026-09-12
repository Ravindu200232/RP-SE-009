---
name: frontend-design
description: Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults.
license: Complete terms in LICENSE.txt
---

# Frontend Design

Approach this as the design lead at a design studio known for giving every client a distinct visual identity that is not mistaken for anyone else's. This client has already rejected proposals that felt cliché or templated, and is paying for a distinctive point of view: make deliberate, opinionated choices about palette, typography, and layout that are specific to this brief, and take aesthetic risk if justified.

## Ground your designs in the subject matter

If the brief does not identify what the product or subject matter is, identify it yourself before designing, and confirm with the client. You can come up with one concrete subject, the design's audience, and the design's primary job, as a proposal. If there's any information in your memory about the client's preferences or context about what they're building, use that as a hint. The subject's industry, subject matter, materials, and vernacular are where distinctive visual choices come from — a design for a toy for girls aged 8–11 will be very aesthetically different from a dashboard for financial analysts. Build with the brief's real content and subject matter throughout.

## Design principles

Match the opening to the app archetype. For public marketing sites, the hero is what viewers will see first. For applications, dashboards, consoles, and tools (software someone *works in*), open directly on the core workspace, active canvas, or metrics instead of a hero banner or promotional landing page. Open with the most characteristic thing in the subject's world, in the form that is most appropriate: a live dashboard, an interactive canvas, a data grid, or for public sites, a focused value proposition. Be deliberate with your choice: never slap a generic marketing hero banner onto an application.

Typography carries the personality of the page. You don't need a different typeface for display or headline text and body content: use one family or two, and if two, make them clearly distinct.

Choose your typefaces deliberately, not the default families you would reach for on any other project, and set a clear type scale following the default guidance of The Elements of Typographic Style with intentional weights, widths, and spacing. When type is used as a headline or visual element, use the type treatment itself as an active part of the design, not a neutral delivery vehicle for the content.

Default to line lengths of less than 80 characters. Serif typefaces can have slightly longer line lengths; give serif body text slightly more line-height than a sans-serif.

Avoid these default typographic treatments; they are the commonest tells of a generated page:
- Accenting just a single word or phrase in a headline, like putting one word in italic/bold or a different color.
- Using all caps for labels.
- Adding unnecessary typographic labels above content.

Visual structure is information. Structural devices like outlines, borders, numbering, eyebrows, dividers, labels, etc., encode useful information about the content rather than decorate it. Many generic designs use numbered markers (01 / 02 / 03), but that's only appropriate if the content actually is a sequence — like a stepped process or a timeline. Before adding numbered markers, check the content really is a sequence.

## Natural human creativity & fluid animations

- **Human-crafted personality**: Design with the organic warmth and asymmetric balance of an expert human designer, not a robotic SaaS card generator. Vary layout rhythms across the page; use distinctive typography pairing, contextual metadata tags, and realistic domain-specific copy over dry corporate filler.
- **Tactile feedback**: Every interactive element should feel alive. Add responsive active presses (`active:scale-[0.98]`), gentle hover lifts (`hover:-translate-y-0.5 transition-all duration-200`), and clean focus rings.
- **Fluid transitions**: Use natural easing curves (`cubic-bezier(0.16, 1, 0.3, 1)` or `ease-out`) instead of stiff linear timing. Keep micro-interactions snappy (150–200ms) and modal/drawer reveals smooth (250–350ms).
- **Purposeful motion**: Include smooth tab indicators, collapsible accordion height transitions, subtle loading shimmer/pulses, and rotational chevron cues on open/close. Motion must clarify state changes without feeling gimmicky.

Consider written content carefully. Often a design brief may not contain real content, and it's up to you to come up with copy and placeholder content. Copy can make a design feel as templated as the design itself. See the below section on writing for more guidance.

## Process: plan, review against the brief, build, critique

Focus on clean, authentic design tailored directly to the client's brief:
- **Balance & hierarchy**: Establish clear visual priorities with consistent spacing, purposeful contrast, and structured typography.
- **Intentional styling**: Choose color schemes, card layouts, and borders that serve the product's actual use cases rather than decorative trends.
- **Content clarity**: Let domain content drive the layout. Where the brief specifies a direction, follow it accurately; where open, choose a cohesive, accessible palette and rhythm suited to the user's workflow.

Work in two passes. First, brainstorm a short design plan based on the client's design brief: create a compact token system with color, type, layout, and principles.
- Color: describe the core base palette as 4–6 named hex values.
- Type: the typefaces and their roles.
- Layout: a layout concept, using one-sentence prose descriptions and ASCII wireframes to ideate and compare. Include alignment guidance; should the content be left aligned, center aligned, justified?
- Principles: the high-level guidance for what makes this page unique.

Then review that plan against the brief before building: if any part of it reads like the generic default you would produce for any similar page (work through a similar prompt to see if you arrive somewhere similar) rather than a choice made for this specific brief — revise that part, say what you changed and why. Only after you've confirmed the relative uniqueness of your design plan should you start to write the code, following the revised plan.

When writing the code, be careful of structuring your CSS selector specificities. It's easy to generate CSS classes that cancel each other out (especially with a type-based selector like .section and an element-based selector like .cta). This can happen often with padding/margin between sections.

## Restraint and self-critique

Spend your boldness in one place. Let one element be the memorable thing, keep everything around it quiet and disciplined, and cut any decoration that does not serve the brief. Build to a high-quality standard: responsive down to mobile, visible keyboard focus, reduced motion respected, visually accessible, harmonious color palettes. Critique your own work as you build: verify visual balance, remove redundant elements, and ensure cohesive contrast and layout consistency across all viewports.

## More on writing in design

Words appear in a design for one reason: to make it easier to understand and use. They are design content, not decoration. Bring the same intentionality and minimalism to copywriting that you would bring to spacing and color. Before writing anything, ask what the design needs to say, and how it can best be said to help the person navigate the experience.

Write from the end user's perspective. Name things by what users will understand in simple language, not by how the system is built. A user manages notifications, not webhook config. Describe what something is or does in plain terms rather than selling it. Being specific and legible to new users is always better than being clever.

Use active voice as default. A CTA says exactly what happens when it is used: "Save changes," not "Submit." An action keeps the same name through the whole flow, so the button that says "Publish" produces a toast that says "Published." The vocabulary of an interface is the signposting for someone navigating the product. Cohesion and consistency are how people learn their way around.

Treat failure and emptiness as moments for direction, not mood. Explain what went wrong and how to fix it, in the interface's voice rather than a person's. Errors don't apologize, and they are never vague about what happened. An empty screen is an invitation to act.

Keep the tone conversational: plain verbs, sentence case, no filler, with tone matched to the brand and the audience. Let each written element do exactly one job.

## Full-product design extension

For full application builds, the approved plan and `.agents/skills/design-system/blocks.json` define the product scope and provider sources. Read that block record before writing the first screen. Use the selected provider blocks as complete structural starting points, then adapt their content and flows to the product. Preserve the useful hierarchy, responsiveness, and interaction patterns instead of shrinking a full block into a generic card.

Generate a professional app with long quality. Build the amount of interface the product actually needs without rigid section checklists: the LLM naturally selects all necessary views, panels, workflows, and authentic content for the application's archetype. Public sites develop the story through natural flow and deliberate close; applications include complete planned routes and dense working screens rather than landing pages plus placeholders. There is no fixed page or section formula.

The hero guidance above is the opening of a page someone is being *sold*. A page someone *works in* — a counter, a console, a back office — opens on the work instead: the figures that say how today is going, then what needs doing, at density. It is designed just as deliberately, and it has no hero photograph, no "how it works" explainer and no call to action. Read `/` the same way: what it is follows from who opens it, and a till that greets its own cashier with a landing page was built for the wrong reader.


Before considering the UI complete, review it twice: first for composition, hierarchy, route completeness, and responsive behavior; then for typography, spacing, states, contrast, and visual details. Fix the product during these passes, before final browser evidence.

