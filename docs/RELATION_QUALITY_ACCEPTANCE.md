# Relation quality acceptance policy

This document accompanies issue #135 and the post-v1 relation quality slice.

A relation is eligible for durable consolidation only when both endpoints are stable enough to stand without unresolved conversational context.

Context-dependent pronouns, deixis, and interrogative terms are rejected as relation endpoints. The first protected set includes Portuguese forms such as `isso`, `isto`, `aquilo`, `ele`, `ela`, `aqui`, `quem`, `onde`, `como`, and `quando`.

The change is intentionally conservative and does not introduce embeddings, neural classification, or probabilistic language models. Explicit compact copular statements retain the existing confidence contract.
