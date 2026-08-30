"""Public planning agent composed from small planning stages."""
from __future__ import annotations

# Source: request_planner.py — creates the first plan from the user request.
from agents.planner.planning.request_planner import RequestPlannerMixin
# Source: gap_closer.py — detects missing requirements and closes gaps.
from agents.planner.planning.gap_closer import GapCloserMixin
# Source: route_normalizer.py — cleans the site map and route contracts.
from agents.planner.planning.route_normalizer import RouteNormalizerMixin
# Source: data_access_normalizer.py — cleans data, auth, API and capability contracts.
from agents.planner.planning.data_access_normalizer import DataAccessNormalizerMixin
# Source: journey_file_normalizer.py — cleans journeys, files, tasks and dependencies.
from agents.planner.planning.journey_file_normalizer import JourneyFileNormalizerMixin
# Source: documents/plan_md_maker.py — writes plan.md.
from agents.planner.planning.documents.plan_md_maker import PlanMarkdownMixin
# Source: documents/design_md_maker.py — writes design.md.
from agents.planner.planning.documents.design_md_maker import DesignMarkdownMixin
# Source: documents/architecture_md_maker.py — writes architecture.md.
from agents.planner.planning.documents.architecture_md_maker import ArchitectureMarkdownMixin
# Source: planning_helpers.py — shared plan result and public helpers.
from agents.planner.planning.planning_helpers import PlanBundle, PROMPT_PATH
from agents.planner.planning.sitemap_maker import render_sitemap_xml


class PlannerAgent(RequestPlannerMixin, GapCloserMixin, RouteNormalizerMixin,
                   DataAccessNormalizerMixin, JourneyFileNormalizerMixin,
                   PlanMarkdownMixin, DesignMarkdownMixin, ArchitectureMarkdownMixin):
    """Create one normalized implementation plan for every later stage."""


__all__ = ["PlanBundle", "PlannerAgent", "PROMPT_PATH", "render_sitemap_xml"]
