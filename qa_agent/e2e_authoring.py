"""E2E authoring façade."""
from .e2e_journeys import E2EJourneyAuthoringMixin
from .e2e_grounding import E2EGroundingMixin

class E2EAuthoringMixin(E2EJourneyAuthoringMixin, E2EGroundingMixin):
    pass
