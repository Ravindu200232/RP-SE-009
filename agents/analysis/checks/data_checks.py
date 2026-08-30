"""Data Checks.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
from agents.analysis.analysis_shared import (
    BCRYPT_LITERAL_RE,
    Finding,
    _strip_noncode,
    re,
)

class DataChecksMixin:
    """Keep data checks behavior together."""

    # Inspect the generated source for data ui problems and return evidence only when a real issue is found.
    def _data_ui_invariants(self):
        """Prepare the data ui invariants value or state used by this focused pipeline step."""
        out = []
        # From: agents/analysis/checks/scan_state.py
        for rel, body in sorted(self.code_files().items()):
            if "seed" in rel.lower() and "ensureSeeded" in body:
                # From: agents/analysis/analysis_shared.py
                if re.search(r"countDocuments\s*\([^)]*\)[\s\S]{0,100}(?:===?|>|!==?)\s*0", body) and not re.search(r"\$setOnInsert|upsert\s*:\s*true|bulkWrite", body): out.append(Finding("blocker", "STALE_SEED_GUARD", "seeding stops whenever the collection is non-empty, so one signup can permanently prevent demo identities", rel, "upsert each seeded row by stable identity with $setOnInsert"))
                # From: agents/analysis/analysis_shared.py
                if "insertMany" in body and not re.search(r"ordered\s*:\s*false|code\s*!==?\s*11000|upsert\s*:\s*true|let\s+\w*[Ss]eed\w*\s*=\s*null", body): out.append(Finding("blocker", "SEED_RACE", "ensureSeeded can insert twice concurrently and fail with E11000", rel, "cache a seed promise and use idempotent upserts"))
                # From: agents/analysis/analysis_shared.py
                if re.search(r"createIndex\s*\([^)]*?unique\s*:\s*true", body, re.S): out.append(Finding("blocker", "UNIQUE_INDEX_IN_SEED", "the seed creates a unique index against data that survives regeneration", rel, "move migration out of request-time seeding or make it backward-compatible"))
            if rel.startswith(("app/", "components/")):
                # From: agents/analysis/analysis_shared.py
                if re.search(r"href\s*=\s*['\"]#['\"]|onClick\s*=\s*\{\s*\(?[^=]*=>\s*\{\s*\}\s*\}", body, re.S): out.append(Finding("major", "INERT_CONTROL", "renders a visible control with no reachable action", rel, "wire the accepted capability or remove the control", [rel]))
                # From: agents/analysis/analysis_shared.py
                if re.search(r"\b(?:window\.)?alert\s*\(", body): out.append(Finding("blocker", "NATIVE_ALERT", "uses a blocking browser alert instead of the app's required React toast UI", rel, "replace it with toast.success/toast.error through the shared ToastHost", [rel]))
                # From: agents/analysis/analysis_shared.py
                mutates = self._AUTH_CALL_RE.search(body) or re.search(r"method\s*:\s*['\"](?:POST|PUT|PATCH|DELETE)['\"]", body, re.I)
                # From: agents/analysis/analysis_shared.py
                if mutates and not re.search(r"\btoast\.(?:success|error)\s*\(", body): out.append(Finding("blocker", "MUTATION_FEEDBACK_MISSING", "auth/mutation UI does not use the required React toast success/error feedback", rel, "use toast.success after the real result and toast.error on failure", [rel]))
                # From: agents/analysis/analysis_shared.py
                if re.search(r"if\s*\(\s*!\w+\.ok\s*\)\s*\{\s*console\.(?:error|warn)\s*\(", body, re.S): out.append(Finding("blocker", "SILENT_MUTATION_FAILURE", "a failed persisted request is only logged, so the UI can still report success", rel, "throw/return on the failed response, show toast.error, and never run the success path", [rel]))
                # From: agents/analysis/analysis_shared.py
                if self._AUTH_CALL_RE.search(body) and re.search(r"router\.(?:push|replace)\s*\(", _strip_noncode(body)): out.append(Finding("blocker", "AUTH_SOFT_NAV", "successful auth uses client-router navigation, which can leave the auth page/navbar on stale session state", rel, "after success toast, resolve the planned role home and use window.location.assign(target)", [rel]))
                # From: agents/analysis/analysis_shared.py
                if not self._CLIENT_RE.search(body) and self._EVENT_RE.search(body): out.append(Finding("blocker", "SERVER_CLIENT_EVENT_HANDLER", "a Server Component renders an event handler React cannot serialize", rel, "move the interactive subtree into a Client Component", [rel]))
                # From: agents/analysis/analysis_shared.py
                if re.search(r"<form\b[^>]*\bmethod\s*=\s*(?:\{\s*)?['\"](?:put|patch|delete)['\"]", body, re.I | re.S): out.append(Finding("blocker", "UNSUPPORTED_FORM_METHOD", "an HTML form declares PUT/PATCH/DELETE, but browsers submit only GET/POST", rel, "use client fetch or a server action", [rel]))
            # From: agents/analysis/analysis_shared.py
            for value in BCRYPT_LITERAL_RE.findall(body):
                # From: agents/analysis/analysis_shared.py
                if len(value) != 60: out.append(Finding("blocker", "FAKE_HASH", "contains a malformed bcrypt literal, so every password comparison fails", rel, "create credentials through the configured auth provider")); break
            # From: agents/analysis/analysis_shared.py
            if "seed" in rel.lower() and "passwordHash" in body and not re.search(r"hashSync|\bhash\(", body): out.append(Finding("blocker", "UNHASHED_SEED", "writes passwordHash without hashing", rel, "use the configured provider or hash the real password"))
        # From: agents/analysis/checks/auth_checks.py
        out += self._unguarded_client_pages()
        # From: agents/analysis/checks/auth_checks.py
        out += self._auth_result_misread()
        # From: agents/analysis/checks/scan_state.py
        files = self.code_files(); layout = files.get("app/layout.jsx", "")
        # From: agents/analysis/analysis_shared.py
        if any(re.search(r"\btoast\.(?:success|error)\s*\(", b) for b in files.values()) and not re.search(r"<\s*(?:Toaster|ToastHost)\b", layout): out.append(Finding("blocker", "TOAST_HOST_MISSING", "toast calls exist but the root layout mounts no Toaster/ToastHost, so users see no feedback", "app/layout.jsx", "mount the shared ToastHost/Toaster once in app/layout.jsx", ["app/layout.jsx"]))
        return out

    # Inspect the generated source for data contract problems and return evidence only when a real issue is found.
    def _data_contract_findings(self):
        """Prepare the data contract findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        plan, files, out = getattr(self.arch, "plan", None) or {}, self.code_files(), []
        models = {str(m.get("collection") or ""): m for m in plan.get("data_model") or [] if m.get("collection")}
        allowed = set(models) | {"user", "account", "session", "verification"}
        refs = {name: [] for name in models}
        # From: agents/analysis/analysis_shared.py
        rx = re.compile(r"(?:getCollection|\.collection)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
        for rel, body in files.items():
            for name in rx.findall(body):
                if name not in allowed:
                    # From: agents/analysis/analysis_shared.py
                    out.append(Finding("blocker", "UNKNOWN_COLLECTION", f"source uses collection '{name}', but the approved data model does not define it", rel, "use the exact planned collection name everywhere", [rel]))
                elif name in refs and "seed" not in rel.lower():
                    refs[name].append(rel)
        for name, owners in refs.items():
            if not owners:
                # From: agents/analysis/analysis_shared.py
                out.append(Finding("blocker", "ENTITY_FLOW_MISSING", f"planned collection '{name}' is only seeded or never used by application source", "lib/seed.js", "connect this entity through a real page/API read or write in its planned user journey"))
        return out

    # Inspect the generated source for planned data problems and return evidence only when a real issue is found.
    def planned_data_findings(self):
        """Prepare the planned data findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/code_checks.py
        return self._semantic_requirement(
            "planned collection reads, writes, API transport and persistence",
            "MISSING_PLANNED_DATA")

    # Check the generated source for seed volume and return the small result used by the Analyzer.
    def seed_volume(self):
        """Prepare the seed volume value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        if "Sample data: requested" in self.plan_text(): return []
        out = []
        # From: agents/analysis/checks/scan_state.py
        for path, body in self.code_files().items():
            if "seed" not in path.lower(): continue
            # From: agents/analysis/analysis_shared.py
            counts = [int(a or b) for a, b in re.findall(
                r"Array\.from\s*\(\s*\{\s*length\s*:\s*(\d+)|for\s*\(\s*(?:let|var)\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*(\d+)", body)]
            # From: agents/analysis/analysis_shared.py
            if counts and max(counts) >= 5: out.append(Finding(
                "minor", "SEED_VOLUME", f"seeds {max(counts)} generated demo rows without a sample-data requirement",
                path, "keep only the few rows needed to prove the screens"))
        return out

    # Inspect the generated source for mongo id type problems and return evidence only when a real issue is found.
    def mongo_id_type_findings(self):
        """Prepare the mongo id type findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/code_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._cross_file_invariants(), "MONGO_ID_TYPE")

    # Inspect the generated source for leaks password hash problems and return evidence only when a real issue is
    # found.
    def leaks_password_hash(self):
        """Prepare the leaks password hash value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/code_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._cross_file_invariants(), "HASH_LEAK")
