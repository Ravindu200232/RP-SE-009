"""Build tests for generated full-stack apps.

Static checks (fast): every generated .js passes node --check; imports resolve to
a generated file or a known scaffold/npm module; no duplicate model names; every
ref points at a real collection; no invalid ObjectId usage. Then ONE real
`next build` proves the generated Next.js + Mongo app actually compiles end to end.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import data_model_planner as dmp
from app import crud_generator as cg
from app import auth_page_generator as auth
from app import app_shell_generator as shell
from app import nextgen

RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


_KNOWN = ("next/server", "next/navigation", "next/link", "react", "mongodb", "fs", "path")


def _resolves(imp, files, collections):
    if imp in _KNOWN or imp.startswith("next/") or not (imp.startswith("@/") or imp.startswith(".")):
        return True
    if imp.startswith("@/"):
        target = "src/" + imp[2:]
        return any(f == target + ".js" or f == target + ".jsx" or f.startswith(target + "/") for f in files)
    return True  # relative within-dir (rare here)


def main():
    print("=" * 72)
    print("GENERATED APP CRUD BUILD")
    print("=" * 72)

    pos = dmp.plan_data_model("POS inventory ERP with products, brands, categories, branches, suppliers, stock, GRN, invoices, invoice items, payments, customers, employees, stock movements")
    bundle = cg.generate_crud(pos)
    files = bundle["files"]

    # 1. node --check every generated .js
    tmp = tempfile.mkdtemp()
    bad, js_count = [], 0
    for rel, content in files.items():
        if not rel.endswith(".js"):
            continue
        js_count += 1
        p = os.path.join(tmp, rel.replace("/", "_"))
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((rel, (r.stderr or "")[:100]))
    shutil.rmtree(tmp, ignore_errors=True)
    rec("1. API routes + schemas + services compile (node --check)", not bad, {"checked": js_count, "bad": bad[:3]})

    # 2. imports resolve (no broken imports). The API routes import @/lib/access
    # (written by app_shell_generator) and the CRUD UI imports @/lib/api (the
    # static scaffold's session helper, copied in by nextgen.create_project) -
    # in the real pipeline all of these land in the same project dir together.
    collections = set(bundle["collections"])
    all_files = set(files) | {"src/lib/access.js", "src/lib/api.js"}
    unresolved = []
    for rel, content in files.items():
        for imp in re.findall(r"from '([^']+)'", content):
            if not _resolves(imp, all_files, collections):
                unresolved.append((rel, imp))
    rec("2. no broken imports (every @/ import resolves to a generated file)", not unresolved, {"unresolved": unresolved[:4]})

    # 3. no duplicate model names; every ref collection exists; no undefined models
    names = bundle["entity_names"]
    dup = len(names) != len(set(names))
    undefined = []
    for e in pos["entities"]:
        for r in e["relationships"]:
            tcoll = next((x["collection"] for x in pos["entities"] if x["name"] == r["target"]), None)
            if r["target"] != "User" and tcoll is None:
                undefined.append((e["name"], r["target"]))
    rec("3. no duplicate model names + no undefined model references", not dup and not undefined,
        {"dup": dup, "undefined": undefined[:4]})

    # 4. no invalid ObjectId usage (string ids only — never `new ObjectId` without import)
    objid = [rel for rel, c in files.items() if "new ObjectId" in c]
    rec("4. no invalid ObjectId usage", not objid, {"files": objid[:3]})

    # 5. REAL next build of a generated app
    out = os.path.abspath(os.path.join("output", "prj_crud_build_test"))
    shutil.rmtree(out, ignore_errors=True)
    nextgen.create_project(out)
    edu = dmp.plan_data_model("Create an online course platform with courses, modules, lessons, instructors, students, enrollments, and progress.")
    dmp.write_data_model(out, edu)
    cg.write_crud(out, edu)
    auth.write_auth_pages(out, edu["domain"])
    shell.write_app_shell(out, edu)
    build = subprocess.run(["npm", "run", "build"], cwd=out, capture_output=True, text=True, shell=True, timeout=420)
    out_text = (build.stdout or "") + (build.stderr or "")
    built = build.returncode == 0 and ("Compiled successfully" in out_text or "Route (app)" in out_text)
    rec("5. generated Next.js + Mongo app builds (real next build)", built,
        {"returncode": build.returncode, "tail": out_text.strip().splitlines()[-4:] if not built else "ok"})

    print("=" * 72)
    ok = all(RESULTS)
    print(f"GENERATED APP CRUD BUILD GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
