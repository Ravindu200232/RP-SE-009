import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
from test import _support  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deployment-agent' / 'deploy_agent'))
sys.path.insert(0, str(ROOT / 'deployment-agent'))
from deployment_agent.exporter import EvidenceExporter

class EvidenceReportTests(unittest.TestCase):
    def test_report_is_offline_escaped_masked_and_uses_detected_framework(self):
        store = Mock(); store.get_events.return_value = [{'stage':'security','message':'mongodb://name:password@host/database account 123456789012'}]
        run = {'project_name':'<script>bad</script>', 'state':'LIVE','plan':{'target':'aws_ec2'},
               'spec':{'services':[{'name':'catalog','framework':'express','root':'packages/catalog','port':4101}]}}
        output = EvidenceExporter(store)._report_html('test-run',run)
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;',output)
        self.assertNotIn('name:password',output)
        self.assertNotIn('123456789012',output)
        self.assertIn('express',output)
        self.assertNotIn('Next.js',output)
        self.assertIn("default-src 'none'",output)
