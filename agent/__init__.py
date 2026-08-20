"""lean-prover — agent that writes and iterates Lean 4 proofs."""

__version__ = "0.1.0"

# Package-root re-exports for Tau import parity (DoD §12 checklist):
# ``from agent import JSONValue, ProviderConfig`` works as in ``tau_coding``.
from .provider_config import ProviderConfig
from .types import JSONValue

__all__ = ["JSONValue", "ProviderConfig", "__version__"]
