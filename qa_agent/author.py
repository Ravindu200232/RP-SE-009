"""Public UnitTestAuthor façade."""
from .author_common import *
from .author_write import UnitAuthorWriteMixin
from .author_repair import UnitAuthorRepairMixin
from .author_guards import UnitAuthorGuardMixin

class UnitTestAuthor(UnitAuthorWriteMixin, UnitAuthorRepairMixin, UnitAuthorGuardMixin):
    pass

__all__ = ["UnitTestAuthor"]

# Preserve the public surface of the pre-refactor module.
__all__ = ['CALL_BUDGET', 'MAX_READS', 'MAX_VERIFY_ROUNDS', 'QA_FIX_WORKERS', 'SETTLE_MAX_S', 'SYSTEM', 'TEMPERATURE', 'UnitTestAuthor', 'log']
