# Post-v1 native relation resolve activation

This slice activates the already-validated native concept-relation traversal behind the existing `memoria_mobile_resolve_context_json` boundary.

## Precedence

1. Existing temporal / trajectory / semantic / concept-rewrite resolution runs first.
2. Only a legacy `UNRESOLVED` result is eligible for relation traversal.
3. Relation traversal requires explicit `relation_source` and `relation_target` anchors plus a non-empty `concept_namespace`.
4. A relation HIT is returned only when exactly one bounded path is justified.
5. Ambiguity, missing anchors, namespace mismatch, insufficient confidence, or multiple returned paths remain `UNRESOLVED`.

No conversational anchor extraction is added in this slice. That is intentionally deferred until the resolver-level precedence and evidence-path contract are proven stable.

## Native bounds

- maximum hops: 4;
- maximum candidate paths: 2;
- minimum path confidence: 0.80;
- memory namespace remains isolated;
- concept namespace remains isolated;
- evidence IDs from persisted relations are preserved in the response.

## Response additions on relation HIT

The existing ABI symbol is unchanged. A relation-derived HIT adds:

- `relation_inference_used: true`;
- `inference_hops`;
- `inference_evidence_ids`;
- `memory_ids` containing the same original persisted relation evidence IDs;
- an auditable `selected_context` path.

Existing direct HIT response shape and priority are unchanged.
