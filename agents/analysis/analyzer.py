"""Public analyzer composed from small evidence, runtime and repair stages."""
from __future__ import annotations

# Source: scan_state.py — source snapshots and the combined deterministic scan.
from agents.analysis.checks.scan_state import ScanStateMixin
# Source: auth_checks.py — identity, role and authentication checks.
from agents.analysis.checks.auth_checks import AuthChecksMixin
# Source: data_checks.py — seed, database and UI-data checks.
from agents.analysis.checks.data_checks import DataChecksMixin
# Source: route_checks.py — page/link/API route and HTTP-method checks.
from agents.analysis.checks.route_checks import RouteChecksMixin
# Source: code_checks.py — source-level Next.js/component checks.
from agents.analysis.checks.code_checks import CodeChecksMixin
# Source: runtime_probe.py — live route and demo-login verification.
from agents.analysis.runtime.runtime_probe import RuntimeProbeMixin
# Source: semantic_audit.py — evidence-backed requirement meaning checks.
from agents.analysis.repair.semantic_audit import SemanticAuditMixin
# Source: repair_runner.py — scoped repair and progress recheck.
from agents.analysis.repair.repair_runner import RepairRunnerMixin
# Source: analysis_shared.py — finding/report types and shared constants.
from agents.analysis.analysis_shared import (
    AnalyzerReport, Finding, REPAIRABLE_MAJOR, BCRYPT_LITERAL_RE, CODE_EXT,
    FETCH_URL_RE, HTTP_METHOD_RE, LINK_HREF_RE, MAX_FILE_BYTES, NEXT_ROOTS,
    PLACEHOLDER_RE, PROSE_PATH_RE, ROOT_SOURCE, ROUTER_PUSH_RE, SEVERITIES,
    SKIP_DIRS, SOURCE_EXT, log, re,
)


class AnalyzerAgent(ScanStateMixin, AuthChecksMixin, DataChecksMixin, RouteChecksMixin,
                    CodeChecksMixin, RuntimeProbeMixin, SemanticAuditMixin, RepairRunnerMixin):
    """Compare the generated app with its plan, source contracts and live behavior."""
    PLACEHOLDER_MARKERS = ("Building…", "Building&hellip;", "Building...")
    ALWAYS_CHECKED = ("app/page.jsx", "app/page.js")
    # From: agents/analysis/analysis_shared.py
    _UNAWAITED_RE = re.compile(r"(?<!await\s)(?<!await)\b(getCollection|getDb|getSessionUser)\s*\([^()]*\)\s*\.\s*([A-Za-z_$][\w$]*)")
    # From: agents/analysis/analysis_shared.py
    _OID_RE = re.compile(r"\bnew\s+ObjectId\s*\(\s*([^)]{1,80}?)\s*\)")
    # From: agents/analysis/analysis_shared.py
    _SELF_PARAMS_RE = re.compile(r"const\s*\{\s*(params|searchParams)\s*:\s*\w+[^}]*\}\s*=\s*await\s+\1\b")
    # From: agents/analysis/analysis_shared.py
    _DIRECT_PARAMS_RE = re.compile(r"(?:function|=>)[^{]{0,300}\{\s*params\s*\}[^\n{]*\{[\s\S]{0,1200}?\bparams\.")
    # From: agents/analysis/analysis_shared.py
    _CLIENT_RE = re.compile(r"^\s*(?:(?://[^\n]*\n)|(?:/\*.*?\*/\s*))*['\"]use client['\"]", re.S)
    # From: agents/analysis/analysis_shared.py
    _EVENT_RE = re.compile(r"\bon(?:Click|Change|Submit|Select|Blur|Focus|Key\w*|Mouse\w*|Pointer\w*|Drag\w*|Drop|Input|Toggle|Close|Open|Save|Delete|Update|Create)\s*=", re.I)
    # From: agents/analysis/analysis_shared.py
    _AUTH_CALL_RE = re.compile(r"\b(?:(?:signIn|signUp)\.email|signOut)\s*\(")
    # From: agents/analysis/analysis_shared.py
    _AUTH_SUCCESS_RE = re.compile(r"\b(?:result|res|response|data|out)\s*(?:\?)?\.\s*success\b")
    # From: agents/analysis/analysis_shared.py
    _IMPORT_RE = re.compile(r"""from\s+['"]@/(components/[\w./-]+)['"]""")
    # From: agents/analysis/analysis_shared.py
    _FETCH_RE = re.compile(r"""fetch\(\s*[`'"](/api/[\w./\[\]-]+)""")


__all__ = ["AnalyzerAgent", "AnalyzerReport", "Finding", "REPAIRABLE_MAJOR",
           "BCRYPT_LITERAL_RE", "CODE_EXT", "FETCH_URL_RE", "HTTP_METHOD_RE",
           "LINK_HREF_RE", "MAX_FILE_BYTES", "NEXT_ROOTS", "PLACEHOLDER_RE",
           "PROSE_PATH_RE", "ROOT_SOURCE", "ROUTER_PUSH_RE", "SEVERITIES",
           "SKIP_DIRS", "SOURCE_EXT", "log"]
