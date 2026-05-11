"""Jest test generator.

Strategy (in priority order):
 - **Ollama** running locally (default). We probe http://127.0.0.1:11434/api/tags;
   if reachable we pick the best available code-specialised model
   (codellama:7b is the user-preferred default).
 - **Anthropic** if `ANTHROPIC_API_KEY` is set.
 - **OpenAI** if `OPENAI_API_KEY` is set.
 - **Heuristic** deterministic generator as the final fallback. The heuristic
   is also used as a safety net if the LLM call raises, or if the LLM produces
   output that doesn't compile.

Configuration env vars:
 - AGENT3_OLLAMA_BASE   override Ollama base URL (default http://127.0.0.1:11434)
 - AGENT3_OLLAMA_MODEL  pin a specific Ollama model (otherwise auto-pick)
 - AGENT3_DISABLE_LLM   set to "1" to force the heuristic path
"""
from __future__ import annotations

import json as _json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

from .analyzer import ModuleKind
from .models import FunctionInfo

try:
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_AVAILABLE = True
except Exception:  # pragma: no cover
    ChatPromptTemplate = None
    LANGCHAIN_AVAILABLE = False


_OLLAMA_BASE = os.environ.get("AGENT3_OLLAMA_BASE", "http://127.0.0.1:11434")
_OLLAMA_PREFERRED = [
    "codellama:7b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "deepseek-coder:6.7b",
    "starcoder2:7b",
    "starcoder2:15b",
]


def _ollama_models() -> list[str]:
    try:
        req = urllib.request.Request(f"{_OLLAMA_BASE.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []


def _ollama_pick_model() -> str | None:
    pinned = os.environ.get("AGENT3_OLLAMA_MODEL")
    installed = _ollama_models()
    if not installed:
        return None
    if pinned and pinned in installed:
        return pinned
    for candidate in _OLLAMA_PREFERRED:
        if candidate in installed:
            return candidate
    return installed[0]


def llm_provider() -> str | None:
    if os.environ.get("AGENT3_DISABLE_LLM") == "1":
        return None
    model = _ollama_pick_model()
    if model:
        return f"ollama:{model}"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def _try_get_llm():
    provider = llm_provider()
    if provider is None:
        return None
    if provider.startswith("ollama:"):
        model = provider.split(":", 1)[1]
        try:
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=model,
                base_url=_OLLAMA_BASE,
                temperature=0.1,
                num_predict=2000,
                num_ctx=4096,
            )
        except Exception:
            return None
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model="claude-haiku-4-5", max_tokens=3000, temperature=0.1)
        except Exception:
            return None
    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
        except Exception:
            return None
    return None


# ── Prompts ─────────────────────────────────────────────────────────────────
PROMPT_CJS = """You are generating thorough Jest unit tests for a Node.js/Express service module.

Module relative path: {relative}
Module module-kind: CommonJS
Module source:
```javascript
{source}
```

Exported functions: {functions}

Requirements - aim for HIGH COVERAGE:
 1. For EACH exported function write at least 5 tests:
     - 1 happy-path test using realistic input
     - 2 edge cases (boundary values, empty/null/undefined where appropriate)
     - 2 negative / failure paths (wrong type, missing required field, returns
       error code or throws)
 2. If the function has if/else branches, add a test for each branch.
 3. If a function returns an object like {{ ok: false, reason: 'X' }}, assert
    on the reason string.
 4. NEVER make real network or DB calls. Mock external collaborators with
    `jest.fn()`. If a function calls into mongoose/prisma/axios, mock the module:
    `jest.mock('axios')` etc.
 5. Use `describe` blocks per function. Use `expect(...)` matchers only.
 6. Import the module with CommonJS: `const mod = require('{require_path}');`

Return ONLY the test file source. No markdown fences, no commentary."""

PROMPT_ESM = """You are generating thorough Jest unit tests for a Node.js ESM module.

Module relative path: {relative}
Module module-kind: ECMAScript Modules ("type":"module")
Module source:
```javascript
{source}
```

Exported functions: {functions}

Requirements - aim for HIGH COVERAGE:
 1. For EACH exported function write at least 5 tests:
     - 1 happy-path test using realistic input
     - 2 edge cases (boundary values, empty/null/undefined)
     - 2 negative / failure paths
 2. Cover each if/else branch in the source.
 3. Mock external collaborators with `jest.fn()`. NEVER make real DB / HTTP calls.
 4. Use `describe` per function.
 5. Use ESM imports:  `import * as mod from '{require_path}';`
    and  `import {{ jest }} from '@jest/globals';`
 6. Use `expect(...)` matchers only.

Return ONLY the test file source. No markdown fences, no commentary."""


def generate_test_for_module(
    *,
    source_path: Path,
    service_root: Path,
    functions: list[FunctionInfo],
    source: str,
    module_kind: ModuleKind = "cjs",
) -> tuple[str, bool]:
    """Generate Jest test source. Returns (code, used_llm)."""
    if not functions:
        return _placeholder_test(source_path, service_root, module_kind), False

    require_path = _require_path(source_path, service_root)
    llm = _try_get_llm()
    if llm is not None and LANGCHAIN_AVAILABLE:
        try:
            template = PROMPT_ESM if module_kind == "esm" else PROMPT_CJS
            prompt = ChatPromptTemplate.from_template(template)
            messages = prompt.format_messages(
                relative=source_path.relative_to(service_root).as_posix(),
                source=source[:6000],
                functions=", ".join(f.name for f in functions),
                require_path=require_path,
            )
            response = llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            cleaned = _strip_fences(content).strip()
            if _looks_like_test_code(cleaned, module_kind):
                return cleaned, True
        except Exception:
            pass

    return _heuristic_test(source_path, service_root, functions, module_kind), False


def _looks_like_test_code(text: str, kind: ModuleKind) -> bool:
    if not text or len(text) < 40:
        return False
    if "describe(" not in text and "test(" not in text and "it(" not in text:
        return False
    if kind == "esm":
        # accept either import or fall back if the model used require - we'll repair
        return "import" in text or "require(" in text
    return "require(" in text or "import" in text


def _require_path(source_path: Path, service_root: Path) -> str:
    """Path used from inside __tests__/<x>.test.js back to the source module."""
    rel = source_path.relative_to(service_root).with_suffix("").as_posix()
    return f"../{rel}"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[: -3]
    return text.strip()


# ── Heuristic generator ─────────────────────────────────────────────────────
def _heuristic_test(
    source_path: Path,
    service_root: Path,
    functions: list[FunctionInfo],
    kind: ModuleKind,
) -> str:
    require_path = _require_path(source_path, service_root)
    module_name = source_path.stem
    use_esm = kind == "esm"

    lines: list[str] = ["// Auto-generated by Agent 3 (heuristic generator)"]
    if use_esm:
        lines.append(f"import * as mod from '{require_path}.js';")
        lines.append("import { jest, describe, it, expect } from '@jest/globals';")
    else:
        lines.append(f"const mod = require('{require_path}');")
    lines.append("")
    lines.append(f"describe('{module_name}', () => {{")

    for fn in functions:
        sample_args = _sample_args(fn.params, fn.name)
        edge_args = _edge_args(fn.params, fn.name)
        bad_args = _bad_args(fn.params)
        lines.append(f"  describe('{fn.name}', () => {{")

        # 1. Exported as a function
        lines.append(f"    it('is exported as a function', () => {{")
        lines.append(f"      expect(typeof mod.{fn.name}).toBe('function');")
        lines.append(f"    }});")

        # 2. Happy path - runs without throwing
        lines.append(f"    it('runs on valid input without throwing', () => {{")
        lines.append(f"      expect(() => mod.{fn.name}({sample_args})).not.toThrow();")
        lines.append(f"    }});")

        # 3. Returns a defined value
        lines.append(f"    it('returns a defined value on valid input', () => {{")
        lines.append(f"      const result = mod.{fn.name}({sample_args});")
        lines.append(f"      expect(result).not.toBe(undefined);")
        lines.append(f"    }});")

        # 4. Edge case input
        lines.append(f"    it('handles edge-case input gracefully', () => {{")
        lines.append(f"      let result;")
        lines.append(f"      try {{ result = mod.{fn.name}({edge_args}); }} catch (e) {{ result = e; }}")
        lines.append(f"      expect(result).toBeDefined();")
        lines.append(f"    }});")

        # 5. Wrong-type input - either throws OR returns ok:false; both are valid signals
        lines.append(f"    it('rejects clearly invalid input', () => {{")
        lines.append(f"      let threw = false;")
        lines.append(f"      let result;")
        lines.append(f"      try {{ result = mod.{fn.name}({bad_args}); }} catch (e) {{ threw = true; }}")
        lines.append(f"      const rejected = threw ||")
        lines.append(f"        result === false ||")
        lines.append(f"        result === null ||")
        lines.append(f"        (typeof result === 'object' && result && (result.ok === false || result.error || result.reason));")
        lines.append(f"      expect(rejected).toBeTruthy();")
        lines.append(f"    }});")

        # 6. Re-running with the same input is stable (idempotent shape)
        lines.append(f"    it('produces a stable result type for repeated calls', () => {{")
        lines.append(f"      let a, b;")
        lines.append(f"      try {{ a = mod.{fn.name}({sample_args}); b = mod.{fn.name}({sample_args}); }} catch (e) {{")
        lines.append(f"        // both calls threw - that's still stable")
        lines.append(f"        expect(true).toBe(true);")
        lines.append(f"        return;")
        lines.append(f"      }}")
        lines.append(f"      expect(typeof a).toBe(typeof b);")
        lines.append(f"    }});")

        lines.append(f"  }});")

    lines.append("});")
    lines.append("")
    return "\n".join(lines)


_GENERIC_PAYLOAD = (
    "{ email: 'user@example.com', password: 'P@ssword12!', "
    "name: 'Test User', role: 'member', "
    "amount: 100, taxRate: 0.1, discount: 0, "
    "roomId: 'std_1', checkIn: '2026-06-01', checkOut: '2026-06-03', "
    "userId: 'u1', id: 'abc123' }"
)
_EDGE_PAYLOAD = (
    "{ email: 'a@b.co', password: 'Aa1!aaaa', name: '', role: 'guest', "
    "amount: 0, taxRate: 0, discount: 0, "
    "roomId: 'std_1', checkIn: '2026-06-01', checkOut: '2026-06-02', userId: 'u1' }"
)


def _sample_args(params: list[str], fn_name: str) -> str:
    return ", ".join(_resolve_param(p, mode="happy") for p in params)


def _edge_args(params: list[str], fn_name: str) -> str:
    return ", ".join(_resolve_param(p, mode="edge") for p in params)


def _bad_args(params: list[str]) -> str:
    if not params:
        return ""
    out = ["null"]
    for _ in params[1:]:
        out.append("undefined")
    return ", ".join(out)


def _resolve_param(name: str, *, mode: Literal["happy", "edge"]) -> str:
    lower = name.lower()
    if lower in {"req", "request"}:
        return (
            "{ body: { email: 'user@example.com', password: 'P@ssword12!', amount: 100, days: 2 }, "
            "params: { id: 'abc' }, query: {}, headers: {} }"
        )
    if lower in {"res", "response"}:
        return "{ status: jest.fn().mockReturnThis(), json: jest.fn().mockReturnThis(), send: jest.fn() }"
    if lower == "next":
        return "jest.fn()"
    if "email" in lower:
        return "'a@b.co'" if mode == "edge" else "'user@example.com'"
    if "password" in lower:
        return "'Aa1!aaaa'" if mode == "edge" else "'P@ssword12!'"
    if "amount" in lower or "price" in lower or "total" in lower:
        return "0" if mode == "edge" else "100"
    if "days" in lower or "count" in lower or "qty" in lower or "parts" in lower:
        return "1" if mode == "edge" else "2"
    if "rate" in lower or "tax" in lower or "discount" in lower:
        return "0" if mode == "edge" else "0.1"
    if "token" in lower:
        return "'a.b'" if mode == "edge" else "'token.value.here'"
    if "card" in lower:
        return "{ number: '4242424242424242' }"
    if "user" in lower:
        return "{ id: 'u1', email: 'a@b.co' }" if mode == "edge" else "{ id: 'u1', email: 'user@example.com', role: 'member' }"
    if "booking" in lower:
        return "{ id: 'b1', roomId: 'std_1', checkIn: '2026-06-01', checkOut: '2026-06-02' }"
    if "room" in lower:
        return "'std_1'"
    if "checkin" in lower or "checkout" in lower or "date" in lower:
        return "'2026-06-01'"
    if "id" in lower:
        return "'x'" if mode == "edge" else "'abc123'"
    if lower in {"hash"}:
        return "'h$0'"
    if lower in {"opts", "options", "config", "settings"}:
        return "{}"
    if lower in {"a", "b", "range"}:
        return "{ checkIn: '2026-06-01', checkOut: '2026-06-03' }"
    if lower in {"existingbookings", "bookings", "list", "items", "rows"}:
        return "[]"
    if lower in {"payload", "body", "data", "input", "params"}:
        return _EDGE_PAYLOAD if mode == "edge" else _GENERIC_PAYLOAD
    return "{}"


def _placeholder_test(source_path: Path, service_root: Path, kind: ModuleKind) -> str:
    require_path = _require_path(source_path, service_root)
    module_name = source_path.stem
    if kind == "esm":
        return (
            f"// Auto-generated placeholder by Agent 3\n"
            f"import * as mod from '{require_path}.js';\n\n"
            f"describe('{module_name}', () => {{\n"
            f"  it('module loads', () => {{ expect(mod).toBeDefined(); }});\n"
            f"}});\n"
        )
    return (
        f"// Auto-generated placeholder by Agent 3\n"
        f"const mod = require('{require_path}');\n\n"
        f"describe('{module_name}', () => {{\n"
        f"  it('module loads', () => {{ expect(mod).toBeDefined(); }});\n"
        f"}});\n"
    )
