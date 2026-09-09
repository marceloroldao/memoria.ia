# Topological hub stress — experimental notes

Status: **experimental measurement only**. No selectivity/ranking formula is committed by this document.

Branch: `experiment/topological-temporal-memory-v1`

## Goal

Measure how high-frequency language nodes behave in the addressable topology before assigning them any ranking or routing policy.

Target words include `de`, `para`, `que`, `e`, `a`, and `o`. Rare comparison nodes include names/identifiers such as `Alt` and `XQZ91`.

## Raw measurements

`src/memoria_resolutiva/topological_metrics.py` exposes measurement helpers that report only observable graph facts:

- occurrence count;
- inbound degree;
- outbound degree;
- total degree;
- number of phrase parents;
- distinct parent-node kinds;
- total new/reused nodes across an ingestion sequence;
- average new/reused nodes per ingestion.

No score such as `1/density`, TF-IDF, probabilistic weight, embedding similarity, or hand-selected hub penalty is used at this stage.

## Stress corpus

`tests/test_topological_hub_metrics.py` builds a deterministic mixed-domain corpus containing repeated function words across sensors, servers, state routing and ordinary language, then adds rare nodes such as `Alt` and `XQZ91`.

Acceptance properties:

1. Dense function words must accumulate more occurrences than rare one-off nodes.
2. Dense function words must accumulate more distinct phrase parents than rare one-off nodes.
3. The observations must emerge from topology, not from a hardcoded list of domain entities.
4. Re-ingesting exactly the same sentence must create zero new nodes after the first ingestion.
5. Duplicate deterministic addresses must remain zero.
6. Reuse should dominate new-node creation for a repeated sentence sequence.

## Windows regression finding

The first complete Windows regression for the language-planner head produced 9 setup errors in `tests/test_native_python_concept_rewrite_parity.py` while Ubuntu passed. The native C compilation itself succeeded. The failure was caused by the test checking the extensionless output path even though GCC on Windows emitted `concept_query_rewrite_cli.exe`.

This finding is unrelated to the topological resolver runtime. A portable test-path correction was isolated in PR #279 and mirrored into the experimental branch so the mandatory Linux/Windows experiment gate can validate it.

## Decision rule

Do **not** select a hub/selectivity formula from this first corpus. The next decision requires at least:

- successful Linux + Windows full regression;
- observed hub/rare separation on more than one corpus shape;
- candidate-set measurements during retrieval/activation, not only ingestion degree;
- latency and memory-growth measurements;
- proof that suppressing hubs does not destroy useful relational paths.

Only after those measurements should density/selectivity become an activation policy rather than an observation.
