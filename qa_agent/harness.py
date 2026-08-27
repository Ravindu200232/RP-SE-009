"""Public TestHarness façade."""
from .harness_common import *
from .harness_mocks import HarnessMockMixin
from .harness_install import HarnessInstallMixin

class TestHarness(HarnessMockMixin, HarnessInstallMixin):
    pass

__all__ = ["TestHarness", "CONFIG", "DEV_DEPS", "NPM_LOCK"]

# Preserve the public surface of the pre-refactor module.
__all__ = ['CONFIG', 'DEV_DEPS', 'HELPERS', 'NPM_LOCK', 'SETUP', 'TestHarness', 'log', 'npm_busy']
