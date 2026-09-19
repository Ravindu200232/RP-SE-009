"""The Remix stack, and the things about it that are not like the other two.

Every stack here is a fixed contract with a template behind it, and the
template is only worth having if it actually installs, builds and serves. This
one did, before it shipped: `npm install` (738 packages, no peer conflict),
`remix vite:build` (client and SSR bundles), `vitest run` (4 passing), and both
`vite:dev` and `remix-serve` answering 200 with the page rendered into the
server's own HTML.

What a test can hold after that is the shape: that the pins still compose, that
the framework is the one the skill describes, and that the two places which
special-case a stack know about this one.
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from builder_agent.config import STACKS, detect_stack, stack_for, stack_of
from builder_agent.skills import SKILL_ROOT, read_manifest, select
from builder_agent.templates import TEMPLATE_ROOT, install_template

STACK = "remix-mongo"
ROOT = Path(__file__).resolve().parents[3]


class ContractTests(unittest.TestCase):
    def test_the_stack_exists_and_names_its_own_skill(self):
        stack = stack_for(STACK)
        self.assertEqual(stack.id, STACK)
        self.assertIn("stack-remix", stack.skills)
        self.assertIn("Remix", stack.tech)

    def test_asking_for_remix_is_what_chooses_it(self):
        self.assertEqual(detect_stack("build it with remix"), STACK)
        self.assertEqual(detect_stack("a Remix blog"), STACK)

    def test_a_request_that_never_says_remix_does_not_get_it(self):
        """The default must not move on a word nobody used."""
        for prompt in ("a booking app", "a shop with a checkout",
                       "a dashboard for a clinic", "a mern microservices shop"):
            with self.subTest(prompt):
                self.assertNotEqual(detect_stack(prompt), STACK)

    def test_its_own_skill_is_not_selectable_on_another_stack(self):
        entries = read_manifest()
        self.assertIn("stack-remix", select(entries, "", "a remix app", STACK))
        for other in ("nextjs-mongo", "mern-microservices"):
            with self.subTest(other):
                self.assertNotIn("stack-remix",
                                 select(entries, "", "a remix app", other))


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def scaffold(self):
        result = install_template(self.root, STACK)
        self.assertTrue(result.scaffolded, result.reason)
        return result

    def manifest(self):
        return json.loads((self.root / "package.json").read_text(encoding="utf-8"))

    def test_an_empty_workspace_gets_the_verified_starting_point(self):
        result = self.scaffold()
        for name in ("package.json", "vite.config.js", "vitest.config.js",
                     "app/root.jsx", "app/routes/_index.jsx", "lib/db.js"):
            with self.subTest(name):
                self.assertIn(name, result.files)

    def test_the_guard_suffix_is_stripped_so_the_project_can_run(self):
        result = self.scaffold()
        self.assertFalse([f for f in result.files if f.endswith(".tpl")])
        self.assertIn("test/money.test.js", result.files)

    def test_a_project_on_disk_is_recognised_without_being_told(self):
        """An edit must get this contract, not the default one."""
        self.scaffold()
        self.assertEqual(stack_of(self.root), STACK)

    def test_the_vite_pin_is_one_the_framework_accepts(self):
        """`@remix-run/dev` peer-requires vite ^5 || ^6, and vite is past 8.

        Pinning the latest is what would break this, silently, on the next
        install - so the range is deliberate and this is what says so.
        """
        self.scaffold()
        vite = self.manifest()["devDependencies"]["vite"]
        major = int(re.search(r"(\d+)", vite).group(1))
        self.assertIn(major, (5, 6), f"vite {vite} is outside the Remix peer range")

    def test_the_framework_packages_all_move_together(self):
        """A mixed set of @remix-run versions is a class of bug on its own."""
        self.scaffold()
        manifest = self.manifest()
        pinned = {name: spec
                  for group in ("dependencies", "devDependencies")
                  for name, spec in manifest[group].items()
                  if name.startswith("@remix-run/")}
        self.assertEqual(len(pinned), 4, pinned)
        self.assertEqual(len(set(pinned.values())), 1, pinned)

    def test_it_is_remix_v2_on_vite_and_says_so(self):
        """v1's config file is ignored here, and writing one wastes an hour."""
        self.scaffold()
        self.assertFalse((self.root / "remix.config.js").exists())
        self.assertIn("vitePlugin as remix",
                      (self.root / "vite.config.js").read_text(encoding="utf-8"))

    def test_the_test_runner_does_not_load_the_framework_plugin(self):
        """It expects a Remix request in flight; under the runner there is none."""
        self.scaffold()
        body = (self.root / "vitest.config.js").read_text(encoding="utf-8")
        self.assertNotIn("@remix-run/dev", body)

    def test_the_index_route_serves_the_root_path(self):
        """`index.jsx` would serve `/index`, which is never what was meant."""
        self.scaffold()
        self.assertTrue((self.root / "app" / "routes" / "_index.jsx").is_file())
        self.assertFalse((self.root / "app" / "routes" / "index.jsx").exists())

    def test_the_document_is_complete_enough_to_be_interactive(self):
        """A root without Scripts renders and then does nothing."""
        body = (TEMPLATE_ROOT / STACK / "app" / "root.jsx").read_text(encoding="utf-8")
        for tag in ("<Meta />", "<Links />", "<Scripts />", "<Outlet />"):
            with self.subTest(tag):
                self.assertIn(tag, body)

    def test_the_skill_ships_every_page_its_index_names(self):
        index = (SKILL_ROOT / "stack-remix" / "SKILL.md").read_text(encoding="utf-8")
        named = set(re.findall(r'resourcePath="([^"]+\.md)"', index))
        self.assertTrue(named)
        for name in sorted(named):
            with self.subTest(name):
                self.assertTrue((SKILL_ROOT / "stack-remix" / name).is_file())


class PreviewTests(unittest.TestCase):
    """The one place a stack's dev server is actually started."""

    def source(self):
        return (ROOT / "server_modules" / "core" / "preview_runtime.py").read_text(
            encoding="utf-8")

    def test_the_runtime_knows_this_stack_is_not_next(self):
        """Next's `--hostname` is not a Vite flag, and the wrong spelling
        starts the server somewhere the preview never finds it."""
        spawn = self.source().split("def _spawn_preview")[1].split("\ndef ")[0]
        self.assertIn('stack == "remix-mongo"', spawn)
        remix = spawn.split('stack == "remix-mongo"')[1].split("else:")[0]
        self.assertIn('"--host"', remix)
        self.assertNotIn('"--hostname"', remix)

    def test_every_stack_that_ships_has_a_template(self):
        for name in STACKS:
            with self.subTest(name):
                self.assertTrue((TEMPLATE_ROOT / name).is_dir(),
                                f"{name} is selectable and has no starting point")


class StackWiringTests(unittest.TestCase):
    """The places that hold a stack id and are not `config.py`.

    Each of these is a map keyed by stack, written before there was a third
    stack, and each failed silently rather than loudly when one was added: a
    missing pack meant the model was simply never shown its stack's contents
    page, and a missing tech string meant the handoff told the builder the
    technology was "remix-mongo". Neither raised anything.
    """

    def test_every_stack_preloads_its_own_skill_pack(self):
        from builder_agent.loop import STACK_PACKS
        self.assertEqual(set(STACK_PACKS), set(STACKS))
        for stack, pack in STACK_PACKS.items():
            with self.subTest(stack):
                self.assertTrue((SKILL_ROOT / pack / "SKILL.md").is_file())
                self.assertIn(pack, stack_for(stack).skills)

    def test_the_handoff_names_the_technology_of_every_stack(self):
        """`builder.md` is what the build is told it is building."""
        source = (ROOT / "srs-agent" / "srs_agent" / "app" / "generators"
                  / "agent_handoff.py").read_text(encoding="utf-8")
        declared = source.split("tech = {")[1].split("}")[0]
        for name in STACKS:
            with self.subTest(name):
                self.assertIn(f'"{name}"', declared)
                # The value has to be the framework, not the id repeated back.
                self.assertIn(stack_for(name).tech, declared)


if __name__ == "__main__":
    unittest.main()
