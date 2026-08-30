"""Combines the small feature-planning responsibilities used by FeaturesAgent."""
# Source: feature_contract.py — imported helper(s) come from this file.
from agents.features.feature_contract import *
# Source: request_planning.py — imported helper(s) come from this file.
from agents.features.planning.request_planning import FeatureRequestPlanningMixin
# Source: evidence_planning.py — imported helper(s) come from this file.
from agents.features.planning.evidence_planning import FeatureEvidencePlanningMixin


class FeaturesAgentPlanningMixin(FeatureRequestPlanningMixin, FeatureEvidencePlanningMixin):
    # Parses the feature-planning model response into the structured change plan expected by the feature writer.
    def _parse(self, reply: str) -> FeatureSpec:
        """Read current step in the standard shape used by the rest of the pipeline."""
        # From: agents/features/feature_contract.py
        spec = FeatureSpec(context={
            "current": "", "gap": "", "cause": "", "evidence": [],
            "verify": "", "confidence": "",
        })
        limits = {"CURRENT": 500, "GAP": 500, "CAUSE": 700,
                  "VERIFY": 700}
        # From: agents/features/feature_contract.py
        for kind, rest in protocol_lines(reply):
            if kind in limits:
                spec.context[kind.lower()] = rest[:limits[kind]]
            elif kind == "EVIDENCE":
                parts = [p.strip().strip("`") for p in rest.split("::", 1)]
                if len(parts) == 2:
                    # From: agents/features/feature_contract.py
                    path = normalise_change_path(parts[0])
                    if path in (getattr(self.arch, "files", {}) or {}):
                        spec.context["evidence"].append({"path": path, "fact": parts[1][:700]})
            elif kind == "CONFIDENCE":
                spec.context["confidence"] = rest.split()[0].lower() if rest else ""
            elif kind == "SUMMARY":
                spec.summary = rest[:200]
            elif kind == "PACKAGE" and rest:
                name = rest.split("::")[0].strip().strip("`")
                # From: agents/features/feature_contract.py
                if package_requested(name) and self.arch.PKG_NAME_RE.match(name) and \
                        name not in self.arch.NODE_BUILTINS:
                    spec.packages.append(name)
            elif kind == "ROUTE" and rest.startswith("/"):
                spec.routes.append(rest.split()[0])
            elif kind == "FILE":
                # From: agents/features/feature_contract.py
                entry = change_entry(rest)
                if entry:
                    spec.files.append(entry)

        # From: agents/features/feature_contract.py
        spec.files = unique_paths(spec.files)
        spec.packages = list(dict.fromkeys(spec.packages))
        evidence = spec.context.get("evidence") or []
        spec.context["evidence"] = list({
            (item["path"], item["fact"]): item for item in evidence
        }.values())
        return spec

