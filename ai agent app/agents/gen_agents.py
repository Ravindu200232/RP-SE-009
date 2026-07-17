"""agents/gen_agents.py — the rule-based generation agents (v2 engine).

Each agent reads its RULE doc (agents/rules/*.md) + the shared markdown MEMORY, asks gemma4:12b
to generate ONE artifact, streams the code live, extracts it, and writes the file. No templates —
the rules + memory are the only structure. Generation writes whole files; the separate
bugfix_agent does surgical line-level fixes.
"""
from __future__ import annotations

import re
from pathlib import Path

from agents import llm
from agents.analyzer import format_diagnostics
from agents.scaffold import pascal, route_name

RULES_DIR = Path(__file__).parent / "rules"

SYSTEM = (
    "You are a senior Next.js 16 (App Router) + React 19 + TypeScript + Mongoose engineer. "
    "You write production code that compiles with `next build` under strict TypeScript. "
    "You output ONLY the code for the single requested file — no markdown fences, no prose, "
    "no explanation, no notes. Follow the RULE exactly and stay consistent with the MEMORY."
)

_FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
_CODE_START = ("'use client'", '"use client"', "import ", "export ", "//", "/*",
               "const ", "let ", "type ", "interface ", "function ", "async ")

# `className="p-8 text-red-500\">` — the model occasionally escapes the closing quote of a JSX
# attribute. JSX attribute values are raw (no escape processing), so the backslash ends the value
# early and SWC dies with `Expected '</', got 'jsx text'`. It is unfixable by the repair LLM (three
# passes and a cloud escalation never landed it) and trivially fixable here. Matching `name="` with no
# space leaves real JS escapes (`const s = "he said \"hi\""`) untouched — those never follow `name="`.
_JSX_ESCAPED_QUOTE = re.compile(r'(\s[A-Za-z][\w:.-]*=")([^"\n]*?)\\+(")')

# `<Grid item xs={12} md={6}>` — MUI v5's Grid API. This app pins MUI v7, where Grid IS the old Grid2:
# no `item` prop, no `xs`/`md` props, breakpoints go in `size`. gemma's training data is dominated by
# v5, so it writes v5 by reflex and `next build` dies on "No overload matches this call" — an error the
# repair model can't fix either, because it knows the same v5. The rules forbid Grid; this catches the
# reflex before the file ever reaches a build.
# `{error && <Alert …>{error}</Alert}` — inside a JSX expression container the model types the
# container's `}` but drops the tag's `>`. A closing tag can only end in `>`, so this is always a typo
# and always fatal ("Expected '</', got '}'"); the repair model burned a whole build-fix loop on it and
# gave up. Rewriting to `</Alert>` alone just moves the error — that `}` was closing the container — so
# brace balance decides whether the `}` is kept.
_BAD_CLOSE = re.compile(r"</\s*([A-Za-z][\w.]*)\s*\}")


def _fix_bad_closes(content: str) -> tuple[str, int]:
    out, fixed = [], 0
    for line in content.split("\n"):
        if _BAD_CLOSE.search(line):
            # Balanced braces mean this `}` closes a container opened on this line → keep it (`>}`).
            # A surplus `}` means the container closes elsewhere → the brace is spurious (`>`).
            keep = line.count("}") <= line.count("{")
            line, k = _BAD_CLOSE.subn(r"</\1>}" if keep else r"</\1>", line)
            fixed += k
        out.append(line)
    return "\n".join(out), fixed

# `import HeartIcon from '@mui/icons-material/Heart'` — MUI ships Material Design names, but the model
# reaches for the lucide/Feather names it has written a thousand times (Heart, Trash, Plus), and the
# build dies on a module that never existed. Same reflex as the v5 Grid: translate it rather than let
# a hallucinated icon burn a repair loop.
_ICON_ALIASES = {
    "Heart": "Favorite", "HeartOutline": "FavoriteBorder", "Trash": "Delete", "Trash2": "Delete",
    "Plus": "Add", "PlusCircle": "AddCircle", "Minus": "Remove", "Pencil": "Edit", "Pen": "Edit",
    "X": "Close", "Cross": "Close", "Tick": "Check", "Checkmark": "Check", "User": "Person",
    "Users": "People", "Gear": "Settings", "Cog": "Settings", "Cart": "ShoppingCart",
    "ShoppingBag": "ShoppingCart", "Calendar": "CalendarToday", "Clock": "AccessTime",
    "Money": "AttachMoney", "Dollar": "AttachMoney", "DollarSign": "AttachMoney",
    "Bell": "Notifications", "Eye": "Visibility", "EyeOff": "VisibilityOff", "Filter": "FilterList",
    "Trending": "TrendingUp", "Chart": "BarChart", "PieChartIcon": "PieChart", "File": "Description",
    "FileText": "Description", "Doc": "Description", "Box": "Inventory", "Package": "Inventory",
    "Sparkles": "AutoAwesome", "Star": "StarBorder", "Send": "Send", "Mail": "Email",
    "Phone": "Phone", "Home": "Home", "Search": "Search", "Menu": "Menu", "Logout": "Logout",
    # Domain nouns the model invents when the generic list has nothing that fits — its instinct is
    # right (a recipe app wants a cooking icon), only the name is wrong. All targets verified present
    # in the installed package.
    "Cook": "Restaurant", "Chef": "Restaurant", "Cooking": "Restaurant", "Recipe": "MenuBook",
    "Food": "Fastfood", "Meal": "LocalDining", "Dining": "LocalDining", "Coffee": "LocalCafe",
    "Basket": "ShoppingBasket", "Tag": "LocalOffer", "Book": "MenuBook", "Timer": "Timer",
    "Bookmark": "Bookmark", "Share": "Share", "Print": "Print", "Globe": "Language",
    # The model's strongest reflex: name the icon after the ENTITY (a blog app asks for `Post`, a task
    # app for `Task`). Map the common nouns onto the Material name that means the same thing.
    "Post": "Article", "Posts": "Article", "Blog": "Article", "Comment": "Comment",
    "Note": "StickyNote2", "Notes": "StickyNote2", "Review": "RateReview", "Task": "Task",
    "Todo": "Task", "Event": "Event", "Booking": "Event", "Appointment": "Event",
    "Customer": "Group", "Member": "Group", "Team": "Group", "Product": "Inventory2",
    "Order": "Receipt", "Invoice": "Receipt", "Payment": "Payments", "Report": "Assessment",
    "Medicine": "Medication", "Patient": "Person", "Doctor": "MedicalServices",
    "Pharmacy": "LocalPharmacy", "Drug": "Medication", "Prescription": "Medication",
    "Supplier": "LocalShipping", "Vendor": "LocalShipping", "Stock": "Inventory2",
    "Sale": "PointOfSale", "Sales": "PointOfSale", "Shop": "Storefront", "Store": "Storefront",
    "Cashier": "PointOfSale", "Health": "HealthAndSafety", "Room": "MeetingRoom",
    "Hotel": "Hotel", "Flight": "Flight", "Car": "DirectionsCar", "School": "School",
}
_ICON_IMPORT = re.compile(r"(from\s+['\"]@mui/icons-material/)([A-Za-z][\w]*)(['\"])")

# `from '@types'` — the model drops the slash out of the path alias. tsconfig maps `@/*` and nothing
# else, so `@types`, `@components/x`, `@lib/x` are never resolvable; the intent is unambiguous.
_ALIAS_IMPORT = re.compile(r"(from\s+['\"])@(types|components|lib|models)(['\"/])")

# `import { Link } from 'next/link'` — these modules export a DEFAULT, and only a default. The named
# form is always wrong ("has no exported member 'Link'"); the compiler even suggests the fix, but that
# costs a regeneration to apply. `{ useRouter }` from next/navigation is a real named export — only
# the single-default modules belong here.
_DEFAULT_IMPORT = re.compile(r"import\s*\{\s*(Link|Image|Head|Script|Document)\s*\}\s*from\s*"
                             r"(['\"])next/(link|image|head|script|document)\2")

_GRID_OPEN = re.compile(r"<Grid\b([^>]*?)(/?)>", re.S)
_GRID_ITEM = re.compile(r"\s+item\b(?!\s*=)")
_GRID_BP = re.compile(r"\s+(xs|sm|md|lg|xl)\s*=\s*\{([^{}]*)\}|\s+(xs|sm|md|lg|xl)\s*=\s*\"([^\"]*)\"")


def _grid_to_v7(match: re.Match, counter: list) -> str:
    attrs, close = match.group(1), match.group(2)
    if "container" in attrs or ("item" not in attrs and not _GRID_BP.search(attrs)):
        return match.group(0)          # a container (or already-v7 Grid) needs no rewrite
    sizes: list[str] = []

    def take(m: re.Match) -> str:
        bp, val = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        sizes.append(f"{bp}: {val.strip()}")
        return ""

    attrs = _GRID_BP.sub(take, attrs)
    attrs = _GRID_ITEM.sub("", attrs)
    size = " size={{ " + ", ".join(sizes) + " }}" if sizes else ""
    counter.append(1)
    return f"<Grid{size}{attrs.rstrip()}{close}>"


def _resolve_icon(name: str, icons_dir) -> str | None:
    """The real Material name for what the model asked for, or None to leave it alone.

    The package is ON DISK — there is no need to guess. Beyond the alias table, the model's other
    reflex is decorating a real name (`ShoppingBasketAlt`, `NewPost_outlined`); strip the decoration
    and check again."""
    if icons_dir is None:
        return _ICON_ALIASES.get(name)
    exists = lambda n: n and (icons_dir / f"{n}.js").exists()  # noqa: E731
    if exists(name):
        return None                                   # already real
    alias = _ICON_ALIASES.get(name)
    if exists(alias):
        return alias
    stripped = re.sub(r"(?:_?(?:outlined|filled|rounded|sharp|twotone|alt|icon))+$", "", name,
                      flags=re.I)
    if stripped != name:
        if exists(stripped):
            return stripped
        alias = _ICON_ALIASES.get(stripped)
        if exists(alias):
            return alias
    return None                                       # unknown — the compiler will say so


def scrub_jsx(rel: str, content: str, project_dir=None) -> tuple[str, int]:
    """Fix the mechanical TSX mistakes the model repeats and neither repair model can undo.

    Returns (content, n_fixed). Prevention beats repair: each of these that reaches `next build` costs
    minutes of LLM repair that historically failed anyway. `project_dir` grounds the icon check in the
    package actually installed."""
    if not rel.endswith((".tsx", ".jsx")):
        return content, 0
    content, n = _JSX_ESCAPED_QUOTE.subn(r"\1\2\3", content)
    content, c = _fix_bad_closes(content)
    content, a = _ALIAS_IMPORT.subn(r"\1@/\2\3", content)
    content, d = _DEFAULT_IMPORT.subn(r"import \1 from \2next/\3\2", content)
    a += d
    icons: list = []
    icons_dir = (Path(project_dir) / "node_modules" / "@mui" / "icons-material") if project_dir else None
    if icons_dir is not None and not icons_dir.exists():
        icons_dir = None                              # pre-install → fall back to the alias table

    def _icon(m: re.Match) -> str:
        real = _resolve_icon(m.group(2), icons_dir)
        if not real or real == m.group(2):
            return m.group(0)
        icons.append(1)
        return f"{m.group(1)}{real}{m.group(3)}"

    content = _ICON_IMPORT.sub(_icon, content)
    grids: list = []
    content = _GRID_OPEN.sub(lambda m: _grid_to_v7(m, grids), content)
    return content, n + c + a + len(icons) + len(grids)


def design_ctx(spec: dict) -> str:
    """This app's visual identity, injected into EVERY UI generation.

    The design brief was computed and written to `.locode/design-brief.json` but never reached a
    prompt: the model was told the page ARCHETYPE and nothing about the brand, mood or palette, so
    every app came out looking like the same default. The palette is stated for intent only — styling
    goes through the MUI theme (`color="primary"`), never a hard-coded hex."""
    from agents.design.planner import design_brief
    from agents.scaffold import _palette

    brief = design_brief(spec)
    acc, acc2 = _palette(spec)
    brand = spec.get("brand_name") or spec.get("title") or "the app"
    scheme = str(spec.get("color_scheme") or "").strip()
    lines = [
        "DESIGN — this app's identity. Every surface you write must look like it belongs to it:",
        f"- Brand: **{brand}** — {brief['domain']}. Personality: {brief['personality']}.",
        f"- Audience: {spec.get('target_audience') or 'everyday users'}.",
        f"- Palette: primary `{acc}`, secondary `{acc2}`" + (f" — {scheme}" if scheme else "")
        + ". These ARE the MUI theme's primary/secondary: reach for `color=\"primary\"` / "
          "`color=\"secondary\"` / `sx={{ bgcolor: 'background.paper' }}`, NEVER a hard-coded hex.",
        f"- Density: {brief['density']} — "
        + ("tight rows, compact controls, information-dense; the user works here all day."
           if brief["density"] == "compact" else
           "generous spacing, larger type, room to breathe."),
        f"- Corners: {brief['radius']} radius, consistent everywhere.",
        "- Hold the DESIGN BAR in the RULE above. A page that compiles but looks unfinished is a FAIL.",
    ]
    return "\n".join(lines) + "\n\n"


def read_rule(name: str) -> str:
    try:
        return (RULES_DIR / f"{name}.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def extract_code(text: str) -> str:
    """Pull the file body out of possibly-fenced, possibly-chatty model output."""
    text = llm.strip_think(text or "")
    fences = _FENCE.findall(text)
    if fences:
        text = max(fences, key=len)
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith(_CODE_START):
            start = i
            break
    body = "\n".join(lines[start:]).strip()
    # drop a stray trailing ``` if the fence regex missed it
    body = re.sub(r"\n```+\s*$", "", body)
    return body + "\n"


def field_lines(model: dict) -> str:
    out = []
    for f in (model.get("fields") or []):
        if not f.get("name"):
            continue
        bits = [f"{f['name']}: {f.get('type', 'String')}"]
        if f.get("enum"):
            bits.append("enum=" + "|".join(str(v) for v in f["enum"]))
        if f.get("ref"):
            bits.append(f"ref={f['ref']}")
        if f.get("required"):
            bits.append("required")
        if f.get("unique"):
            bits.append("unique+sparse" if not f.get("required") else "unique")
        if f.get("isEmbeddedArray"):
            bits.append("embedded-array")
        if "default" in f:
            bits.append(f"default={f['default']}")
        out.append("  - " + ", ".join(bits))
    return "\n".join(out)


def ref_hints(model: dict | None, memory=None) -> str:
    """Prescriptive dropdown instructions for every ObjectId-ref field (prevents Cast errors)."""
    lines = []
    for f in ((model or {}).get("fields") or []):
        if f.get("ref"):
            rseg = route_name(f["ref"])
            lines.append(f"- `{f['name']}` references {f['ref']} → dropdown from `/api/{rseg}` "
                         f"(option value = `_id`, {_ref_label(f['ref'], memory)})")
    if not lines:
        return ""
    return ("REFERENCE FIELDS (render each as a <Select> loading its endpoint, NEVER a text input):\n"
            + "\n".join(lines) + "\n\n")


def _ref_label(ref: str, memory) -> str:
    """What to SHOW for a referenced record — its real display field, not a guess.

    The rules' example reaches for `o.name`, so the model writes `o.name` even when the entity has
    `companyName` and TypeScript rejects it. The answer is already computed
    (`contract.display_field`); it just never reached the prompt."""
    rmodel = memory.entity(pascal(ref)) if memory else None
    if not rmodel:
        return "show its display field"
    from agents.contract import display_field
    field = display_field(rmodel)
    names = [f.get("name") for f in (rmodel.get("fields") or []) if f.get("name")]
    return (f"option label = `o.{field}` — the ONLY fields it has are: "
            f"{', '.join(f'`{n}`' for n in ['_id'] + names)}")


class GenAgent:
    """Base: prompt gemma with rule + memory, stream, extract, CHECK, write."""
    name = "agent"

    # A file that fails the compiler twice will not pass on a third identical ask; two regenerations
    # cost ~2 min against a repair phase that costs 10-30 and often still ends red.
    ANALYZER_RETRIES = 2

    def __init__(self, project_dir, memory, emit=None, model=None, get_analyzer=None, contract=None):
        self.project_dir = Path(project_dir)
        self.memory = memory
        self.emit = emit or (lambda *a, **k: None)
        self.model = model or llm.GEN_MODEL
        # Callable returning the shared Analyzer (built lazily, after install). Absent → the loop is
        # skipped entirely and the harness stays the safety net.
        self.get_analyzer = get_analyzer
        # The route/API contract, for the checks a compiler cannot make: a "Login" button in an app
        # with no login page compiles perfectly and 404s on click.
        self.contract = contract or {}

    # ── llm ───────────────────────────────────────────────────────────────────
    def _gen(self, label: str, user: str, num_predict: int = 4096) -> str:
        self.emit("start", {"label": label})
        full = ""
        try:
            # think=False, and it must stay false: thinking tokens are spent from num_predict, not from
            # the (huge) context window. Measured on this build — the real route prompt at its real
            # budget: think=False → 3978 chars of complete code (`stop`); think='low' → 6505 chars of
            # thinking and ZERO code (`length`); raising the budget to 4096 just bought 15256 chars of
            # thinking and still no code. Every file came back truncated or empty.
            for tok in llm.stream_chat([{"role": "user", "content": user}],
                                       model=self.model, system=SYSTEM,
                                       num_predict=num_predict, think=False):
                full += tok
                self.emit("token", tok)
        except Exception as e:  # noqa: BLE001
            self.emit("log", {"text": f"gen error ({label}): {e}"})
        self.emit("end", {})
        return extract_code(full)

    # ── compiler in the loop ──────────────────────────────────────────────────
    def _contract_diagnostics(self, rel: str, code: str) -> list[dict]:
        """The faults a green build hides: a link to a route that doesn't exist, a fetch to an API
        that doesn't exist, invented metrics. Shaped like compiler diagnostics so one loop fixes
        both — these checks existed and reported at the very end, where nothing acted on them."""
        if not self.contract or not rel.endswith((".ts", ".tsx")):
            return []
        try:
            from agents.quality import scan_source
            return [{"line": None, "code": f["signature"].split(":")[0], "message": f["message"]}
                    for f in scan_source(rel, code, self.contract)]
        except Exception:  # noqa: BLE001
            return []

    def exemplar_ctx(self, shape: str) -> str:
        """A sibling of this shape that the compiler already passed, as a worked example.

        The 11 stuck files in a 97-file app were almost all invented API surface (`labelId` on a
        TextField, `fullWeight`, `warning`) — the compiler names the fix and the model still misses it
        twice, so writing a rule per invention is a losing race. A real, compiling example of the same
        shape settles it by showing rather than arguing."""
        code = self.memory.exemplar(shape) if (shape and self.memory) else None
        if not code:
            return ""
        return (
            "── A COMPONENT OF THIS EXACT SHAPE THAT ALREADY COMPILES IN THIS APP ──\n"
            "Copy its structure, its imports and its MUI prop usage. Do NOT copy its entity, fields, "
            "labels or copy — yours are different and are specified below.\n"
            f"```tsx\n{code.strip()}\n```\n\n"
        )

    def _gen_checked(self, rel: str, user: str, num_predict: int = 4096, shape: str = "") -> str:
        """Generate `rel`, then let the real TypeScript compiler read it BEFORE it lands.

        The old flow wrote whatever came back and discovered the truth from `next build` ten minutes
        later, when only the repair LLM could help — and it routinely couldn't: three guarded regens
        and a cloud escalation never landed a one-character `</Alert}`. Here the same model rewrites
        its own file against the compiler's exact words, seconds after writing it, while the whole
        prompt that produced it is still the prompt."""
        code = self._gen(rel, user, num_predict)
        code, _ = scrub_jsx(rel, code, self.project_dir)
        az = self.get_analyzer() if self.get_analyzer else None
        if not az or not az.ok or not rel.endswith((".ts", ".tsx")):
            return code

        # Keep the BEST attempt, not the last: a regeneration can make things worse (measured — one
        # page went 5 diagnostics → 9), and the harness learned this lesson the expensive way.
        best, best_diags = code, None

        for attempt in range(self.ANALYZER_RETRIES + 1):
            diags = az.check(rel, code) + self._contract_diagnostics(rel, code)
            if not diags:
                self.emit("log", {"text": f"analyzer: {rel} clean"
                                          + (f" (after {attempt} regeneration(s))" if attempt else "")})
                az.release(rel)
                # Only a FIRST-try pass earns the exemplar slot: a file that needed the compiler's
                # help is not the example to hand the next one.
                if shape and attempt == 0 and self.memory:
                    self.memory.store_exemplar(shape, code)
                return code
            if best_diags is None or len(diags) < len(best_diags):
                best, best_diags = code, diags
            if attempt == self.ANALYZER_RETRIES:
                self.emit("log", {"text": f"analyzer: {rel} still has {len(best_diags)} diagnostic(s) after "
                                          f"{attempt} regeneration(s) — keeping the best attempt for the "
                                          f"repair harness"})
                break
            # Name the top diagnostic: a class that recurs across files is a RULE bug, and the log is
            # where that becomes visible (every one found so far was the rule teaching the mistake).
            top = " ".join(str(diags[0].get("message", "")).split())[:90]
            self.emit("log", {"text": f"analyzer: {rel} — {len(diags)} diagnostic(s), regenerating "
                                      f"({attempt + 1}/{self.ANALYZER_RETRIES}); top = {top}"})
            # A truncated file is a different failure: the model stopped mid-JSX, so handing the stump
            # back with "fix these errors" reproduces it — measured, 4 diagnostics → 4 → 4, and the
            # cut-off is nowhere near the token budget (215 lines of a 5000-token allowance). It needs
            # to be told it ran out of rope and to write something it can finish, not to patch.
            truncated = any(d.get("code") in (17008, 1005) or
                            "no corresponding closing tag" in str(d.get("message", ""))
                            for d in diags)
            if truncated:
                fix = (
                    f"{user}\n\n"
                    "── YOUR PREVIOUS ATTEMPT WAS CUT OFF PART-WAY THROUGH ──\n"
                    f"{format_diagnostics(diags, limit=2)}\n\n"
                    "You stopped mid-JSX and the file was never closed. Do NOT try to patch it — write "
                    "the file again from the start, SHORTER and COMPLETE:\n"
                    "- keep it under ~150 lines;\n"
                    "- fewer, simpler sections — every tag you open, close;\n"
                    "- drop decorative markup before you drop working behaviour (the form, the list, "
                    "the states must all still be there);\n"
                    "- finish with the closing brace of the component.\n"
                    "Output only the complete TSX file."
                )
            else:
                fix = (
                    f"{user}\n\n"
                    "── YOUR PREVIOUS ATTEMPT AT THIS FILE FAILED THE TYPESCRIPT COMPILER ──\n"
                    f"{format_diagnostics(diags)}\n\n"
                    "This is the file you wrote:\n"
                    f"```tsx\n{code}\n```\n"
                    "Fix EVERY error above and output the COMPLETE corrected file — same task, same "
                    "rules, no explanation, no markdown fence. Do not suppress errors with `any`, "
                    "`@ts-ignore` or by deleting the feature; fix the actual cause."
                )
            new = self._gen(rel, fix, num_predict)
            if not new.strip():
                break            # empty regeneration — keep the best we have
            code, _ = scrub_jsx(rel, new, self.project_dir)
        az.release(rel)
        return best

    # ── disk + streaming ──────────────────────────────────────────────────────
    def write(self, rel: str, content: str):
        content, scrubbed = scrub_jsx(rel, content, self.project_dir)
        if scrubbed:
            self.emit("log", {"text": f"scrubbed {scrubbed} mechanical TSX fix(es) in {rel}"})
        fp = self.project_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        self.emit("file", {"path": rel, "content": content})
        try:
            self.memory.note_progress(f"{self.name}: wrote {rel} ({len(content)}B)")
        except Exception:
            pass
        return rel


class ModelAgent(GenAgent):
    name = "model"

    def generate(self, model: dict) -> str:
        name = pascal(model.get("name", "Item"))
        others = [n for n in self.memory.model_names() if n != name]
        user = (
            f"RULE:\n{read_rule('model')}\n\n"
            f"MEMORY (all models — refs must point at one of these):\n{self.memory.context('MODELS')}\n\n"
            f"TASK: Generate `models/{name}.ts` for model **{name}** with EXACTLY these fields:\n"
            f"{field_lines(model)}\n\n"
            f"Valid ref targets: {', '.join(others) or '(none)'}.\n"
            f"Output only the TypeScript file."
        )
        code = self._gen_checked(f"models/{name}.ts", user, num_predict=1800)
        return self.write(f"models/{name}.ts", code)


class RouteAgent(GenAgent):
    name = "route"

    def generate(self, model: dict) -> list[str]:
        from agents.scaffold import auth_enabled
        name = pascal(model.get("name", "Item"))
        seg = route_name(name)
        written = []
        # The RULE documents `requireUser`/`requireRole` and says to apply "the auth rule supplied by the
        # TASK" — so the TASK must supply one. Left unsaid, the model imports '@/lib/auth', which only
        # exists in auth-enabled apps: a no-auth app then fails to build with "Can't resolve '@/lib/auth'".
        if auth_enabled(self.memory.spec):
            auth_ctx = ("AUTH: this app HAS authentication. Apply the auth rule from the RULE section "
                        "(`requireUser()` / `requireRole('admin')` from '@/lib/auth') before any database "
                        "access, and derive ownership from the session — never from the request body.\n\n")
        else:
            auth_ctx = ("AUTH: this app has NO authentication and NO user accounts. '@/lib/auth' DOES NOT "
                        "EXIST — importing it breaks the build. Never import it; never call requireUser, "
                        "requireRole, getSession or auth(); never reference session/owner/userId fields. "
                        "Every handler is public: connect to the DB and act directly.\n\n")
        base = (
            f"RULE:\n{read_rule('route')}\n\n"
            f"{auth_ctx}"
            f"MEMORY (this model's fields):\n## {name}\n{field_lines(model)}\n\n"
        )
        coll = self._gen_checked(
            f"app/api/{seg}/route.ts",
            base + f"TASK: Generate the COLLECTION handler `app/api/{seg}/route.ts` "
                   f"(GET list + POST create) for model **{name}** (import from '@/models/{name}'). "
                   f"Output only the file.",
            num_predict=1800)
        written.append(self.write(f"app/api/{seg}/route.ts", coll))
        one = self._gen_checked(
            f"app/api/{seg}/[id]/route.ts",
            base + f"TASK: Generate the ITEM handler `app/api/{seg}/[id]/route.ts` "
                   f"(GET one + PUT + DELETE, validate ObjectId) for model **{name}** "
                   f"(import from '@/models/{name}'). Each handler signature MUST be exactly "
                   f"`(_req: Request, {{ params }}: {{ params: Promise<{{ id: string }}> }})` and use "
                   f"`const {{ id }} = await params`. NEVER read the id from req.url. Output only the file.",
            num_predict=1800)
        written.append(self.write(f"app/api/{seg}/[id]/route.ts", one))
        return written


class PageAgent(GenAgent):
    name = "page"

    def _page_file(self, path: str) -> str:
        clean = str(path or "/").strip("/")
        return f"app/{clean}/page.tsx" if clean else "app/page.tsx"

    def generate(self, page: dict, component: str) -> str:
        path = str(page.get("path") or "/")
        kind = str(page.get("kind") or "static")
        resource = pascal(page.get("resource")) if page.get("resource") else ""

        # The body is generated first, so its signature is a FACT — read it from the file instead of
        # having two rule docs agree about it by convention. They didn't: `rules/page.md` said "pass
        # `initialItem` for every `[id]` route" while the section agent only declared props for
        # `kind == "detail"`, so an edit page passed a prop to a body that took none. Every such
        # mismatch was a type error the model could not have known about.
        body_rel = f"components/pages/{component}.tsx"
        signature = ""
        az = self.get_analyzer() if self.get_analyzer else None
        if az and az.ok:
            itf = az.interface(body_rel)
            if itf.get("found") and itf.get("name"):
                props = itf.get("props")
                signature = (
                    f"THE BODY COMPONENT ALREADY EXISTS. Its real signature, read from the file:\n"
                    f"  `export default function {itf['name']}({props or ''})`\n"
                    + ("It takes NO props — render it as `<%s />` and pass nothing.\n" % itf["name"]
                       if not props else
                       "Pass EXACTLY those props, with those exact names — nothing else.\n")
                )

        user = (
            f"RULE:\n{read_rule('page')}\n\n"
            f"{signature}"
            f"TASK: Generate the route wrapper `{self._page_file(path)}` for route `{path}` "
            f"(kind=`{kind}`). It renders the body component `@/components/pages/{component}`"
            + (f" and the resource model is **{resource}**." if resource else ".")
            + " Output only the file."
        )
        code = self._gen_checked(self._page_file(path), user, num_predict=900)
        return self.write(self._page_file(path), code)


class SectionAgent(GenAgent):
    name = "section"

    def generate(self, page: dict, component: str, imports=None,
                 archetype: str = "", pattern: str = "") -> str:
        path = str(page.get("path") or "/")
        kind = str(page.get("kind") or "static")
        resource = pascal(page.get("resource")) if page.get("resource") else ""
        model = self.memory.entity(resource) if resource else None
        seg = route_name(resource) if resource else ""
        fields_ctx = f"Resource **{resource}** (`/api/{seg}`) fields:\n{field_lines(model)}\n\n" if model else ""
        # Reference fields → exact dropdown endpoints (prevents 'Cast to ObjectId' runtime crashes).
        # One builder for both agents: this used to be a second copy that drifted — it never learned
        # to name the referenced entity's real display field.
        ref_ctx = ref_hints(model, self.memory)
        # Sections may be plain strings (AutoHub SRS) or objects {section_name, components}
        # (role-wise SRS). Normalize to labels; collect declared component hints.
        sections, comp_hints = [], []
        for s in (page.get("sections") or []):
            if isinstance(s, dict):
                if s.get("section_name"):
                    sections.append(str(s["section_name"]))
                comp_hints += [str(c) for c in (s.get("components") or [])]
            elif str(s).strip():
                sections.append(str(s))
        funcs = page.get("functions") or []
        # `Record<string, any>` (not `unknown`): a detail page renders `{initialItem.field}` directly,
        # and `unknown` is not a ReactNode — every field render would be a type error.
        # The page wrapper server-fetches the record for EVERY `[id]` route and passes `initialItem`
        # (see rules/page.md) — an edit route is `kind: form` but still has an id, and only `detail`
        # was told about the prop. So the page passed one and the body took none: a type error on
        # every edit page in every role-wise app.
        takes_item = kind == "detail" or (kind in ("form", "admin") and "[id]" in path)
        detail = "initialItem: Record<string, any>" if takes_item else ""
        seg_detail = f"/{seg}/[id]" if seg else ""
        has_detail = seg_detail in self.memory.valid_routes() if seg else False
        # When declared components have already been generated as their own files, the page
        # body COMPOSES them (imports + layout) instead of re-implementing all UI. This keeps
        # each generation small, so it is not truncated.
        imports = imports or []
        compose_ctx = ""
        if imports:
            imp_lines = "\n".join(f"import {pascal(n)} from '{p}'" for n, p in imports)
            render = " ".join(f"<{pascal(n)} />" for n, _ in imports)
            # Show each chunk's REAL signature, read from the file just written. The page is the only
            # place that knows the state, so a chunk with props must be WIRED here — and a wiring
            # invented against a remembered contract is exactly the mismatch this whole loop exists to
            # stop. The compiler checks it a second later, but only if the page was told the truth.
            az = self.get_analyzer() if self.get_analyzer else None
            sig_lines = []
            for n, p in imports:
                itf = az.interface(p.replace("@/", "") + ".tsx") if az and az.ok else {}
                if itf.get("name"):
                    sig_lines.append(f"  `export default function {itf['name']}({itf.get('props') or ''})`")
            sigs = ("Their REAL signatures, read from the files:\n" + "\n".join(sig_lines) + "\n"
                    "Pass EXACTLY those props — this page owns the state they need.\n"
                    if sig_lines else "")
            compose_ctx = (
                "COMPOSE existing components — these are ALREADY generated. Import each EXACTLY as shown "
                "and place it inside its section; do NOT re-implement their internals:\n"
                + imp_lines + "\n" + sigs
                + f"Render them within the sections: {render}. Add only section headings/layout around them.\n\n")
        # A composing page and a standalone one are different shapes: the first wires chunks, the
        # second writes the whole surface. Keying them together would teach the wrong lesson.
        shape = f"section:{kind}" + (":composed" if imports else "")
        user = (
            f"RULE:\n{read_rule('section')}\n\n"
            f"MEMORY:\n{self.memory.context('LINKS', 'API', 'CONTRACT')}\n\n"
            f"{design_ctx(self.memory.spec)}"
            f"{self.exemplar_ctx(shape)}"
            f"{fields_ctx}{ref_ctx}{compose_ctx}"
            f"TASK: Generate the page body `components/pages/{component}.tsx`.\n"
            f"Route: `{path}`  Kind: `{kind}`  Access: `{page.get('access', 'public')}`\n"
            + (f"PAGE ARCHETYPE — build the page in THIS shape (not a generic table/dashboard): "
               f"**{archetype}** — {pattern}\n" if archetype and pattern else "")
            + (f"Declared sections (render each as its own <section>, min 4): {', '.join(sections)}\n" if sections else "")
            + (f"Declared UI blocks to include: {', '.join(dict.fromkeys(comp_hints))}\n" if comp_hints and not imports else "")
            + (f"Declared functions to support: {', '.join(funcs)}\n" if funcs else "")
            + (f"Component props: {{ {detail} }}\n" if detail else "")
            + (f"Type records with the entity DTO: `import type {{ {resource} }} from '@/types'` and use "
               f"ONLY its exact field names (see CONTRACT). NEVER invent a field name.\n" if resource else "")
            + "LINK RULES: only use <a href> / navigation to a route in VALID ROUTES above. "
              "NEVER invent a route or link to one not listed (it will 404). For per-record actions, "
              "call the API with fetch — do not navigate.\n"
            + (f"A detail page `{seg_detail}` EXISTS — list rows may link to it.\n" if has_detail
               else (f"There is NO detail page for this resource — do NOT link rows to `/{seg}/<id>`; "
                     f"edit inline via a modal + the API instead.\n" if seg else ""))
            + "Output only the TSX file (first line 'use client')."
        )
        # Composing pages are small (imports + layout); only non-composed rich pages need headroom.
        np = 3200 if imports else (10000 if kind in ("landing", "static", "table-crud", "pos", "finance", "workflow", "reports") else 5000)
        rel = f"components/pages/{component}.tsx"
        code = self._gen_checked(rel, user, num_predict=np, shape=shape)
        # Record the produced page-body component so COMPONENTS.md + LOCATIONS.md are complete (page
        # bodies used to be invisible to memory — COMPONENTS.md always read "(none yet)").
        self.memory.note_component(rel)
        return self.write(rel, code)


class LogicAgent(GenAgent):
    name = "logic"

    def generate(self, rel: str, task: str, num_predict: int = 2400) -> str:
        user = (
            f"RULE:\n{read_rule('logic')}\n\n"
            f"MEMORY:\n{self.memory.context('MODELS', 'API')}\n\n"
            f"TASK: Generate `{rel}`. {task}\nOutput only the TypeScript file."
        )
        code = self._gen_checked(rel, user, num_predict=num_predict)
        return self.write(rel, code)


class ComponentAgent(GenAgent):
    name = "component"

    def generate(self, rel: str, task: str, num_predict: int = 1800) -> str:
        user = (
            f"RULE:\n{read_rule('component')}\n\n"
            f"TASK: Generate `{rel}`. {task}\nOutput only the TSX file."
        )
        code = self._gen_checked(rel, user, num_predict=num_predict)
        self.memory.note_component(rel)
        return self.write(rel, code)

    def generate_contract(self, contract: dict, rel: str) -> str:
        """Generate one declared, self-contained reusable component from its contract."""
        name = pascal(contract.get("name", "Component"))
        ctype = str(contract.get("type", "display"))
        resources = [pascal(r) for r in (contract.get("allowed_resources") or [])]
        model, primary = None, ""
        for rn in resources:
            model = self.memory.entity(rn)
            if model:
                primary = rn
                break
        if not primary and resources:
            primary = resources[0]
        seg = route_name(primary) if primary else ""
        fields_ctx = (f"Primary resource **{primary}** (`/api/{seg}`) fields:\n{field_lines(model)}\n\n"
                      if model else "")
        detail_seg = f"/{seg}/[id]" if seg else ""
        has_detail = detail_seg in self.memory.valid_routes() if seg else False
        # A CHUNK declares its props and is driven by its parent; a self-contained component fetches
        # for itself. Chunking exists because a 340-line page body is where the model loses the thread
        # and truncates mid-JSX — the one failure regeneration cannot fix, because the rewrite is just
        # as long. Small pieces converge; the analyzer then verifies the wiring between them.
        props = str(contract.get("props") or "").strip()
        signature = f"function {name}({{ {', '.join(p.split(':')[0].strip() for p in props.split(';') if p.strip())} }}: {{ {props} }})" if props else f"function {name}()"

        # An app asks for a dozen of each shape (12 tables, 12 form dialogs). Key the exemplar on the
        # shape, not the entity, so the second Table learns from the first.
        shape = f"component:{ctype}"
        user = (
            f"RULE:\n{read_rule('component')}\n\n"
            f"MEMORY:\n{self.memory.context('LINKS', 'API', 'CONTRACT')}\n\n"
            f"{design_ctx(self.memory.spec)}"
            f"{self.exemplar_ctx(shape)}"
            f"{fields_ctx}{ref_hints(model, self.memory)}"
            f"TASK: Generate the reusable component `{rel}`.\n"
            f"Default export EXACTLY `{signature}` (kind: {ctype}).\n"
            + (f"These props are its ENTIRE input — the parent page passes exactly these and nothing "
               f"else. Declare them exactly as written, add no others, and give none a default.\n"
               if props else "")
            + ("" if props else
               (f"It works with **{primary}** at `/api/{seg}` — fetch its own data on mount and handle "
                f"loading/empty/error states.\n" if seg else
                "If it needs data, fetch a real endpoint from the API memory; otherwise render its UI.\n"))
            + (f"Type records with the entity DTO: `import type {{ {primary} }} from '@/types'` and use "
               f"ONLY its exact field names (see CONTRACT). NEVER invent a field name.\n" if primary else "")
            + "Keep it COMPLETE and under ~140 lines; close every tag and brace.\n"
            + "LINK RULES: only <a href> to a route in VALID ROUTES; for record actions call the API with fetch.\n"
            + (f"A detail page `{detail_seg}` EXISTS — rows may link to it.\n" if has_detail
               else (f"There is NO detail page for `{primary}` — edit inline via a modal + the API.\n" if seg else ""))
            + "Output only the TSX file (first line 'use client')."
        )
        code = self._gen_checked(rel, user, num_predict=4200, shape=shape)
        self.memory.note_component(rel)
        return self.write(rel, code)
