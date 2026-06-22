"""Element edit pipeline regression tests (Prompt 7).

Asserts: simple edits are DETERMINISTIC (no LLM); when the LLM is used it returns a
STRUCTURED plan applied deterministically; whole-file rewrites never happen for simple
edits; validate-then-atomic _commit means invalid JSX / invalid LLM output never modify
the live file; selected-element isolation; readable errors for bad ids/targets.

Most cases need NO Ollama (deterministic paths + monkeypatched plans).
Run:  python _test_element_edit.py   (exit 1 on any failure)
"""
import os, sys, re, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import editor
import app.agents as agents

PID = "prj_iv_school"
PAGE = os.path.join("output", PID, "src", "app", "(marketing)", "page.jsx")
RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def snap():
    return open(PAGE, encoding="utf-8").read()


def restore(text):
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(text)


def find(tag, after=""):
    s = snap()
    m = re.search(r"<" + tag + r"\b[^>]*className=\"([^\"]+)\"[^>]*>([^<{][^<]*)</" + tag + r">", s)
    return (m.group(1), m.group(2).strip()) if m else (None, None)


def main():
    base = snap()
    _ORIG_PLAN = editor._llm_edit_plan      # restore after monkeypatching
    _ORIG_GET_LLM = agents.get_llm
    print("=" * 66)
    print("ELEMENT EDIT REGRESSION (deterministic-first; LLM=intent->plan)")
    print("=" * 66)
    h1_cls = re.search(r"<h1 className=\"([^\"]+)\"", base).group(1)
    p_cls, p_txt = find("p")
    a_m = re.search(r"<Link\b[^>]*className=\"([^\"]+)\"[^>]*>([^<]+)</Link>", base)
    a_cls, a_txt = (a_m.group(1), a_m.group(2).strip()) if a_m else (None, None)

    try:
        # 1) text color (deterministic STYLE_TWEAK, NO LLM, not whole-file)
        restore(base)
        r = editor.edit_component(PID, "home", "make it red", tag="h1", class_name=h1_cls)
        after = snap()
        rec("change text color (STYLE_TWEAK, deterministic, not whole-file)",
            r.get("mode") == "STYLE_TWEAK" and "text-red-500" in after and "export default" in after, r.get("mode"))

        # 2) background color (deterministic)
        restore(base)
        r = editor.edit_component(PID, "home", "make the background blue", tag="h1", class_name=h1_cls)
        rec("change background color (STYLE_TWEAK)", r.get("mode") == "STYLE_TWEAK" and "bg-blue-500" in snap(), r.get("classes"))

        # 3) add Tailwind class (deterministic style_element)
        restore(base)
        r = editor.style_element(PID, [{"component_id": "home", "class_name": h1_cls}], ["uppercase", "tracking-wide"], [])
        rec("add Tailwind class (style_element class_add)", r.get("ok") and "uppercase" in snap())

        # 4) remove Tailwind class (deterministic)
        restore(base)
        first_cls = h1_cls.split()[0]
        r = editor.style_element(PID, [{"component_id": "home", "class_name": h1_cls}], [], [first_cls])
        new_h1 = re.search(r"<h1 className=\"([^\"]+)\"", snap()).group(1)
        rec("remove Tailwind class (style_element class_remove)", r.get("ok") and first_cls not in new_h1.split(), f"removed {first_cls}")

        # 5) button text via STRUCTURED PLAN -> deterministic apply (monkeypatched plan, no Ollama)
        restore(base)
        if a_cls and a_txt:
            editor._llm_edit_plan = lambda *a, **k: {"action": "text_replace", "text_replace": "Start Now Today"}
            before_n = snap().count(a_txt)
            r = editor.edit_component(PID, "home", "reword the button", tag="a", text=a_txt, class_name=a_cls)
            rec("change button text (structured plan -> PLAN_TEXT deterministic)",
                r.get("ok") and "Start Now Today" in snap() and snap().count(a_txt) == before_n - 1, r.get("mode"))
        else:
            rec("change button text", False, "no <Link> button found")

        # 6) paragraph text via deterministic exact-text path
        restore(base)
        if p_txt:
            r = editor.edit_component(PID, "home", 'change the text to "A bold new paragraph."', tag="p", text=p_txt, class_name=p_cls)
            rec("change paragraph text (deterministic text replace)",
                r.get("ok") and "A bold new paragraph." in snap(), r.get("mode"))
        else:
            rec("change paragraph text", False, "no <p> found")

        # 7) structured PLAN style_update -> deterministic PLAN_STYLE (monkeypatched)
        restore(base)
        editor._llm_edit_plan = lambda *a, **k: {"action": "style_update", "class_add": ["ring-4", "ring-indigo-500"], "class_remove": []}
        r = editor.edit_component(PID, "home", "make it look like the premium tier", tag="h1", class_name=h1_cls)
        rec("LLM intent -> structured plan -> deterministic apply (PLAN_STYLE)",
            r.get("mode") == "PLAN_STYLE" and "ring-4" in snap(), r.get("mode"))

        # 8) selected-element ISOLATION: editing the h1 must not change the button line
        restore(base)
        btn_before = re.search(r"<Link\b.*?</Link>", snap(), re.S)
        btn_before = btn_before.group(0) if btn_before else ""
        editor._llm_edit_plan = lambda *a, **k: {}   # force deterministic
        editor.edit_component(PID, "home", "make it green", tag="h1", class_name=h1_cls)
        btn_after = re.search(r"<Link\b.*?</Link>", snap(), re.S)
        btn_after = btn_after.group(0) if btn_after else ""
        rec("selected-element isolation (unrelated <Link> unchanged)", btn_before and btn_before == btn_after)

        # 8b) add section (deterministic builder stubbed) -> inserted + validates
        restore(base)
        from app import page_sections
        _orig_fs = page_sections.freeform_section
        page_sections.freeform_section = lambda prompt: '<section className="py-10"><h2>Test Band XYZ</h2></section>'
        try:
            ra = editor.add_section(PID, "home", "add a testimonials band")
        finally:
            page_sections.freeform_section = _orig_fs
        rec("add section successfully (deterministic, validated)",
            ra.get("ok") and "Test Band XYZ" in snap(), ra.get("mode"))

        # 9) invalid component id -> readable string error
        restore(base)
        rb = editor.edit_component(PID, "no-such-component-zzz", "make it red", tag="h1")
        rec("invalid component id -> readable error", (not rb.get("ok")) and isinstance(rb.get("error"), str), rb.get("error"))

        # 10) invalid target/selector (className not in file) -> readable error from style_element
        restore(base)
        rt = editor.style_element(PID, [{"component_id": "home", "class_name": "this-class-does-not-exist-xyz"}], ["text-red-500"], [])
        rec("invalid selector/target -> readable error", (not rt.get("ok")) and isinstance(rt.get("error"), str), rt.get("error"))

        # 11) invalid JSX patch auto-rolls back (validate-then-atomic _commit)
        restore(base)
        before = snap()
        bad = editor._commit(PAGE, before, before + "\n<div><<< broken jsx", "TEST", "rel")
        rec("invalid JSX patch -> auto rollback, file unchanged",
            bad is not None and not bad.get("ok") and snap() == before, "reverted")

        # 12) invalid LLM output never modifies the file (real plan fn + ALL llm calls stubbed -> garbage)
        restore(base)
        before = snap()

        class _R:  # noqa
            def __init__(s, c): s.content = c

        class _Stub:  # noqa
            def invoke(s, msgs): return _R("<<< not valid json or jsx >>>")

        editor._llm_edit_plan = _ORIG_PLAN            # real plan fn (so it hits the stubbed LLM)
        agents.get_llm = lambda *a, **k: _Stub()      # every LLM path now returns invalid content
        ri = editor.edit_component(PID, "home", "make it look fancy and bespoke and unique", tag="h1", class_name=h1_cls)
        rec("invalid LLM output -> file UNCHANGED + safe error",
            (not ri.get("ok")) and snap() == before, f"ok={ri.get('ok')}, unchanged={snap() == before}")
    finally:
        editor._llm_edit_plan = _ORIG_PLAN
        agents.get_llm = _ORIG_GET_LLM
        restore(base)

    ok = all(RESULTS)
    print("=" * 66)
    print((f"ELEMENT EDIT GREEN  ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES  ({sum(RESULTS)}/{len(RESULTS)} passed)"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
