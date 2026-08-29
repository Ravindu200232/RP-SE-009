"""Public agentic E2E debugger façade."""
from .debugger_common import *
from .debugger_investigate import DebuggerInvestigateMixin
from .debugger_reasoning import DebuggerReasoningMixin

class AgenticE2EDebugger(DebuggerInvestigateMixin, DebuggerReasoningMixin):
    pass

__all__ = ["AgenticE2EDebugger", "DebugNotebook"]

# Preserve the public surface of the pre-refactor module.
__all__ = ['AgenticE2EDebugger', 'DebugNotebook', 'MAX_TOOL_TURNS', 'SYSTEM', 'TOOL_RESULT_CHARS', 'VERDICTS', 'log']
