# Retrieval v2 realistic matrix

This post-v1 gate exercises deterministic Retrieval v2 against distractor and authority-conflict scenarios inspired by OFF.IA use.

It verifies that:

- a highly authoritative but off-topic source cannot outrank a lower-authority relevant source;
- organization/company names sharing tokens with countries/topics do not automatically win;
- assistant-generated echoes remain below direct user/public evidence;
- incomplete subject coverage fails closed;
- equally supported conflicting public evidence remains unresolved for the consolidation layer;
- Portuguese morphology/paraphrases keep their expected hits.

The matrix intentionally does not use embeddings, neural networks or an LLM, and does not rewrite persisted text.
