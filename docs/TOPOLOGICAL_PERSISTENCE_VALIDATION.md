# Topological persistence / restart validation

Status: **experimental SQLite sidecar validated on Linux and Windows; not part of the RC7 storage path**.

Branch: `experiment/topological-temporal-memory-v1`

Validated head: `f986570512561303bbf26e532a65250068f554cb`

Experimental PR regression: run `#243` / GitHub Actions run `34197578393`.

## Scope

`src/memoria_resolutiva/topological_persistence.py` adds a separate SQLite snapshot adapter for the experimental topology and temporal event store. It does not replace or modify EvidenceCore, BDR, mobile ABI persistence, or RC7 product storage.

The snapshot preserves:

- deterministic topological node addresses;
- node kind, canonical value and occurrence count;
- ordered composition components;
- graph edges;
- exact raw memories;
- temporal events and source metadata;
- transitions;
- internal monotonic next-sequence state;
- ingestion/new-node/reused-node counters used by experimental metrics.

## Restart acceptance results

`tests/test_topological_persistence.py` proves:

1. `CURRENT`, `HISTORY` and `STATE_DIFF` results are structurally identical before and after reload.
2. Entity/value addresses remain identical across restart.
3. Raw input text reconstructs exactly after reload.
4. Address-space metrics remain identical after reload.
5. A timeline ending at explicit sequence `31` resumes at sequence `32` after restart rather than reusing an event ID.
6. The same adapter works across car, sensor, server, robot and cat domains without domain-specific persistence branches.
7. An empty snapshot fails closed instead of silently constructing a valid-looking empty memory.

## CI result

Full experimental regression passed on both:

- `ubuntu-latest`: success;
- `windows-latest`: success.

The run also includes the existing repository regression suite, so this persistence slice did not introduce a detected baseline regression.

## Non-claims / remaining work

This validation does **not** establish SQLite as the final Memoria.ia storage engine. It only proves that the experimental state model has a complete restart representation.

Still required before convergence/freeze:

- compare persistence/storage costs against existing storage and BDR candidates;
- retrieval-time hub/selectivity measurements;
- measured retrieval latency and memory/database growth;
- experimental EvidenceCore provenance bridge;
- contamination-barrier regression when cognitive results are compiled for an LLM;
- Context Compiler integration.
