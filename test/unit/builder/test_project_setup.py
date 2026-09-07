"""Skills, templates and the design contract.

These decide what a build starts from, and all three are things the engine does
before the model writes a line. A wrong answer here is expensive: the wrong
skill teaches the wrong conventions, a missing scaffold means twenty boilerplate
files written from memory, and one hard-coded palette means every app the
studio produces looks identical.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from builder_agent import design
from builder_agent.knowledge import Knowledge
from builder_agent.layout import format_layout, inspect_layout
from builder_agent.skills import (SKILL_ROOT, catalog, install_skill_pack, read_manifest,
                                  read_skill, select)
from builder_agent.templates import install_template, is_greenfield, template_notice


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
        self.assertIn(f'"name": "{self.root.name.lower()}"',
                      (self.root / "package.json").read_text(encoding="utf-8"))

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


class DesignContractTests(unittest.TestCase):
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


class ProjectLayoutTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
