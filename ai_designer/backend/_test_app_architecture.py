"""App-architecture regression tests (mega-prompt Parts A, B, E, F + genome-driven structure).

Verifies the UNIVERSAL app-generation + intelligent-editing pieces:
  A  App Understanding  - any prompt -> a category (+domain), unknown -> 'custom'.
  B  Design Genome      - same prompt twice => STRUCTURALLY different; N prompts all
                          distinct (anti-similarity); genome is persisted + history grows.
  G  Genome DRIVES code - genome axes map to real scaffold knobs (nav/dash/dashLayout/list/
                          appNav + per-entity crud_layout + section order); site.js carries
                          them; the scaffold consumes them; a genome-driven app BUILDS.
  D  Domain modeler     - unknown/custom prompt still yields entities/fields/workflows/pages.
  E  Target property    - "fill/box/card/button color" -> background; "text" -> text
                          colour; "border" -> border (role-aware, explicit word wins).
  F  Selection-aware add-section - lands BEFORE/AFTER/INSIDE the selected anchor;
                          footer-fallback only when no anchor; invalid JSX auto-reverts.
  I  Intent confidence  - a low-confidence ambiguous edit asks to clarify, never guesses.

No GPU/Ollama/network needed. A real `next build` runs unless FAST=1 (or 'fast' arg).
Run:  python _test_app_architecture.py            (full, includes one build)
      python _test_app_architecture.py fast       (skip the build)
"""
import os, sys, re, glob, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import design_genome as dg
from app import design_research, editor, inspiration_library, nextgen, page_sections

FAST = "fast" in sys.argv or os.getenv("FAST") == "1"
RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def classes(prompt, tag):
    return editor.nl_to_classes(prompt, tag)[0]


def main():
    print("=" * 70)
    print("APP ARCHITECTURE (understanding + genome + fill-vs-text + add-section)")
    print("=" * 70)

    # ---------------- PART A: App Understanding ----------------
    print("-- Part A: app understanding --")
    known = {
        "a hospital patient records and appointment system": "healthcare",
        "an online marketplace for handmade goods with sellers": "marketplace",
        "a school LMS with courses, students and exams": "education",
        "a loan and invoice tracker for a microfinance bank": "finance",
        "a warehouse inventory and supplier stock system": "inventory",
    }
    good = 0
    for prompt, cat in known.items():
        u = dg.infer_app_understanding(prompt)
        good += 1 if u["app_category"] == cat else 0
    rec("known prompts classify to the right category (>=4/5)", good >= 4, f"{good}/5")

    u_custom = dg.infer_app_understanding("a beehive honey harvest and queen-bee lineage tracker")
    rec("unknown prompt -> 'custom' with a non-empty inferred domain",
        u_custom["app_category"] == "custom" and len(u_custom["domain"].strip()) > 0,
        f"domain={u_custom['domain']!r}")
    rec("understanding always carries public_vs_private + complexity",
        u_custom["public_vs_private"] in ("internal", "public", "hybrid")
        and u_custom["app_complexity"] in ("simple", "medium", "advanced"),
        f"{u_custom['public_vs_private']}/{u_custom['app_complexity']}")

    # ---------------- PART B: Design Genome ----------------
    print("-- Part B: design genome --")
    same = "a clinic appointment booking app"
    sigs = {dg.genome_signature(dg.make_genome(same)) for _ in range(5)}
    rec("SAME prompt twice => structurally DIFFERENT genome (>=4/5 distinct)",
        len(sigs) >= 4, f"{len(sigs)}/5 unique")

    prompts = ["a hotel booking site", "a fintech loan dashboard", "an internal CRM for sales",
               "a food-blog CMS", "a community forum for gamers"]
    hist, fp_sigs = [], []
    for p in prompts:
        g = dg.make_genome(p, history=hist)
        hist.append(g)
        fp_sigs.append(dg.genome_signature(g))
    rec("5 different prompts => 5 DISTINCT structural signatures (anti-similarity)",
        len(set(fp_sigs)) == 5, f"{len(set(fp_sigs))}/5 unique")

    with tempfile.TemporaryDirectory() as td:
        out_dir = os.path.join(td, "prj_demo")
        os.makedirs(out_dir)
        g1 = dg.write_genome(out_dir, "a telehealth video clinic", base_dir=td)
        loaded = dg.load_genome(out_dir)
        hist_after = dg.load_history(td)
        rec("genome is persisted to _design_genome.json + readable back",
            loaded is not None and loaded.get("app_seed") == g1.get("app_seed")
            and os.path.exists(os.path.join(out_dir, dg.GENOME_FILE)), g1.get("layout_family"))
        rec("genome signature appended to shared _genome_history.json", len(hist_after) >= 1,
            f"history={len(hist_after)}")

    # category bias is VISIBLE (finance leans enterprise/analytics) but never the sole option
    fin = [dg.make_genome("a finance analytics platform") for _ in range(40)]
    biased = sum(1 for g in fin if g["visual_style"] in ("enterprise", "premium-dark")
                 or g["dashboard_style"] in ("analytics", "kpi-cards"))
    varied = len({dg.genome_signature(g) for g in fin})
    rec("category bias is visible yet still varied (finance: biased>=8 & many distinct)",
        biased >= 8 and varied >= 20, f"biased={biased}/40, distinct={varied}/40")

    # ---------------- PART C: curated inspiration library ----------------
    print("-- Part C: curated inspiration library --")
    required = {"name", "url", "category", "design_family", "hero_patterns", "navigation_patterns",
                "section_patterns", "card_patterns", "typography_style", "spacing_style",
                "color_palette_family", "image_strategy", "CTA_patterns", "footer_patterns",
                "best_for_domains"}
    refs = inspiration_library.CURATED_REFERENCES
    rec("curated library contains 100 complete metadata-only references",
        len(refs) == 100 and all(required <= set(r) for r in refs),
        f"{len(refs)} references")

    expected = {
        "hospital management website": ("healthcare-trust-saas", ("SaaS", "Finance", "POS")),
        "vehicle sales website with inventory and financing": ("ecommerce-product", ("Ecommerce",)),
        "POS inventory app for restaurants": ("operational-business", ("POS", "SaaS")),
        "portfolio site for a creative agency": ("creative-agency", ("Portfolio", "Marketing")),
        "AI developer tool landing page": ("ai-devtools", ("AI", "SaaS")),
        "fintech wallet and invoice dashboard": ("fintech-trust", ("Finance", "SaaS")),
        "online course platform for students": ("education-media", ("Education", "Marketing")),
    }
    picked = {}
    for prompt, (family, category_bits) in expected.items():
        ins = inspiration_library.select_curated_inspiration(prompt)
        picked[prompt] = ins
        cats = [r["category"] for r in ins["selected_inspirations"]]
        rec(f"inspiration: {family} selected for {prompt[:18]}...",
            ins["inspiration_family"] == family and any(any(bit in c for bit in category_bits) for c in cats),
            f"{ins['inspiration_family']} / {cats[:3]}")

    fams = {ins["inspiration_family"] for ins in picked.values()}
    rec("generated inspiration_family differs across domains", len(fams) >= 6, sorted(fams))

    genomes = [dg.make_genome(p) for p in expected]
    visual_sigs = {dg.visual_structure_signature(g, dg.genome_to_styles(g), dg.genome_crud_layouts(g, 3)) for g in genomes}
    rec("inspiration changes visual_structure_signature across domains",
        len(visual_sigs) >= 6, f"{len(visual_sigs)}/7")

    g_h = dg.make_genome("hospital management website")
    g_v = dg.make_genome("vehicle sales website with inventory and financing")
    src_h = page_sections.compose_marketing_page({"name": "Home", "slug": "home", "template": "content"},
                                                 {"domain": "hospital management"}, 0, "CareOS", False, [],
                                                 dg.genome_visual_composition(g_h))
    src_v = page_sections.compose_marketing_page({"name": "Home", "slug": "home", "template": "content"},
                                                 {"domain": "vehicle sales"}, 0, "AutoDesk", False, [],
                                                 dg.genome_visual_composition(g_v))
    leak_terms = []
    for r in (g_h.get("selected_inspirations") or []) + (g_v.get("selected_inspirations") or []):
        leak_terms.extend([r.get("name", ""), r.get("url", "")])
    rec("inspiration affects generated JSX hero/cards/sections",
        src_h != src_v and "data-inspiration-family" in src_h and "data-page-card-style" in src_h,
        f"{g_h.get('inspiration_family')} vs {g_v.get('inspiration_family')}")
    rec("generated page JSX does not include copied reference names or URLs",
        all((not t) or (t not in src_h and t not in src_v) for t in leak_terms),
        f"checked={len(leak_terms)} terms")

    old_env = {k: os.environ.get(k) for k in (
        "DESIGN_RESEARCH_ENABLED", "DESIGN_INSPIRATION_MODE", "DESIGN_SEARCH_PROVIDER",
        "DESIGN_SEARCH_API_KEY", "DESIGN_GOOGLE_CSE_ID", "DESIGN_RESEARCH_MAX_RESULTS",
        "DESIGN_RESEARCH_TIMEOUT_SECONDS")}
    try:
        os.environ["DESIGN_RESEARCH_ENABLED"] = "false"
        os.environ["DESIGN_INSPIRATION_MODE"] = "curated"
        off = inspiration_library.select_inspiration("AI developer tool landing page")
        os.environ["DESIGN_RESEARCH_ENABLED"] = "true"
        os.environ["DESIGN_INSPIRATION_MODE"] = "hybrid"
        os.environ["DESIGN_SEARCH_PROVIDER"] = "serpapi"
        os.environ.pop("DESIGN_SEARCH_API_KEY", None)
        fail = inspiration_library.select_inspiration("AI developer tool landing page")
        os.environ["DESIGN_SEARCH_PROVIDER"] = "google"
        os.environ["DESIGN_SEARCH_API_KEY"] = "test-key-redacted"
        os.environ.pop("DESIGN_GOOGLE_CSE_ID", None)
        google_missing_cx = design_research.fetch_online_design_dna("hospital management website")
        os.environ["DESIGN_SEARCH_PROVIDER"] = "local"
        local_online = inspiration_library.select_inspiration("online course platform")
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    rec("generation works with online research disabled", off["mode"] == "curated" and off["selected_inspirations"])
    rec("online research failure falls back to curated DNA",
        fail["selected_inspirations"] and not fail.get("online_research", {}).get("ok"),
        fail.get("online_research", {}).get("reason", ""))
    rec("google design search requires DESIGN_GOOGLE_CSE_ID and fails clearly",
        not google_missing_cx.get("ok")
        and google_missing_cx.get("reason") == "Google search disabled: missing DESIGN_GOOGLE_CSE_ID"
        and google_missing_cx.get("provider") == "google",
        google_missing_cx.get("reason", ""))
    rec("hybrid local research merges abstract DNA when online path succeeds",
        local_online.get("mode") == "hybrid"
        and local_online.get("online_research", {}).get("ok")
        and local_online.get("online_research", {}).get("queries"),
        local_online.get("online_research", {}).get("provider", ""))

    # ---------------- PART E: target property (fill vs text vs border) ----------------
    print("-- Part E: fill-vs-text target --")
    rec("'change box fill color to blue' on a div -> BACKGROUND",
        "bg-blue-500" in classes("change box fill color to blue", "div"))
    rec("'card color red' on a div -> BACKGROUND (not text)",
        "bg-red-500" in classes("card color red", "div"))
    rec("'make button blue' on a button -> BACKGROUND",
        "bg-blue-500" in classes("make button blue", "button"))
    rec("'make text red' on a paragraph -> TEXT colour",
        "text-red-500" in classes("make text red", "p"))
    rec("'change the border color to green' -> BORDER colour",
        "border-green-500" in classes("change the border color to green", "div"))
    rec("explicit 'button text white' overrides container default -> TEXT",
        "text-white" in classes("make the button text white", "button"))

    # ---------------- PART F: selection-aware add-section ----------------
    print("-- Part F: selection-aware add-section --")
    PID = "prj_iv_school"
    pg = os.path.join("output", PID, "src", "app", "(marketing)", "page.jsx")
    if not os.path.isfile(pg):
        rec("selection-aware add-section (skipped: prj_iv_school marketing page missing)", True, "skipped")
    else:
        orig = open(pg, encoding="utf-8").read()
        m = re.search(r">([A-Za-z][A-Za-z ]{6,40})<", orig)
        anchor = m.group(1).strip() if m else None
        orig_freeform = page_sections.freeform_section
        page_sections.freeform_section = lambda prompt, app_name="": (
            '\n      <section className="mx-auto max-w-5xl px-6 py-16">\n'
            '        <h2 className="font-display text-3xl font-bold">Architecture Test Section</h2>\n'
            '        <p className="mt-3 max-w-2xl text-muted-foreground">Deterministic test section.</p>\n'
            '      </section>\n')

        def land(**kw):
            r = editor.add_section(PID, "home", "a pricing band with three tiers", **kw)
            after = open(pg, encoding="utf-8").read()
            valid = editor._validate(pg)[0]
            open(pg, "w", encoding="utf-8").write(orig)          # always restore
            return r, after, valid

        # after the selected anchor (lands between the anchor and the footer)
        r, after, valid = land(insert_position="after", selected_text=anchor)
        foot = min([x for x in (after.find("FOOTER"), after.find("<footer"), after.find("Footer")) if x != -1]
                   or [len(after)])
        ai = after.find(anchor) if anchor else -1
        rec("anchor found -> placement 'after-selected', valid JSX, between anchor & footer",
            r.get("ok") and r.get("placement") == "after-selected" and valid and (ai == -1 or ai < foot),
            r.get("placement"))

        # before the selected anchor
        r2, _, valid2 = land(insert_position="before", selected_text=anchor)
        rec("insert_position 'before' -> placement 'before-selected', valid JSX",
            r2.get("ok") and r2.get("placement") == "before-selected" and valid2, r2.get("placement"))

        # inside the selected anchor (or graceful 'after' if it has no closing tag)
        r_in, _, valid_in = land(insert_position="inside", selected_text=anchor)
        rec("insert_position 'inside' -> placed inside/after the anchor, valid JSX",
            r_in.get("ok") and r_in.get("placement") in ("inside-selected", "after-selected") and valid_in,
            r_in.get("placement"))

        # NO anchor -> footer fallback (logged), still valid
        r3, _, valid3 = land(insert_position="after", selected_text=None)
        rec("no anchor -> footer/wrapper fallback (logged) + valid JSX",
            r3.get("ok") and r3.get("placement", "").endswith("fallback") and valid3, r3.get("placement"))

        # invalid JSX -> auto-revert, file unchanged
        orig_validate = editor._validate
        editor._validate = lambda p: (False, "forced failure")
        try:
            r4 = editor.add_section(PID, "home", "x", insert_position="after", selected_text=anchor)
        finally:
            editor._validate = orig_validate
        rec("invalid section -> reverted, source file unchanged",
            (not r4.get("ok")) and r4.get("reverted") and open(pg, encoding="utf-8").read() == orig,
            r4.get("error"))
        page_sections.freeform_section = orig_freeform

    # ---------------- PART G: genome DRIVES real generated structure ----------------
    print("-- Part G: genome drives structure --")

    # crud_style -> multiple distinct REAL CRUD components
    comps = {dg.genome_to_crud_layout(cs) for cs in dg.CRUD_STYLES}
    rec("different crud_style values -> multiple distinct CRUD components",
        len(comps) >= 4 and {"kanban", "timeline", "split-pane"} <= comps, sorted(comps))

    # navigation_pattern -> both sidebar AND topnav app shells
    orient = {dg.genome_to_styles({"navigation_pattern": p})["appNav"] for p in dg.NAV_PATTERNS}
    rec("navigation_pattern -> both sidebar AND topnav app shells", orient == {"sidebar", "topnav"}, sorted(orient))

    # dashboard_style -> multiple distinct dashboard compositions
    dls = {dg.genome_to_styles({"dashboard_style": d})["dashLayout"] for d in dg.DASHBOARD_STYLES}
    rec("dashboard_style -> multiple distinct dashboard compositions", len(dls) >= 3 and dls <= set(dg.DASH_LAYOUTS), sorted(dls))

    # same prompt twice => different STRUCTURE signature (not just metadata)
    def sig_of(g):
        return dg.structure_signature(g, dg.genome_to_styles(g), dg.genome_crud_layouts(g, 4))
    same_sigs = {sig_of(dg.make_genome("a clinic appointment booking app")) for _ in range(5)}
    rec("same prompt twice => different STRUCTURE signature (>=4/5 distinct)", len(same_sigs) >= 4, f"{len(same_sigs)}/5")

    hist2, struct_sigs = [], []
    for p in ["a hotel booking site", "a fintech loan dashboard", "an internal CRM for sales",
              "a food-blog CMS", "a community forum for gamers"]:
        g = dg.make_genome(p, history=hist2); hist2.append(g)
        struct_sigs.append(sig_of(g))
    rec("5 different prompts => 5 DISTINCT structure signatures", len(set(struct_sigs)) == 5, f"{len(set(struct_sigs))}/5")

    # genome axes land in the generated site.js (the scaffold's single source of truth)
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "src", "lib"))
        g = dg.make_genome("a finance analytics platform"); st = dg.genome_to_styles(g)
        lays = dg.genome_crud_layouts(g, 3)
        ents = [{"name": n, "label": n + "s", "slug": n.lower(), "icon": "Box", "crud_layout": l,
                 "fields": [{"name": "name", "label": "Name", "type": "text"}]} for n, l in zip(["Account", "Invoice", "Client"], lays)]
        nextgen.write_site(td, "Fin", "t", [{"label": "Home", "href": "/"}],
                           [{"label": "Dashboard", "href": "/dashboard", "icon": "Box"}], ents, ["Admin"], st, True)
        site_js = open(os.path.join(td, "src", "lib", "site.js"), encoding="utf-8").read()
        rec("genome axes are written into site.js (nav/dash/dashLayout/list/appNav + crud layouts)",
            all(st[k] in site_js for k in ("nav", "dash", "dashLayout", "list", "appNav"))
            and all(l in site_js for l in lays), f"appNav={st['appNav']}, dash={st['dashLayout']}")

    # the scaffold actually CONSUMES those knobs (real structural effect, not dead metadata)
    dash_src = open("next_scaffold/src/app/(app)/dashboard/page.jsx", encoding="utf-8").read()
    lay_src = open("next_scaffold/src/app/(app)/layout.jsx", encoding="utf-8").read()
    rec("scaffold dashboard reorders blocks by styles.dashLayout (order-* classes)",
        "styles.dashLayout" in dash_src and "DASH_ORDER" in dash_src and "order-1" in dash_src and "order-3" in dash_src)
    rec("scaffold app shell switches sidebar<->topnav by styles.appNav",
        "styles.appNav" in lay_src and "TopNav" in lay_src
        and os.path.isfile("next_scaffold/src/components/shell/TopNav.jsx"))

    # a genome-driven app (topnav + analytics + kanban) really BUILDS
    if FAST:
        rec("genome-driven app (topnav+analytics+kanban) builds (skipped: fast)", True, "fast")
    else:
        pid = "prj_arch_build"; out = os.path.join("output", pid)
        try:
            nextgen.create_project(out)
            g = dg.make_genome("an inventory and supplier stock control system")
            g["navigation_pattern"] = "topnav"; g["dashboard_style"] = "analytics"; g["crud_style"] = "kanban"
            st = dg.genome_to_styles(g); lays = dg.genome_crud_layouts(g, 3)
            ents = [{"name": n, "label": n + "s", "slug": n.lower(), "icon": "Package", "crud_layout": l,
                     "fields": [{"name": "name", "label": "Name", "type": "text"},
                                {"name": "status", "label": "Status", "type": "select", "options": ["Active", "Pending", "Done"]}]}
                    for n, l in zip(["Product", "Supplier", "Order"], lays)]
            sl = [{"label": "Dashboard", "href": "/dashboard", "icon": "LayoutDashboard"}] + \
                 [{"label": e["label"], "href": "/e/" + e["slug"], "icon": "Package"} for e in ents]
            nextgen.write_site(out, "StockPilot", "Run your warehouse", [{"label": "Home", "href": "/"}],
                               sl, ents, ["Admin", "Staff"], st, True)
            nextgen.write_theme(out, "indigo", "Sora", "Inter", "minimal")
            nextgen.write_layout_meta(out, "StockPilot", "Run your warehouse", "", "minimal")
            nextgen.write_db(out, nextgen.generate_seeds({"app_name": "StockPilot", "entities": ents, "roles": ["Admin", "Staff"]}))
            nextgen.seed_placeholder_images(out)
            bok, _bout = nextgen.run_build(out)
            site_js = open(os.path.join(out, "src", "lib", "site.js"), encoding="utf-8").read()
            rec("genome-driven app (topnav+analytics+kanban) BUILDS + site.js carries the structure",
                bok and st["appNav"] in site_js and st["dashLayout"] in site_js and "kanban" in site_js,
                f"build={'ok' if bok else 'FAIL'}")
        finally:
            shutil.rmtree(out, ignore_errors=True)

    # ---------------- PART D: universal domain modeler (unknown prompt) ----------------
    print("-- Part D: domain modeler --")
    dm = dg.infer_domain_model("a beehive honey harvest and queen-bee lineage tracker for beekeepers who sell jars")
    de = dm["entities"]
    rec("unknown/custom prompt -> meaningful entities + fields + workflows + pages",
        len(de) >= 2 and all(e["fields"] for e in de) and dm["workflows"] and dm["pages"],
        f"ents={[e['name'] for e in de]}, wf={dm['workflows']}, pages={dm['pages']}")
    dm2 = dg.infer_domain_model("a warehouse inventory and supplier stock system")
    rec("recognised domain -> category-shaped entities (inventory)",
        any(e["name"] in ("Product", "Supplier", "Order", "Shipment") for e in dm2["entities"]),
        f"ents={[e['name'] for e in dm2['entities']]}")

    # ---------------- PART I: intent-engine confidence gate ----------------
    print("-- Part I: intent confidence --")
    pgc = os.path.join("output", "prj_iv_school", "src", "app", "(marketing)", "page.jsx")
    if not os.path.isfile(pgc):
        rec("low-confidence ambiguous edit asks to clarify (skipped: project missing)", True, "skipped")
    else:
        o2 = open(pgc, encoding="utf-8").read()
        m = re.search(r'className="([^"]{12,40})"', o2); cls = m.group(1) if m else None
        save = editor._llm_edit_plan
        editor._llm_edit_plan = lambda *a, **k: {"action": "layout_update", "confidence": 0.2,
                                                 "clarify": "Did you mean the background or the text colour?"}
        try:
            rc = editor.edit_component("prj_iv_school", "home", "make it pop", tag="div", text=None, class_name=cls)
            after = open(pgc, encoding="utf-8").read()
        finally:
            editor._llm_edit_plan = save
            open(pgc, "w", encoding="utf-8").write(o2)
        rec("low-confidence ambiguous edit -> asks clarification, file UNCHANGED",
            rc.get("needs_clarification") and not rc.get("ok") and after == o2, rc.get("question"))

    print("=" * 70)
    ok = all(RESULTS)
    print(f"APP ARCHITECTURE GREEN  ({sum(RESULTS)}/{len(RESULTS)})" if ok
          else f"FAILURES  ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
