import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.build.builder_common import (
    SYSTEM_PROMPT,
    _safe_component,
    _stream_chat,
    set_stream_callback,
)
from agents.build.builder_generation import BuilderAgent
from agents.build.builder_templates import _load_scaffold
from agents.build.tester_browser import TesterAgent
from agents.build.tester_common import set_emit


class _StreamResponse:
    def raise_for_status(self):
        return None

    def iter_lines(self):
        chunks = (
            [],
            {"message": "malformed"},
            {"message": {"content": "export default "}},
            {"message": {"content": "function App() {}"}},
            {"done": True},
        )
        return [json.dumps(chunk).encode() for chunk in chunks]


class BuilderRefactorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.builder = BuilderAgent("http://ollama", "model", self.root)

    def tearDown(self):
        set_stream_callback(None)
        set_emit(None)
        self.temp.cleanup()

    def test_public_joins_and_assets_remain_available(self):
        self.assertTrue(issubclass(BuilderAgent, object))
        self.assertTrue(issubclass(TesterAgent, object))
        self.assertIn("export default function Card", _safe_component("Card"))
        self.assertIn("Non-negotiable runtime rules", SYSTEM_PROMPT)

        files = self.builder._config_files("A Hotel & Spa")
        package = json.loads(files["package.json"])
        self.assertEqual("a-hotel---spa", package["name"])
        self.assertIn("framer-motion", package["dependencies"])
        self.assertIn("plugins: [react()]", files["vite.config.js"])
        self.assertIn("<title>A Hotel</title>", self.builder._index_html("A Hotel"))

    @patch("pathlib.Path.read_text", side_effect=OSError("missing"))
    def test_scaffold_fallback_is_still_buildable(self, _read_text):
        scaffold = _load_scaffold()
        self.assertIn("framer-motion", scaffold["package"]["dependencies"])
        self.assertIn("@vitejs/plugin-react", scaffold["package"]["devDependencies"])
        self.assertIn("vite.config.js", scaffold["config_files"])

    @patch("agents.build.builder_common.requests.post")
    def test_stream_contract_frames_tokens_and_keeps_request_budget(self, post):
        post.return_value = _StreamResponse()
        events = []
        set_stream_callback(events.append)

        result = _stream_chat(
            "http://ollama/api/chat",
            "gemma4:31b-cloud",
            "Build it",
            "App",
            temperature=0.15,
            timeout=240,
        )

        self.assertEqual("export default function App() {}", result)
        self.assertEqual("\x00START:App", events[0])
        self.assertEqual("\x00END", events[-1])
        payload = post.call_args.kwargs
        self.assertTrue(payload["stream"])
        self.assertEqual(240, payload["timeout"])
        self.assertEqual(4096, payload["json"]["options"]["num_predict"])
        self.assertEqual(SYSTEM_PROMPT, payload["json"]["messages"][0]["content"])

    @patch("agents.build.builder_common.requests.post")
    def test_failed_stream_still_closes_callback_frame(self, post):
        post.side_effect = RuntimeError("offline")
        events = []
        set_stream_callback(events.append)
        with self.assertRaisesRegex(RuntimeError, "offline"):
            _stream_chat("url", "model", "prompt", "App", 0.1, 10)
        self.assertEqual(["\x00END"], events)

    def test_fix_adds_build_evidence_then_uses_one_repair_path(self):
        self.builder._npm_build_errors = Mock(return_value="compiler evidence")
        self.builder.fix_with_errors = Mock()
        self.builder.fix(["browser evidence"])
        evidence = self.builder.fix_with_errors.call_args.args[0]
        self.assertIn("browser evidence", evidence)
        self.assertIn("compiler evidence", evidence)

    def test_sanitizer_preserves_component_and_repairs_known_hazards(self):
        source = """\
import { FiOval } from 'react-icons/all'
import map from 'react-leaflet'
export default function Card() {
  return (
    <div className={`card`}><input step={30/60}></div>
  )
}
"""
        result = self.builder._sanitize_jsx(source, "src/components/Card.jsx")
        self.assertIn("react-icons/fi", result)
        self.assertIn("FiCircle", result)
        self.assertNotIn("react-leaflet", result)
        self.assertIn("const _dv0 = 30/60", result)
        self.assertIn("step={_dv0}", result)
        self.assertIn("<input step={_dv0} />", result)

    def test_write_protocol_updates_memory_disk_and_callback(self):
        callback = Mock()
        self.builder._on_write = callback
        source = (
            "import React from 'react'\n"
            "export default function Card() { return <input> }"
        )
        self.builder._write_one("src/components/Card.jsx", source)

        written = self.root / "src" / "components" / "Card.jsx"
        self.assertTrue(written.is_file())
        self.assertIn("<input />", written.read_text(encoding="utf-8"))
        self.assertEqual(written.read_text(encoding="utf-8"),
                         self.builder.built_files["src/components/Card.jsx"])
        self.assertEqual("src/components/Card.jsx", callback.call_args.args[0])

    def test_broken_file_detection_keeps_generated_ownership_boundary(self):
        path = "src/components/Hero.jsx"
        self.builder.built_files[path] = "export default function Hero() {}"
        error = "[plugin:vite:react] /src/components/Hero.jsx:9:2"
        self.assertEqual([path], self.builder._identify_broken(error))
        unknown = "[plugin:vite:react] /src/components/Unknown.jsx:9:2"
        self.assertEqual([], self.builder._identify_broken(unknown))


if __name__ == "__main__":
    unittest.main()
