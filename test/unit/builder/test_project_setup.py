"""Skills, templates and the design contract.

These decide what a build starts from, and all three are things the engine does
before the model writes a line. A wrong answer here is expensive: the wrong
skill teaches the wrong conventions, a missing scaffold means twenty boilerplate
files written from memory, and one hard-coded palette means every app the
studio produces looks identical.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test import _support  # noqa: F401
from builder_agent import design
from builder_agent.knowledge import Knowledge
from builder_agent.layout import format_layout, inspect_layout
from builder_agent.skills import (SKILL_ROOT, catalog, install_skill_pack, read_manifest,
                                  read_skill, select)
from builder_agent.config import stack_of
from builder_agent.templates import (_package_name, install_template, is_greenfield,
                                     template_notice, restore_styling)


class SkillPackTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.entries = read_manifest()

    def test_every_manifest_entry_ships_a_skill_directory(self):
        missing = [name for name in self.entries if not (SKILL_ROOT / name / "SKILL.md").is_file()]
        self.assertEqual(missing, [])

    def test_every_dependency_a_skill_declares_actually_exists(self):
        for name, item in self.entries.items():
            for dependency in item["requires"]:
                self.assertIn(dependency, self.entries, f"{name} requires {dependency}")

    def test_the_stack_core_is_always_selected_whatever_the_request_says(self):
        selected = select(self.entries, "", "hello", "nextjs-mongo")
        for name in ("full-app-builder", "nextjs", "mongoose", "vitest", "browser-e2e", "runtime"):
            self.assertIn(name, selected)

    def test_a_skill_belonging_to_another_stack_is_never_selectable(self):
        # An express dependency in a Next.js project must not drag the
        # microservices guidance into the build.
        selected = select(self.entries, "express gateway service", "add an api", "nextjs-mongo")
        for name in ("express", "api-gateway", "mern-microservices"):
            self.assertNotIn(name, selected)

    def test_a_request_that_rules_a_term_out_does_not_get_its_skill(self):
        with_docker = select(self.entries, "", "a mern shop with docker", "mern-microservices")
        without = select(self.entries, "", "a mern shop, no docker", "mern-microservices")

        self.assertIn("docker", with_docker)
        self.assertNotIn("docker", without)

    def test_the_sinhala_forms_studio_users_type_are_understood(self):
        # "docker nathuwa" and "docker epa" both mean "without docker"; the
        # studio's users write them, and ignoring that installs guidance the
        # user has just asked not to have.
        for phrase in ("mern shop docker nathuwa", "mern shop docker epa"):
            self.assertNotIn("docker", select(self.entries, "", phrase, "mern-microservices"),
                             phrase)

    def test_installing_copies_the_selected_skills_into_the_project(self):
        pack = install_skill_pack(self.root, "build a hotel booking app", "nextjs-mongo")

        self.assertEqual(pack.warnings, [])
        self.assertIn("full-app-builder", pack.installed)
        self.assertTrue((self.root / ".agents/skills/full-app-builder/SKILL.md").is_file())
        self.assertIn("unit", pack.phase_skills)

    def test_page_composition_reaches_both_stacks_with_the_design_skill(self):
        """Composition is UI work, so it travels wherever the design does."""
        for stack in ("nextjs-mongo", "mern-microservices"):
            with self.subTest(stack=stack):
                picked = select(self.entries, "", "build a site with pages", stack)
                self.assertIn("page-composition", picked)
                self.assertIn("frontend-design", picked)

    def test_composition_defers_to_the_contract_instead_of_re_deciding_it(self):
        """Two skills that both choose a palette would fight over every build."""
        body = (SKILL_ROOT / "page-composition" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Do not re-open either here", body)
        for owned in ("palette", "corners", "spacing", "motion", "contrast"):
            self.assertIn(owned, body.split("## Make it this product")[0])


    def test_a_project_that_overrides_a_skill_keeps_its_own_version(self):
        target = self.root / ".agents/skills/runtime"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("mine", encoding="utf-8")

        pack = install_skill_pack(self.root, "build an app", "nextjs-mongo")

        self.assertIn("runtime", pack.preserved)
        self.assertEqual((target / "SKILL.md").read_text(), "mine")
        self.assertEqual(read_skill(self.root, "runtime"), "mine")

    def test_an_example_file_is_read_by_the_name_it_would_really_have(self):
        """Sketch files carry a guard suffix; the model asks for the real name.

        `.txt` keeps npm from treating a sketch as a workspace and keeps the
        project's runner from collecting its tests. Asking the model to know
        that would cost a turn every time, so the suffix resolves here.
        """
        install_skill_pack(self.root, "build a nextjs shop", "nextjs-mongo")

        body = read_skill(self.root, "nextjs-sketch", "sketch/test/product.model.test.js")

        self.assertIn("vitest", body)

    def test_a_missing_resource_lists_what_the_skill_does_have(self):
        install_skill_pack(self.root, "build a nextjs shop", "nextjs-mongo")

        with self.assertRaises(ValueError) as caught:
            read_skill(self.root, "nextjs-sketch", "sketch/test/nope.js")

        message = str(caught.exception)
        self.assertIn("has no file", message)
        self.assertIn("SKILL.md", message)
        # Listed by their logical names, not their guarded ones.
        self.assertNotIn(".test.js.txt", message)

    def test_a_resource_path_cannot_escape_the_skill_it_belongs_to(self):
        install_skill_pack(self.root, "build an app", "nextjs-mongo")
        with self.assertRaises(ValueError):
            read_skill(self.root, "runtime", "../../../etc/passwd")

    def test_the_catalog_prefers_the_project_copy_of_a_skill(self):
        install_skill_pack(self.root, "build an app", "nextjs-mongo")
        rows = {row["name"]: row for row in catalog(self.root)}
        self.assertEqual(rows["runtime"]["source"], "project")


class StackTemplateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_an_empty_workspace_gets_the_verified_starting_point(self):
        result = install_template(self.root, "nextjs-mongo")

        self.assertTrue(result.scaffolded)
        self.assertIn("package.json", result.files)
        self.assertIn("vitest.config.js", result.files)
        self.assertIn("Do not rewrite these files from memory", template_notice(result))

    def test_the_root_manifest_takes_the_folder_name_so_npm_can_install_it(self):
        install_template(self.root, "nextjs-mongo")
        self.assertIn(f'"name": "{_package_name(self.root)}"',
                      (self.root / "package.json").read_text(encoding="utf-8"))

    def test_the_notice_says_how_to_replace_what_it_says_to_replace(self):
        """It asks for the placeholder page to be replaced; writeFile refuses that."""
        notice = template_notice(install_template(self.root, "nextjs-mongo"))
        self.assertIn("replace them", notice)
        self.assertIn("overwrite:true", notice)
        self.assertIn("patchFile", notice)

    def test_a_folder_name_npm_would_reject_is_made_installable(self):
        """npm refuses leading dots, capitals and spaces; the folder may have them."""
        for folder, expected in (("My Shop", "my-shop"), ("_draft_", "draft"),
                                 (".hidden", "hidden"), ("plant nursery!", "plant-nursery")):
            with self.subTest(folder=folder):
                workspace = self.root / folder
                workspace.mkdir()
                self.assertEqual(_package_name(workspace), expected)

    def test_a_workspace_that_already_has_a_project_is_never_touched(self):
        (self.root / "package.json").write_text('{"name":"mine"}', encoding="utf-8")

        result = install_template(self.root, "nextjs-mongo")

        self.assertFalse(result.scaffolded)
        self.assertIn("already contains a project", result.reason)
        self.assertEqual((self.root / "package.json").read_text(), '{"name":"mine"}')

    def test_the_engines_own_directories_do_not_make_a_workspace_non_empty(self):
        (self.root / ".agent").mkdir()
        (self.root / ".gitignore").write_text("node_modules\n", encoding="utf-8")
        self.assertTrue(is_greenfield(self.root))

    def test_the_names_the_setup_step_wrote_down_do_not_either(self):
        """`.env.example` is the engine's note of what it asked for.

        It cost a stack: any build that asked a setup question arrived here
        with that one file, was told the workspace already contained a
        project, and was never given its template - so MERN projects had no
        .gitignore, and their security review then read the client bundle and
        reported four findings against React's own minified code.
        """
        (self.root / ".agentforge").mkdir()
        (self.root / ".env.example").write_text("STRIPE_SECRET_KEY=\n", encoding="utf-8")

        self.assertTrue(is_greenfield(self.root))
        result = install_template(self.root, "mern-microservices")

        self.assertTrue(result.scaffolded)
        self.assertIn(".gitignore", result.files)
        self.assertIn("dist", (self.root / ".gitignore").read_text(encoding="utf-8"))
        # And what it had written down is still there.
        self.assertIn("STRIPE_SECRET_KEY", (self.root / ".env.example").read_text(encoding="utf-8"))

    def test_a_file_the_workspace_already_has_survives_scaffolding(self):
        (self.root / ".gitignore").write_text("mine\n", encoding="utf-8")

        result = install_template(self.root, "nextjs-mongo")

        self.assertIn(".gitignore", result.preserved)
        self.assertEqual((self.root / ".gitignore").read_text(), "mine\n")

    def test_the_microservices_template_keeps_its_scaffold_directory_inert(self):
        install_template(self.root, "mern-microservices")

        # A package.json under scaffold/ would make npm treat the skeleton as a
        # workspace, and a .test.js there would be collected by the runner.
        self.assertTrue((self.root / "scaffold/service/package.json.tpl").is_file())
        self.assertFalse((self.root / "scaffold/service/package.json").is_file())

    def test_different_products_get_different_designs(self):
        chosen = {task: design.choose(task)["palette"] for task in (
            "a hospital patient records system",
            "a street food delivery marketplace",
            "a wedding photography portfolio",
            "a developer log monitoring console",
        )}
        self.assertEqual(len(set(chosen.values())), 4, chosen)

    def test_the_subject_of_the_product_outvotes_the_shape_of_it(self):
        # "dashboard" describes the shape; "hospital" describes the product.
        self.assertEqual(design.choose("hospital patient management dashboard")["palette"],
                         "ocean-slate")

    def test_the_choice_is_deterministic(self):
        first = design.choose("a small hotel booking site")
        second = design.choose("a small hotel booking site")
        self.assertEqual(first, second)

    def test_an_unrecognised_product_still_gets_a_complete_contract(self):
        selection = design.choose("something nobody has words for")
        self.assertFalse(selection["matched"])
        self.assertIn(selection["palette"], {p["id"] for p in design.PALETTES})

    def test_every_palette_reads_at_the_contrast_it_promises(self):
        for palette in design.PALETTES:
            for mode in ("light", "dark"):
                tokens = design.tokens(palette["id"], mode)
                ratio = design.contrast_ratio(tokens["text"], tokens["background"])
                self.assertGreaterEqual(ratio, 4.5, f"{palette['id']} {mode}")

    def test_the_foreground_on_a_fill_is_measured_not_assumed(self):
        for palette in design.PALETTES:
            tokens = design.tokens(palette["id"], "light")
            ratio = design.contrast_ratio(tokens["onPrimary"], tokens["primary"])
            self.assertGreaterEqual(ratio, 4.5, palette["id"])

    def test_the_contract_is_written_where_the_model_will_read_it(self):
        root = Path(tempfile.mkdtemp())
        written = design.write_design_skill(root, design.choose("a hotel booking site"), "hotel")

        skill = root / ".agents/skills/design-system/SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertTrue((root / ".agents/skills/design-system/tokens.css").is_file())
        body = skill.read_text(encoding="utf-8")
        self.assertIn("Never hard-code a hex value in a component", body)
        self.assertIn("--primary:", body)
        self.assertEqual(written["path"], ".agents/skills/design-system/SKILL.md")


class DesignReachTests(unittest.TestCase):
    """Which requests get a design contract at all.

    This was the bug that made the customiser look absent: the check wanted a
    literal "app", "page" or "site" in the request, and nobody writes those.
    Every realistic prompt silently lost its design.
    """

    def test_the_requests_people_actually_write_get_a_design(self):
        from builder_agent.agent import wants_design
        for prompt in (
            "A plant nursery. A visitor browses plants on /plants and adds one to a basket.",
            "A small bookshop with a cart and an owner who marks orders fulfilled.",
            "A boutique hotel. A guest browses rooms with photos and books one.",
            "hospital patient records with three roles",
        ):
            self.assertTrue(wants_design(prompt), prompt)

    def test_work_with_no_screen_still_gets_none(self):
        from builder_agent.agent import wants_design
        for prompt in ("write a cron job that prunes old sessions",
                       "add a seed script", "a command line tool that exports orders",
                       "an api only service", "build a library for currency formatting"):
            self.assertFalse(wants_design(prompt), prompt)

    def test_a_plan_that_files_components_settles_it(self):
        from builder_agent.agent import wants_design
        self.assertTrue(wants_design(
            "a worker that emails receipts",
            plan="Phase 3: app/receipts/page.jsx and components/ReceiptRow.jsx"))

    def test_the_catalogue_covers_every_dimension_the_contract_states(self):
        form = design.form_payload("a plant nursery with a basket")
        for key in ("palettes", "fonts", "typeScales", "radii", "densities", "borders",
                    "elevations", "motions", "themeModes", "tones", "contrasts",
                    "containers", "pages"):
            self.assertTrue(form[key], key)
        # Light, dark, and both - a toggle is a real choice, not an afterthought.
        self.assertEqual({m["id"] for m in form["themeModes"]}, {"light", "dark", "both"})

    def test_screen_inventory_is_left_to_the_approved_plan(self):
        chosen = design.choose("a shop where a visitor fills a basket and an admin "
                               "signs in to see orders")
        self.assertEqual(chosen["pages"], [])

    def test_every_chosen_dimension_reaches_the_written_contract(self):
        root = Path(tempfile.mkdtemp())
        selection = design.apply_answer(design.choose("a plant nursery"), {
            "themeMode": "both", "tone": "playful", "border": "bold",
            "motion": "expressive", "contrast": "aaa", "container": "1440"})
        design.write_design_skill(root, selection, "nursery")

        body = (root / ".agents/skills/design-system/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Playful", body)
        self.assertIn("WCAG AAA", body)
        self.assertIn("1440px", body)
        self.assertIn("springs", body)          # expressive motion
        self.assertIn("Strong outlines", body)  # bold borders
        self.assertIn('[data-theme="dark"]', body)

    def test_routes_are_read_from_where_the_files_sit(self):
        root = Path(tempfile.mkdtemp())
        (root / "app/rooms/[slug]").mkdir(parents=True)
        (root / "app/rooms/[slug]/page.jsx").write_text("export default function P(){}",
                                                        encoding="utf-8")
        (root / "app/api/bookings").mkdir(parents=True)
        (root / "app/api/bookings/route.js").write_text("export async function GET(){}",
                                                        encoding="utf-8")
        (root / "package.json").write_text(
            '{"scripts":{"dev":"next dev"},"dependencies":{"next":"15"}}', encoding="utf-8")

        layout = inspect_layout(root)
        rendered = format_layout(layout)

        self.assertIn("/rooms/[slug] [page]", rendered)
        self.assertIn("/api/bookings [api]", rendered)
        self.assertIn("dev=next dev", rendered)
        self.assertIn("Package manager: npm", rendered)

    def test_the_signature_changes_only_when_the_project_does(self):
        root = Path(tempfile.mkdtemp())
        (root / "app").mkdir()
        first = inspect_layout(root)["signature"]
        self.assertEqual(first, inspect_layout(root)["signature"])

        (root / "app/page.jsx").write_text("x", encoding="utf-8")
        self.assertNotEqual(first, inspect_layout(root)["signature"])


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.state = Path(tempfile.mkdtemp())
        self.knowledge = Knowledge(self.root, self.state)

    def test_an_unverified_hunch_is_never_recorded_as_knowledge(self):
        self.knowledge.record({"problem": "mongoose blows up on reload",
                               "cause": "model redefined", "fix": "cache it",
                               "category": "COMMAND"})
        self.assertEqual(self.knowledge.recall("mongoose reload"), [])

    def test_a_verified_lesson_is_recalled_by_what_it_is_about(self):
        self.knowledge.record({"problem": "OverwriteModelError on hot reload",
                               "cause": "the model is redefined each reload",
                               "fix": "reuse mongoose.models.X",
                               "category": "COMMAND",
                               "verification": "runTests passed"}, stack="nextjs-mongo")

        rows = self.knowledge.recall("OverwriteModelError mongoose")

        self.assertTrue(rows)
        self.assertIn("reuse mongoose.models.X", self.knowledge.format(rows))
        self.assertIn("retrieval hints, not", self.knowledge.format(rows))

    def test_lessons_become_an_ordinary_skill_in_the_next_project(self):
        self.knowledge.record({"problem": "a repeated mistake", "cause": "x", "fix": "y",
                               "category": "TEST", "verification": "proved"},
                              stack="nextjs-mongo")
        other = Path(tempfile.mkdtemp())

        name = self.knowledge.install_skill(other, "nextjs-mongo")

        self.assertEqual(name, "learned-lessons")
        self.assertIn("a repeated mistake",
                      (other / ".agents/skills/learned-lessons/SKILL.md").read_text(encoding="utf-8"))

    def test_a_fresh_installation_has_nothing_to_publish(self):
        self.assertIsNone(Knowledge(self.root, Path(tempfile.mkdtemp()))
                          .install_skill(Path(tempfile.mkdtemp()), "nextjs-mongo"))


class ProjectStackTests(unittest.TestCase):
    """An existing project knows its own stack better than a sentence does."""

    def project(self, manifest):
        root = Path(tempfile.mkdtemp())
        (root / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root

    def test_a_workspaces_repository_is_the_microservices_stack(self):
        root = self.project({"name": "shop", "private": True,
                             "workspaces": ["packages/*", "client"]})
        self.assertEqual(stack_of(root), "mern-microservices")

    def test_a_next_dependency_is_the_single_application_stack(self):
        root = self.project({"name": "shop",
                             "dependencies": {"next": "^15.1.4", "react": "^18.3.1"}})
        self.assertEqual(stack_of(root), "nextjs-mongo")

    def test_a_project_that_says_neither_is_left_undecided(self):
        """An empty answer falls back to reading the request, as before."""
        self.assertEqual(stack_of(self.project({"name": "shop"})), "")

    def test_a_missing_or_broken_manifest_is_not_a_crash(self):
        self.assertEqual(stack_of(Path("no-such-project")), "")
        root = Path(tempfile.mkdtemp())
        (root / "package.json").write_text("{ not json", encoding="utf-8")
        self.assertEqual(stack_of(root), "")

    def test_the_real_stacks_round_trip_through_their_own_templates(self):
        """Whatever a template scaffolds must read back as that same stack."""
        for stack in ("nextjs-mongo", "mern-microservices"):
            with self.subTest(stack=stack):
                root = Path(tempfile.mkdtemp())
                install_template(root, stack)
                self.assertEqual(stack_of(root), stack)


class PlannedScreenTests(unittest.TestCase):
    """The screens on offer are the screens the approved plan named.

    Offering landing / login / profile / settings to every product asks the
    user to design an application nobody planned. The plan has already been
    approved by this point and it says which screens exist, so it is the only
    honest source for the list.
    """

    PLAN = """## Pages
- `/` - the home page, listing the newest recipes
- `/recipes` - browse every recipe with filters
- `/recipes/[slug]` - one recipe, its ingredients and steps
- `/admin/login` - the kitchen team signs in here

## API
- `/api/recipes` - returns the recipe list as JSON
"""

    def form(self, plan=None):
        return design.form_payload("a recipe site", plan=self.PLAN if plan is None else plan)

    def test_the_offered_screens_are_the_ones_the_plan_names(self):
        form = self.form()
        self.assertEqual([page["route"] for page in form["pages"]],
                         ["/", "/admin/login", "/recipes", "/recipes/[slug]"])
        self.assertTrue(form["planned"])

    def test_a_route_that_is_not_a_screen_is_never_offered_as_one(self):
        """An API handler has no design, so it is not a design question."""
        routes = [page["route"] for page in design.pages_from_plan(self.PLAN)]
        self.assertNotIn("/api/recipes", routes)

    def test_every_planned_screen_starts_selected(self):
        form = self.form()
        self.assertEqual(form["chosen"]["pages"], [page["id"] for page in form["pages"]])

    def test_a_screen_says_what_the_plan_says_it_is_for(self):
        pages = {page["route"]: page for page in design.pages_from_plan(self.PLAN)}
        self.assertEqual(pages["/"]["label"], "Home")
        self.assertEqual(pages["/recipes/[slug]"]["label"], "Recipe detail")
        self.assertEqual(pages["/admin/login"]["label"], "Admin login")
        self.assertIn("ingredients", pages["/recipes/[slug]"]["what"])
        # The description explains the screen instead of repeating its route.
        self.assertNotIn("/recipes", pages["/recipes/[slug]"]["what"])

    def test_a_plan_naming_no_screens_falls_back_to_the_general_list(self):
        form = self.form(plan="Write a nightly job that emails the summary.")
        self.assertFalse(form["planned"])
        self.assertEqual([page["id"] for page in form["pages"]],
                         [page for page, _, _ in design.PAGES])
        self.assertEqual(form["chosen"]["pages"], [])

    def test_turning_a_planned_screen_off_removes_only_that_one(self):
        form = self.form()
        keep = [page for page in form["chosen"]["pages"] if page != "/admin/login"]
        picked = design.apply_answer(form["chosen"], {"pages": keep})
        self.assertEqual(picked["pages"], keep)
        self.assertNotIn("/admin/login", picked["pages"])

    def test_a_screen_the_plan_never_named_cannot_be_added_by_the_answer(self):
        form = self.form()
        picked = design.apply_answer(form["chosen"], {"pages": ["/", "/wp-admin"]})
        self.assertEqual(picked["pages"], ["/"])
if __name__ == "__main__":
    unittest.main()


class RealPlanScreenTests(unittest.TestCase):
    """A plan is prose with slashes in it, not a list of routes.

    Measured on a real plan for a five-screen cafe, reading every slash-word
    found thirty-eight "screens": /127 out of an IP address, /db out of
    "test/db", /vitest out of "jest-dom/vitest", /menu/page out of a file path.
    The design dialog offered all of them.
    """

    PLAN = """# Small Soup Cafe

A Next.js (App Router) + React + MongoDB/Mongoose app where a customer browses
soups on `/menu` and pays at `/checkout`. MongoDB runs at 127.0.0.1:27017 and
the database is `agentforge_smallsoupcafe`.

## Phases
- Phase 2 — Menu: `/menu` renders the six seeded soups with prices.
- Phase 3 — Checkout: `/checkout` builds a Stripe session; the webhook lives at
  `/api/webhook`, whose handler is `app/api/webhook/route.js`.
- Phase 4 — Admin: `/admin/login` signs the demo admin in; `/admin/orders`
  lists every order.
- Build: `npm run build` compiles cleanly with all routes (`/menu`,
  `/checkout`, `/admin/login`, `/admin/orders`).
- Tests: unit/integration under `test/` with jest-dom/vitest.
"""

    def screens(self):
        return design.pages_from_plan(self.PLAN)

    def test_only_the_routes_the_plan_wrote_as_routes_are_offered(self):
        self.assertEqual([page["route"] for page in self.screens()],
                         ["/", "/admin/login", "/admin/orders", "/checkout", "/menu"][1:])

    def test_prose_with_a_slash_in_it_is_not_a_screen(self):
        routes = [page["route"] for page in self.screens()]
        for wrong in ("/Mongoose", "/mongoose", "/integration", "/vitest", "/127", "/0"):
            self.assertNotIn(wrong, routes)

    def test_a_file_path_is_not_a_second_screen(self):
        """`app/api/webhook/route.js` builds a route; it is not one."""
        routes = [page["route"] for page in self.screens()]
        self.assertNotIn("/api/webhook/route", routes)
        self.assertNotIn("/menu/page", routes)

    def test_a_line_that_lists_routes_describes_none_of_them(self):
        """"compiles cleanly with all routes (…)" is not a description."""
        described = {page["route"]: page["what"] for page in self.screens()}
        self.assertIn("six seeded soups", described["/menu"])
        for what in described.values():
            self.assertNotIn("compiles cleanly", what)

    def test_a_plan_that_quotes_nothing_still_finds_its_routes(self):
        pages = design.pages_from_plan(
            "- /menu shows the soups\n"
            "- /admin/orders lists every order\n"
            "- built with MongoDB/Mongoose against 127.0.0.1:27017\n"
            "- the page lives at app/menu/page.jsx\n")
        self.assertEqual([page["route"] for page in pages], ["/admin/orders", "/menu"])


class UnmatchedPaletteTests(unittest.TestCase):
    """A request that names no known domain still gets a look of its own.

    Found by building a bookshop: "Wayfarer Books, an online bookshop" matches
    no keyword in any palette's domain list — and most real requests match
    none — so every one of them fell through to the same first palette. That is
    the one thing this module exists to prevent.
    """

    UNMATCHED = ("Wayfarer Books, an online bookshop",
                 "a tool for tracking beehives",
                 "somewhere to keep my grandmother's letters",
                 "a rota for the village hall")

    def test_none_of_these_match_a_domain(self):
        """If one starts matching, this test is measuring the wrong thing."""
        for goal in self.UNMATCHED:
            with self.subTest(goal=goal):
                self.assertFalse(design.choose(goal)["matched"])

    def test_unmatched_products_do_not_all_look_the_same(self):
        palettes = {design.choose(goal)["palette"] for goal in self.UNMATCHED}
        self.assertGreater(len(palettes), 1)

    def test_the_same_request_always_gets_the_same_look(self):
        for goal in self.UNMATCHED:
            with self.subTest(goal=goal):
                self.assertEqual(design.choose(goal)["palette"],
                                 design.choose(goal)["palette"])

    def test_a_recognised_domain_still_wins_over_the_digest(self):
        self.assertEqual(design.choose("a small soup cafe")["palette"], "sunset-ember")
        self.assertEqual(design.choose("a hospital appointment system")["palette"],
                         "ocean-slate")

    def test_every_palette_the_digest_can_land_on_is_a_real_one(self):
        known = {p["id"] for p in design.PALETTES}
        for n in range(200):
            self.assertIn(design.choose(f"a thing numbered {n}")["palette"], known)


class NamedScreenTests(unittest.TestCase):
    """A plan names its screens in prose as often as it writes their paths.

    Found on screen: a six-screen booking product reached the design step as
    "SCREENS IN THE PLAN (1 OF 1)" — one page called Home — because the plan
    described its screens without writing a single route.
    """

    PROSE = """# Atlas — Build Plan

## Requirements (enumerated from the request)
1. A rooms page: the room inventory grid with filters.
2. A bookings page: the live booking ledger with status.
3. A payments page: transactions, refunds, settlements.
4. A settings page: workspace, billing, integrations.
"""

    SECTIONED = """# Atlas

## Screens
- Dashboard — KPIs and a recent-bookings overview.
- Rooms — room inventory grid with filters.
- Bookings — live booking ledger with status.
- Payments — transactions, refunds, settlements.

## Phases
Phase 1 — the shell.
"""

    WITH_ROUTES = """## Screens
- `/` — Home: today's soups.
- `/menu` — Menu: the whole menu.
- `/admin/orders` — Admin orders: every order.
"""

    def labels(self, plan):
        return [page["label"] for page in design.pages_from_plan(plan)]

    def test_a_screens_section_is_read_as_the_screens(self):
        self.assertEqual(self.labels(self.SECTIONED),
                         ["Bookings", "Dashboard", "Payments", "Rooms"])

    def test_each_one_keeps_what_the_plan_said_it_is_for(self):
        described = {page["label"]: page["what"] for page in design.pages_from_plan(self.SECTIONED)}
        self.assertIn("recent-bookings", described["Dashboard"])
        self.assertIn("filters", described["Rooms"])

    def test_screens_named_in_prose_are_found_without_a_section(self):
        self.assertEqual(self.labels(self.PROSE),
                         ["Bookings", "Payments", "Rooms", "Settings"])

    def test_a_screen_with_no_stated_route_does_not_get_an_invented_one(self):
        """The plan did not say the path, so the studio does not claim one."""
        for page in design.pages_from_plan(self.SECTIONED):
            self.assertEqual(page["route"], "")
            self.assertTrue(page["id"])

    def test_written_routes_still_win_outright(self):
        pages = design.pages_from_plan(self.WITH_ROUTES)
        self.assertEqual([page["route"] for page in pages], ["/", "/admin/orders", "/menu"])

    def test_a_plan_with_one_route_and_named_screens_shows_them_all(self):
        """The case from the screenshot: one stray route, six real screens."""
        pages = design.pages_from_plan("Serve it at `/`.\n\n" + self.SECTIONED)
        self.assertGreater(len(pages), 1)
        self.assertIn("Dashboard", [page["label"] for page in pages])

    def test_a_plan_with_no_screens_at_all_still_offers_none(self):
        self.assertEqual(design.pages_from_plan("Write a nightly job that emails a summary."), [])


class StylingSurvivesTheBuildTests(unittest.TestCase):
    """The scaffold's CSS toolchain is not the build's to drop.

    A build rewrote package.json and the result was the template's manifest
    byte for byte, minus tailwindcss, postcss and autoprefixer; the two config
    files went with them. Nothing failed - it compiled, served, and passed unit,
    e2e and runtime - and the app rendered as unstyled HTML, because a missing
    CSS toolchain has no symptom other than the absence of CSS.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "app").mkdir()
        (self.root / "app" / "globals.css").write_text(
            "@tailwind base;\n@tailwind utilities;\n", encoding="utf-8")

    def _manifest(self, dev: dict):
        (self.root / "package.json").write_text(json.dumps(
            {"name": "x", "dependencies": {"next": "^15.1.4"}, "devDependencies": dev}),
            encoding="utf-8")

    def _dev(self):
        return json.loads((self.root / "package.json").read_text(encoding="utf-8")
                          ).get("devDependencies", {})

    def test_a_dropped_toolchain_is_put_back(self):
        self._manifest({"vitest": "^2.1.8"})
        restored = restore_styling(self.root, "nextjs-mongo")
        self.assertIn("tailwindcss", restored)
        self.assertIn("tailwindcss", self._dev())
        self.assertTrue((self.root / "postcss.config.mjs").is_file())

    def test_a_toolchain_that_is_still_there_is_left_alone(self):
        self._manifest({"tailwindcss": "^9.9.9", "postcss": "^8", "autoprefixer": "^10"})
        (self.root / "tailwind.config.mjs").write_text("export default {}", encoding="utf-8")
        (self.root / "postcss.config.mjs").write_text("export default {}", encoding="utf-8")
        self.assertEqual(restore_styling(self.root, "nextjs-mongo"), [])
        # And the project's own version is not overwritten with the template's.
        self.assertEqual(self._dev()["tailwindcss"], "^9.9.9")

    def test_a_project_that_does_not_use_tailwind_is_not_given_it(self):
        (self.root / "app" / "globals.css").write_text("body { margin: 0 }", encoding="utf-8")
        self._manifest({"vitest": "^2.1.8"})
        self.assertEqual(restore_styling(self.root, "nextjs-mongo"), [])
        self.assertNotIn("tailwindcss", self._dev())

    def test_an_unknown_stack_changes_nothing(self):
        self._manifest({})
        self.assertEqual(restore_styling(self.root, "no-such-stack"), [])


class TheChosenThemeIsTheDefaultTests(unittest.TestCase):
    """Choosing one dark theme has to produce a dark page.

    render_tokens_css wrote the light values into `:root` whatever had been
    chosen and put the dark ones under `[data-theme="dark"]`. Nothing sets that
    attribute, so a Ferrari platform chosen dark drew twenty pages of
    `<html lang="en">` on #FAFAFA with a dark block sitting unused underneath.
    """

    def _css(self, mode):
        from builder_agent.design import render_tokens_css, choose, apply_answer
        selection = apply_answer(choose("a supercar platform"),
                                 {"palette": "mono-contrast", "themeMode": mode})
        return render_tokens_css(selection)

    def _root_background(self, css):
        root = css.split("}")[0]
        return [l.split(":")[1].strip(" ;") for l in root.splitlines()
                if l.strip().startswith("--background")][0]

    def test_dark_puts_the_dark_values_where_nothing_has_to_be_toggled(self):
        css = self._css("dark")
        self.assertEqual(self._root_background(css).upper(), "#09090B")
        self.assertIn('[data-theme="light"]', css)

    def test_light_is_unchanged(self):
        css = self._css("light")
        self.assertEqual(self._root_background(css).upper(), "#FAFAFA")
        self.assertIn('[data-theme="dark"]', css)

    def test_both_keeps_light_as_the_default_and_dark_behind_the_toggle(self):
        css = self._css("both")
        self.assertEqual(self._root_background(css).upper(), "#FAFAFA")
        self.assertIn('[data-theme="dark"]', css)

    def test_the_contract_says_how_the_theme_is_switched_on(self):
        from builder_agent.design import render_skill, choose, apply_answer
        dark = apply_answer(choose("x"), {"themeMode": "dark"})
        self.assertIn("dark by default", render_skill(dark, ""))
