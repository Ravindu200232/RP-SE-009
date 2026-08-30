"""Public application builder composed from small builder stages."""
from __future__ import annotations

# Source: builder_setup.py — model/session setup and streaming.
from agents.planner.builder.builder_setup import BuilderSetupMixin
# Source: file_writer.py — safe project writes and scaffold status.
from agents.planner.builder.file_writer import FileWriterMixin
# Source: build_tasks.py — plan-to-files build loop.
from agents.planner.builder.build_tasks import BuildTasksMixin
# Source: dependency_manager.py — package/import dependency recovery.
from agents.planner.builder.dependency_manager import DependencyManagerMixin
# Source: build_validation.py — lint and output contract checks.
from agents.planner.builder.build_validation import BuildValidationMixin
# Source: project_memory.py — snapshots, resume state and ledgers.
from agents.planner.builder.project_memory import ProjectMemoryMixin
# Source: write_stream.py — parses streamed file blocks.
from agents.planner.builder.write_stream import FileStreamParser
# Source: builder_shared.py — class-level constants used by the builder.
from agents.planner.builder.builder_shared import CHARS_PER_TOKEN, EDIT_TIMEOUT, HISTORY_BUDGET, re


class ArchitectAgent(BuilderSetupMixin, FileWriterMixin, BuildTasksMixin,
                     DependencyManagerMixin, BuildValidationMixin,
                     ProjectMemoryMixin):
    """Turn one approved plan into a complete working application."""
    """Build, resume, and update one generated application."""

    # Scaffold files the product is EXPECTED to replace. app/page.jsx ships as
    # a "Building…" placeholder and lib/seed.js as a no-op stub, purely so the
    # app compiles before the product exists. Guarding them the same way as the
    # real defaults meant that when the plan came back empty, nothing could
    # ever overwrite the placeholder — not the builder, not the repair pass —
    # and the app served "Building…" while still passing its own journey.
    NEXT_PLACEHOLDERS = frozenset({"app/page.jsx", "lib/seed.js"})
    NEXT_SCAFFOLD = NEXT_PLACEHOLDERS | frozenset({
        "package.json", "next.config.mjs", "jsconfig.json", "tailwind.config.js",
        "postcss.config.js", "app/globals.css", "app/layout.jsx",
        "lib/mongodb.js", "app/api/health/route.js", "app/api/seed/route.js",
        ".env.local", ".gitignore",
        "lib/auth.js", "lib/auth-client.js", "app/api/auth/[...all]/route.js",
    })
    NEXT_PROTECTED = (NEXT_SCAFFOLD - NEXT_PLACEHOLDERS) | {
        "vitest.config.mjs", "playwright.config.js"}
    NODE_BUILTINS = {"assert", "buffer", "child_process", "crypto", "events", "fs",
                     "fs/promises", "http", "https", "module", "net", "os", "path",
                     "process", "stream", "timers", "tls", "url", "util", "zlib"}
    PREINSTALLED = {"react", "react-dom", "next", "mongodb", "better-auth",
                    "@better-auth/mongo-adapter", "lucide-react", "framer-motion"}
    # From: agents/planner/builder/builder_shared.py
    PKG_NAME_RE = re.compile(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", re.I)
    # From: agents/planner/builder/builder_shared.py
    IMPORT_SPEC_RE = re.compile(r"(?:\bfrom\s*|\brequire\s*\(\s*|\bimport\s*\(\s*|\bimport\s+)[\"']([^\"'\s()]+)[\"']")
    # From: agents/planner/builder/builder_shared.py
    LOCAL_IMPORT_RE = re.compile(r"(?:from\s+|import\s*)[\"'](\.[^\"']+)[\"']")
    # From: agents/planner/builder/builder_shared.py
    ALIAS_IMPORT_RE = re.compile(r"(?:from\s+|import\s*)[\"']@/([^\"']+)[\"']")
    # From: agents/planner/builder/builder_shared.py
    STRAY_DIRECTIVE_RE = re.compile(r"^[^\S\n]*[\"']use client[\"'][^\S\n]*;?", re.M)
    # From: agents/planner/builder/builder_shared.py
    UNRESOLVED_RE = re.compile(r"(?:Can't resolve|Cannot find module)\s*[\"']([^\"'\n]+)[\"']")
    EDIT_TIMEOUT = EDIT_TIMEOUT


__all__ = ["ArchitectAgent", "FileStreamParser", "CHARS_PER_TOKEN", "HISTORY_BUDGET"]
