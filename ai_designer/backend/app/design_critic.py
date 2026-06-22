"""Design Critic Agent — evaluates visual quality and SRS coverage.

Runs after the build, taking QA results + design blueprint + SRS data.
Returns a structured critique with pass/fail, score, and per-page fix
instructions so graph.py can selectively regenerate only failing pages.

Auto-fails when the visual similarity checker flagged too_similar = True.
Passes automatically when no meaningful QA data is available (avoids
blocking builds on infra issues).
"""
import json
import os

_CRITIC_SYSTEM = """\
You are a senior UX design reviewer and web quality auditor.

You receive page analysis data and design information for a generated web app.
Evaluate quality and return a structured JSON report.

Return ONLY valid JSON — no explanation, no markdown — with this exact schema:
{
  "overall_passed": true,
  "score": 85,
  "issues": ["list of specific issues found across all pages"],
  "page_assessments": {
    "home": {
      "passed": true,
      "score": 90,
      "issues": ["specific issues on this page"],
      "fix_instructions": "one paragraph of targeted fix instructions"
    }
  },
  "fix_priority": ["page_name_1", "page_name_2"],
  "summary": "one-line overall summary"
}

Score 0-100. overall_passed = true when score >= 65.
Be strict but fair. Focus on:
  1. SRS section coverage (are required sections present?)
  2. Domain appropriateness (does content match the stated domain?)
  3. No placeholder / lorem ipsum text
  4. No broken imports or unresolved template markers
  5. Visual uniqueness (not cookie-cutter generic)
  6. Nav clarity, card alignment, text readability
"""


def _critic_prompt(
    qa_results: list,
    blueprint: dict,
    srs_summary: str,
    similarity: dict,
) -> str:
    lines = [
        f"App: {blueprint.get('app_name', 'Unknown')} ({blueprint.get('system_category', 'custom')})",
        f"Domain mood: {blueprint.get('domain_mood', 'professional')}",
        f"Target feel: {blueprint.get('target_feel', 'Modern')}",
        f"Layout style: {blueprint.get('layout_style', 'split-hero')}",
        f"SRS summary: {srs_summary}",
        "",
        f"Visual similarity: {similarity.get('recommendation', 'N/A')}",
        "",
        "Page QA results:",
    ]

    for r in qa_results:
        status_icon = "✓" if r.get("status") == "ok" else "✗"
        issues = "; ".join(r.get("issues", [])[:3]) or "none"
        missing = ", ".join(r.get("sections_missing", [])[:4]) or "none"
        lines.append(
            f"  {status_icon} {r['name']} ({r.get('route', '')}): "
            f"issues=[{issues}] missing_sections=[{missing}]"
        )

    lines += ["", "Evaluate and return the JSON report."]
    return "\n".join(lines)


def _auto_pass(reason: str) -> dict:
    return {
        "overall_passed": True,
        "score": 70,
        "issues": [],
        "page_assessments": {},
        "fix_priority": [],
        "summary": f"PASS ({reason})",
    }


def _auto_fail(reason: str, page: str = "all", fix: str = "") -> dict:
    return {
        "overall_passed": False,
        "score": 20,
        "issues": [reason],
        "page_assessments": {
            page: {"passed": False, "score": 20, "issues": [reason],
                   "fix_instructions": fix or reason}
        },
        "fix_priority": [page],
        "summary": f"FAIL: {reason}",
    }


def critique_design(
    qa_results: list,
    blueprint: dict,
    srs_data: dict,
    similarity_result: dict,
) -> dict:
    """Run the design critic and return a critique dict.

    graph.py uses 'overall_passed' and 'fix_priority' to decide whether to
    regenerate specific pages. 'page_assessments[page].fix_instructions' is
    passed back to llm_ui_generator.generate_page() as additional guidance.
    """
    from app.agents import get_llm, extract_json, ensure_ollama
    from langchain_core.prompts import ChatPromptTemplate

    # 1. Auto-fail on visual similarity
    if similarity_result.get("too_similar"):
        similar_to = similarity_result.get("most_similar_app", "previous app")
        return _auto_fail(
            f"Design too similar to '{similar_to}' "
            f"(score={similarity_result.get('similarity', 0):.2f})",
            page="all",
            fix="Regenerate blueprint with different navbar_style, hero_composition, and primary colour.",
        )

    # 2. Pass immediately if we have no useful QA data
    if not qa_results or all(r.get("status") == "skipped" for r in qa_results):
        return _auto_pass("no QA data available — build passed")

    # 3. Score based on static analysis alone (fast, no LLM needed when trivially good)
    total_issues = sum(len(r.get("issues", [])) for r in qa_results)
    if total_issues == 0:
        return _auto_pass("all pages passed static analysis")

    # 4. LLM critique for pages with issues
    doc = (srs_data.get("srs_document") or srs_data) if isinstance(srs_data, dict) else {}
    app_name = doc.get("app_name") or srs_data.get("app_name", blueprint.get("app_name", "App"))
    category = doc.get("system_category", "custom")
    summary = str(doc.get("app_summary", ""))[:250]
    srs_summary = f"{app_name} ({category}): {summary}"

    if not ensure_ollama():
        # Fallback: derive pass/fail from static analysis issue count
        passing = total_issues <= len(qa_results)  # <= 1 issue per page is ok
        return {
            "overall_passed": passing,
            "score": max(40, 90 - total_issues * 10),
            "issues": [r["issues"][0] for r in qa_results if r.get("issues")],
            "page_assessments": {
                r["name"]: {
                    "passed": not r.get("issues"),
                    "score": 50 if r.get("issues") else 85,
                    "issues": r.get("issues", []),
                    "fix_instructions": "; ".join(r.get("issues", [])),
                }
                for r in qa_results
            },
            "fix_priority": [r["name"] for r in qa_results if r.get("issues")],
            "summary": f"{'PASS' if passing else 'FAIL'} (LLM unavailable; static analysis only)",
        }

    fallback = _auto_pass("LLM critic fallback")
    try:
        chain = ChatPromptTemplate.from_messages([
            ("system", _CRITIC_SYSTEM),
            ("user", "{prompt}"),
        ]) | get_llm(temperature=0.2, num_predict=2048, json_mode=True)

        prompt = _critic_prompt(qa_results, blueprint, srs_summary, similarity_result)
        result = chain.invoke({"prompt": prompt})
        content = result.content if hasattr(result, "content") else str(result)
        critique = extract_json(content)

        if not isinstance(critique, dict) or "overall_passed" not in critique:
            return fallback

        # Ensure score drives overall_passed (guard against inconsistent LLM output)
        score = int(critique.get("score", 70))
        critique["overall_passed"] = score >= 65

        return critique
    except Exception:
        return fallback


def pages_needing_regeneration(critique: dict, max_pages: int = 3) -> list[dict]:
    """Return list of {name, fix_instructions} for pages that failed critique.

    Capped at max_pages so a bad critic result can't trigger a rebuild storm.
    """
    priority = critique.get("fix_priority", [])
    assessments = critique.get("page_assessments", {})
    result = []

    for name in priority[:max_pages]:
        assessment = assessments.get(name, {})
        if not assessment.get("passed", True):
            result.append({
                "name": name,
                "fix_instructions": assessment.get("fix_instructions", ""),
                "issues": assessment.get("issues", []),
            })

    return result
