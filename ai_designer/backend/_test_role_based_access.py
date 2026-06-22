"""Role-based access regression test (Part 5 wiring).

Proves the reported bug stays fixed: a multi-role app's sidebar, lib/access.js,
and dashboard are role-scoped from the planned data model, AND a disallowed
role is rejected server-side (not just hidden in the UI) on a real next build.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import data_model_planner as dmp
from app import crud_generator as cg
from app import auth_page_generator as auth
from app import app_shell_generator as shell
from app import nextgen
from _test_real_browser_visual_regression import _start_next, _stop_process

RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def main():
    print("=" * 72)
    print("ROLE-BASED ACCESS")
    print("=" * 72)

    model = dmp.plan_data_model(
        "Create an online course platform with courses, modules, lessons, instructors, students, and enrollments.")

    # 1. the planner role-scopes the transactional entity; a plain entity isn't.
    enroll = next(e for e in model["entities"] if e["name"] == "Enrollment")
    course = next(e for e in model["entities"] if e["name"] == "Course")
    rec("1. Enrollment is role-scoped to Student/Admin; Course carries no access restriction",
        enroll.get("access", {}).get("create") == ["Student", "Admin"] and not course.get("access"),
        {"roles": model["roles"]})

    # 2. lib/access.js aggregates that into roleAccess, omitting unrestricted collections.
    access_js = shell.generate_access(model)
    rec("2. lib/access.js roleAccess has enrollments:[Student,Admin], no entry for courses",
        '"enrollments"' in access_js and '"Student"' in access_js and '"Admin"' in access_js
        and '"courses"' not in access_js,
        {})

    # 3. write_app_shell's sidebar attaches roles only to the restricted collection.
    tmp = tempfile.mkdtemp()
    bundle = shell.write_app_shell(tmp, model)
    shutil.rmtree(tmp, ignore_errors=True)
    sidebar = {s["href"]: s for s in bundle["sidebar"]}
    enroll_link = sidebar.get("/manage/enrollments")
    course_link = sidebar.get("/manage/courses")
    rec("3. sidebar: /manage/enrollments carries roles, /manage/courses does not",
        bool(enroll_link) and enroll_link.get("roles") == ["Student", "Admin"]
        and bool(course_link) and "roles" not in course_link,
        {"enroll_link": enroll_link, "course_link": course_link})

    # 4. the scaffold dashboard ships role-aware code (sources from the data model,
    # not the legacy entity list, and filters by canAccess).
    dash_src_path = os.path.join("next_scaffold", "src", "app", "(app)", "dashboard", "page.jsx")
    with open(dash_src_path, encoding="utf-8") as fh:
        dash_src = fh.read()
    rec("4. scaffold dashboard is role-aware (reads @/lib/models + @/lib/access + canAccess)",
        "@/lib/models" in dash_src and "@/lib/access" in dash_src and "canAccess" in dash_src, {})

    # 5. REAL build of a generated education app via the proven Part-5 write sequence.
    out = os.path.abspath(os.path.join("output", "prj_role_access_test"))
    shutil.rmtree(out, ignore_errors=True)
    nextgen.create_project(out)
    dmp.write_data_model(out, model)
    cg.write_crud(out, model)
    auth.write_auth_pages(out, model["domain"])
    shell.write_app_shell(out, model)
    build = subprocess.run(["npm", "run", "build"], cwd=out, capture_output=True, text=True, shell=True, timeout=420)
    out_text = (build.stdout or "") + (build.stderr or "")
    built = build.returncode == 0 and ("Compiled successfully" in out_text or "Route (app)" in out_text)
    rec("5. generated education app builds (real next build)", built,
        {"returncode": build.returncode, "tail": out_text.strip().splitlines()[-4:] if not built else "ok"})

    # 6/7. LIVE enforcement: start the built app and hit the API directly - a role
    # not in Enrollment's allowed list must get 403; an allowed role must not.
    if built:
        proc, log = None, None
        try:
            proc, log = _start_next(out, 4799)
            base = "http://127.0.0.1:4799"

            def post(role):
                headers = {"Content-Type": "application/json"}
                if role:
                    headers["x-user-role"] = role
                req = urllib.request.Request(
                    base + "/api/enrollments", data=b'{"status":"active"}', method="POST", headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status
                except urllib.error.HTTPError as e:
                    return e.code

            forbidden = post("Instructor")
            allowed = post("Student")
            rec("6. disallowed role (Instructor) is rejected with 403 on POST /api/enrollments",
                forbidden == 403, {"status": forbidden})
            rec("7. allowed role (Student) is NOT rejected (may still 400 on payload, never 403)",
                allowed != 403, {"status": allowed})
        finally:
            if proc:
                _stop_process(proc)
            if log:
                log.close()
    else:
        rec("6. disallowed role (Instructor) is rejected with 403 on POST /api/enrollments", False, "build failed, skipped")
        rec("7. allowed role (Student) is NOT rejected (may still 400 on payload, never 403)", False, "build failed, skipped")

    print("=" * 72)
    ok = all(RESULTS)
    print(f"ROLE-BASED ACCESS GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
