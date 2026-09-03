# Post-v1 factual / generative memory separation

This document records the first post-RC4 evolution slice for issue #156.

## Invariant

Memoria.ia persists conversational/generative history without granting it factual authority.

Two logical memory spaces are recognized:

- `factual`: user/world evidence that may participate in current factual resolution under provenance and authority rules;
- `generative`: assistant-generated or replayed material that may be retained for conversation continuity but cannot independently create, supersede, corroborate, or resolve factual state.

A generative record may participate in factual lineage only when it explicitly points to an already factual parent. This preserves assistant echoes of known facts without allowing generated inventions to become roots of truth.

## Compatibility

The separation is additive. Existing provenance `source_type` remains authoritative for backwards compatibility. `memory_space` is derived deterministically from source type and factual lineage, so existing stores do not require destructive migration.

## Promotion boundary

Promotion of a generative candidate into factual memory is intentionally not automatic. A later operation may create a new factual record from independent evidence or explicit user confirmation while preserving lineage to the original generative candidate.

## Acceptance slice

1. generated-only memory remains persisted and inspectable;
2. generated-only memory cannot resolve a factual query;
3. user assertions remain factual after restart;
4. assistant echoes can retain lineage to a factual root;
5. factual selection ignores unpromoted generative roots;
6. the logical `memory_space` is exposed by provenance inspection without changing persisted schema.
