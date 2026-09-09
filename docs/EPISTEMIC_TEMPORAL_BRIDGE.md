# EvidenceCore -> temporal memory epistemic bridge

Status: experimental, additive, outside the frozen RC7 runtime path.

## Goal

Project preserved EvidenceCore observations into the topological temporal store without allowing every source to mutate factual CURRENT/HISTORY state.

The EvidenceCore remains the source-backed evidence graph. The temporal store remains the state/history engine. The bridge is the explicit epistemic policy boundary between them.

## Source classes

The bridge classifies evidence into:

- `USER_CONFIRMED`
- `SENSOR_OBSERVED`
- `SYSTEM_INFERRED`
- `LLM_GENERATED`
- `EXTERNAL_PUBLIC`
- `DERIVED`

Unknown provenance fails closed as `SYSTEM_INFERRED`.

## Default promotion policy

Only these sources mutate temporal factual state automatically:

- `USER_CONFIRMED`
- `SENSOR_OBSERVED`

These remain evidence/audit candidates by default and do not alter `CURRENT`, `PREVIOUS_STATE` or `HISTORY`:

- `SYSTEM_INFERRED`
- `EXTERNAL_PUBLIC`
- `DERIVED`
- `LLM_GENERATED`

`LLM_GENERATED` has an additional hard barrier: even a custom promotable-source set cannot make it auto-promotable. A future explicit Learning Gate must create or promote trusted evidence after validation rather than treating model output itself as factual observation.

## Projection behavior

Every EvidenceCore edge produces an `EvidenceProjection` recording:

- evidence id;
- epistemic class;
- promoted/quarantined decision;
- decision reason;
- provenance;
- origin;
- confidence;
- optional created temporal event.

Promoted evidence:

1. preserves the original `source_text` as exact raw memory;
2. creates/reuses subject, predicate/attribute and value addresses;
3. appends one temporal event;
4. may create a state transition when the value changes.

Quarantined evidence remains available through the EvidenceCore and the projection result but creates no temporal event.

## Contamination barrier acceptance

Required regression:

1. user says `minha camisa.cor = azul` -> temporal CURRENT = azul;
2. LLM later outputs `minha camisa.cor = vermelha` with high confidence;
3. the LLM edge remains evidence but is quarantined;
4. temporal CURRENT remains azul;
5. temporal HISTORY contains only promoted factual observations.

The same rule applies regardless of model confidence.

## Non-claims / next work

This bridge does not yet persist the full projection audit metadata in BDR. Current temporal events preserve their epistemic source and raw-memory provenance, while `EvidenceProjection` carries evidence id, origin, provenance and confidence during projection.

Before convergence we still need:

- durable epistemic audit records in the BDR mapping;
- explicit Learning Gate/Response Validator contract;
- tests proving accepted/rejected learning decisions across restart;
- Context Compiler filtering that can use quarantined evidence for reasoning without silently converting it into factual memory.
