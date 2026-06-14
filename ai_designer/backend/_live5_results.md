# 5-App Live Validation — Final Accuracy Loop

## V2 PIPELINE (Next.js full-stack) — E2E PROOF: prj_0720bef1 (hospital)
- Phases worked: pages(~1min) -> images(13/13) -> qa("plan and build match; no duplicate
  images; copy complete") -> next build OK -> done -> studio auto-revealed running app
  (gated preview confirmed: "Image generating..." shown, no preview until done)
- DB: users 4, PatientProfile 10, Appointment 10, DoctorProfile 3, Prescription 3
- REAL API login (admin@example.com) -> Admin; API CRUD list/create/delete WORKS (10->11->10)
- 10/10 app routes render (4 entity lists, doctor+nurse workspaces, notif/profile/settings/dash)
- All landing images :ok and DISTINCT; create form renders (6 fields); delete dialog opens
- V2 audit verdict: ZERO defects.

## V2 round 2 — gym prj_f09cd753 + hospital re-run prj_74ba9d42
- gym: build FAILED on apostrophe in metadata ("GymFit's") -> agent fix `_meta_safe`
  (typographic quotes) + layout.jsx in build-retry regex; app repaired+rebuilt: done.
- hospital re-run: proved VARIETY (slate+Lexend vs run1) and MONGO (Atlas db
  'prj_74ba9d42' seeded, name=project id; local DNS blocks SRV -> public-DNS fix
  baked into db.js/seed.mjs). BUT planning extraction failed once (GPU contention
  during qwen load) -> generic Item entities -> agent fix: 3x retry w/ backoff.
- hospital #3 prj_eb1e47b6: degraded too -> ROOT CAUSE: OLLAMA WAS DOWN (connection
  refused, all retries instant-fail) -> agent fix: `ensure_ollama()` self-healing
  guard (auto-starts `ollama serve`) at the top of every generation.
- hospital #4 prj_50dbecd4: FULL PROOF, ZERO DEFECTS. Real entities (PatientProfile
  + fields), 4th distinct design (creative-dark, lime, Plus Jakarta Sans), 13/13
  images, Atlas db 'prj_50dbecd4' seeded (4 entities + users), real login -> Admin,
  Mongo-backed CRUD via app API verified live (n -> n+1 -> n), build green, gated
  preview revealed the running app. Screenshot: dark lime landing w/ ward photo.

## V2 round 3 — restaurant prj_f3108168 + school prj_7b7f168e
- restaurant: real entities (MenuItem/Order/Table/Reservation), 5th distinct design
  (violet + Bricolage Grotesque), 13/13 images, build green, CRUD via API WORKS.
  BUG CAUGHT: transient Atlas failure left Mongo seeded EMPTY (login 401, blank
  lists masked by JSON-fallback logic) -> agent fix: seed result VERIFIED ("SEED:
  ok"), 3x retry, else .env.local removed so the app runs fully on JSON. Restaurant
  re-seeded manually: login 200, 12 menu items live from Atlas.
- school prj_7b7f168e: done, 13/13 images, real entities (Course/Student/Assignment/
  Grade), 6th distinct design (fuchsia + Rubik). Seeds were thin (3/entity) ->
  agent fix: top-up to >=8 rows from deterministic generator.
- e-commerce prj_f8953eb1: done, ZERO defects. Product/Order/Customer/Category,
  7th distinct design (rose + Plus Jakarta), 13/13 images, **seed top-up verified
  (12 rows/entity)**, login 200, 12 products live, 0 broken images.

## 5-DOMAIN SET COMPLETE: hospital, gym, restaurant, school, e-commerce — all
## built green, audited live, every discovered bug fixed at agent level.

## Round 4 additions (user directives):
- SECTION BANK: 11 sections remixed from the user's own projects (CleanMate,
  lms-ui patterns) -> composed landings (validated 5/5 unique + build green).
- KNOWLEDGE BASE: 249 pages of the user's 5 projects indexed; [AGENT: Knowledge]
  matches similar past pages per input, feeds structure hints + design bias.
- RBAC: sidebar filters by logged-in role; workspaces visible only to their role
  (+admin); Settings admin-only; direct-URL access shows a denial card.
- hospital #5 prj_f12f34d6: RBAC VALIDATED LIVE — nurse login: sidebar filtered
  (no Doctor Workspace, no admin Settings); direct /workspace/doctor URL ->
  "No access to this workspace - The Doctor workspace is only visible to Doctors."

## Round 5 — COMPONENT BANK (10 variants x 5 families)
- 10 heroes (section files), 10 nav / 10 dash / 10 list style presets (scaffold,
  via site.styles), 10 footer registry entries; tag-matched per input + anti-repeat.
- Verified: same input twice -> different combos; 10 heroes x compose x hostile
  copy-fill ALL GREEN; scaffold builds green.
- audio shop prj_3199c473 (closing run): Product/Order/Customer/Brand entities,
  styles {nav: accent-top, footer: centered, dash: outline, list: dense}.

Agent build: design library (3 landings + 2 dashboards + pro-table), child page planner,
named fix agents (Button/Popup, Overlap, Completeness, Null-Safety), role workspaces,
icon alias resolver + new icons, 10 images/app (logo..banner), two-round flow
(prototype first, Fooocus images pop in), GPU handoff (`_unload_llm`).

Audit per app: every route renders (no crash/fallback), images :ok with relative paths,
notif dropdown + delete-modal + FAQ probes, text-overlap boxes, seeds realistic,
landing >= 3.5KB with real copy, role workspace pages render.

| # | Domain | Project | Round1 | Routes clean | Images | Probes | Notes |
|---|--------|---------|--------|--------------|--------|--------|-------|
| 1 | Hospital | prj_2ac06c83 | done | 27/27 render (Home+Contact were stubs -> regenerated) | 10/10 | bell WORKS, 12 icons, role pages OK | seeds real; 2 agent bugs found+fixed: (a) 12KB template echo through JSON broke -> COPY-SLOTS system (landing now deterministic, validated ALL GREEN); (b) `<br>` JSX parse error -> auto-close in _clean_code; also url() asset paths normalized + mantis pill flex fix |
| 2 | Gym | - | queued | - | - | - | - |
| 3 | Restaurant | - | queued | - | - | - | - |
| 4 | School LMS | - | queued | - | - | - | - |
| 5 | E-commerce | - | queued | - | - | - | - |

Inputs 2-5 (submit via studio textarea + Enter):
2. A gym and fitness center app. Roles: Admin, Trainer, Member. Manage Members, Classes, Trainers and Membership Plans.
3. A restaurant management system. Roles: Admin, Manager, Waiter. Manage Menu Items, Orders, Tables and Reservations.
4. A school learning management system. Roles: Admin, Teacher, Student. Manage Courses, Students, Assignments and Grades.
5. An e-commerce store admin. Roles: Admin, Seller. Manage Products, Orders, Customers and Categories.

Earlier validated (pre-upgrade builds): prj_b7b234a1 hospital 25/25, prj_b07ec0fb gym 25/25,
prj_5ab4ff7f restaurant 25/25 (landing regenerated 12KB), prj_38e329ac school 24/25→fixed
(charAt hardened in templates), dashboards/lists from library verified working.
