"""Auth + post-login app shell generation tests (domain-aware, distinct, protected)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import auth_page_generator as auth
from app import app_shell_generator as shell
from app import data_model_planner as dmp

RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def main():
    print("=" * 72)
    print("AUTH + APP SHELL GENERATION")
    print("=" * 72)

    login_h = auth.generate_login("healthcare")
    register_h = auth.generate_register("healthcare")

    # 1. login and register are not identical
    rec("1. Login and Register pages are not identical",
        login_h != register_h and len(login_h) > 800 and len(register_h) > 800, {})

    # 2. they have visibly different structure (login = split brand panel; register = role-selection onboarding)
    rec("2. Login and Register have different layouts (brand panel vs role-selection onboarding)",
        "lg:grid-cols-2" in login_h and "bg-primary p-10" in login_h   # login: split brand panel
        and "I am a" in register_h and "set('role'" in register_h        # register: role-selection cards
        and "lg:grid-cols-2" not in register_h,
        {})

    # 3. domain-aware copy differs across domains
    login_re = auth.generate_login("real-estate")
    register_fit = auth.generate_register("fitness")
    register_re = auth.generate_register("real-estate")
    rec("3. Auth pages are domain-aware (copy differs by domain)",
        "Secure access to care" in login_h and "Find your next home" in login_re and login_h != login_re
        and ("Personal coaching" in register_fit or "class booking" in register_fit)
        and ("Verified agents" in register_re or "saved searches" in register_re.lower())
        and register_fit != register_re,
        {})

    # 4. register has role selection + terms + extra domain field
    rec("4. Register has role selection, terms/privacy checkbox, and domain fields",
        "site.roles" in register_h and "I agree to the terms" in register_h
        and ("Phone" in register_h or "phone" in register_h),
        {})

    # 5. login has validation + forgot password + link to register
    rec("5. Login has form validation, forgot password, register link",
        "required" in login_h and "Forgot password" in login_h and "/register" in login_h
        and "Demo:" in login_h,
        {})

    # 6. post-login dashboard is domain + model aware and different from marketing
    re_model = dmp.plan_data_model("Create a real estate platform with listings, neighborhoods, agents, property tours, leads.")
    dash_re = shell.generate_dashboard(re_model)
    pos_model = dmp.plan_data_model("POS inventory ERP with products, stock, branches, invoices, suppliers")
    dash_pos = shell.generate_dashboard(pos_model)
    rec("6. Post-login dashboard is domain/role-aware and differs across apps",
        "Brokerage dashboard" in dash_re and "Operations dashboard" in dash_pos and dash_re != dash_pos
        and "Models" in dash_re and "/manage/" in dash_re,
        {})

    # 7. internal dashboard is different from public marketing (no marketing hero; entity-driven)
    rec("7. Internal dashboard differs from marketing pages (entity KPIs, not hero/marketing)",
        "data-art-component" not in dash_re and "Quick actions" in dash_re and "Relationships" in dash_re,
        {})

    # 8. route protection metadata exists + role access from the model
    access = shell.generate_access(re_model)
    rec("8. Route protection metadata exists (protectedRoutes + roleAccess + canAccess)",
        "protectedRoutes" in access and "roleAccess" in access and "canAccess" in access
        and "/dashboard" in access and "/manage" in access,
        {})

    # 9. a test-auth helper proves a real session WITHOUT disabling auth globally
    import os as _os
    files = shell.write_app_shell(_os.path.join(__import__("tempfile").mkdtemp()), re_model)["written"]
    dev = shell._DEV_AUTH
    rec("9. dev-auth helper seeds the real localStorage 'session' (no global auth disable)",
        any("dev-auth" in f for f in files)
        and "localStorage.setItem('session'" in dev and "router.replace(next)" in dev
        and "'/dashboard'" in dev and "site.auth = false" not in dev and "auth: false" not in dev,
        {})

    print("=" * 72)
    ok = all(RESULTS)
    print(f"AUTH + APP SHELL GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
