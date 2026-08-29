"""Explicit Python reference implementation for episodic semantics.

This module is loaded only when MEMORIA_EPISODIC_RUNTIME=python is selected.
The production default is the native runtime. The implementation remains useful
for parity fixtures and migration diagnostics, but it is not a production
semantic authority.
"""

from .product_episodic import ProductEpisodicService

__all__ = ["ProductEpisodicService"]
