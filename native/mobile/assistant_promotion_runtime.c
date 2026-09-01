/*
 * Final post-v1 turn-ingest policy layer.
 *
 * evidence_metrics_runtime.c remains the composed implementation for durable
 * metrics and episode capture. This wrapper supplies source provenance to the
 * relation-promotion path for exactly one ingest call, then clears the
 * thread-local policy context. External/public ingestion is intentionally not
 * wrapped here and remains evidence-eligible.
 */
#define memoria_mobile_learn_turn_json memoria_mobile_learn_turn_json_evidence_core
#include "evidence_metrics_runtime.c"
#undef memoria_mobile_learn_turn_json

static char *assistant_promotion_source_type(memoria_mobile_buffer request_json) {
    char *json = NULL, *source_type = NULL, *role = NULL;
    if (!request_json.data || !request_json.size) return NULL;
    json = buffer_to_string(request_json);
    if (!json) return NULL;
    source_type = json_string(json, "source_type");
    if (!source_type) {
        role = json_string(json, "role");
        if (role)
            source_type = dup_string(strcmp(role, "assistant") == 0 ? "assistant_generated" : "user_assertion");
    }
    free(role);
    free(json);
    return source_type;
}

memoria_mobile_status memoria_mobile_learn_turn_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *source_type;
    memoria_mobile_status status;
    if (!handle || !response_json) return MEMORIA_MOBILE_INVALID_ARGUMENT;

    source_type = assistant_promotion_source_type(request_json);
    memoria_relation_promotion_set_source_type(source_type);
    status = memoria_mobile_learn_turn_json_evidence_core(handle, request_json, response_json);
    memoria_relation_promotion_clear_source_type();
    free(source_type);
    return status;
}
