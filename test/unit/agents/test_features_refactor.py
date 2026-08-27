import re
import unittest
from types import SimpleNamespace

from agents.features.capture import CaptureResult, PENCIL_SYSTEM, capture_region
from agents.features.features_apply import FeaturesAgent
from agents.features.features_common import (
    FeatureSpec, package_requested, safe_change_path,
)
from agents.features.images import ImageAgent
from agents.features.picker import (
    ELEMENT_EDIT_SYSTEM, ElementResolver, describe, guard_scope,
    routes_rendering,
)
from agents.features.source_guidance import feature_prompt


class FeaturesRefactorTests(unittest.TestCase):
    def parser(self):
        agent = FeaturesAgent.__new__(FeaturesAgent)
        agent.arch = SimpleNamespace(
            files={"app/page.jsx": "export default function Page() {}"},
            PKG_NAME_RE=re.compile(r"^(?:@?[a-z0-9][a-z0-9._-]*)(?:/[a-z0-9._-]+)?$"),
            NODE_BUILTINS=set(),
        )
        return agent

    def test_package_sentinels_never_become_install_requests(self):
        for sentinel in ("none", "NONE", "null", "n/a", "n-a",
                         "no package", "no-package", "(none)"):
            with self.subTest(sentinel=sentinel):
                reply = (
                    "CURRENT :: page exists\nGAP :: change absent\n"
                    "CAUSE :: page owns it\n"
                    "EVIDENCE :: app/page.jsx :: current source fact\n"
                    f"PACKAGE :: {sentinel}\n"
                    "FILE :: edit :: app/page.jsx :: server :: update it\n"
                    "VERIFY :: page renders change\nCONFIDENCE :: high\nDONE"
                )
                self.assertEqual(self.parser()._parse(reply).packages, [])
                self.assertFalse(package_requested(sentinel))

        commands = []
        agent = FeaturesAgent.__new__(FeaturesAgent)
        agent.cb, agent.model = {}, None
        agent.arch = SimpleNamespace(
            files={"app/page.jsx": "export default function Page() {}"},
            convo=[], _workspace_tool_cache={},
            _builder_sys=lambda: "builder",
            _stream=lambda *args, **kwargs: None,
            run_requested_commands=lambda raw: [],
            write_file=lambda path, content: False,
            sync_dependencies=lambda: None,
        )
        agent.az = SimpleNamespace(
            cmd=SimpleNamespace(run=commands.append),
            source_files=lambda: dict(agent.arch.files),
            _budget_chars=lambda: 100_000,
        )
        spec = FeatureSpec(
            packages=["none"],
            files=[{"path": "app/page.jsx", "action": "edit",
                    "kind": "server", "why": "exercise apply defense"}],
        )
        self.assertEqual(agent.apply("change it", spec), 0)
        self.assertEqual(commands, [])

    def test_real_package_and_public_contracts_survive(self):
        spec = self.parser()._parse(
            "PACKAGE :: date-fns\n"
            "FILE :: edit :: app/page.jsx :: server :: format a date"
        )
        self.assertEqual(spec.packages, ["date-fns"])
        self.assertTrue(safe_change_path("app/page.jsx"))
        self.assertFalse(safe_change_path("../outside.js"))
        self.assertIsInstance(FeatureSpec(), FeatureSpec)
        self.assertTrue(callable(capture_region))
        shot = CaptureResult(png_b64="crop", page_b64="page")
        self.assertTrue(shot.ok())
        self.assertEqual(shot.vision_images(), ["crop", "page"])
        self.assertTrue(callable(guard_scope))
        self.assertTrue(callable(describe))
        self.assertTrue(callable(routes_rendering))
        self.assertTrue(ElementResolver)
        self.assertTrue(ImageAgent)

    def test_markdown_prompts_load_with_agentic_contracts(self):
        self.assertIn("workspace tools", feature_prompt("PLAN", foundation=True))
        self.assertIn("CURRENT ::", feature_prompt("PLAN"))
        self.assertIn("RESULT :: PASS|FAIL", feature_prompt("AUDIT"))
        self.assertIn("NEED <path>", ELEMENT_EDIT_SYSTEM)
        self.assertIn("/generated/", PENCIL_SYSTEM)


if __name__ == "__main__":
    unittest.main()
