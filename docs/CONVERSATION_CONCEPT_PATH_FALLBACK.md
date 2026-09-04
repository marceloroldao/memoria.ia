# Conversational concept-path fallback

The production conversational integration remains deliberately conservative.

Resolution order:
1. ordinary conversation recall;
2. explicit concept/alias rewrite;
3. concept-relation path traversal only if the query exposes exactly two graph anchors and exactly one directed path orientation succeeds.

The fallback does not use a free-form intent parser, embeddings or LLM-generated anchors. A graph anchor is either an exact normalized lexical endpoint already present in active evidence, or an explicit semantic concept alias/canonical surface that resolves to a concept currently present in the relation graph.

Fail-closed cases include fewer or more than two anchors, zero paths, paths in both directions, multiple equal-confidence best paths, ambiguous concepts and missing evidence rows.

A successful path is converted back into the normal `ConversationResolveResult` from its original evidence rows so source text, provenance, confidence, namespace and memory IDs remain auditable.