# Memoria.ia Core Autonomous Memory v0.97 — Experimental Contract

## Motivation

The first native Windows product test exposed a core limitation: the stable v0.95 API requires the caller to supply the trajectory for both `remember()` and `recall()`. The v0.96 semantic experiments can rank among pre-registered concepts, but they do not yet provide an autonomous conversational-memory contract.

The v0.97 experiment therefore moves memory selection responsibility into the core.

## Goal

A caller should be able to provide natural-language observations and later natural-language queries without manually supplying memory keys or trajectories.

The core should:

1. derive a deterministic local address/profile from an observation;
2. decide conservatively whether to create, reinforce, update, separate, or abstain;
3. retrieve a small ranked set of relevant memories for a later query;
4. expose confidence, margin, abstention and latency metrics;
5. operate without a neural network or external LLM in the routing path;
6. preserve exact-key O(1) lookup for already-resolved addresses;
7. persist all state required to reproduce the same routing decision after restart.

## Non-goals

- general natural-language understanding;
- replacing an LLM;
- forcing a match for ambiguous queries;
- claiming O(1) for semantic discovery;
- modifying the validated v0.95 public facade in place;
- coupling the core to the web UI, OpenAI, Gemini or MA2A.

## Proposed core boundary

The experiment will introduce an autonomous layer above the validated routed lifecycle memory.

Conceptual API:

```python
memory.observe(text, payload=None, provenance="...")
result = memory.query(text, top_k=3)
```

`observe()` must return a decision record describing what the core did. `query()` must return ranked candidates plus an explicit unresolved/abstained result when evidence is insufficient.

## Addressing stages

The routing pipeline should remain deterministic and inspectable:

1. normalization;
2. token/feature extraction;
3. local contextual profile construction;
4. candidate generation;
5. relation-aware scoring;
6. score + runner-up-margin gate;
7. exact trajectory/address resolution for accepted candidates;
8. lifecycle reinforcement/contradiction update.

No opaque embedding call is permitted in the v0.97 baseline.

## Conservative semantics

The system must distinguish at least:

- `same`: sufficiently strong evidence for an existing memory;
- `related`: contextually related but not safe to merge;
- `conflict`: contradictory evidence about an established concept;
- `distinct`: new memory candidate;
- `unresolved`: insufficient evidence; no destructive action.

Ambiguity must prefer `unresolved` over a false positive.

## Required metrics

Per observation/query:

- candidate_count;
- selected_count;
- best_score;
- runner_up_score;
- margin;
- decision;
- exact_lookup_used;
- semantic_discovery_latency_ms;
- exact_lookup_latency_ms;
- memories_created;
- memories_reinforced;
- memories_updated;
- abstentions.

These metrics are core metrics. The product layer may aggregate them but must not invent them.

## Acceptance tests

The first promotion gate must include:

1. **Exact paraphrase retrieval** — a stored fact is recovered from a paraphrased query.
2. **Distractor resistance** — unrelated memories do not become false positives.
3. **Polysemy separation** — the same token in different contexts remains separable.
4. **Conflict handling** — contradictory observations do not silently overwrite established knowledge.
5. **Open-set abstention** — unseen queries may return unresolved.
6. **Restart determinism** — observation/query decisions are reproduced after save/load.
7. **Scaling** — semantic discovery cost is measured separately from exact lookup cost.
8. **No-neural baseline** — all acceptance tests run with no external model dependency.
9. **Product scenario** — store `Meu carro de teste se chama Orion e a cor dele é verde.` and later retrieve the relevant memory from `Qual é o nome e a cor do meu carro de teste?` without caller-supplied memory keys.

## Promotion rule

Do not integrate this experiment into the product chat merely because a demonstration works. Promotion requires a reproducible holdout protocol with false-positive, abstention, conflict and restart metrics. The stable exact-key path remains available as a fallback throughout the experiment.
