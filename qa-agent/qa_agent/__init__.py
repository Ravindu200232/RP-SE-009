"""The QA agent: proves a generated application and records what it proved.

Runs the builder engine at the deep verification profile - the one place that
profile is spent - and writes the studio's Testing record.

    from qa_agent import QAAgent
    outcome = QAAgent(project="hotel", project_dir="./hotel", model="…").run()
"""
from .agent import QAAgent, QAOutcome
from .report import build_pdf, read as read_results, write as write_results

__all__ = ["QAAgent", "QAOutcome", "build_pdf", "read_results", "write_results"]

__version__ = "1.0.0"
