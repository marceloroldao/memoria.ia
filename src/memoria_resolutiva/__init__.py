from .api_v90 import MemoryConfig, ResolutiveMemoryAPI
from .bdr_store import BDRPolicy, BDRResolutiveMemory, native_bdr_available
from .distributed_consensus import ConsensusDecision, KnowledgeDescriptor
from .hybrid_text_router_v96 import HybridRoutingStats, HybridTextResolution, HybridTextRouterV96
from .layers import LayerSpec, layer_bits
from .semantic_router_v96 import AdaptiveRoutingStats, AdaptiveSemanticRouterV96, SemanticRouterV96, TextResolution
from .storage_backend import open_resolutive_memory, preferred_backend
from .store import ResolutiveMemory
from .structural_router_v96 import StructuralResolution, StructuralSemanticRouterV96, native_structural_available

__version__ = "0.95.0"

__all__ = [
    "MemoryConfig",
    "ResolutiveMemoryAPI",
    "KnowledgeDescriptor",
    "ConsensusDecision",
    "LayerSpec",
    "layer_bits",
    "ResolutiveMemory",
    "BDRPolicy",
    "BDRResolutiveMemory",
    "native_bdr_available",
    "open_resolutive_memory",
    "preferred_backend",
    "SemanticRouterV96",
    "AdaptiveSemanticRouterV96",
    "AdaptiveRoutingStats",
    "TextResolution",
    "StructuralSemanticRouterV96",
    "StructuralResolution",
    "native_structural_available",
    "HybridTextRouterV96",
    "HybridTextResolution",
    "HybridRoutingStats",
    "__version__",
]
