"""Next auth/root-layout verification, generated linting and component checks."""
from agents.planning.architect_core import *
from agents.planning.architect_core import _fix_doubled_tags, _strip_fence, _safe_flush_len, _RefusalLoop
from agents.planning.architect_prompts import *


class ArchitectNextRulesMixin:
    def fix_next_imports(self) -> int:
        """Rewrite the Pages-Router habits models fall back into."""
        fixed = 0
        for path, content in self._next_files():
            out = content
            out = out.replace("from 'next/router'", "from 'next/navigation'")
            out = out.replace('from "next/router"', 'from "next/navigation"')

            if "<Head" not in out:
                out = re.sub(r"^\s*import\s+\w+\s+from\s+['\"]next/head['\"].*$\n?",
                             "", out, flags=re.M)
            out = re.sub(r"(<Link\b[^>]*?)\sto=", r"\1 href=", out)

            out = re.sub(r"https?://localhost:\d+", "", out)
            if out != content:
                self.write_file(path, out)
                fixed += 1
        if fixed:
            self._log("INFO", f"   🔧 Fixed Next.js imports in {fixed} file(s)")
        return fixed

    TRUSTED_ORIGINS = "['http://localhost:*', 'http://127.0.0.1:*']"
    TRUSTED_RE = re.compile(r"^\s*trustedOrigins:.*?,\s*$\n?", re.M | re.S)

    def verify_auth_config(self) -> bool:
        """
        Make sure Better Auth trusts the origin the app is actually viewed from.

        Without this the login and signup forms answer "Invalid origin" and no
        account is created — and the user meets it as a red message on a form,
        with nothing in the build output.

        It is a healing pass, not just a guard, because the config can be wrong
        for a reason no build-time check would catch: Python does not reload an
        imported module, so an AgentForge server started before this rule existed
        goes on scaffolding the old file for as long as it runs. Repairing on
        every build and every update means such a project is corrected the
        first time anything touches it, rather than staying broken until
        somebody notices and regenerates.
        """
        auth = self.files.get("lib/auth.js")
        if not auth or "betterAuth(" not in auth:
            return True
        if self.TRUSTED_ORIGINS in auth:
            return True

        if "trustedOrigins" in auth:

            fixed = self.TRUSTED_RE.sub("", auth, count=1)
            why = "replacing a hardcoded origin list"
        else:
            fixed, why = auth, "it trusted no origin but its own baseURL"

        anchor = "  plugins:"
        if anchor not in fixed:
            anchor = "})"
        if anchor not in fixed:
            self._log("WARN", "   ⚠ lib/auth.js has no place to add "
                              "trustedOrigins — leaving it alone")
            return False
        fixed = fixed.replace(
            anchor,
            f"  trustedOrigins: {self.TRUSTED_ORIGINS},\n{anchor}", 1)

        self._log("WARN", f"   🔧 lib/auth.js — {why}; the preview is served "
                          f"from a different port than the dev server, and "
                          f"Better Auth answers 'Invalid origin' for it")
        self._scaffolding = True
        try:
            return self.write_file("lib/auth.js", fixed)
        finally:
            self._scaffolding = False

    _SOLE_ELEMENT_RE = r"^[ \t]*<%s(?:\s[^>]*?)?/>[ \t]*\r?\n"

    def _drop_layout_duplicates(self, key: str, content: str) -> str:
        """
        Take out what the ROOT LAYOUT already renders.

        The root layout wraps every page, so a component it renders is on the
        screen once already. A page that renders it again puts two of them
        there — measured on this build, `<Header />` in both `app/layout.jsx`
        and `app/page.jsx`, and the home page served two identical navbars.
        Nothing catches it: it compiles, it renders, there is no error, and the
        browser pass counts characters rather than headers. The same shape was
        reported on a 404 page an earlier build shipped, so it recurs.

        Only pages and nested layouts are touched, only for components the root
        layout really renders, and only where the element stands alone on its
        line. Anything less clear-cut is left alone and said out loud.
        """
        if not key.startswith("app/") or not key.endswith((".jsx", ".js")):
            return content
        name = key.rsplit("/", 1)[-1]
        if not (name.startswith("page.") or name.startswith("layout.")):
            return content
        if key in ("app/layout.jsx", "app/layout.js"):
            return content

        root = self.files.get("app/layout.jsx") or self.files.get("app/layout.js")
        if not root:
            return content
        rendered = {m for m in re.findall(r"<([A-Z]\w*)\s*(?:\s[^>]*?)?/>", root)}
        if not rendered:
            return content

        for comp in sorted(rendered):
            if f"<{comp}" not in content:
                continue
            fixed, n = re.subn(self._SOLE_ELEMENT_RE % comp, "", content,
                               flags=re.M)
            if not n:
                self._log("WARN", f"   ⚠ {key} renders <{comp}/>, which the "
                                  f"root layout already renders — that is two "
                                  f"of them on the page. Left as it is: it is "
                                  f"not on a line of its own.")
                continue

            if f"<{comp}" not in fixed:
                fixed = re.sub(
                    r"^import\s+%s\s+from\s+['\"][^'\"]+['\"];?[ \t]*\r?\n" % comp,
                    "", fixed, flags=re.M)
            self._log("WARN", f"   🔧 {key} — removed <{comp}/>; the root "
                              f"layout already renders it, so the page was "
                              f"showing two")
            content = fixed
        return content

    def verify_root_layout(self) -> bool:
        """The model may overwrite layout.js and drop what makes it a layout."""
        layout = self.files.get("app/layout.js") or self.files.get("app/layout.jsx")
        if layout and all(t in layout for t in ("<html", "<body", "globals.css")):
            return True
        self._log("WARN", "   🔧 Restoring app/layout.js — it lost <html>/<body>")
        title = self.plan.get("title", "AgentForge App")
        self.write_file("app/layout.jsx", textwrap.dedent(f"""\
            import './globals.css'

            export const metadata = {{ title: {json.dumps(title)} }}

            export default function RootLayout({{ children }}) {{
              // suppressHydrationWarning is on <html> and <body> because
              // extensions — Grammarly (data-gr-ext-installed), QuillBot
              // (data-qb-installed), password managers — inject attributes
              // into exactly these two elements before React hydrates. That
              // produces a red "tree hydrated but some attributes … didn't
              // match" overlay on every page for anyone running one, and it
              // is not a fault in the app. The suppression is one level deep:
              // real mismatches inside the tree are still reported.
              return (
                <html lang="en" suppressHydrationWarning>
                  <body className="min-h-screen antialiased" suppressHydrationWarning>
                    {{children}}
                  </body>
                </html>
              )
            }}
            """))
        return False

    STRAY_DIRECTIVE_RE = re.compile(
        r"^[^\S\n]*['\"]use client['\"][^\S\n]*;?[^\S\n]*$", re.M)

    def lint_generated(self) -> list:
        """Problems worth one targeted repair turn rather than shipping."""
        errors = []
        for path, content in self._next_files():
            hits = list(self.STRAY_DIRECTIVE_RE.finditer(content))

            for m in hits:
                head = content[:m.start()]
                head = re.sub(r"//[^\n]*|/\*.*?\*/", "", head, flags=re.S).strip()
                if head:
                    line = content[:m.start()].count("\n") + 1
                    errors.append(
                        f"{path}:{line}: a 'use client' directive appears after "
                        f"other code — it must be the first line of the file, "
                        f"and only once. Move the interactive part into its own "
                        f"file under components/ and import it.")
                    break
        ts = re.compile(r"^\s*interface\s+\w+|:\s*(string|number|boolean|any)\s*[,)=;]"
                        r"|\bas\s+(string|number|const)\b")
        for path, content in self._next_files():
            if ts.search(content):
                errors.append(f"{path}: contains TypeScript syntax — this is a "
                              f"JavaScript project")
            if "react-router-dom" in content:
                errors.append(f"{path}: imports react-router-dom — Next.js uses "
                              f"filesystem routing, not a router library")
            if (path not in {"lib/mongodb.js", "lib/auth.js"}
                    and re.search(r"\bnew\s+MongoClient\b", content)):
                # These are framework-owned boundaries.
                errors.append(f"{path}: constructs a MongoClient — import "
                              f"getDb/getCollection from '@/lib/mongodb' instead")
            # Standalone mongod refuses every transaction.
            if re.search(r"\bstartSession\s*\(|\bwithTransaction\s*\(", content):
                errors.append(f"{path}: opens a MongoDB transaction — the mongod "
                              f"is standalone and answers 'Transaction numbers "
                              f"are only allowed on a replica set member or "
                              f"mongos'; use one atomic updateOne with a guard "
                              f"in the filter and check modifiedCount instead")
            for hit in re.finditer(
                    r"\$inc\s*:\s*\{\s*([A-Za-z_][\w.]*)\s*:\s*-\s*\d", content):
                field = hit.group(1)
                near = content[max(0, hit.start() - 600):hit.end() + 400]
                guarded = re.search(re.escape(field) + r"\s*:\s*\{\s*\$gte?\b", near)
                if not guarded and "modifiedCount" not in near:
                    errors.append(
                        f"{path}: decrements {field} with no guard — two "
                        f"requests can both pass the check and both decrement; "
                        f"put {field}: {{ $gt: 0 }} in the updateOne filter and "
                        f"treat modifiedCount === 0 as the failure")
            if "next/head" in content and "<Head" in content:
                errors.append(f"{path}: uses next/head — the App Router has no "
                              f"<Head>; export a `metadata` object instead")
            if path.endswith("route.js") and re.search(r"export\s+default", content):
                errors.append(f"{path}: route handlers must use named exports "
                              f"(GET/POST/...), never export default")
        for path in self.files:
            if path.startswith("pages/"):
                errors.append(f"{path}: the Pages Router is banned — put routes "
                              f"under app/")
            if path.endswith((".ts", ".tsx")):
                errors.append(f"{path}: TypeScript files are banned — use .js/.jsx")

        try:
            from agents.core.exports_syntax import check_syntax, syntax_messages
            broken, _why = check_syntax(self.project_dir, self.files)
            errors.extend(syntax_messages(broken))
        except Exception:                                  # noqa: BLE001

            pass

        for name in self.unresolved_packages():
            errors.append(f"'{name}' is imported but not installed — run "
                          f"<run_command>npm install {name}</run_command>")

        errors.extend(self.client_server_mix())
        errors.extend(self.undefined_jsx_components())
        errors.extend(self.orphaned_components())
        errors.extend(self.event_handlers_in_server())
        errors.extend(self.component_props_to_client())
        errors.extend(self.bson_props_to_client())
        errors.extend(self.broken_named_imports())

        for path in self.missing_planned_files():
            errors.append(f"{path}: the plan lists this file but it was never "
                          f"written — the route it serves will 404")
        return errors

    JSX_TAG_RE = re.compile(r"</?([A-Z][\w.]*)")

    def orphaned_components(self) -> list:
        """
        Components written and then never rendered by anything.

        The opposite of `undefined_jsx_components`, and the quieter of the two:
        a component nobody imports does not break a build, does not fail a
        test, and does not show up in a route probe. It simply is not there.

        Measured shape: a bakery whose `components/Navbar.jsx` held the site's
        entire navigation and its logo, and whose `app/layout.jsx` rendered
        `{children}` and nothing else. Every gate passed. The app shipped with
        no navigation on any page, and the logo the user had picked and
        approved was on disk, referenced, and invisible. Six other generated
        apps had the same shape — `TopBar`, `CartDrawer`, `ProductTable`.

        Layouts and pages are excluded: Next mounts those by their path, so
        `app/**/page.jsx` being imported by nobody is how routing works.
        """
        out = []
        comps = {p: c for p, c in self._next_files()
                 if p.startswith("components/") and p.endswith((".jsx", ".js"))}
        if not comps:
            return out
        others = [(p, c) for p, c in self._next_files() if p not in comps]
        for path in sorted(comps):
            name = Path(path).stem
            if name.lower() in ("index",):
                continue
            used = re.compile(rf"\b{re.escape(name)}\b")
            if any(used.search(body) for _, body in others):
                continue

            if any(used.search(b) for p, b in comps.items() if p != path):
                continue
            out.append(
                f"{path}: nothing imports or renders {name}. It was written "
                f"and then left out of the tree, so none of it reaches a "
                f"page. Either render it where it belongs — a navbar goes in "
                f"app/layout.jsx around {{children}} — or say why it is not "
                f"needed and delete it.")
        return out

    def undefined_jsx_components(self) -> list:
        """
        Components rendered in JSX that the file never imports or defines.

        The measured shape: `app/page.jsx` renders `<ShoppingCart size={20}/>`
        and the lucide import at the top lists every icon on the page except
        that one. It compiles — JavaScript has no compile-time check for a free
        identifier — and dies at request time with `ReferenceError:
        ShoppingCart is not defined`, taking the whole page with it.

        The test is deliberately conservative: a name is only reported when
        EVERY occurrence of it in the file is a JSX tag. One mention anywhere
        else — an import, a `function` of that name, a destructured prop, an
        assignment — and it is left alone. That way a component arriving by a
        route this cannot model is never falsely accused, at the cost of
        missing a name that is also used as a bare prop value.
        """
        out = []
        for path, content in self._next_files():
            code = strip_noncode(content)
            used = {m.group(1).split(".")[0]
                    for m in self.JSX_TAG_RE.finditer(code)}
            missing = []
            for name in sorted(used):
                total = len(re.findall(rf"\b{re.escape(name)}\b", code))
                as_tag = len(re.findall(rf"</?{re.escape(name)}\b", code))
                if total and total == as_tag:
                    missing.append(name)
            if missing:
                out.append(
                    f"{path}: renders {', '.join(missing[:5])} but never "
                    f"imports or defines "
                    f"{'them' if len(missing) > 1 else 'it'} — this compiles "
                    f"and then throws \"{missing[0]} is not defined\" the "
                    f"first time the page is requested. Add the missing "
                    f"import at the top (lucide icons come from "
                    f"'lucide-react'), or remove the element.")
        return out
