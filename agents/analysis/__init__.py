"""Analyzer package: deterministic checks, live proof, then scoped repair."""

# Source: analyzer.py — combines all analyzer responsibilities.
from agents.analysis.analyzer import AnalyzerAgent, AnalyzerReport, Finding
# Source: repair/bug_fixer.py — edits the smallest evidence-backed file set.
from agents.analysis.repair.bug_fixer import BugFixerAgent, FixVerdict
# Source: runtime/browser_reproduction.py — reproduces browser failures before repair.
from agents.analysis.runtime.browser_reproduction import Reproduction, reproduce

__all__ = ["AnalyzerAgent", "AnalyzerReport", "Finding", "BugFixerAgent",
           "FixVerdict", "Reproduction", "reproduce"]
