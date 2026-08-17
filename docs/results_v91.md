# memoria.ia v0.91 — Routed persistence stabilization

## Scope

This iteration closes a major v0.95 blocker: persistence and restoration of the complete routed memory graph, including shared knowledge payloads and independent route lifecycles.

## Findings

A stabilization defect was found before persistence testing: `routed_lifecycle.py` imported a stable module name that did not exist in a clean checkout. A compatibility implementation was added as `saturating_lifecycle.py` with the candidate defaults `levels=5`, `max_strength=1.25`, and layer rate `r_L = 2^-L`.

The routed snapshot format now stores:

- one payload per knowledge node;
- all trajectory-to-knowledge mappings;
- modalities and provenance;
- per-route lifecycle time;
- per-layer strength, active state, historical activation state, activation count and deactivation count;
- format version and CRC32 checksum.

Snapshots are written through a temporary file, `fsync`, and atomic replacement.

## Regression probe

A controlled two-route case was exercised:

- private visual route and collective language route pointed to the same `cup` knowledge payload;
- both routes were reinforced to active depth 4;
- only the visual route received sustained contradiction and deactivated to active depth -1 while retaining historical depth 4;
- the collective route remained active at depth 4;
- after encode/decode round-trip, those states were preserved exactly;
- the restored graph still contained one knowledge node and two routes.

This confirms the intended invariant:

`shared payload + independent route confidence` survives persistence.

## Explicit limitation

The v0.91 format currently requires JSON-serializable payloads and trajectory nodes. Unsupported Python objects are rejected explicitly rather than silently converted. This constraint must be documented or generalized before v1.0.

## Status

The routed-persistence blocker is provisionally closed. The next stabilization work should focus on full regression coverage, API compatibility, serialization limits, scaling after persistence, and release-candidate documentation.
