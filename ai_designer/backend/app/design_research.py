"""Optional abstract design research.

This module intentionally returns design DNA only. It never returns source
copy, images, logos, colors from a live site, or website layouts. Network/API
providers are optional; if anything is missing or slow, callers fall back to the
curated inspiration library.
"""
from __future__ import annotations

import os
import json
import re
import time
import urllib.parse
import urllib.request


def _truthy(name: str, default: str = "false") -> bool:
    return (os.getenv(name) or default).strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _local_dna(prompt: str) -> dict:
    text = (prompt or "").lower()
    if any(k in text for k in ("ai", "developer", "api", "code", "agent")):
        return {
            "hero_patterns": ["dashboard proof", "code workspace"],
            "navigation_patterns": ["utility bar", "floating nav"],
            "section_patterns": ["portal preview", "stats band", "timeline"],
            "card_patterns": ["glass", "bordered"],
            "typography_style": "technical sans",
            "spacing_style": "data-heavy",
            "color_palette_family": "developer dark",
            "image_strategy": "dashboard mockup",
            "CTA_patterns": ["hero-split", "nav-cta"],
            "footer_patterns": ["developer footer"],
        }
    if any(k in text for k in ("vehicle", "car", "shop", "store", "product", "sales")):
        return {
            "hero_patterns": ["immersive brand image", "product spotlight"],
            "navigation_patterns": ["action topnav", "centered topnav"],
            "section_patterns": ["gallery", "feature cards", "split image/text"],
            "card_patterns": ["image-card", "shadow"],
            "typography_style": "premium sans",
            "spacing_style": "image-heavy",
            "color_palette_family": "premium product",
            "image_strategy": "gallery",
            "CTA_patterns": ["hero-primary", "nav-cta"],
            "footer_patterns": ["commerce footer"],
        }
    if any(k in text for k in ("finance", "bank", "loan", "invoice", "payment", "wallet")):
        return {
            "hero_patterns": ["metrics first", "dashboard proof"],
            "navigation_patterns": ["utility bar", "action topnav"],
            "section_patterns": ["stats band", "portal preview", "FAQ"],
            "card_patterns": ["stat-card", "bordered"],
            "typography_style": "precise sans",
            "spacing_style": "data-heavy",
            "color_palette_family": "fintech trust",
            "image_strategy": "dashboard mockup",
            "CTA_patterns": ["after-stats", "hero-primary"],
            "footer_patterns": ["trust footer"],
        }
    return {
        "hero_patterns": ["split product story", "dashboard proof"],
        "navigation_patterns": ["action topnav", "centered topnav"],
        "section_patterns": ["feature cards", "portal preview", "FAQ"],
        "card_patterns": ["bordered", "shadow"],
        "typography_style": "precise sans",
        "spacing_style": "spacious",
        "color_palette_family": "calm trust",
        "image_strategy": "dashboard mockup",
        "CTA_patterns": ["hero-primary", "floating"],
        "footer_patterns": ["product footer"],
    }


def _get_json(req, timeout: int) -> dict:
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read(500_000).decode("utf-8", errors="ignore"))


def _research_queries(prompt: str) -> list[str]:
    clean = re.sub(r"\s+", " ", str(prompt or "").strip())
    if not clean:
        clean = "professional web app"
    return [
        clean + " website design examples",
        clean + " landing page interface inspiration",
    ]


def _safe_result(title: str = "", snippet: str = "", url: str = "") -> dict:
    return {
        "title": str(title or "")[:160],
        "snippet": str(snippet or "")[:260],
        "url": str(url or "")[:300],
    }


def _search_results(prompt: str, provider: str, api_key: str, max_results: int, timeout: int, google_cse_id: str = "") -> dict:
    queries = _research_queries(prompt)
    results: list[dict] = []
    if provider == "tavily":
        for query in queries:
            body = json.dumps({
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            data = _get_json(req, timeout)
            results.extend(
                _safe_result(r.get("title", ""), r.get("content", ""), r.get("url", ""))
                for r in data.get("results", [])
            )
            if len(results) >= max_results:
                break
        return {"queries": queries, "results": results[:max_results]}
    if provider == "serpapi":
        for query in queries:
            qs = urllib.parse.urlencode({"engine": "google", "q": query, "api_key": api_key, "num": max_results})
            req = urllib.request.Request("https://serpapi.com/search.json?" + qs)
            data = _get_json(req, timeout)
            results.extend(
                _safe_result(r.get("title", ""), r.get("snippet", ""), r.get("link", ""))
                for r in data.get("organic_results", [])
            )
            if len(results) >= max_results:
                break
        return {"queries": queries, "results": results[:max_results]}
    if provider == "google":
        for query in queries:
            qs = urllib.parse.urlencode({
                "key": api_key,
                "cx": google_cse_id,
                "q": query,
                "num": min(max_results, 10),
            })
            req = urllib.request.Request(
                "https://www.googleapis.com/customsearch/v1?" + qs,
                headers={"Accept": "application/json"},
            )
            data = _get_json(req, timeout)
            results.extend(
                _safe_result(r.get("title", ""), r.get("snippet", ""), r.get("link", ""))
                for r in data.get("items", [])
            )
            if len(results) >= max_results:
                break
        return {"queries": queries, "results": results[:max_results]}
    if provider == "bing":
        for query in queries:
            qs = urllib.parse.urlencode({"q": query, "count": max_results})
            req = urllib.request.Request(
                "https://api.bing.microsoft.com/v7.0/search?" + qs,
                headers={"Ocp-Apim-Subscription-Key": api_key},
            )
            data = _get_json(req, timeout)
            results.extend(
                _safe_result(r.get("name", ""), r.get("snippet", ""), r.get("url", ""))
                for r in (data.get("webPages", {}) or {}).get("value", [])
            )
            if len(results) >= max_results:
                break
        return {"queries": queries, "results": results[:max_results]}
    return {"queries": queries, "results": []}


def _abstract_from_results(prompt: str, results: list[dict]) -> dict:
    blob = " ".join((r.get("title", "") + " " + r.get("snippet", ""))[:220] for r in results)
    # Reduce provider output to our own closed vocabulary. No titles, snippets,
    # URLs, assets, colors, or brand content are returned to generation.
    return _local_dna(prompt + " " + blob)


def fetch_online_design_dna(prompt: str) -> dict:
    """Return abstract online design DNA or an ok=False result.

    Provider API integrations can be expanded here later. For now, `local`
    behaves as a deterministic online-research stand-in for tests and offline
    development; named external providers require an API key and otherwise fail
    cleanly.
    """
    if not _truthy("DESIGN_RESEARCH_ENABLED"):
        return {
            "ok": False,
            "enabled": False,
            "mode": os.getenv("DESIGN_INSPIRATION_MODE", "curated"),
            "provider": os.getenv("DESIGN_SEARCH_PROVIDER", "local"),
            "reason": "disabled",
            "queries": [],
            "result_count": 0,
            "references": [],
        }

    mode = (os.getenv("DESIGN_INSPIRATION_MODE") or "curated").strip().lower()
    provider = (os.getenv("DESIGN_SEARCH_PROVIDER") or "local").strip().lower()
    timeout = max(1, _int_env("DESIGN_RESEARCH_TIMEOUT_SECONDS", 20))
    max_results = max(1, _int_env("DESIGN_RESEARCH_MAX_RESULTS", 5))
    started = time.time()
    queries = _research_queries(prompt)

    api_key = os.getenv("DESIGN_SEARCH_API_KEY", "")
    if provider != "local" and not api_key:
        return {"ok": False, "enabled": True, "mode": mode, "reason": "missing api key", "provider": provider, "queries": queries, "result_count": 0, "references": []}
    google_cse_id = os.getenv("DESIGN_GOOGLE_CSE_ID", "").strip()
    if provider == "google" and not google_cse_id:
        return {
            "ok": False,
            "enabled": True,
            "mode": mode,
            "reason": "Google search disabled: missing DESIGN_GOOGLE_CSE_ID",
            "provider": provider,
            "queries": queries,
            "result_count": 0,
            "references": [],
        }
    if provider not in {"local", "google", "bing", "serpapi", "tavily"}:
        return {"ok": False, "enabled": True, "mode": mode, "reason": "unsupported provider", "provider": provider, "queries": queries, "result_count": 0, "references": []}
    if time.time() - started > timeout:
        return {"ok": False, "enabled": True, "mode": mode, "reason": "timeout", "provider": provider, "queries": queries, "result_count": 0, "references": []}

    try:
        search = {"queries": queries, "results": []}
        if provider != "local":
            search = _search_results(prompt, provider, api_key, max_results, timeout, google_cse_id=google_cse_id)
        results = list(search.get("results") or [])[:max_results]
        dna = _abstract_from_results(prompt, results) if results else _local_dna(prompt)
    except Exception as exc:
        return {"ok": False, "enabled": True, "mode": mode, "reason": str(exc)[:120], "provider": provider, "queries": queries, "result_count": 0, "references": []}
    return {
        "ok": True,
        "enabled": True,
        "mode": mode,
        "provider": provider,
        "max_results": max_results,
        "queries": list(search.get("queries") or queries),
        "result_count": len(results),
        "references": [{"title": r.get("title", ""), "url": r.get("url", "")} for r in results],
        "design_dna": dna,
        "notes": re.sub(r"[^a-z0-9 -]", "", (prompt or "").lower())[:120],
        "elapsed_ms": int((time.time() - started) * 1000),
    }
