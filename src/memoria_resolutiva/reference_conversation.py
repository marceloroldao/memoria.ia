"""Explicit Python reference implementation for conversation semantics.

This module is loaded only when MEMORIA_CONVERSATION_RUNTIME=python is selected.
The production default is the native runtime. The implementation remains useful
for parity fixtures and migration diagnostics, but it is not a production
semantic authority.
"""

from .product_conversation import ConversationSemanticService

__all__ = ["ConversationSemanticService"]
