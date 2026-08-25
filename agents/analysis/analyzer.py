"""Public post-generation analyzer façade composed from purpose-specific mixins."""
from agents.analysis.analyzer_common import *
from agents.analysis.analyzer_context import AnalyzerContextMixin
from agents.analysis.analyzer_data import AnalyzerDataMixin
from agents.analysis.analyzer_code import AnalyzerCodeMixin
from agents.analysis.analyzer_ui import AnalyzerUIMixin
from agents.analysis.analyzer_workflows import AnalyzerWorkflowMixin
from agents.analysis.analyzer_runtime import AnalyzerRuntimeMixin
from agents.analysis.analyzer_repair_run import AnalyzerRepairMixin


class AnalyzerAgent(
    AnalyzerContextMixin, AnalyzerDataMixin, AnalyzerCodeMixin, AnalyzerUIMixin,
    AnalyzerWorkflowMixin, AnalyzerRuntimeMixin, AnalyzerRepairMixin,
):
    """Read a finished project back and compare it against its accepted plan."""
    pass


# Preserve the public surface of the pre-refactor module.
__all__ = ['AnalyzerAgent', 'AnalyzerReport', 'BCRYPT_LITERAL_RE', 'CODE_EXT', 'FETCH_URL_RE', 'Finding', 'HTTP_METHOD_RE', 'LINK_HREF_RE', 'MAX_FILE_BYTES', 'NEXT_ROOTS', 'PLACEHOLDER_RE', 'PROSE_PATH_RE', 'ROOT_SOURCE', 'ROUTER_PUSH_RE', 'SEVERITIES', 'SKIP_DIRS', 'SOURCE_EXT', 'log']
