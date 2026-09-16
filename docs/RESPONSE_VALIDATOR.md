# Response Validator

Status: experimental sidecar for the topological/temporal branch.

## Purpose

`ResponseValidator` is the post-LLM epistemic boundary. It receives a previously compiled `CognitivePacket`, the model response text and structured response claims. It deterministically compares those claims against the packet and records them in `EvidenceCore` only as `LLM_GENERATED` evidence.

It does **not** write temporal state, change `CURRENT`, append factual `HISTORY`, or promote model output.

## Claim classification

Each structured claim is classified as:

- `SUPPORTED_BY_CONTEXT`: the same subject/attribute/value is present in the cognitive packet;
- `CONFLICTS_WITH_CONTEXT`: the packet contains the same subject/attribute with another value;
- `UNVERIFIED`: the packet does not contain the relevant subject/attribute slot.

These statuses describe consistency with the packet, not epistemic authority. A supported model claim is still model-generated evidence.

## Epistemic invariant

```text
CognitivePacket
      ↓
LLM response
      ↓
ResponseValidator
      ↓
LLM_GENERATED EvidenceCore candidate
      ↓
EvidenceTemporalBridge
      ↓
QUARANTINED
```

Only an independent validation path may create a trusted edge:

```text
LLM_GENERATED candidate
      ↓
EpistemicLearningGate
      ↓ USER_CONFIRMED or SENSOR_OBSERVED
new trusted EvidenceCore edge
      ↓
EvidenceTemporalBridge
      ↓
factual TemporalEvent
```

The original LLM candidate is never rewritten or reclassified.

## Structured claims, not autonomous truth extraction

Claim extraction is deliberately outside `ResponseValidator`. An adapter may use a deterministic parser or a model-specific structured-output contract, but the extracted claim still enters as `LLM_GENERATED` and cannot bypass the Learning Gate.

This avoids making the Response Validator itself another probabilistic source of factual state.

## Idempotency

`response_id` is an idempotency boundary. Re-validating the same response id fails closed. `restore_response_ids(...)` exists so persistence can restore that boundary across restart.

## Tests

`tests/test_response_validator.py` covers:

- supported model claims remain `LLM_GENERATED`;
- conflicting claims are quarantined and cannot change `CURRENT`;
- unverified claims do not create state;
- explicit user validation creates a separate trusted edge and only that edge changes temporal state;
- duplicate response ids fail closed;
- restored response ids preserve idempotency;
- invalid confidence fails before any evidence write.

## Remaining work

Before OFF.IA integration, response-validator audit/idempotency metadata should be included in the durable epistemic BDR snapshot, followed by integration tests covering compile → model response → validation → explicit learning → restart.
