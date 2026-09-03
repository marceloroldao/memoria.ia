# Factual and Generative Memory Spaces

Status: post-v1 experiment, issue #156.

Memoria.ia separates persisted information into two logical epistemic spaces without requiring a destructive persistence migration.

## Factual space

Records in the factual space may participate in current factual state when provenance, supersession, conflict and authority rules allow it.

Typical source classes:

- `direct_observation`
- `user_correction`
- `user_assertion`
- `external_import`
- `derived_relation` when its complete factual lineage remains active

## Generative space

Records in the generative space are preserved for conversational continuity, history, alternatives and audit, but they cannot independently establish factual state.

Current source classes:

- `assistant_generated`
- `retrieved_replay`

A generative record may point to factual parents. In that case it may be used as an echo/history object whose active ultimate source remains factual, but its direct memory space remains `generative`.

## Promotion bridge

Promotion never converts a generative record in place.

A candidate becomes factual only by creating a new `derived_relation` memory event backed by independent active factual validation, such as a user assertion/correction or accepted external evidence. The candidate remains preserved in generative space and is referenced through separate promotion-audit metadata.

The promoted record therefore does not become a new factual root. Its factual authority remains anchored in the validating evidence.

This prevents recursive self-confirmation while preserving complete lineage.

## Inspection contract

The post-v1 inspection view exposes:

- direct `source_type`;
- direct `memory_space` (`factual` or `generative`);
- whether an active factual lineage exists;
- active ultimate factual source when one exists.

The public conversation provenance also exposes `ultimate_memory_space` so clients can distinguish the direct record from the epistemic root without removing or renaming existing fields.

This distinction matters for assistant echoes: the direct record is generative, while the lineage it reflects may still terminate at a valid user/world fact.

## Native/mobile parity

The native contract mirrors Python classification. Native lineage traversal may pass through `assistant_generated` and `retrieved_replay` to reach factual parents, but `active_lineage_root()` rejects a terminal root whose direct memory space is generative.

The host parity vectors include an assistant-only invention and require both Python and native/mobile to return `UNRESOLVED`, including after persistence/reopen.

## Invariants

1. Generated output alone cannot create authoritative factual state.
2. Generated repetition cannot increase factual authority.
3. Generated output cannot supersede a user/world fact by itself.
4. Generated history remains persistable and inspectable.
5. Promotion requires independent factual validation and creates a new memory record.
6. Promotion preserves the original candidate instead of rewriting history.
7. A promoted record is derived; its factual root remains the independent validator.
8. Python and native/mobile apply the same terminal-root rule.
9. The public API exposes direct and ultimate memory spaces additively.
10. Existing RC4 persistence remains readable; the logical discriminator is derived from existing provenance metadata during this experiment.
