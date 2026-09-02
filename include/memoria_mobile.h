#ifndef MEMORIA_MOBILE_H
#define MEMORIA_MOBILE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MEMORIA_MOBILE_ABI_VERSION 1

typedef struct memoria_mobile_handle memoria_mobile_handle;

typedef enum memoria_mobile_status {
    MEMORIA_MOBILE_OK = 0,
    MEMORIA_MOBILE_INVALID_ARGUMENT = 1,
    MEMORIA_MOBILE_UNRESOLVED = 2,
    MEMORIA_MOBILE_NOT_FOUND = 3,
    MEMORIA_MOBILE_PERSISTENCE_ERROR = 4,
    MEMORIA_MOBILE_INTERNAL_ERROR = 5
} memoria_mobile_status;

typedef struct memoria_mobile_buffer {
    const uint8_t *data;
    size_t size;
} memoria_mobile_buffer;

uint32_t memoria_mobile_abi_version(void);
memoria_mobile_status memoria_mobile_open(const char *data_dir,const char *organization_id,memoria_mobile_handle **out_handle);
memoria_mobile_status memoria_mobile_learn_turn_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);
memoria_mobile_status memoria_mobile_learn_external_knowledge_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);

/* Guarded post-v1 external/public ingestion. The request carries the normal
 * external knowledge fields plus origin_query. A deterministic relevance gate
 * runs before persistence. Irrelevant evidence returns UNRESOLVED with
 * persisted=false and never delegates to the durable ingest path. */
memoria_mobile_status memoria_mobile_learn_external_knowledge_guarded_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_inspect_external_knowledge_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);

/* Inspect the distinct evidence dimensions persisted beside one external_public
 * source. Request requires memory_id and may include namespace/source_url.
 * source_authority, retrieval_relevance, semantic_confidence and freshness are
 * independent dimensions; none is a universal confidence score. */
memoria_mobile_status memoria_mobile_inspect_evidence_metrics_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

/* Deterministically classify the durable external_public provenance attached to
 * one memory. Request requires memory_id (and optional namespace) and accepts
 * optional min_independent_domains/min_validation_confidence policy overrides.
 * The result is derived from BDR-backed provenance, so it survives restart
 * without duplicating a second consolidation state. "corroborated" is evidence
 * state only; it is not a declaration of truth. */
memoria_mobile_status memoria_mobile_inspect_external_consolidation_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_resolve_context_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);

/* Read-only conservative 2-hop inference over already-promoted persisted
 * relations. Request requires subject and predicate, with optional namespace.
 * The result never persists an inferred fact. */
memoria_mobile_status memoria_mobile_infer_two_hop_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

/* Explicit answer-origin resolver. Request requires query; subject/predicate are
 * optional inference hints. DIRECT always wins when retrieval resolves. Only a
 * direct miss may fall through to conservative inference. Returned resolution is
 * one of DIRECT, INFERRED, UNRESOLVED or CONFLICT. */
memoria_mobile_status memoria_mobile_resolve_mode_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

/* Explicit post-v1 read-only state composition. Request requires entity and a
 * non-empty properties array (maximum 8), with optional namespace. The result
 * combines only already-promoted current facts and returns each property's exact
 * source memory/order/authority. It never persists or infers a new fact. */
memoria_mobile_status memoria_mobile_resolve_composed_state_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_subconscious_peek_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);
memoria_mobile_status memoria_mobile_subconscious_satisfy_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);
memoria_mobile_status memoria_mobile_store_episode_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);
memoria_mobile_status memoria_mobile_recall_episode_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);
memoria_mobile_status memoria_mobile_export_snapshot_json(memoria_mobile_handle *handle,memoria_mobile_buffer request_json,memoria_mobile_buffer *response_json);
memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *handle);
void memoria_mobile_free_buffer(memoria_mobile_buffer buffer);
void memoria_mobile_close(memoria_mobile_handle *handle);

#ifdef __cplusplus
}
#endif
#endif