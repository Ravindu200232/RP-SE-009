import json
import os
import re
import subprocess
import tempfile
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from app.state import GraphState
from app.themes import pick_theme, fonts_url, design_brief
from app import planner
from app import design_library
from app import landing_copy

# Local code model: Gemma 4 12B via Ollama (replaces qwen / Gemini everywhere).
# An env override lets the model be swapped without code edits.
MODEL_NAME = os.getenv("AI_DESIGNER_MODEL", "gemma4:12b")

def ensure_ollama(timeout: int = 45) -> bool:
    """Self-healing LLM runtime: if Ollama isn't answering, start `ollama serve`
    and wait for it. Every generation begins with this, so a crashed/closed
    Ollama can never silently degrade an app to generic fallbacks again."""
    import subprocess
    import time as _time
    import urllib.request

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def up() -> bool:
        try:
            with urllib.request.urlopen(f"{host}/api/version", timeout=3):
                return True
        except Exception:
            return False

    if up():
        return True
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, shell=True)
    except Exception:
        return False
    for _ in range(timeout // 3):
        _time.sleep(3)
        if up():
            return True
    return False


def get_llm(temperature: float = 0.0, num_predict: int = 4096, json_mode: bool = True) -> ChatOllama:
    # Allow custom ollama host from env
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    kwargs = {}
    # Gemma 4 is a THINKING model: disable reasoning so the response is clean,
    # directly-parseable JSON (no chain-of-thought trace polluting the output).
    if "gemma" in MODEL_NAME.lower():
        kwargs["reasoning"] = False
    return ChatOllama(
        model=MODEL_NAME,
        format="json" if json_mode else "",   # json_mode=False -> raw text (code edits)
        temperature=temperature,
        base_url=ollama_host,
        num_ctx=16384,
        # Cap generation length to stop runaway/rambling generations. Default
        # 4096 fits normal pages; planned content-heavy pages (landing etc.)
        # pass a higher budget - a truncated JSON envelope can never parse, so
        # an undersized cap silently turns rich pages into fallback stubs.
        num_predict=num_predict,
        **kwargs,
    )

def extract_json(text: str) -> dict:
    if not text:
        raise ValueError("Empty response from LLM")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        # Fallback to finding outer braces
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise

# =========================================================================
# CODE-GENERATION HELPERS (validation + retry so we never save empty stubs)
# =========================================================================
_PLACEHOLDER_LINE = re.compile(r"^\s*//.*code here\.\.\.\s*$", re.IGNORECASE)

def _clean_code(code) -> str:
    """Normalize an LLM 'code' value: join lists, strip code fences, and drop the
    leading '// ... code here...' placeholder line that small models copy from
    the example in the prompt."""
    if code is None:
        return ""
    if isinstance(code, list):
        code = "\n".join(str(part) for part in code)
    if not isinstance(code, str):
        code = str(code)
    text = code.strip()
    text = re.sub(r"^```(?:\w+)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # The model sometimes double-escapes newlines/tabs in its JSON, so they land
    # as a LITERAL backslash-n in the source (e.g. `);\n    navigate(...)`) -> a JS
    # syntax error that kills the whole app. Mis-escaped ones are followed by
    # indentation; real in-string escapes are not, so this is safe.
    text = re.sub(r"\\n(?=[ \t])", "\n", text)
    text = re.sub(r"\\t(?= )", "\t", text)
    # JSX requires void tags to self-close; models keep writing HTML-style
    # <br>/<hr>, which is a fatal parse error.
    text = re.sub(r"<(br|hr)\s*>", r"<\1/>", text)
    # Fix unescaped newlines/carriage returns inside JS regular expression character classes (like [^\r\n])
    # which get parsed as literal newlines by json.loads and cause "Unterminated regular expression" syntax errors.
    text = re.sub(r"\[\^([^\r\n\]]*)[\r\n]+([^\r\n\]]*)\]", r"[^\1\\n\2]", text)
    lines = text.splitlines()
    while lines and (_PLACEHOLDER_LINE.match(lines[0]) or not lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines).strip()

def _is_real_code(code: str, min_len: int = 80) -> bool:
    """True only if `code` looks like a real file rather than an empty stub or a
    copied placeholder comment."""
    if not code or len(code) < min_len:
        return False
    body = "\n".join(
        line for line in code.splitlines()
        if line.strip() and not line.strip().startswith("//")
    ).strip()
    return len(body) >= 30

def _looks_like_html_or_module(code: str) -> bool:
    """True if the model returned a full HTML document or an ES module instead of
    a browser-global UMD component (a known small-model failure that breaks the
    inlined build). Such output must be rejected and regenerated."""
    low = code.lower()
    if "<!doctype" in low or "<html" in low:
        return True
    for line in code.splitlines():
        s = line.strip()
        if s.startswith("import ") or s.startswith("export "):
            return True
    return False

# backend/validate_jsx.js -- parses code with the frontend's @babel/parser.
_VALIDATOR_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "validate_jsx.js")

def _jsx_syntax_error(code: str):
    """Return a one-line syntax-error message if `code` is invalid JS/JSX, else
    None. Best-effort: if node / the parser is unavailable it returns None so it
    never blocks generation."""
    if not os.path.exists(_VALIDATOR_PATH):
        return None
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".jsx", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        res = subprocess.run(["node", _VALIDATOR_PATH, tmp], capture_output=True, text=True, timeout=25)
        if res.returncode == 0:
            return None
        return (res.stderr or "").strip()[:140] or "syntax error"
    except Exception:
        return None
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass

def _generate_code(system_prompt: str, user_prompt: str, invoke_vars: dict,
                   min_len: int = 80, max_attempts: int = 3,
                   num_predict: int = 4096) -> str:
    """Invoke the LLM expecting {"code": "..."} and return cleaned, validated
    source. Retries with an escalating nudge when the model returns empty or
    placeholder text, and raises if it never produces real code."""
    last_reason = "unknown"
    for attempt in range(1, max_attempts + 1):
        sys_prompt = system_prompt
        if attempt > 1:
            sys_prompt += (
                "\n\nIMPORTANT: Your previous response was invalid (empty, a "
                "placeholder, or a full HTML document / ES module). Return ONLY "
                "the COMPLETE source as browser globals - NO <!DOCTYPE> or "
                "<html>, NO import/export statements, attach the component to "
                "window. Use REAL newlines (never a literal backslash-n) and valid "
                "JavaScript. Fully implement everything now."
            )
        llm = get_llm(temperature=0.0 if attempt == 1 else 0.3, num_predict=num_predict)
        chain = ChatPromptTemplate.from_messages([
            ("system", sys_prompt),
            ("user", user_prompt),
        ]) | llm
        try:
            res = chain.invoke(invoke_vars)
            code = _clean_code(extract_json(res.content).get("code", ""))
        except Exception as exc:  # bad JSON, missing key, etc.
            last_reason = f"parse error: {exc}"
            continue
        if not _is_real_code(code, min_len):
            last_reason = f"empty/placeholder output (len={len(code)})"
            continue
        if _looks_like_html_or_module(code):
            last_reason = "returned an HTML document or import/export instead of a UMD module"
            continue
        syntax_err = _jsx_syntax_error(code)
        if syntax_err:
            last_reason = f"JS/JSX syntax error: {syntax_err}"
            try:
                with open("failed_generations.log", "a", encoding="utf-8") as df:
                    df.write(f"=== FAILED ATTEMPT: {invoke_vars.get('page_name', 'unknown')} ===\n")
                    df.write(f"Reason: {last_reason}\n")
                    df.write(code)
                    df.write("\n====================================\n\n")
            except Exception:
                pass
            continue
        return code
    raise ValueError(
        f"Code generation failed after {max_attempts} attempts ({last_reason})."
    )

_ASSET_SRC = re.compile(r"""src=(["'])(?:https?://[^"']*/|/)?assets/""")
_ASSET_URL = re.compile(r"""url\((['"]?)(?:https?://[^'")]*/|/)?assets/""")

def _normalize_asset_paths(code: str) -> str:
    """Images live at <project>/assets/*.jpg and pages are served from the
    project root, so the src MUST be relative ('assets/x.jpg'). Models keep
    writing '/assets/x.jpg' or a full host URL, which resolves to the SERVER
    root and never loads. Rewrite all variants - src attributes AND CSS
    url(...) backgrounds - to the relative form."""
    code = _ASSET_SRC.sub(lambda m: f"src={m.group(1)}assets/", code)
    return _ASSET_URL.sub(lambda m: f"url({m.group(1)}assets/", code)

def _ensure_component(page_name: str, code: str) -> str:
    """Guarantee the page is a mountable component attached to `window`.

    Small models often return bare JSX with no function wrapper or no
    `window.X = X` line. app.jsx reads pages from `window` (`const { X } = window`),
    so without this the page is `undefined` and renders nothing. This deterministically
    normalizes the output so the prototype actually mounts."""
    code = (code or "").strip()
    name = re.escape(page_name)
    has_decl = bool(
        re.search(rf"\b(function|class)\s+{name}\b", code)
        or re.search(rf"\b(const|let|var)\s+{name}\b\s*=", code)
    )
    has_attach = f"window.{page_name}" in code

    if has_decl:
        if has_attach:
            return code
        return code + f"\n\nwindow.{page_name} = {page_name};\n"

    # No matching declaration. If it looks like bare JSX, wrap it into a component.
    if code.lstrip().startswith(("<", "(")):
        indented = "\n".join(("      " + ln) if ln.strip() else ln for ln in code.splitlines())
        return (
            f"function {page_name}() {{\n"
            "  const { useState, useEffect } = React;\n"
            "  const { useNavigate, Link } = ReactRouterDOM;\n"
            "  const { Icon } = window;\n"
            "  return (\n"
            "    <>\n"
            f"{indented}\n"
            "    </>\n"
            "  );\n"
            "}\n"
            f"window.{page_name} = {page_name};\n"
        )

    # Unknown shape: best effort, just make sure it attaches to window.
    if not has_attach:
        return code + f"\n\nwindow.{page_name} = {page_name};\n"
    return code

def _fallback_page(page_name: str, page_desc: str) -> str:
    """A minimal but VALID page used only when the model repeatedly fails, so a
    single bad generation degrades gracefully instead of breaking the build."""
    safe_desc = (page_desc or "This page is being prepared.").replace('"', "'")
    title = page_name.replace("_", " ")
    # High-contrast, theme-agnostic card (explicit white bg + slate text) so even
    # a fallback page is clearly visible content, never a blank/invisible screen.
    return (
        "const { useState } = React;\n"
        f"function {page_name}() {{\n"
        "  return (\n"
        '    <div className="min-h-[60vh] flex items-center justify-center p-6">\n'
        '      <div className="bg-white text-slate-800 border border-slate-200 rounded-2xl shadow-xl p-8 max-w-xl w-full text-center">\n'
        f'        <h1 className="text-2xl font-bold text-slate-900 mb-2">{title}</h1>\n'
        f'        <p className="text-slate-500 mb-5">{safe_desc}</p>\n'
        '        <a href="#/dashboard" className="inline-block bg-slate-800 hover:bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-semibold">Back to Dashboard</a>\n'
        "      </div>\n"
        "    </div>\n"
        "  );\n"
        "}\n"
        f"window.{page_name} = {page_name};\n"
    )

# =========================================================================
# 1. PLANNER AGENT
# =========================================================================
_EXTRACT_PROMPT = """You extract a data model from an app idea so a multi-page prototype can be generated.
Read the user's request (a short description) and output ONLY raw JSON in this shape:
{{
  "app_name": "Short App Name",
  "roles": ["Admin", "Staff", "User"],
  "entities": [
    {{ "name": "MemberProfile", "label": "Member",
       "fields": [
         {{ "name": "full_name", "label": "Full Name", "type": "text", "required": true }},
         {{ "name": "status", "label": "Status", "type": "select", "required": true, "options": ["Active", "Inactive"] }}
       ] }}
  ]
}}
RULES:
- 2 to 5 entities, each with 4 to 8 realistic fields.
- field "type" is one of: text, textarea, number, email, tel, date, datetime-local, select, checkbox.
- entity "name" PascalCase; field "name" snake_case. Add "options" only for select fields.
No markdown, no comments, only raw JSON."""

def plan_design_agent(state: GraphState):
    """Build a rich 15+ page site plan. SRS JSON is parsed deterministically;
    a natural-language prompt is turned into a spec by one focused LLM call.
    Either way the page set + flow is expanded DETERMINISTICALLY by planner.py."""
    prompt_text = state["prompt"]

    spec = planner.parse_srs(prompt_text)
    source = "SRS JSON"
    if spec is None:
        # The extraction defines EVERYTHING downstream (entities, roles, pages,
        # seeds) - a single transient LLM failure (e.g. the model still loading
        # into VRAM after a restart) must not silently degrade the whole app to
        # the generic fallback. Retry with backoff before giving up.
        import time as _time
        raw = {}
        for attempt in range(3):
            try:
                llm = get_llm(temperature=0.1 if attempt == 0 else 0.3)
                chain = ChatPromptTemplate.from_messages([
                    ("system", _EXTRACT_PROMPT),
                    ("user", "App request:\n\n{prompt}")
                ]) | llm
                raw = extract_json(chain.invoke({"prompt": prompt_text}).content)
                if raw.get("entities"):
                    break
            except Exception:
                raw = {}
            _time.sleep(8 * (attempt + 1))
        spec = planner.normalize_spec(raw)
        source = "prompt"

    pages = planner.build_pages(spec)
    return {
        "roles": spec.get("roles", ["Admin", "User"]),
        "entities": spec.get("entities", []),
        "app_name": spec.get("app_name", "App"),
        "pages": pages,
        "status": f"Planner ({source}): {len(spec.get('entities', []))} entities -> {len(pages)} pages.",
    }

# =========================================================================
# 2. LOCALSTORAGE DB GENERATOR
# =========================================================================
_DB_PROMPT = """You are a React developer. Generate `src/db.jsx`: a mock database on `window.AppDB` backed by browser localStorage. No import/export.

Implement EXACTLY these functions:
- `window.AppDB.init()`: if not already seeded (guard with a flag key), seed everything below into localStorage (one localStorage key per entity, value = a JSON array). Also seed the users array.
- `window.AppDB.getCurrentUser()`: parse localStorage 'session' (JSON) and return the user object, or null.
- `window.AppDB.login(email, password)`: find a user in the 'users' list with matching email and password; on success store it as 'session' (JSON) and return true; otherwise return false.
- `window.AppDB.logout()`: remove 'session'.
- `window.AppDB.register(email, password, role, extra)`: push a new user into 'users', store 'session', and return the user.
- `window.AppDB.getRecords(key)`: return JSON.parse(localStorage[key]) or an empty array.
- `window.AppDB.createRecord(key, data)`: generate a unique string id, push `{{ id, ...data }}`, persist, and return it.
- `window.AppDB.updateRecord(key, id, data)`: merge data into the record with that id and persist.
- `window.AppDB.deleteRecord(key, id)`: remove the record with that id and persist.
Call `window.AppDB.init()` once at the very end of the file.

USERS to seed (one per role, every password = 'password123'): {roles}

ENTITIES to seed - use the EXACT localStorage key and the EXACT field names shown, give every record a unique string `id`, and create 15-20 highly realistic, domain-specific, and detailed rows each (using varied, descriptive names, titles, values, prices, numbers, proper dates and statuses - NEVER use generic names like "Item 1", "Test", or "Lorem ipsum"):
{entities_brief}

SEED RULES (CRITICAL):
- Every seed row is a LITERAL hand-written object with realistic values, e.g. {{ id: 'p1', full_name: 'Amara Silva', date_of_birth: '1989-04-12', gender: 'Female', contact_number: '+1 555-0182', email: 'amara.silva@example.com', status: 'Active' }}.
- ABSOLUTELY FORBIDDEN in seed data: Math.random, Date.now arithmetic, loops (for/while/Array.from/.map) to fabricate rows, template-literal value tricks, or copy-pasting the same row. Each row unique, hand-written, domain-appropriate.

Return ONLY a JSON object with one key "code" (the COMPLETE db.jsx source). No markdown, no placeholders, no ellipses."""

def _entities_seed_brief(entities) -> str:
    if not entities:
        return "- 'Item': records { id, name, status } - seed 5 realistic rows."
    lines = []
    for e in entities:
        key = e.get("storage_key", e.get("name", "Item"))
        fnames = ", ".join(f["name"] for f in e.get("fields", [])) or "name"
        lines.append(f"- '{key}': each record has {{ id, {fnames} }}")
    return "\n".join(lines)

# Math.random().toString(36) is the legit id-generation idiom - only flag
# Math.random used for VALUES (not immediately stringified into an id).
_LAZY_SEED = re.compile(r"Math\.random\(\)\s*(?!\.toString)|Array\.from|Array\(\s*\d+\s*\)\.fill|for\s*\(.*<\s*\d+", re.S)

def generate_db_agent(state: GraphState):
    invoke_vars = {
        "roles": ", ".join(state.get("roles", ["Admin", "User"])),
        "entities_brief": _entities_seed_brief(state.get("entities", [])),
    }
    sys_prompt = _DB_PROMPT
    code = ""
    for attempt in range(2):
        code = _generate_code(sys_prompt, "Generate the db.jsx code.", invoke_vars, min_len=1000)
        # Lazy seeds (random numbers / loop-fabricated rows) make every list and
        # dashboard look like garbage ("4 31" as a patient name). Retry once with
        # an explicit correction; the page-level empty-states still hold if it
        # somehow persists.
        if not _LAZY_SEED.search(code):
            break
        sys_prompt = _DB_PROMPT + (
            "\n\nIMPORTANT: Your previous attempt fabricated seed rows with Math.random/loops. "
            "That is FORBIDDEN. Write every seed row as a literal, hand-written object with "
            "realistic domain values (real names, dates, statuses)."
        )
    return {
        "files": {**state.get("files", {}), "src/db.jsx": code},
        "status": "LocalStorage mock database generated successfully."
        + (" [WARNING: lazy seeds detected twice]" if _LAZY_SEED.search(code) else ""),
    }

# =========================================================================
# 2.5 CHILD PAGE PLANNER -- plans ONE rich page (sections + real copy) before
# the coder writes it. The main planner divides the app into pages; this child
# planner divides a page into sections with exact content, so the 7B coder
# only has to IMPLEMENT, not invent. Used for the content-heavy pages.
# =========================================================================
_PAGE_PLAN_PROMPT = """You are a senior product designer planning ONE page of a professional web app.
App: "{app_name}" - {app_context}
Page to plan: {page_name} (type: {kind}). Visual layout style: {layout_name}.

Write the COMPLETE content plan as ordered sections. This page must feel like a real, polished product - generous, specific, professional.
Output ONLY raw JSON:
{{"sections": [{{"title": "<section heading>", "kind": "<hero|logos|features|how|stats|testimonials|pricing|faq|cta|footer|widgets|chart|table|form|content>", "copy": "<the EXACT text content: headlines, sentences, item names + descriptions, numbers, names - written out in full>"}}]}}

RULES:
- LANDING page: 10-14 sections in this spirit: hero (headline+subline+2 CTA labels), trusted-by logos row (5 company names), features (6 items: name + 1-sentence description each), how-it-works (3 steps), big stats (4 number+label pairs), product highlights band, testimonials (3: full name, role, 2-sentence quote), pricing (3 tiers: name, monthly price, 5 features each), FAQ (5 real questions + 2-sentence answers), final CTA, footer columns.
- FEATURES/ABOUT/CONTACT: 5-8 sections, equally specific (about: mission, story, values (4), timeline (4 milestones), team (4 members: name+role)).
- DASHBOARD: one section per widget: stat cards (one per entity: label + caption), overview chart (12 month values 20-95), this-week card, recent table (which columns), quick actions (button labels + target routes), activity feed (4 entries).
- Write REAL copy for "{app_name}" specifically - actual sentences, realistic names, prices, numbers. NEVER "Lorem ipsum", never placeholders, never "Feature 1".
- All in English. No markdown, ONLY the JSON object."""

_PLANNED_KINDS = {"landing", "features", "about", "contact", "dashboard"}

def plan_page_agent(state: GraphState, page: dict, layout_name: str) -> str:
    """Return a rendered section plan for a rich page ('' when not applicable
    or planning fails - generation then falls back to the static brief alone)."""
    if page.get("kind") not in _PLANNED_KINDS:
        return ""
    try:
        llm = get_llm(temperature=0.4)
        chain = ChatPromptTemplate.from_messages([
            ("system", _PAGE_PLAN_PROMPT),
            ("user", "Plan the {page_name} page now."),
        ]) | llm
        raw = extract_json(chain.invoke({
            "app_name": state.get("app_name", "App"),
            "app_context": (state.get("prompt") or "")[:300],
            "page_name": page.get("name", "Page"),
            "kind": page.get("kind", "content"),
            "layout_name": layout_name,
        }).content)
        sections = raw.get("sections") or []
        if not isinstance(sections, list) or len(sections) < 3:
            return ""
        lines = []
        for i, s in enumerate(sections[:12], 1):
            if not isinstance(s, dict):
                continue
            copy = s.get("copy")
            if isinstance(copy, (dict, list)):
                copy = json.dumps(copy, ensure_ascii=False)
            lines.append(f"{i}. [{s.get('kind','content')}] {s.get('title','Section')}: {str(copy)[:500]}")
        if not lines:
            return ""
        return ("\n\nPAGE PLAN - implement EVERY section below, in this order, using this EXACT copy "
                "(expand visually, never skip or shorten a section):\n" + "\n".join(lines))
    except Exception:
        return ""

# =========================================================================
# 3. PAGE GENERATOR
# =========================================================================
_PAGE_PROMPT = """You are a Senior Frontend Developer expert in Tailwind CSS and React.
Create the page component `{page_name}` for the app "{app_name}".

APP CONTEXT — write ALL visible text specifically for THIS real app:
- App name (use it EXACTLY as the brand and as the hero headline — do NOT output the literal word "AppName"): {app_name}
- What the app is about: {app_context}
- Every heading, card, feature, label and sample value must be CONCRETE and domain-specific to this app. ABSOLUTELY FORBIDDEN strings: "AppName", "App Name", "Lorem ipsum", "Feature 1"/"Feature 2"/"Feature 3", "premium app", "Your Company", "Title", "Description here", or any filler text.
- Do NOT emit repeated placeholder cards via `[1,2,3].map(...)` or `Array(n).fill()` with identical "Feature {{i}}" + "Lorem ipsum" content. Write each feature/step/testimonial/FAQ item out EXPLICITLY, each with its own real, distinct title and description relevant to {app_name}.

GLOBALS (no import/export - everything is a browser global):
- `const {{ useState, useEffect }} = React;`
- `const {{ useNavigate, Link }} = ReactRouterDOM;` (also available as bare globals)
- `const {{ Icon }} = window;`  ->  use `<Icon name="..." className="w-5 h-5" />`
- Mock DB: `window.AppDB.getRecords(key)`, `.createRecord(key, data)`, `.updateRecord(key, id, data)`, `.deleteRecord(key, id)`, `.getCurrentUser()`.

HARD RULES:
- Attach the component to window: `window.{page_name} = {page_name};`. Return a COMPLETE `function {page_name}() {{ ... }}` module. NEVER return bare JSX, an HTML document, or import/export.
- NULL-SAFETY (the #1 cause of blank pages): DB data and the current user are null/undefined on the FIRST render. Use `useState([])` for lists; read the user directly (`const user = window.AppDB.getCurrentUser();`) and ALWAYS optional-chain: `{{user?.email || 'Guest'}}`, `{{rec?.field ?? '-'}}`. NEVER read `obj.prop` where obj can be null on first render. When calling a string method in a search filter, the FIELD may be missing/numeric (`row?.field.toLowerCase()` still crashes) - wrap it: `String(row?.field ?? '').toLowerCase()`. For an AVATAR INITIAL never write `user.name[0]` or `user?.name[0]` (the field may be undefined -> "reading '0'" crash) - use `String(user?.name || user?.email || '?').charAt(0).toUpperCase()`. The same applies to ANY `x.field[0]` / `x.field.charAt(0)`: wrap with `String(x?.field ?? '')` first.
- NO INFINITE LOOPS: never put an object/array that is re-created every render (e.g. `window.AppDB.getCurrentUser()` or `window.AppDB.getRecords(...)`) into a useEffect dependency array - its identity changes each render and triggers "Maximum update depth exceeded". Use an EMPTY dependency array `[]` to load data once, or depend only on a primitive (string/number/boolean).
- CONTROLLED INPUTS: initialise EVERY form field to an empty string `''` (NEVER null/undefined), keep input values as strings in state, and bind `value={{formData.field ?? ''}}`. When pre-filling an edit form from a record, build the state FIELD BY FIELD with defaults (`{{ name: rec?.name ?? '', date: rec?.date ?? '' }}`) - never `useState(rec)`. Parse numbers only inside the submit handler. This avoids "value should not be null" and "controlled to uncontrolled" warnings.
- AVATAR INITIALS / CHAR INDEXING: never index a possibly-missing string (`user.name[0]` crashes when name is absent). Always `String(user?.name || user?.email || '?').charAt(0).toUpperCase()`.
- IMAGE PATHS: asset images are RELATIVE: `src="assets/hero.jpg"` - never `/assets/...`, never a domain.
- REGEX ESCAPES: Never use `\\r` or `\\n` inside regular expression literals (like email validation regex). Instead of `/^[^\r\n@]+@[^\r\n@]+$/`, use a simple standard regex like `/^[^\s@]+@[^\s@]+\\.[^\s@]+$/` or `/^[^@]+@[^@]+\\.[^@]+$/`. Backslash-r/n inside regex literals get mangled by JSON encoding into literal newlines, which causes JS syntax compile errors.
- INTERACTIVITY (no dead controls - every single button must DO something): every `<button>` MUST have a working `onClick` (navigate(...), open/close a modal, or change visible state), unless it is `type="submit"` inside a `<form onSubmit={{...}}>`. Never render a decorative button. POPUPS/MODALS: implement with local state - `const [showX, setShowX] = useState(false);` and when true render `<div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={{() => setShowX(false)}}><div className="..themed card.. max-w-md w-full" onClick={{(e) => e.stopPropagation()}}>...</div></div>` with a working Close button. Confirm-delete popups must actually delete on confirm. Icon-only buttons (bell, dots-menu) must toggle a dropdown/panel that really opens.
- LAYOUT SAFETY (text must NEVER overlap): never absolutely position TEXT over other text. Use `absolute` ONLY for decorative shapes/badges inside a `relative` parent that reserves space with padding. NEVER give a fixed height (`h-40`, `h-screen`) to a container with flowing text - use `min-h-*` so it grows. Long/unknown strings (emails, names, descriptions) get `truncate` (single line) or `break-words` (multi-line), and any flex row holding text needs `min-w-0` on the text child. Do not use negative margins to pull elements over text. Keep `z-` layering only for navbars/modals/decorative backgrounds (`-z-10` behind content).
- {shell_rule}
- Apply the DESIGN SYSTEM tokens below as the EXACT Tailwind classes for backgrounds, cards, buttons, inputs, text and accents. Do not invent other color families. Add smooth hover transitions and clear, modern typography. Fully responsive.

{design_brief}

THIS PAGE ({page_name}):
{kind_brief}

QUALITY BAR (make it look like a real, polished SaaS product - thin/empty pages are NOT acceptable):
- RICH LAYOUT: a clear visual hierarchy with MULTIPLE well-structured sections. Center content in a `max-w-7xl mx-auto` container, use grid/flex layouts with `gap-6`, generous section padding (`py-10`+), and rounded cards with the theme's shadow. Never leave large empty/blank areas.
- REALISTIC CONTENT: write real, domain-specific copy and sample data for THIS app - real-sounding names, titles, descriptions, prices, dates, statuses. NEVER use generic placeholders like "Item", "Title 1", "Lorem ipsum", or unrelated "User/Post/Comment" labels.
- POLISH: put an `<Icon/>` next to section headings and key labels; use colored status badges (rounded-full pills), avatars for people, subtle dividers, and hover transitions on cards/buttons/rows.
- DENSITY: the page must feel complete and cover multiple visual/functional sections. The page component should be fully implemented with no placeholders. Dashboard should have multiple widgets; List should include search, filters, pagination; Detail page should have multiple tabs; Wizard/Step form layout for Create/Edit.
- HEADINGS use the display font (`font-display` via the theme) and are bold; body text is readable and well-spaced.

Return ONLY a JSON object with one key "code" (the COMPLETE component source). No markdown, no placeholders, no ellipses."""

# =========================================================================
# AUDITOR AGENT -- reviews each generated page for known runtime bugs and
# auto-fixes them DURING generation. Gated by a fast deterministic check so
# clean pages skip the extra LLM pass (keeps generation reasonably quick).
# =========================================================================
def _page_risk_flags(code: str) -> list:
    """Deterministically flag the runtime-bug patterns we've seen cause blank /
    crashing pages. Returns the list of issues found (empty == looks clean)."""
    flags = []
    if re.search(r"\}\s*,\s*\[\s*(user|currentUser|records|data|items|list|rows|formData|profile)\s*\]\s*\)", code):
        flags.append("object-in-useEffect-deps")
    if re.search(r"\b\w+\.\w+\.(toLowerCase|toUpperCase|includes|startsWith|endsWith|split|trim)\s*\(", code):
        flags.append("unguarded-string-method-on-field")
    if "getCurrentUser" in code and re.search(r"\b(user|currentUser)\.\w+", code) and not re.search(r"\b(user|currentUser)\?\.", code):
        flags.append("unguarded-null-user-read")
    if re.search(r"value=\{", code) and (re.search(r"useState\(\s*null\s*\)", code) or re.search(r":\s*null\b", code)):
        flags.append("possible-null-controlled-input")
    # user.name[0] / rec.title[0] etc. -> crashes when the field is missing
    if re.search(r"\b\w+\.\w+\[0\]", code):
        flags.append("unguarded-char-index")
    # formData seeded straight from a record object (missing fields stay
    # undefined -> controlled inputs flip to uncontrolled)
    if re.search(r"(useState|setFormData)\(\s*(rec|record|row|item)\b", code):
        flags.append("formdata-seeded-from-record")
    # a <button> with neither onClick nor type= (submit) does nothing when
    # clicked -> the "dead button" complaint
    if re.search(r"<button(?![^>]*onClick)(?![^>]*type=)[^>]*>", code):
        flags.append("dead-button-no-handler")
    # a popup-implying control (bell/notifications/export/menu) in a component
    # with NO state at all can't open anything
    if re.search(r"(Notifications|notification|Export|kebab|dots)", code) and "useState" not in code:
        flags.append("popup-not-wired")
    # static text-overlap risks: absolutely-positioned elements that directly
    # contain text (not overlay/decoration), or large negative top margins
    if re.search(r'className="[^"]*\babsolute\b[^"]*"[^>]*>\s*[A-Za-z]', code) and not re.search(r"inset-0|-z-10|pointer-events-none", code):
        flags.append("absolute-text-overlap-risk")
    if re.search(r"-mt-(1[2-9]|[2-9]\d)", code):
        flags.append("negative-margin-overlap-risk")
    return flags

def _valid_routes(state: GraphState) -> str:
    """All routes that actually exist in the plan (incl. CRUD children)."""
    routes = set()
    for p in state.get("pages", []):
        path = p.get("path", "/")
        routes.add(path)
    return ", ".join(sorted(routes))

def _route_flags(code: str, valid_routes: str) -> list:
    """Flag navigate()/Link targets that point at routes that don't exist."""
    valid = set(r.strip() for r in valid_routes.split(",") if r.strip())
    used = set(re.findall(r"navigate\(['\"]([^'\"]+)['\"]", code)) | set(re.findall(r"to=\"(/[^\"]*)\"", code))
    broken = []
    for u in used:
        base = u.split("?")[0]
        if not base.startswith("/"):
            continue
        # CRUD children are valid when their list route exists
        parent = "/" + base.strip("/").split("/")[0]
        if base in valid or parent in valid:
            continue
        broken.append(base)
    return ["broken-route:" + b for b in sorted(set(broken))[:4]]

_AGENT_NAME_MAP = [
    (("dead-button", "popup-not-wired"), "Button/Popup Agent"),
    (("absolute-text", "negative-margin"), "Overlap Agent"),
    (("broken-route",), "Completeness Agent"),
    (("unguarded", "possible-null", "object-in-useEffect", "formdata-seeded"), "Null-Safety Agent"),
]

def _agent_names(flags) -> str:
    names = []
    for keys, label in _AGENT_NAME_MAP:
        if any(any(k in f for k in keys) for f in flags) and label not in names:
            names.append(label)
    return " + ".join(names) or "Auditor"

_AUDITOR_PROMPT = """You are a strict React code reviewer for a no-backend, browser-global prototype.
Audit the component and FIX every one of these bugs that is present, then return the COMPLETE corrected component:
1. Reading `.prop` on a value that can be null/undefined on first render -> use optional chaining and defaults. The current user (`window.AppDB.getCurrentUser()`) and fetched records are null/[] on first render.
2. An object/array (the user object, `getRecords(...)`, form state) used in a useEffect DEPENDENCY ARRAY -> infinite render loop ("Maximum update depth"). Use `[]` or a primitive instead.
3. A controlled input whose `value` may be null/undefined -> initialise the field to '' and bind `value={{x ?? ''}}`.
4. A string method on a possibly-missing field (`row.field.toLowerCase()`) -> `String(row?.field ?? '').toLowerCase()`.
5. Char-indexing a possibly-missing string (`user.name[0]`, `rec.title[0]`) -> `String(user?.name || user?.email || '?').charAt(0).toUpperCase()` (avatars) or `String(x?.field ?? '').charAt(0)`.
6. A form state seeded straight from a record object (`useState(rec)`, `setFormData(rec)`) -> build it field by field with defaults: `{ field1: rec?.field1 ?? '', field2: rec?.field2 ?? '' }` so every controlled input always has a string value.
7. A `<button>` with NO `onClick` and NO `type="submit"` -> a dead control. Wire EVERY such button to something real: navigate(...) to the obvious route, toggle a state (dropdown/modal/tab), or perform the labelled action. A 'Notifications' button toggles a notification dropdown panel; 'Export'/'Print' style buttons show a brief success toast via state.
8. A navigate()/Link target that is NOT one of the app's real routes -> replace it with the closest VALID route from this list: {valid_routes} (CRUD children like <list>/new, <list>/detail, <list>/edit are valid when the list route exists).
9. TEXT OVERLAP RISKS: an absolutely-positioned element that directly contains text (move it into normal flow or give the parent reserved padding); large negative top margins pulling text over text (remove them).
RULES: keep it a UMD browser-global component (NO import/export, NO <!DOCTYPE>/<html>), keep ALL existing Tailwind classes / design / behaviour, and end with `window.{name} = {name};`.
Output ONLY a JSON object: {{ "code": "<complete corrected component source>" }}. If nothing needs fixing, return the original code."""

def _audit_and_fix_page(name: str, code: str, valid_routes: str = ""):
    """If a page trips a known bug pattern, run the LLM auditor to fix it.
    Returns (code, flags). Falls back to the original code if the auditor fails
    (the per-page ErrorBoundary still contains any residual issue)."""
    flags = _page_risk_flags(code)
    if valid_routes:
        flags += _route_flags(code, valid_routes)
    if not flags:
        return code, []
    try:
        fixed = _generate_code(
            _AUDITOR_PROMPT,
            "Audit and fix this component named {name}. Issues detected: {flags}\n\n{code}",
            {"name": name, "code": code, "flags": ", ".join(flags),
             "valid_routes": valid_routes or "(unknown - keep existing routes)"},
            min_len=max(80, int(len(code) * 0.4)),
            num_predict=8192,
        )
        return _ensure_component(name, fixed), flags
    except Exception:
        return code, flags

# =========================================================================
# DESIGN-LIBRARY INSTANTIATION -- deterministic token fill for templates.
# List pages and dashboards are wired entirely in Python (real entities, keys,
# routes, columns): instant, and immune to model mistakes. Landings keep their
# LLM edit pass because the copy is the point there.
# =========================================================================
def _entity_meta(state: GraphState):
    out = []
    for e in state.get("entities", []):
        name = e.get("name", "Item")
        out.append({
            "label": name,
            "key": e.get("storage_key", name),
            "route": "/" + planner.slug_of(name),
            "fields": [f.get("name") for f in e.get("fields", [])] or ["name"],
        })
    return out

_DASH_ICONS = ["users", "chart", "calendar", "star", "shield", "zap"]

def _instantiate_dashboard(src: str, state: GraphState) -> str:
    ents = _entity_meta(state) or [{"label": "Records", "key": "records", "route": "/dashboard", "fields": ["name"]}]
    rows = ",\n    ".join(
        "{ label: '%s', key: '%s', route: '%s', icon: '%s' }"
        % (e["label"], e["key"], e["route"], _DASH_ICONS[i % len(_DASH_ICONS)])
        for i, e in enumerate(ents)
    )
    src = re.sub(r"const entities = \[.*?\];", "const entities = [\n    " + rows + "\n  ];", src, count=1, flags=re.S)
    first = ents[0]["fields"]
    col1, col2 = (first + ["status", "id"])[:2]
    return (src.replace("__COL1__", col1.replace("_", " ").title())
               .replace("__COL2__", col2.replace("_", " ").title())
               .replace("__FIELD1__", col1).replace("__FIELD2__", col2))

def _instantiate_list(src: str, page: dict, state: GraphState) -> str:
    name = page.get("name", "List")
    entity = page.get("entity") or "Item"
    meta = next((e for e in _entity_meta(state) if e["label"] == entity), None) or {
        "label": entity, "key": entity, "route": "/" + planner.slug_of(entity), "fields": ["name"]}
    f = (meta["fields"] + ["status", "id", "id"])[:3]
    return (src.replace("__PAGE__", name)
               .replace("__ENTITY1__", meta["label"])
               .replace("__KEY1__", meta["key"])
               .replace("__ROUTE1__", meta["route"])
               .replace("__COL1__", f[0].replace("_", " ").title())
               .replace("__COL2__", f[1].replace("_", " ").title())
               .replace("__COL3__", f[2].replace("_", " ").title())
               .replace("__FIELD1__", f[0]).replace("__FIELD2__", f[1]).replace("__FIELD3__", f[2]))

_TEMPLATE_EDIT_PROMPT = """You are a senior frontend developer. You are given a COMPLETE, polished page template.
EDIT it for the app "{app_name}" ({app_context}).

WHAT TO CHANGE:
- Rewrite EVERY placeholder text into REAL, specific copy for {app_name}. Placeholders include (not limited to): "Headline part", "accent words", "Feature one..six", "Question one..five?", "Full Name", "Role, Company", "App Name", "Tagline category", "New: announcement text", "Banner headline", "Step one title", "Item A..K", "Pillar one title", company names like BRANDONE/NORTHLY, stats labels, footer text. After editing, NO placeholder-sounding text may remain anywhere. Use this content plan as the source:
{page_plan}
- Keep the SAME number of items in every list (features, tiers, faqs, quotes, stats) or MORE - never fewer. You are encouraged to EXPAND: 6 features -> 8, 5 FAQs -> 6, add a second sentence to hero/about paragraphs. The page should feel generous and complete.

WHAT TO KEEP (DO NOT TOUCH):
- Every className EXACTLY as it is. Every image src (assets/*.jpg) and onError handler. All component structure, state logic, Link targets (/register, /login, /features, /about, /contact). The function name and the final window.X = X; line.

Return ONLY a JSON object {{"code": "<the COMPLETE edited file>"}}. No markdown, no placeholders, no ellipses, REAL newlines."""

# Rich pages must come out SUBSTANTIAL: a landing under ~3.5KB of source is a
# thin page, so reject and retry. CRUD pages keep the lighter default.
_KIND_MIN_LEN = {"landing": 3500, "features": 2200, "about": 2200, "dashboard": 2200, "contact": 1500, "role_home": 1800}
# ... and need a BIGGER output budget: a 12-section landing is ~5-6K tokens of
# source. With the default 4096 cap the JSON envelope truncates -> parse fails
# 3x -> fallback stub (the "tiny landing" bug).
_KIND_NUM_PREDICT = {"landing": 8192, "features": 6144, "about": 6144, "dashboard": 6144, "contact": 6144}

def generate_page_agent(state: GraphState, page: dict):
    name = page.get("name", "Page")
    role = page.get("role", "Public")
    entity = page.get("entity")
    theme = state.get("theme") or pick_theme()

    ent = next((e for e in state.get("entities", []) if e.get("name") == entity), None)
    fields = ent.get("fields", []) if ent else []

    # Inject the REAL app identity so the weak model writes domain-specific copy
    # instead of "AppName" / "Lorem ipsum" / "Feature 1" placeholders.
    app_name = state.get("app_name") or "the app"
    ent_names = [e.get("name") for e in state.get("entities", [])]
    roles = state.get("roles", [])
    app_context = f"{app_name} is an app for managing {', '.join(ent_names) if ent_names else 'records'}"
    if roles:
        app_context += f"; the user roles are {', '.join(roles)}"
    app_context += "."

    kind = page.get("kind", "content")
    agents_used = []

    # --- DESIGN LIBRARY: deterministic instantiation (no LLM) for app pages ---
    tpl = design_library.match_template(kind, state.get("prompt", ""), theme)
    if tpl and kind == "list":
        code = _instantiate_list(design_library.load_template(tpl, theme), page, state)
        return {
            "files": {**state.get("files", {}), f"src/pages/{name}.jsx": code},
            "status": f"Page {name} generated. [Design Library: '{tpl['name']}' template, deterministic]",
        }
    if tpl and kind == "dashboard":
        code = _instantiate_dashboard(design_library.load_template(tpl, theme), state)
        code = code.replace("function Dashboard()", f"function {name}()").replace("window.Dashboard = Dashboard;", f"window.{name} = {name};") if name != "Dashboard" else code
        return {
            "files": {**state.get("files", {}), f"src/pages/{name}.jsx": code},
            "status": f"Page {name} generated. [Design Library: '{tpl['name']}' template, deterministic]",
        }

    # Child page-planner: a section-by-section content plan (with real copy) for
    # the rich pages; the coder then just implements it. '' for CRUD pages.
    layouts = theme.get("layouts") or {}
    layout_key = "dashboard" if kind == "dashboard" else "landing"
    layout_name = (layouts.get(layout_key) or {}).get("name", "")
    page_plan = plan_page_agent(state, page, layout_name)
    if page_plan:
        agents_used.append("Page Planner")

    if tpl and kind == "landing":
        # --- DESIGN LIBRARY: the LLM writes ONLY the copy (small JSON); the
        # template is filled deterministically, so a landing can never come
        # back syntactically broken or as a fallback stub again.
        agents_used.append(f"Design Library: '{tpl['name']}' (copy-slots)")
        copy = {}
        try:
            chain = ChatPromptTemplate.from_messages([
                ("system", landing_copy._COPY_PROMPT),
                ("user", "Write the landing copy for {app_name} now."),
            ]) | get_llm(temperature=0.4, num_predict=3072)
            copy = extract_json(chain.invoke({"app_name": app_name, "app_context": app_context}).content)
        except Exception:
            copy = {}  # defaults still render a clean, generic landing
        code = landing_copy.apply(tpl["name"], design_library.load_template(tpl, theme), copy, app_name)
    else:
        code = _generate_code(
            _PAGE_PROMPT,
            "Generate the React code for page component: {page_name}",
            {
                "page_name": name,
                "app_name": app_name,
                "app_context": app_context,
                "shell_rule": planner.shell_rule(page),
                "kind_brief": planner.kind_brief(page, fields, state.get("entities", []), theme.get("layouts")) + page_plan,
                "design_brief": design_brief(theme),
            },
            min_len=_KIND_MIN_LEN.get(kind, 1000),
            num_predict=_KIND_NUM_PREDICT.get(kind, 4096),
        )
    code = _ensure_component(name, code)
    code = _normalize_asset_paths(code)
    valid_routes = _valid_routes(state)
    code, audit_flags = _audit_and_fix_page(name, code, valid_routes)
    status = f"Page {name} generated."
    if agents_used:
        status += " [" + "; ".join(agents_used) + "]"
    if audit_flags:
        status += f" [{_agent_names(audit_flags)} auto-fixed: {', '.join(audit_flags)}]"
    return {
        "files": {**state.get("files", {}), f"src/pages/{name}.jsx": code},
        "status": status,
    }

# =========================================================================
# 4. SIDEBAR LAYOUT GENERATOR
# =========================================================================
_SIDEBAR_PROMPT = """You are a React developer.
Create a glassmorphic sidebar component (`src/components/Sidebar.jsx`).
Do NOT use `import` or `export` statements. Attach it to `window.Sidebar = Sidebar;`.

RULES:
- Read active user and role using `window.AppDB.getCurrentUser()`.
- Render navigation links conditionally based on the user's role.
- Highlight the active link (using `window.location.hash`).
- Display user avatar, email, and role at the bottom.
- Provide a Logout button calling `window.AppDB.logout()` and navigating to `/login`.
- Style the sidebar with the DESIGN SYSTEM below (use its sidebar, text and accent classes exactly; do NOT introduce other color families). Keep sleek hover effects and responsive collapsibility on mobile.

{design_brief}

Return ONLY a JSON object with exactly one key "code". Its value must be a single
string containing the COMPLETE React source for src/components/Sidebar.jsx, fully
implemented. No placeholders, no ellipses, no "code here" comments.

Pages list and routes:
{pages_json}"""

def _build_sidebar_jsx(pages, theme: dict, app_name: str = "App") -> str:
    """Deterministically assemble a themed, role-aware Sidebar from the page
    plan. Previously LLM-generated, but small models often returned a full HTML
    document or invalid JSX (`class=` instead of `className=`), breaking the build."""
    links = []
    for p in pages:
        role = p.get("role", "User")
        if str(role).lower() == "public":
            continue  # Login/Register/landing are not sidebar links
        kind = p.get("kind")
        if kind and kind not in planner.NAV_KINDS:
            continue  # only main sections (Dashboard, entity Lists, Profile, Settings...) - skip create/edit/detail
        links.append({"name": planner.nav_label(p), "path": p.get("path", "/"), "role": role})
    links_js = json.dumps(links)

    sidebar_cls = theme["sidebar"]
    accent = theme["accent"]
    text_primary = theme["text_primary"]
    text_muted = theme["text_muted"]
    primary_btn = theme["primary_button"]
    brand = (app_name or "App").strip()[:24] or "App"

    return f"""const {{ Link, useNavigate, useLocation }} = ReactRouterDOM;

function Sidebar() {{
  const navigate = useNavigate();
  const location = useLocation();
  const user = window.AppDB ? window.AppDB.getCurrentUser() : null;
  const role = user && (user.role || (Array.isArray(user.roles) ? user.roles[0] : null));
  const canSee = (r) => r === 'Public' || r === 'User' || !role || r === role || (user && Array.isArray(user.roles) && user.roles.indexOf(r) !== -1);
  const links = {links_js}; // show all nav links (routes are auth-only; sidebar guides everyone)
  const logout = () => {{ try {{ window.AppDB.logout(); }} catch (e) {{}} navigate('/login'); }};
  return (
    <aside className="{sidebar_cls} w-60 shrink-0 min-h-screen p-4 flex flex-col">
      <div className="flex items-center gap-2.5 mb-6">
        <img src="assets/logo.jpg" alt="" className="h-9 w-9 rounded-xl object-cover" onError={{(e) => {{ e.currentTarget.style.display = 'none'; }}}} />
        <span className="font-display text-lg font-bold leading-tight {text_primary}">{brand}</span>
      </div>
      <nav className="flex-1 space-y-1">
        {{links.map((l) => (
          <Link key={{l.path}} to={{l.path}}
            className={{"block px-3 py-2 rounded-lg text-sm transition " + (location.pathname === l.path ? "{accent} font-semibold" : "{text_muted} hover:opacity-80")}}>
            {{l.name}}
          </Link>
        ))}}
      </nav>
      <div className="mt-4 pt-4 border-t border-white/10">
        <p className="text-sm truncate {text_primary}">{{user?.email || 'Guest'}}</p>
        <p className="text-xs mb-2 {text_muted}">{{role || ''}}</p>
        <button onClick={{logout}} className="w-full px-3 py-2 rounded-lg text-sm {primary_btn}">Logout</button>
      </div>
    </aside>
  );
}}
window.Sidebar = Sidebar;
"""

def generate_sidebar_agent(state: GraphState):
    theme = state.get("theme") or pick_theme()
    code = _build_sidebar_jsx(state.get("pages", []), theme, state.get("app_name", "App"))
    return {
        "files": {**state.get("files", {}), "src/components/Sidebar.jsx": code},
        "status": "Sidebar component assembled (deterministic)."
    }

def _build_navbar_jsx(pages, theme: dict, app_name: str = "App") -> str:
    """Deterministic TOP navbar for the public marketing pages (Home/Features/About/
    Contact) + Login / Get Started buttons. Used by PublicLayout in app.jsx."""
    links = [{"name": planner.nav_label(p), "path": p.get("path", "/")} for p in planner.navbar_pages(pages)]
    links_js = json.dumps(links)
    brand = (app_name or "App").strip()[:28] or "App"
    accent = theme["accent"]
    text_primary = theme["text_primary"]
    text_muted = theme["text_muted"]
    primary_btn = theme["primary_button"]
    return f"""const {{ Link, useLocation }} = ReactRouterDOM;
const {{ useState: _nbUseState }} = React;

function Navbar() {{
  const location = useLocation();
  const [open, setOpen] = _nbUseState(false);
  const links = {links_js};
  return (
    <header className="sticky top-0 z-30 w-full backdrop-blur-md border-b border-white/10">
      <nav className="max-w-6xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 font-display font-bold text-lg {text_primary}">
          <img src="assets/logo.jpg" alt="" className="h-8 w-8 rounded-lg object-cover" onError={{(e) => {{ e.currentTarget.style.display = 'none'; }}}} />
          <span>{brand}</span>
        </Link>
        <div className="hidden md:flex items-center gap-6">
          {{links.map((l) => (
            <Link key={{l.path}} to={{l.path}}
              className={{"text-sm font-medium transition hover:opacity-80 " + (location.pathname === l.path ? "{accent}" : "{text_muted}")}}>
              {{l.name}}
            </Link>
          ))}}
        </div>
        <div className="flex items-center gap-2">
          <Link to="/login" className="hidden sm:block text-sm font-medium px-3 py-2 {text_muted} hover:opacity-80">Login</Link>
          <Link to="/register" className="hidden sm:block text-sm font-semibold px-4 py-2 rounded-lg {primary_btn}">Get Started</Link>
          <button aria-label="Menu" onClick={{() => setOpen(!open)}} className="md:hidden p-2 rounded-lg {text_primary} hover:opacity-80">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg>
          </button>
        </div>
      </nav>
      {{open && (
        <div className="md:hidden border-t border-white/10 backdrop-blur-md px-4 py-3 space-y-1">
          {{links.map((l) => (
            <Link key={{l.path}} to={{l.path}} onClick={{() => setOpen(false)}}
              className={{"block px-3 py-2 rounded-lg text-sm font-medium " + (location.pathname === l.path ? "{accent}" : "{text_muted}")}}>
              {{l.name}}
            </Link>
          ))}}
          <Link to="/login" onClick={{() => setOpen(false)}} className="block px-3 py-2 rounded-lg text-sm font-medium {text_muted}">Login</Link>
          <Link to="/register" onClick={{() => setOpen(false)}} className="block px-3 py-2 rounded-lg text-sm font-semibold {accent}">Get Started</Link>
        </div>
      )}}
    </header>
  );
}}
window.Navbar = Navbar;
"""

def generate_navbar_agent(state: GraphState):
    theme = state.get("theme") or pick_theme()
    code = _build_navbar_jsx(state.get("pages", []), theme, state.get("app_name", "App"))
    return {
        "files": {**state.get("files", {}), "src/components/Navbar.jsx": code},
        "status": "Navbar component assembled (deterministic)."
    }

# =========================================================================
# 5. APP SHELL & ROUTER GENERATOR
# =========================================================================
_APP_PROMPT = """You are a React developer.
Create the core entry file `src/app.jsx`.
Do NOT use `import` or `export` statements. It will render the root React tree.

RULES:
- Read routing packages globally from `ReactRouterDOM`:
  `const {{ HashRouter, Routes, Route, Navigate }} = ReactRouterDOM;`
- Read components from `window`: `const {{ Sidebar, Login, Register, Dashboard, ... }} = window;` (refer to pages list).
- Set up a standard Layout page wrapper where the `Sidebar` is displayed on the left, and the main page content is displayed on the right.
- Mount a `ProtectedRoute` wrapper to restrict access: if the page role is not "Public" and there is no active session (`window.AppDB.getCurrentUser()`), redirect to `/login`.
- If the logged-in user's role is not authorized for that page, redirect them to `/dashboard`.
- Render a welcome loading splash screen at startup.
- Mount the React tree to `#root`: `ReactDOM.createRoot(document.getElementById('root')).render(<App />);`.

Return ONLY a JSON object with exactly one key "code". Its value must be a single
string containing the COMPLETE React source for src/app.jsx, fully implemented.
No placeholders, no ellipses, no "code here" comments.

Pages list:
{pages_json}"""

_APP_TEMPLATE = """const { HashRouter, Routes, Route, Navigate } = ReactRouterDOM;

function _Missing(name) {
  return function Missing() {
    // High-contrast, theme-agnostic card (explicit white bg + slate text + shadow)
    // so a missing component is ALWAYS clearly visible, never a blank screen.
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="bg-white text-slate-800 border border-slate-200 rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <div className="text-4xl mb-3">🧩</div>
          <h1 className="text-xl font-bold text-slate-900 mb-1">{name}</h1>
          <p className="text-slate-500 text-sm mb-5">This section is being prepared.</p>
          <a href="#/dashboard" className="inline-block bg-slate-800 hover:bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-semibold">Back to Dashboard</a>
        </div>
      </div>
    );
  };
}

// Pull a component from window, falling back to a visible placeholder so a
// single failed generation can never white-screen the whole app.
function comp(name) { return window[name] || _Missing(name); }

// Catches runtime errors in a generated page so one buggy page shows a friendly
// card instead of unmounting (white-screening) the entire app.
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error: error }; }
  componentDidCatch(error, info) { console.error("Page render error:", error, info); }
  render() {
    if (this.state.error) {
      // High-contrast, theme-agnostic card + recovery actions. A crashed page is
      // NEVER a blank screen — always a clearly visible, recoverable message.
      return (
        <div className="min-h-[60vh] flex items-center justify-center p-6">
          <div className="bg-white text-slate-800 border border-slate-200 rounded-2xl shadow-xl p-8 max-w-lg w-full text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <h1 className="text-xl font-bold text-slate-900 mb-1">This section couldn't load</h1>
            <p className="text-slate-500 text-sm mb-4">A small error occurred on this page. The rest of the app still works.</p>
            <div className="flex gap-2 justify-center">
              <button onClick={() => { this.setState({ error: null }); window.location.hash = '#/dashboard'; }} className="bg-slate-800 hover:bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-semibold">Back to Dashboard</button>
              <button onClick={() => window.location.reload()} className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-5 py-2.5 rounded-lg text-sm font-semibold">Reload</button>
            </div>
            <p className="text-[11px] text-slate-400 break-words mt-4">{String((this.state.error && this.state.error.message) || this.state.error)}</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function ProtectedRoute({ role, children }) {
  // Auth-only gate. We deliberately do NOT redirect on role mismatch: doing so
  // (<Navigate to="/dashboard">) looped forever whenever the dashboard itself was
  // role-restricted and the user's role didn't match -> a BLANK page (the #1
  // recurring "empty page" bug). Any logged-in user may view any page in the
  // prototype; the sidebar still guides navigation by role.
  const user = window.AppDB ? window.AppDB.getCurrentUser() : null;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function Layout({ children }) {
  const Sidebar = comp("Sidebar");
  return (
    <div className="flex min-h-screen">
      <ErrorBoundary><Sidebar /></ErrorBoundary>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}

// Public marketing shell: a top navbar over the page content (no sidebar, no auth).
function PublicLayout({ children }) {
  const Navbar = comp("Navbar");
  return (
    <div className="min-h-screen flex flex-col">
      <ErrorBoundary><Navbar /></ErrorBoundary>
      <main className="flex-1">{children}</main>
    </div>
  );
}

function App() {
__CONSTS__
  return (
    <HashRouter>
      <Routes>
__ROUTES__
      </Routes>
    </HashRouter>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
"""

def _build_app_jsx(pages) -> str:
    """Deterministically assemble src/app.jsx (HashRouter shell + role guards)
    from the page plan. This used to be LLM-generated, but small models often
    returned a full HTML document with ES `import`s instead of a UMD module."""
    names = []
    for p in pages:
        n = p.get("name")
        if n and n not in names:
            names.append(n)
    consts = "\n".join(f'  const {n} = comp("{n}");' for n in names)

    if any(p.get("path") == "/" for p in pages):
        default_path = "/"  # landing page is the catch-all
    elif any(p.get("path") == "/login" for p in pages):
        default_path = "/login"
    else:
        default_path = pages[0].get("path", "/") if pages else "/"

    routes = []
    for p in pages:
        n = p.get("name")
        if not n:
            continue
        path = p.get("path", "/" + n.lower())
        role = p.get("role", "User")
        tier = planner.page_tier(p)
        inner = f'<ErrorBoundary key="{n}"><{n} /></ErrorBoundary>'
        if tier == "marketing":            # public pages -> top navbar shell
            el = f'<PublicLayout>{inner}</PublicLayout>'
        elif tier == "auth":               # login/register -> full screen, no shell
            el = inner
        else:                              # authenticated -> sidebar shell behind auth gate
            el = f'<ProtectedRoute role="{role}"><Layout>{inner}</Layout></ProtectedRoute>'
        routes.append(f'        <Route path="{path}" element={{{el}}} />')
    routes.append(f'        <Route path="*" element={{<Navigate to="{default_path}" replace />}} />')

    return _APP_TEMPLATE.replace("__CONSTS__", consts).replace("__ROUTES__", "\n".join(routes))

def generate_app_agent(state: GraphState):
    code = _build_app_jsx(state["pages"])
    return {
        "files": {**state.get("files", {}), "src/app.jsx": code},
        "status": "App Router shell assembled (deterministic)."
    }

# =========================================================================
# 6. HTML TEMPLATE & BUILD GENERATOR
# =========================================================================
def generate_html_agent(state: GraphState):
    # Determine JSX script tags based on files present in the state
    script_tags = []
    # Order matters: icons, db, layout components, pages, app
    ordered_files = [
        "src/icons.jsx",
        "src/db.jsx",
        "src/components/Sidebar.jsx",
        "src/components/Navbar.jsx",
    ]
    # Add page files
    for filepath in state["files"]:
        if filepath.startswith("src/pages/") and filepath not in ordered_files:
            ordered_files.append(filepath)
    # Add app.jsx last
    ordered_files.append("src/app.jsx")

    # icons.jsx is generated by THIS agent (added to state["files"] only in the
    # return below), so it must be included unconditionally or its <script> tag
    # is dropped and window.Icon never loads (every <Icon/> would crash).
    always_present = {"src/icons.jsx"}
    for f in ordered_files:
        if f in state["files"] or f in always_present:
            script_tags.append(f'  <script type="text/babel" src="./{f}"></script>')

    scripts_str = "\n".join(script_tags)

    # Apply the per-project theme to the HTML shell (fonts + background).
    theme = state.get("theme") or pick_theme()
    fonts_link = fonts_url(theme)
    font_body = theme["font_body"]
    font_display = theme["font_display"]
    body_class = theme["page_background"]
    color_scheme = theme["mode"]

    html_code = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Interactive System Prototype</title>

  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="{fonts_link}" rel="stylesheet" />

  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com?plugins=forms,typography"></script>
  <script>
    tailwind.config = {{
      theme: {{
        extend: {{
          fontFamily: {{
            sans: ['{font_body}', 'ui-sans-serif', 'system-ui'],
            display: ['{font_display}', '{font_body}', 'serif'],
            mono: ['JetBrains Mono', 'ui-monospace'],
          }},
          colors: {{
            navy: {{
              50:  '#eff6fc',
              100: '#dbeafe',
              200: '#bfdbfe',
              300: '#93c5fd',
              400: '#3b82f6',
              500: '#1e5fa8',
              600: '#0e4a8a',
              700: '#063970',
              800: '#052a55',
              900: '#031b3a',
            }},
            sky2: {{
              300: '#7dd3fc',
              400: '#38bdf8',
              500: '#0ea5e9',
            }},
            gold: {{
              300: '#fcd34d',
              400: '#fbbf24',
              500: '#f59e0b',
            }}
          }}
        }}
      }}
    }};
  </script>

  <style>
    :root {{ color-scheme: {color_scheme}; }}
    html, body {{ margin: 0; padding: 0; min-height: 100vh; }}
    body {{ font-family: '{font_body}', sans-serif; -webkit-font-smoothing: antialiased; }}
    .font-display {{ font-family: '{font_display}', serif; }}
    .glass {{
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.3);
    }}
    .glass-dark {{
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }}
  </style>

  <!-- React UMD CDNs -->
  <script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" crossorigin></script>

  <!-- React Router v6 UMD. These MUST load in this order: react-router-dom
       re-exports react-router through getters bound at parse time, so its deps
       have to exist before it parses. -->
  <script src="https://unpkg.com/@remix-run/router@1.15.3/dist/router.umd.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-router@6.22.3/dist/umd/react-router.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-router-dom@6.22.3/dist/umd/react-router-dom.production.min.js" crossorigin></script>
  <script>
    // Rebuild ReactRouterDOM as a plain object so generated code can reliably
    // destructure routing primitives, bypassing the throwing re-export getters.
    (function () {{
      var core = window.ReactRouter || {{}};
      var dom = window.ReactRouterDOM || {{}};
      window.ReactRouterDOM = {{
        HashRouter: dom.HashRouter, BrowserRouter: dom.BrowserRouter,
        Link: dom.Link, NavLink: dom.NavLink, useSearchParams: dom.useSearchParams,
        Routes: core.Routes, Route: core.Route, Navigate: core.Navigate, Outlet: core.Outlet,
        useNavigate: core.useNavigate, useParams: core.useParams, useLocation: core.useLocation
      }};

      // Also expose common hooks/components as globals, so a generated page that
      // forgets to destructure them (e.g. a bare `useState`) still works. Pages
      // that DO destructure simply shadow these locally - harmless.
      var R = window.React || {{}};
      ['useState','useEffect','useRef','useCallback','useMemo','useContext','useReducer','Fragment'].forEach(function (k) {{ if (R[k]) window[k] = R[k]; }});
      var RRD = window.ReactRouterDOM;
      ['useNavigate','useParams','useLocation','useSearchParams','Link','NavLink','Navigate','Outlet'].forEach(function (k) {{ if (RRD[k]) window[k] = RRD[k]; }});
    }})();
  </script>

  <!-- Lottie -->
  <script src="https://unpkg.com/@lottiefiles/lottie-player@2.0.8/dist/lottie-player.js"></script>
</head>
<body class="{body_class}">
  <div id="root"></div>

  <script>
    // Photos are generated in the BACKGROUND after the prototype is ready (the
    // pages reserve assets/*.jpg slots that auto-hide on error). This retries
    // hidden/broken asset images for ~8 minutes so each photo pops in as its
    // file lands - no reload needed. Also re-checks on every route change.
    (function () {{
      function retryPass() {{
        document.querySelectorAll('img[src*="assets/"]').forEach(function (im) {{
          var broken = im.style.display === 'none' || !im.complete || im.naturalWidth === 0;
          if (broken) {{
            im.style.display = '';
            im.src = im.src.split('?')[0] + '?v=' + Date.now();
          }}
        }});
      }}
      var ticks = 0;
      var timer = setInterval(function () {{
        retryPass();
        if (++ticks > 32) clearInterval(timer);
      }}, 15000);
      window.addEventListener('hashchange', function () {{ setTimeout(retryPass, 600); }});
    }})();
  </script>

{scripts_str}
</body>
</html>"""

    # Also generate build.js
    build_js = """const fs = require('fs');
const path = require('path');

const filesToBuild = ['index.html'];

filesToBuild.forEach(fileName => {
  const filePath = path.join(__dirname, fileName);
  if (!fs.existsSync(filePath)) {
    console.log(`File not found: ${fileName}`);
    return;
  }

  let htmlContent = fs.readFileSync(filePath, 'utf8');
  const scriptRegex = /<script\\s+type="text\\/babel"\\s+src="([^"]+)"><\\/script>/g;

  let updatedHtml = htmlContent;
  scriptRegex.lastIndex = 0;

  updatedHtml = updatedHtml.replace(scriptRegex, (fullTag, srcPath) => {
    const absoluteSrcPath = path.resolve(__dirname, srcPath);
    if (fs.existsSync(absoluteSrcPath)) {
      console.log(`Inlining ${srcPath} into ${fileName}...`);
      const fileContent = fs.readFileSync(absoluteSrcPath, 'utf8');
      return `<script type="text/babel">\\n${fileContent}\\n</script>`;
    } else {
      console.warn(`Warning: Source file not found: ${srcPath}`);
      return fullTag;
    }
  });

  fs.writeFileSync(filePath, updatedHtml, 'utf8');
  console.log(`Successfully built ${fileName}`);
});
"""

    package_json = """{
  "name": "ai-designed-prototype",
  "version": "1.0.0",
  "scripts": {
    "dev": "npx serve -l 3000",
    "build": "node build.js"
  }
}
"""

    # We also copy a basic icons file
    icons_jsx = """const ICON_PATHS = {
  Sparkles: 'M9.94 14.34 12 22l2.06-7.66L22 12l-7.94-2.34L12 2l-2.06 7.66L2 12zM19 3l.74 2.26L22 6l-2.26.74L19 9l-.74-2.26L16 6l2.26-.74zM5 16l.74 2.26L8 19l-2.26.74L5 22l-.74-2.26L2 19l2.26-.74z',
  Phone: 'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z',
  Mail: 'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM22 6 12 13 2 6',
  MapPin: 'M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0zM12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  ArrowRight: 'M5 12h14M12 5l7 7-7 7',
  ArrowUpRight: 'M7 17 17 7M7 7h10v10',
  Check: 'M20 6 9 17l-5-5',
  ChevronRight: 'M9 18l6-6-6-6',
  ChevronDown: 'M6 9l6 6 6-6',
  Star: 'M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z',
  Leaf: 'M11 20A7 7 0 0 1 4 13H2a9 9 0 0 0 9 9zM2 22s5-2 5-9 5-11 5-11 5 4 5 11-5 9-5 9-3 0-5 0z',
  Calendar: 'M3 4h18v18H3zM16 2v4M8 2v4M3 10h18',
  Users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  Shield: 'M12 2 4 5v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V5z',
  MessageSquare: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z',
  Dollar: 'M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
  Building: 'M3 21h18M5 21V7l8-4v18M19 21V11l-6-4M9 9h.01M9 13h.01M9 17h.01',
  Bath: 'M9 6 6.5 3.5a1.5 1.5 0 1 0-2.1 2.1L7 8M2 12h20M7 12v5a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-5M4 22l1-2M20 22l-1-2',
  Wand: 'm15 4 3 3M9 21l12-12-3-3L6 18zM18 4l3-3M2 9l4-1 1-4M5 15l3-1 1-3M21 14l-1 3-3 1',
  Award: 'M12 15a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM8.21 13.89 7 23l5-3 5 3-1.21-9.12',
  Clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2',
  TrendingUp: 'm22 7-8.5 8.5-5-5L2 17M16 7h6v6',
  Menu: 'M3 6h18M3 12h18M3 18h18',
  X: 'M18 6 6 18M6 6l12 12',
  Lock: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2zM7 11V7a5 5 0 0 1 10 0v4',
  PlayCircle: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM10 8l6 4-6 4z',
  Settings: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  Send: 'm22 2-7 20-4-9-9-4zM22 2 11 13',
  Globe: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
  Heart: 'M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z',
  Zap: 'M13 2 3 14h9l-1 8 10-12h-9z',
  Droplet: 'M12 2.69 5.64 9.05a9 9 0 1 0 12.72 0z',
  Bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0',
  Plus: 'M12 5v14M5 12h14',
  Edit: 'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z',
  Trash: 'M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6',
  Search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35',
  Inbox: 'M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z',
  Download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
  Filter: 'M22 3H2l8 9.46V19l4 2v-8.54z',
  Eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z'
};

// Alias map so template/LLM icon names always resolve: lowercase, kebab-case
// and common synonyms (chart -> TrendingUp etc.) all land on a real path.
const ICON_ALIASES = {
  chart: 'TrendingUp', graph: 'TrendingUp', analytics: 'TrendingUp', activity: 'TrendingUp',
  notifications: 'Bell', notification: 'Bell', alert: 'Bell',
  delete: 'Trash', remove: 'Trash', pencil: 'Edit', user: 'Users', person: 'Users', team: 'Users',
  money: 'Dollar', price: 'Dollar', location: 'MapPin', pin: 'MapPin', time: 'Clock',
  close: 'X', cancel: 'X', tick: 'Check', checkmark: 'Check', view: 'Eye', sparkle: 'Sparkles',
  envelope: 'Mail', email: 'Mail', message: 'MessageSquare', comment: 'MessageSquare',
};

function _resolveIcon(name) {
  if (!name) return null;
  if (ICON_PATHS[name]) return ICON_PATHS[name];
  const lower = String(name).toLowerCase();
  if (ICON_ALIASES[lower]) return ICON_PATHS[ICON_ALIASES[lower]];
  // kebab/lower -> PascalCase ("chevron-down" -> "ChevronDown", "zap" -> "Zap")
  const pascal = lower.split(/[-_ ]+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join('');
  if (ICON_PATHS[pascal]) return ICON_PATHS[pascal];
  return ICON_PATHS.Sparkles; // visible default - never an empty tile
}

function Icon({ name, className = 'w-5 h-5', strokeWidth = 1.75, fill = 'none' }) {
  const d = _resolveIcon(name);
  if (!d) return null;
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill={fill} stroke="currentColor"
         strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {d.split(/(?=M)/).filter(Boolean).map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
}

window.Icon = Icon;
"""

    return {
        "files": {
            **state.get("files", {}),
            "index.html": html_code,
            "build.js": build_js,
            "package.json": package_json,
            "src/icons.jsx": icons_jsx
        },
        "status": "HTML index template and build scripts generated successfully."
    }

# =========================================================================
# 7. ITERATIVE UPDATE AGENT
# =========================================================================
_UPDATE_PROMPT = """You are an Elite Frontend Code Refactoring Agent.
You are given the CURRENT files generated for a prototype, and the USER's instructions to modify or add design details.
Your task is to modify the codebase to implement the requested changes.

RULES:
- Read the files in JSON map.
- Modify the file contents to satisfy the user's modifications (e.g. changing styles, layout, adding navigation items, updating forms).
- Return ONLY the files that were modified. Do NOT return unchanged files.
- Ensure no ES6 `import` or `export` statements are used. Keep them UMD/global compatible.
- Each value must be the COMPLETE new file contents, fully implemented. No
  placeholders, no ellipses, no "code here" comments.
- The returned JSON must be structured exactly as:
{{
  "updated_files": {{
    "<relative/file/path.jsx>": "<full updated source as a single string>"
  }}
}}

User Request: {prompt}

Current Files Map:
{files_json}"""

def update_prototype_agent(state: GraphState):
    files_summary = state["files"]
    prompt_text = state["prompt"]
    llm = get_llm(temperature=0.0)
    
    chain = ChatPromptTemplate.from_messages([
        ("system", _UPDATE_PROMPT),
        ("user", "Update the prototype code files according to the user instructions.")
    ]) | llm
    
    # We serialize only .jsx and .html files to keep context small
    serializable_files = {k: v for k, v in files_summary.items() if k.endswith((".jsx", ".html"))}
    
    res = chain.invoke({
        "prompt": prompt_text,
        "files_json": json.dumps(serializable_files, indent=2)
    })
    
    update_dict = extract_json(res.content)
    new_files = {**state.get("files", {})}
    applied, skipped = [], []
    for filepath, content in update_dict.get("updated_files", {}).items():
        cleaned = _clean_code(content)
        # Only apply real content so a placeholder reply can't blank a good file
        if _is_real_code(cleaned, min_len=40):
            new_files[filepath] = cleaned
            applied.append(filepath)
        else:
            skipped.append(filepath)

    if applied:
        status = f"Prototype updated ({', '.join(applied)})."
    else:
        status = "Update produced no valid changes; existing files kept."
    if skipped:
        status += f" Skipped empty/placeholder: {', '.join(skipped)}."

    return {
        "files": new_files,
        "status": status
    }
