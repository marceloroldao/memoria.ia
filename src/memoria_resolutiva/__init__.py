from .api_v90 import MemoryConfig, ResolutiveMemoryAPI
from .distributed_consensus import ConsensusDecision, KnowledgeDescriptor
from .layers import LayerSpec, layer_bits
from .store import ResolutiveMemory

__version__ = "1.0.0rc1"

__all__ = [
    "MemoryConfig",
    "ResolutiveMemoryAPI",
    "KnowledgeDescriptor",
    "ConsensusDecision",
    "LayerSpec",
    "layer_bits",
    "ResolutiveMemory",
    "__version__",
]
