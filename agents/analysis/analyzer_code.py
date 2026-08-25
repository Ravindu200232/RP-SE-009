"""JavaScript/import/ObjectId/seed/auth boundary static analysis rules."""
from agents.analysis.analyzer_common import *


class AnalyzerCodeMixin:
    _OID_CALL_RE = re.compile(r"\bnew\s+ObjectId\s*\(\s*([^)]{1,80}?)\s*\)")
    _OID_HEX_RE = re.compile(r"^['\"][0-9a-f]{24}['\"]$", re.I)
    _OID_NOT_ID_RE = re.compile(
        r"\.(email|name|username|title|slug|label|description|password)\b",
        re.I)

    _UNAWAITED_RE = re.compile(
        r"(?<!await\s)(?<!await)\b(getCollection|getDb)\s*\([^()]*\)\s*\.\s*"
        r"([A-Za-z_$][\w$]*)")

    def unawaited_collection(self) -> list:
        """`getCollection(x).findOne(...)` — a method called on a Promise.

        `lib/mongodb.js` declares `export async function getCollection`, so
        without `await` the value is a Promise and every driver method on it
        is undefined:

            TypeError: getCollection(...).findOne is not a function

        `next build` compiles it — the property is only missing at run time —
        and the page 500s on the first request. Measured across the projects
        on disk: nine of these, all in the one app that was serving errors.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            body = _strip_noncode(content)
            for m in self._UNAWAITED_RE.finditer(body):
                fn, method = m.group(1), m.group(2)
                line = body[:m.start()].count("\n") + 1
                out.append(Finding(
                    "blocker", "UNAWAITED_COLLECTION",
                    f"line {line} calls .{method}() straight off {fn}(), which "
                    f"is async — so it runs on the Promise, not the "
                    f"collection, and throws `{fn}(...).{method} is not a "
                    f"function` on the first request. `next build` cannot "
                    f"catch this",
                    path=path,
                    fix=(f"await it: `const col = await {fn}(…)` and then "
                         f"`col.{method}(…)`, or wrap the call — "
                         f"`(await {fn}(…)).{method}(…)`"),
                    extra=[path]))
        return out

    def bad_objectid(self) -> list:
        """`new ObjectId(...)` given something that can never be an id.

        The constructor takes a 24-character hex string, a 12-byte array or
        an integer. Handed an email it throws BSONError — and since seeding
        runs from every page that reads data, one such line in lib/seed.js
        breaks every route in the app while `next build` stays green.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            body = _strip_noncode(content)
            for m in self._OID_CALL_RE.finditer(body):
                arg = m.group(1).strip()
                if not arg:
                    continue
                why = ""
                if arg[:1] in "'\"" and not self._OID_HEX_RE.match(arg):
                    why = f"{arg[:40]} is not a 24-character hex string"
                elif self._OID_NOT_ID_RE.search(arg):
                    why = f"{arg[:40]} is not an id"
                if not why:
                    continue
                line = body[:m.start()].count("\n") + 1
                out.append(Finding(
                    "blocker", "BAD_OBJECTID",
                    f"line {line} calls new ObjectId({arg[:40]}) — {why}, so "
                    f"it throws BSONError at request time. `next build` "
                    f"cannot catch this, and if this runs while seeding it "
                    f"breaks every page that reads data",
                    path=path,
                    fix=("pass a real id: the `_id` of the row you inserted, "
                         "kept from its insert result, or `new ObjectId()` "
                         "with no argument to mint one. To point at a record "
                         "by email, look it up and use the _id it comes back "
                         "with — never build an id out of a field"),
                    extra=[path]))
        return out

    def stray_directives(self) -> list:
        """`'use client'` that is not the first statement — a hard build error."""
        out = []
        for path, content in self.code_files().items():
            for m in self.arch.STRAY_DIRECTIVE_RE.finditer(content):
                head = re.sub(r"//[^\n]*|/\*.*?\*/", "", content[:m.start()],
                              flags=re.S).strip()
                if head:
                    out.append(f"{path}:{content[:m.start()].count(chr(10)) + 1}")
                    break
        return out

    def missing_local_imports(self) -> list:
        """Local imports whose target file does not exist.

        A repair can legitimately introduce a new component and import it from
        an existing page in the same turn.  If the component write is lost or
        rejected, named/default export checks cannot report anything because
        there is no module to inspect.  Catch that state before `next build`.
        """
        out = []
        files = self.code_files()
        suffixes = (".jsx", ".js", ".tsx", ".ts", ".mjs", ".cjs")
        from pathlib import PurePosixPath

        def expected(importer, spec):
            if spec.startswith("@/"):
                raw = spec[2:]
            elif spec.startswith(("./", "../")):
                raw = (PurePosixPath(importer).parent / spec).as_posix()
            else:
                return ""
            parts = []
            for bit in raw.split("/"):
                if bit == "..":
                    if parts:
                        parts.pop()
                elif bit not in ("", "."):
                    parts.append(bit)
            base = "/".join(parts)
            if not base:
                return ""
            if any(base.endswith(ext) for ext in suffixes):
                return base
            return base + ".jsx"

        for rel, src in sorted(files.items()):
            if not isinstance(src, str):
                continue
            for st in parse_imports(src):
                spec = st.spec or ""
                if not spec.startswith(("./", "../", "@/")):
                    continue
                if spec.endswith((".css", ".scss", ".json", ".svg", ".png", ".jpg", ".webp")):
                    continue
                if resolve_local(rel, spec, files) is not None:
                    continue
                target = expected(rel, spec)
                if not target:
                    continue
                out.append(Finding(
                    "blocker", "MISSING_LOCAL_IMPORT",
                    f"imports '{spec}' but no local module exists for it; the "
                    f"next build will fail with Module not found",
                    path=rel,
                    fix=f"write {target} or remove/change the import so it points to an existing module",
                    extra=[target]))
        return out

    def broken_imports(self) -> list:
        """
        Named imports of a local module that the module does not export.

        This is the check that catches the "login reaches the dashboard and
        bounces back" class of bug. JavaScript has no compile-time export
        checking, so `next build` passes and the route 500s at request time
        instead; the missing-file check above cannot see it, because the file
        being imported exists perfectly well — only the names are wrong.

        `extra` carries the target module, because the fix usually belongs
        there (write the missing function) rather than in the importer.
        """
        out = []
        groups = {}
        code = self.code_files()

        # The default import is the other half.
        for b in check_default_imports(code):
            out.append(Finding(
                "blocker", "BROKEN_IMPORT",
                f"imports {b.name} as the DEFAULT export of '{b.spec}', which "
                f"has no default export — it exports "
                f"{', '.join(b.available) or 'nothing'}. The import is "
                f"undefined at runtime, so rendering <{b.name} /> throws "
                f"'Element type is invalid'. `next build` cannot catch this",
                path=b.importer,
                fix=(f"import the name it does export — `import {{ … }} from "
                     f"'{b.spec}'` — or add `export default` to {b.module}, "
                     f"whichever matches how the rest of the app uses it"),
                extra=[b.importer, b.module]))

        for b in check_named_imports(code):
            groups.setdefault((b.importer, b.module, b.spec), []).append(b)
        for (importer, module, spec), items in sorted(groups.items()):
            names = ", ".join(sorted({i.name for i in items}))
            avail = ", ".join(items[0].available) or "(nothing)"
            framework = module in FRAMEWORK_EXPORTS
            out.append(Finding(
                "blocker", "BROKEN_IMPORT",
                f"imports {{ {names} }} from '{spec}', which exports only: "
                f"{avail}. Calling one of those throws at request time, so the "
                f"route returns 500 — `next build` cannot catch this",
                path=importer,
                fix=("use one of those instead — NextResponse.json(…) is "
                     "almost always what is meant" if framework else
                     f"either add the missing export to {module} or use one "
                     f"that already exists. Do not rename or remove the "
                     f"existing exports — other files import them"),

                extra=[] if framework else [module]))
        return out

    def unresolved_packages(self) -> list:
        """Imported but neither declared nor installed. Node builtins excluded."""
        try:
            pkg = json.loads((self.project_dir / "package.json")
                             .read_text(encoding="utf-8"))
            declared = set(pkg.get("dependencies", {})) | \
                set(pkg.get("devDependencies", {}))
        except Exception:
            declared = set()
        nm = self.project_dir / "node_modules"
        missing = []
        for content in self.code_files().values():
            for name in self.arch.imported_packages(content):
                declared_here = name in declared
                installed_here = (nm / name / "package.json").exists()
                if declared_here and installed_here:
                    continue
                if name not in missing:
                    missing.append(name)
        return missing

    def seed_race(self) -> list:
        """
        A seed that is not safe to call twice at once.

        Generated apps call `ensureSeeded()` from the root layout, so it runs on
        every request. `if (await col.countDocuments() === 0) insertMany(docs)`
        is a race: two requests arriving together both read 0, both insert, and
        the loser dies with E11000 — which turns into an HTTP 500 on a page
        that is otherwise correct. `insertMany` also stamps `_id` onto the
        documents it was given, so a module-level array cannot be reused.

        This is intermittent, which is what makes it so confusing in the wild.
        """
        out = []
        for path, content in self.code_files().items():
            if "ensureSeeded" not in content or "insertMany" not in content:
                continue
            if "seed" not in path.lower():
                continue
            guarded = ("ordered: false" in content or "ordered:false" in content
                       or "e.code !== 11000" in content
                       or "code !== 11000" in content
                       or re.search(r"\blet\s+\w*[Ss]eed\w*\s*=\s*null", content)
                       or re.search(r"upsert\s*:\s*true", content))
            if guarded:
                continue
            out.append(Finding(
                "blocker", "SEED_RACE",
                "ensureSeeded() inserts without guarding against a concurrent "
                "run — two requests at once both see an empty collection and "
                "the second insertMany fails with E11000, which 500s the page",
                path=path,
                fix="cache the run in a module-level promise, build the "
                    "documents inside the function, and use "
                    "insertMany(docs, { ordered: false }) inside a try/catch "
                    "that ignores e.code === 11000"))
        return out

    COUNT_GUARD_RE = re.compile(
        r"countDocuments\s*\([^)]*\)\s*\)*\s*(?:[><=!]=?=?)\s*0"
        r"|\.length\s*(?:[><=!]=?=?)\s*0"
        r"|if\s*\(\s*!\s*(?:existing|found|already)\w*\s*\)")

    COUNT_VAR_RE = re.compile(
        r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+[\w.]*countDocuments\s*\(")
    UPSERT_RE = re.compile(r"upsert\s*:\s*true|\$setOnInsert|bulkWrite")

    def stale_seed_guard(self) -> list:
        """
        A seed that stops working the first time a real person signs up.

        `if (await usersCol.countDocuments() > 0) return` reads like "seed
        once". What it actually means is "seed only while nobody has ever
        registered". One signup makes the count non-zero permanently, so the
        demo accounts are never created — while the app still advertises them —
        and every demo login returns 401 from then on.

        Observed exactly that way: a user signed up, and
        `agentforge_json_srs_document_docum_2.users` then held one real account and
        zero of its three demo accounts. The app was correct the day it was
        built and broken the day it was used, which is why nothing caught it:
        every other gate here runs at build time, against a database AgentForge had
        just dropped.

        Measured across the corpus: **13 of 13 seeded projects** have this, and
        not one uses an upsert — because the builder prompt handed them the
        count-guard as its template. Note `seed_race()` above treats
        `upsert: true` as proof of concurrency-safety, which it is; this check
        is the other half of the same fact, and the two agree that an upsert is
        the right shape.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            if "seed" not in path.lower() or "ensureSeeded" not in content:
                continue
            if self.UPSERT_RE.search(content):
                continue
            m = self.COUNT_GUARD_RE.search(content)
            if not m:

                for v in self.COUNT_VAR_RE.finditer(content):
                    name = re.escape(v.group(1))
                    m = re.search(rf"\b{name}\s*(?:[><=!]=?=?)\s*0", content)
                    if m:
                        break
                    m = None
            if not m:
                continue
            line = content[:m.start()].count("\n") + 1
            out.append(Finding(
                "blocker", "STALE_SEED_GUARD",
                f"line {line} gates seeding on whether the collection is "
                f"already populated. The first real signup makes that "
                f"permanently true, so the demo accounts are never created "
                f"and every demo login 401s from then on — while the app goes "
                f"on offering them",
                path=path,
                fix="seed by identity instead: one "
                    "`updateOne({ email }, { $setOnInsert: {…} }, "
                    "{ upsert: true })` per document. `$setOnInsert`, not "
                    "`$set` — a bcrypt hash differs every time it is computed, "
                    "so `$set` would rewrite it on every start and could "
                    "overwrite a password a real user had changed"))
        return out

    def authz_redirect(self) -> list:
        """
        A signed-in user sent to the login page because of their role.

            if (!user || user.role !== 'admin') redirect('/login')

        Two different failures share one branch here. No session means "sign
        in", and `/login` is right. A session with the wrong role means "you may
        not see this" — and sending that user to the login page is
        indistinguishable, from where they are sitting, from having their login
        rejected. They sign in, land back on the login form, and conclude the
        password is wrong.

        That is the "I log in and it throws me back to login" report, and it is
        measured at 7 occurrences across 5 projects — three of them in the app
        that was reported.

        Parenthesis-balanced rather than regex-matched: the common shape is
        `(user.role !== 'a' && user.role !== 'b')`, and a `[^)]*` pattern stops
        at the inner `)` and misses every multi-role guard, which is most of
        them.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            for m in re.finditer(r"if\s*\(\s*!\s*\w+\s*\|\|", content):
                open_paren = content.rindex("(", m.start(), m.end())
                depth = 0
                for k in range(open_paren, min(len(content), open_paren + 800)):
                    if content[k] == "(":
                        depth += 1
                    elif content[k] == ")":
                        depth -= 1
                        if depth:
                            continue
                        cond, tail = content[open_paren:k + 1], content[k + 1:k + 140]
                        if re.search(r"\brole\b|\bisAdmin\b|\bpermission", cond) \
                                and re.search(r"redirect\(\s*['\"]/login", tail):
                            line = content[:open_paren].count("\n") + 1
                            out.append(Finding(
                                "blocker", "AUTHZ_REDIRECT",
                                f"line {line} sends a signed-in user to "
                                f"/login because their role does not match. "
                                f"From the user's side that is identical to a "
                                f"rejected password: they log in, bounce back "
                                f"to the login form, and report that login is "
                                f"broken",
                                path=path,
                                fix="split the two cases — `if (!user) "
                                    "redirect('/login')` for no session, then a "
                                    "separate `if (user.role !== '…') "
                                    "redirect('/')` for the wrong role"))
                        break
        return out

    def seed_behind_auth(self) -> list:
        """
        The seeder placed after an auth guard, so it can never run.

        Observed exactly this, and it deadlocks the app:

            const user = await getSessionUser()
            if (!user) redirect('/login')     // everyone, on a fresh database
            await ensureSeeded()              // never reached

        The first visitor is signed out, so they are redirected before the seed
        runs; the seed is what creates the demo accounts; so no account exists
        to sign in with. You need an account to trigger the code that creates
        accounts. Every gate passes — the page compiles, `/` answers 307, the
        route probe is happy — and the user meets it as "login doesn't work"
        with an empty `user` collection.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            m = re.search(r"\bensureSeeded\s*\(", content)
            if not m:
                continue
            guard = re.search(r"\bredirect\s*\(\s*['\"]", content[:m.start()])
            if not guard:
                continue
            line = content[:m.start()].count("\n") + 1
            gline = content[:guard.start()].count("\n") + 1
            out.append(Finding(
                "blocker", "SEED_BEHIND_AUTH",
                f"calls ensureSeeded() at line {line}, after the redirect at "
                f"line {gline}. On a fresh database nobody is signed in, so "
                f"every visitor is redirected before the seed runs — and the "
                f"seed is what creates the accounts they would sign in with",
                path=path,
                fix="move `await ensureSeeded()` above the session read, so it "
                    "is the first thing the page does. Better still, also call "
                    "it from the login page — that is the page a signed-out "
                    "visitor actually reaches"))
        return out

    LOOPBACK_ORIGIN_RE = re.compile(
        r"trustedOrigins[^\]]*?(localhost:\*|127\.0\.0\.1:\*)", re.S)

    def auth_origin(self) -> list:
        """
        Better Auth configured to refuse the origin the app is viewed from.

        It compares the request's `Origin` header against `trustedOrigins` and
        answers `403 Invalid origin` for anything else — which reaches the user
        as a red line on the login form, with an empty database and nothing at
        all in the build output. Every other gate passes: the app compiles, the
        routes return 200, the seeder works (it is a direct server-side call and
        carries no Origin header).

        The port cannot be pinned down, which is why the check is for a pattern
        rather than a value: AgentForge previews the app through a proxy on a
        different port from the dev server, the dev port moves when one is
        busy, and `localhost` and `127.0.0.1` are distinct origins to a browser.
        """
        auth = self.code_files().get("lib/auth.js", "")
        if "betterAuth(" not in auth:
            return []
        if self.LOOPBACK_ORIGIN_RE.search(auth):
            return []
        listed = "trustedOrigins" in auth
        return [Finding(
            "blocker", "AUTH_ORIGIN",
            "Better Auth "
            + ("lists specific origins" if listed else "trusts only its baseURL")
            + ", so a request from the preview — which is served on a different "
              "port than the dev server — is answered 403 'Invalid origin'. "
              "Login and signup fail on the form with nothing in the log",
            path="lib/auth.js",
            fix="trustedOrigins: ['http://localhost:*', 'http://127.0.0.1:*'] "
                "— a pattern, because the port moves and localhost and "
                "127.0.0.1 are different origins. A remote origin is still "
                "refused.")]

    SESSION_IMPORT_RE = re.compile(
        r"""import\s*\{[^}]*\bgetSessionUser\b[^}]*\}\s*from\s*['"]@/lib/auth""")
    SESSION_ASSIGN_RE = re.compile(
        r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+getSessionUser\s*\(")

    def session_user_id(self) -> list:
        """
        `user._id` on the object Better Auth returns, which has no `_id`.

        Measured against a running generated app: the session user is
        `{createdAt, email, emailVerified, id, name, role, updatedAt}` — `id`
        is a **string**, and `_id` is simply absent. So `user._id` is
        `undefined`, and every comparison against it is false while every
        document written with it stores `undefined`.

        Nothing else can see this. It compiles, the route returns 200 or a
        perfectly ordinary 403, and the page renders — it is only wrong for the
        user. Two real examples from one build: `appt.vetId.toString() !==
        user._id` meant no vet could ever record a visit, and `ownerId:
        user._id` meant a registered pet never appeared in its owner's list,
        because the list queries `{ownerId: user.id}`.

        Scoped to the variable actually assigned from `getSessionUser()`,
        because `._id` on a Mongo document is correct and common — a blanket
        search reports 43 occurrences across the corpus, of which 21 are real.
        """
        out = []
        for rel, body in sorted(self.code_files().items()):
            if not self.SESSION_IMPORT_RE.search(body):
                continue
            for var in dict.fromkeys(self.SESSION_ASSIGN_RE.findall(body)):
                n = len(re.findall(rf"\b{re.escape(var)}\s*\.\s*_id\b", body))
                if not n:
                    continue
                out.append(Finding(
                    "blocker", "SESSION_USER_ID",
                    f"reads `{var}._id` from Better Auth's session "
                    f"({n} time{'s' if n > 1 else ''}), which is always "
                    f"undefined — the session user's id is `{var}.id`, a "
                    f"string. Comparisons against it are never true and "
                    f"documents written with it store undefined",
                    path=rel,
                    fix=f"use `{var}.id` throughout. It is a string, so "
                        f"compare with `doc.someId?.toString() === {var}.id` "
                        f"and store `someId: new ObjectId({var}.id)` when the "
                        f"column holds an ObjectId."))
        return out
