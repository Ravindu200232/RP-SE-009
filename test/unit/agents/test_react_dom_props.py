import tempfile
import unittest
from pathlib import Path

from agents.core.syntax.react_dom_props import (
    find_invalid_react_dom_props,
    normalize_react_dom_props,
)
from agents.planner.builder.file_writer import FileWriterMixin


class ReactDomPropertyTests(unittest.TestCase):
    def test_normalizer_fixes_dom_attributes_but_not_javascript_variables(self):
        source = '''export default function Form() {
  const autocomplete = "keep-variable";
  return <input autocomplete="email" maxlength={50} readonly={false} />;
}\n'''
        fixed = normalize_react_dom_props("app/login/page.jsx", source)
        self.assertIn('const autocomplete = "keep-variable"', fixed)
        self.assertIn('autoComplete="email"', fixed)
        self.assertIn('maxLength={50}', fixed)
        self.assertIn('readOnly={false}', fixed)

    def test_normalizer_does_not_rewrite_custom_component_prop_contracts(self):
        source = 'export default () => <SearchBox autocomplete="off" />;\n'
        self.assertEqual(source, normalize_react_dom_props("app/page.jsx", source))

    def test_analyzer_helper_reports_invalid_dom_property_names(self):
        found = dict(find_invalid_react_dom_props('<label for="x"><input autocomplete="email" /></label>'))
        self.assertEqual(found["for"], "htmlFor")
        self.assertEqual(found["autocomplete"], "autoComplete")

    def test_builder_writer_normalizes_generated_jsx_before_saving(self):
        class DummyWriter(FileWriterMixin):
            NEXT_PROTECTED = set()

            def __init__(self, root):
                self.project_dir = Path(root)
                self.plan = {"file_plan": [{"path": "app/login/page.jsx"}]}
                self.files, self.write_seq, self._scaffolding = {}, 0, False

            def _safe_path(self, rel):
                return self.project_dir / rel

            def _fire(self, *args):
                pass

            def _log(self, *args):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            writer = DummyWriter(tmp)
            self.assertTrue(writer.write_file("app/login/page.jsx", 'export default () => <input autocomplete="email" />;'))
            saved = (Path(tmp) / "app/login/page.jsx").read_text("utf-8")
            self.assertIn('autoComplete="email"', saved)
            self.assertNotIn(' autocomplete=', saved)


if __name__ == "__main__":
    unittest.main()
