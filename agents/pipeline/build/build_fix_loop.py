

# Compile before dev startup and repair conclusive build errors.
def run_build_fix_loop(arch, proj_dir: Path, db_ok: bool,
                       max_rounds: int = MAX_BUILD_FIX) -> bool:
    """Compile before dev startup and repair conclusive build errors."""
    # From: agents/pipeline/build/runtime_faults.py
    align_tailwind(arch, proj_dir)
    for rnd in range(1, max_rounds + 1):
        estep("build", "active")
        eprog(f"Compiling (round {rnd})…", min(84 + rnd * 2, 92))
        ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                "status": "active"})
        # From: agents/build/tester_common.py
        elog("INFO", f"🔨 npm run build (round {rnd}/{max_rounds})…")

        try:
            # From: agents/planner/builder/dependency_manager.py
            arch.sync_dependencies()
            missing_deps = arch.unresolved_packages()
            if missing_deps:
                # From: agents/planner/builder/dependency_manager.py
                arch.install_packages(missing_deps)
            ensure_node_deps(proj_dir)
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ dependency reconciliation could not finish: {e}")

        # From: agents/pipeline/build/project_preview.py
        errors, conclusive = _npm_build_errors(proj_dir, "next")

        if not conclusive:
            # From: agents/build/tester_common.py
            elog("WARN", "   ⚠ Build check timed out — could not verify")
            ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                    "status": "done"})
            return False
        if not errors:
            # From: agents/build/tester_common.py
            elog("INFO", "   ✅ Build clean")
            estep("build", "done")
            ephase({"phase": -3, "title": "Build clean", "status": "done"})
            return True

        lines = [ln.rstrip() for ln in errors.strip().splitlines() if ln.strip()]
        first = lines[0][:120] if lines else "?"
        # From: agents/build/tester_common.py
        elog("WARN", f"   ❌ Build failed: {first}")

        for ln in _diagnostic_lines(lines):
            # From: agents/build/tester_common.py
            elog("WARN", f"      {ln[:160]}")
        emit({"type": "test_fixing", "attempt": rnd,
              "errors": errors.splitlines()[:5]})

        # From: agents/pipeline/build/runtime_faults.py
        broken = _toolchain_break(proj_dir, errors)
        # From: agents/pipeline/build/runtime_faults.py
        if broken and _repair_toolchain(proj_dir, broken):
            # From: agents/pipeline/build/project_preview.py
            errors, conclusive = _npm_build_errors(proj_dir, "next")
            if conclusive and not errors:
                # From: agents/build/tester_common.py
                elog("INFO", "   ✅ Build clean once the toolchain was repaired "
                             "— no application file was touched")
                estep("build", "done")
                ephase({"phase": -3, "title": "Build clean", "status": "done"})
                return True
            lines = [ln.rstrip() for ln in (errors or "").strip().splitlines()
                     if ln.strip()]
            # From: agents/build/tester_common.py
            elog("WARN", "   ❌ Still failing after the reinstall: "
                         + (lines[0][:120] if lines else "?"))
            if not conclusive:
                ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                        "status": "done"})
                return False

        # From: agents/planner/builder/dependency_manager.py
        wanted = arch.packages_named_in(errors)
        # From: agents/planner/builder/dependency_manager.py
        if wanted and arch.install_packages(wanted):
            # From: agents/pipeline/build/project_preview.py
            errors, conclusive = _npm_build_errors(proj_dir, "next")
            if conclusive and not errors:
                # From: agents/build/tester_common.py
                elog("INFO", "   ✅ Build clean once the packages were in")
                estep("build", "done")
                ephase({"phase": -3, "title": "Build clean", "status": "done"})
                return True
            if not conclusive:
                # From: agents/build/tester_common.py
                elog("WARN", "   ⚠ Build check timed out — could not verify")
                ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                        "status": "done"})
                return False
            lines = [ln.rstrip() for ln in errors.strip().splitlines()
                     if ln.strip()]
            # From: agents/build/tester_common.py
            elog("WARN", f"   ❌ Still failing: "
                         f"{(lines[0][:120] if lines else '?')}")

        if rnd == max_rounds:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ Still failing after {max_rounds} rounds — "
                         f"serving anyway so you can see it")
            ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                    "status": "done"})
            return False

        guidance = nextdocs.guidance_for(errors)
        if guidance:
            # From: agents/build/tester_common.py
            elog("INFO", f"   📖 {', '.join(nextdocs.slugs_in(errors)[:2])} "
                         f"— attached Next.js's own fix guide")

        # From: agents/pipeline/build/runtime_faults.py
        # From: agents/planner/builder/project_memory.py
        arch.update(textwrap.dedent(f"""\
            `npm run build` failed. Fix every error below.

            Any package the compiler named has already been installed for
            you, and anything npm could not supply does not exist — so an
            unresolved import that is still here is a name to correct, not one
            to install. Rewrite the affected file completely.

            ```
            {_filter_db_noise(errors, db_ok)[:4000]}
            ```
            """) + _failing_sources(arch, errors)
            + ("\n" + guidance if guidance else ""))

        ensure_node_deps(proj_dir)
        ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                "status": "done"})

    return False


_ERR_FILE_RE = re.compile(r"^\s*\.?/?((?:app|components|lib)/[\w./\[\]@-]+"
                          r"\.(?:jsx?|mjs))\s*$", re.M)
FAIL_SRC_BUDGET = 26_000


_BUILD_NOISE_RE = re.compile(
    r"^\s*(?:[>$]|▲|-\s|✓|⚠|Creating an optimized|Skipping validation"
    r"|Finished TypeScript|Collecting page data|Generating static pages|npm (?:warn|notice))",
    re.I)


# The lines of a failed build that say what actually broke. A Next.js build opens with eight lines of banner — the
# npm script, the version, the environment, "Compiled successfully" — and the real error comes after them.
# Printing the first eight printed the banner every time, so a prerender failure read as a blank wall and the same
# file was rewritten round after round against no information.
def _diagnostic_lines(lines: list[str], keep: int = 8) -> list[str]:
    """The lines of a failed build that say what actually broke.

    A Next.js build opens with eight lines of banner — the npm script, the
    version, the environment, "Compiled successfully" — and the real error
    comes after them. Printing the first eight printed the banner every time,
    so a prerender failure read as a blank wall and the same file was rewritten
    round after round against no information.
    """
    body = [ln for ln in lines[1:] if not _BUILD_NOISE_RE.match(ln)]
    return (body or lines[1:])[:keep]


# Quote current sources explicitly named by compiler diagnostics.
def _failing_sources(arch, errors: str) -> str:
    """Quote current sources explicitly named by compiler diagnostics."""
    seen, blocks, used = set(), [], 0
    for rel in _ERR_FILE_RE.findall(errors or ""):
        rel = rel.replace("\\", "/")
        if rel in seen:
            continue
        seen.add(rel)
        body = (getattr(arch, "files", None) or {}).get(rel)
        if not body:
            continue
        block = f"--- {rel} ---\n{body[:9000]}"
        if used + len(block) > FAIL_SRC_BUDGET and blocks:
            break
        blocks.append(block)
        used += len(block)
    if not blocks:
        return ""
    return ("\n\nThis is what those files contain right now. Rewrite each one "
            "COMPLETE, keeping everything about it that already works — the "
            "error is the only thing to change.\n\n```jsx\n"
            + "\n\n".join(blocks) + "\n```\n")


# Four rounds are always attempted.
