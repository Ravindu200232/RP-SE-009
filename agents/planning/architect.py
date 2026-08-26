"""Public ArchitectAgent façade composed from maintainable purpose-specific mixins."""
from agents.planning.architect_core import *
from agents.planning.architect_prompts import *
from agents.planning.architect_runtime import ArchitectRuntimeMixin
from agents.planning.architect_memory import ArchitectMemoryMixin
from agents.planning.architect_writes import ArchitectWriteMixin
from agents.planning.architect_planning import ArchitectPlanningMixin
from agents.planning.architect_plan_normalize import ArchitectPlanNormalizeMixin
from agents.planning.architect_scaffold import ArchitectScaffoldMixin
from agents.planning.architect_next_scaffold import ArchitectNextScaffoldMixin
from agents.planning.architect_build import ArchitectBuildMixin
from agents.planning.architect_ledgers import ArchitectLedgerMixin
from agents.planning.architect_turns import ArchitectTurnMixin
from agents.planning.architect_symbols import ArchitectSymbolMixin
from agents.planning.architect_next_rules import ArchitectNextRulesMixin
from agents.planning.architect_boundaries import ArchitectBoundaryMixin
from agents.planning.architect_delivery import ArchitectDeliveryMixin
from agents.planning.architect_persistence import ArchitectPersistenceMixin


class ArchitectAgent(
    ArchitectRuntimeMixin, ArchitectMemoryMixin, ArchitectWriteMixin,
    ArchitectPlanningMixin, ArchitectPlanNormalizeMixin, ArchitectScaffoldMixin,
    ArchitectNextScaffoldMixin, ArchitectBuildMixin, ArchitectLedgerMixin,
    ArchitectTurnMixin, ArchitectSymbolMixin, ArchitectNextRulesMixin,
    ArchitectBoundaryMixin, ArchitectDeliveryMixin, ArchitectPersistenceMixin,
):
    """Plan, scaffold, generate, repair and persist a full application."""
    pass


# Preserve the public surface of the pre-refactor module.
__all__ = ['ArchitectAgent', 'CHARS_PER_TOKEN', 'CMD_RE', 'FENCE_RE', 'FileStreamParser', 'HISTORY_BUDGET', 'NEXT_BUILDER_SYSTEM', 'NEXT_PLANNER_SYSTEM', 'NEXT_STACK_RULES', 'OPEN_RE', 'PARTIAL_OPEN_RE', 'PROMPTS', 'SNAPSHOT_CLOSE', 'SNAPSHOT_OPEN', 'SNAPSHOT_RE', 'STUB_MARK', 'VITE_BUILDER_SYSTEM', 'VITE_PLANNER_SYSTEM', 'VITE_STACK_RULES', 'WRITE_FILE_TOOL', 'log']
