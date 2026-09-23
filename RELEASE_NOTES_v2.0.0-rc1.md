# Memoria.ia v2.0.0-rc1 — Structural Memory Baseline

Release date: 2026-09-23

## Summary

`v2.0.0-rc1` freezes the current Memoria.ia V2 structural-memory baseline before the project begins the next inference-oriented development line.

Functional freeze commit:

`bd33b9cfcfa78f0e3850fb5e298cbf4cbdc360b9`

Validated companion Resolutive-DB/BDR pin used by the current native/mobile structural runtime:

`d09914b85646353d8fd004ccf99e96a94fab9eef`

No new cognitive feature is introduced by the publication commits after the functional freeze. Publication-only changes are restricted to version metadata, documentation, validation and the one-shot release workflow.

## What this candidate freezes

The frozen V2 baseline includes:

- structural text observation;
- read-only structural text resolution;
- deterministic structural token identity;
- structural association dynamics;
- recurrence-sensitive ranking;
- coexistence of competing observations instead of destructive correction;
- temporal/decay/selectivity mechanisms already integrated into the V2 structural line;
- persistence and cold reopen over the shared BDR runtime;
- preservation of source text/provenance for retrieved evidence;
- structural server endpoints;
- native/mobile ABI functions for structural observation and resolution;
- OFF.IA-facing structural integration compatibility.

The validated native/mobile ABI includes the structural symbols:

- `memoria_mobile_observe_structural_text_json`;
- `memoria_mobile_resolve_structural_text_json`.

## Empirical boundary

The V2 structural line has been exercised with cases that include:

- direct structural recall;
- repeated observations reinforcing one competing path;
- competing evidence coexisting rather than erasing history;
- unrelated queries remaining unresolved;
- cold reopen preserving structural state;
- native/mobile execution against the pinned BDR dependency.

The query path is intended to remain read-only: a query must not reinforce its own answer.

## Important limitation

This release **does not include the planned Resolutive Inference Engine**.

Specifically, V2 RC1 does not yet claim a general mechanism for:

- explicit stable addresses with evolving state;
- generic forward/reverse trajectory traversal;
- general attractor-based state resolution;
- state-current/state-previous inference independent of language rules;
- no-LLM inference across arbitrary domains;
- a complete Context Compiler;
- modality-neutral inference over bit.analyze RealitySlices.

Those are post-RC1 development goals and must earn their claims through new empirical gates.

## Why freeze here

The freeze creates a reproducible boundary between two stages of the project:

```text
V2 RC1
structural memory + persistence + recurrence + retrieval
                     |
                     | frozen baseline
                     v
post-RC1
addressed state + trajectories + attractors + resolutive inference
```

This allows future inference work to be compared against a known structural-memory baseline instead of silently changing the reference implementation.

## LLM boundary

LLM output is not treated as authoritative memory by default.

The V2 RC1 structural path is intended to provide memory/context to downstream consumers, but this candidate does not claim that the LLM has already been removed from general reasoning.

Future work will explicitly measure which reasoning responsibilities can move from the LLM into Memoria.ia itself.

## BDR boundary

Memoria.ia owns memory behavior and structural/cognitive semantics.

Resolutive-DB/BDR owns durable persistence.

The current validated native/mobile companion pin for this freeze is:

`d09914b85646353d8fd004ccf99e96a94fab9eef`

This pin is recorded for reproducibility and does not redefine the independent BDR release lineage.

## Publication lineage

Previous archived Memoria.ia release:

- `v1.0.0-rc7` — DOI `10.5281/zenodo.22654141`.

Current V2 RC1 archival identifier:

- DOI `10.5281/zenodo.22908785`.

The V2 RC1 DOI was registered after the GitHub pre-release was published; this metadata-only update does not move the release tag or change the frozen runtime.

## Claims boundary

Memoria.ia remains an experimental Resolutive Memory architecture.

This release does not claim:

- AGI;
- unrestricted general reasoning;
- biological equivalence;
- production-security certification;
- complete replacement of general-purpose LLMs;
- completed resolutive inference.

Claims are limited to the implementation, tests and reproducible structural-memory behavior present in the frozen repository lineage.
