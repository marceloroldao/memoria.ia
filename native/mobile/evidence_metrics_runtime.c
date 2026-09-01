/*
 * Additive post-v1 composition layer for evidence metrics and episode capture.
 *
 * The existing post-v1 runtime remains the implementation of primary turn and
 * external/public ingestion. This translation unit wraps those entry points to
 * add post-v1 behavior without editing the frozen v1 implementation.
 */
#define memoria_mobile_learn_external_knowledge_json memoria_mobile_learn_external_knowledge_json_post_v1_core
#define memoria_mobile_learn_turn_json memoria_mobile_learn_turn_json_post_v1_core
#include "memoria_mobile_post_v1.c"
#undef memoria_mobile_learn_turn_json
#undef memoria_mobile_learn_external_knowledge_json

#include "evidence_metrics.h"

#define EVIDENCE_METRICS_MAX_OPS 8u
#define EVIDENCE_METRICS_UNKNOWN_FRESHNESS 0.50

static int evidence_metrics_request(
    memoria_mobile_buffer request_json,
    external_request *external,
    memoria_evidence_metrics *metrics
) {
    char *json;
    double default_authority;
    if (!external || !metrics || !external_parse_request(request_json, external)) return 0;
    json = buffer_to_string(request_json);
    if (!json) { external_request_free(external); return 0; }
    default_authority = strcmp(external->import_kind, "derived") == 0
        ? EXTERNAL_DERIVED_AUTHORITY : EXTERNAL_DEFAULT_AUTHORITY;
    metrics->source_authority = json_double(json, "source_authority", default_authority);
    metrics->retrieval_relevance = json_double(json, "retrieval_relevance", 1.0);
    metrics->semantic_confidence = json_double(json, "semantic_confidence", external->validation_confidence);
    metrics->freshness = json_double(json, "freshness", EVIDENCE_METRICS_UNKNOWN_FRESHNESS);
    free(json);
    return metrics->source_authority >= 0.0 && metrics->source_authority <= 1.0 &&
           metrics->retrieval_relevance >= 0.0 && metrics->retrieval_relevance <= 1.0 &&
           metrics->semantic_confidence >= 0.0 && metrics->semantic_confidence <= 1.0 &&
           metrics->freshness >= 0.0 && metrics->freshness <= 1.0;
}

static int evidence_metrics_response_memory_id(
    memoria_mobile_buffer response,
    char out[MEMORIA_PERSIST_MEMORY_ID_CAP]
) {
    char *json;
    char *ids[1] = {0};
    size_t count;
    if (!response.data || !response.size || !out) return 0;
    json = buffer_to_string(response);
    if (!json) return 0;
    count = json_string_array(json, "stored_memory_ids", ids, 1u);
    free(json);
    if (!count || !ids[0] || !ids[0][0]) { free(ids[0]); return 0; }
    if (strlen(ids[0]) >= MEMORIA_PERSIST_MEMORY_ID_CAP) { free(ids[0]); return 0; }
    strcpy(out, ids[0]);
    free(ids[0]);
    return 1;
}

static int evidence_metrics_find_source_index(
    memoria_mobile_handle *handle,
    size_t slot,
    const char *source_url,
    unsigned long *out_index
) {
    unsigned long count = 0, i;
    if (!handle || !slot || !source_url || !out_index || !external_source_count(handle, slot, &count)) return 0;
    for (i = 0; i < count; ++i) {
        char *stored = NULL;
        if (!external_source_url_at(handle, slot, i, &stored)) return 0;
        if (stored && strcmp(stored, source_url) == 0) {
            free(stored);
            *out_index = i;
            return 1;
        }
        free(stored);
    }
    return 0;
}

static int evidence_metrics_persist(
    memoria_mobile_handle *handle,
    size_t slot,
    unsigned long source_index,
    const memoria_evidence_metrics *metrics
) {
    bdr_atomic_c_operation ops[EVIDENCE_METRICS_MAX_OPS];
    char keys[EVIDENCE_METRICS_MAX_OPS][KEY_CAP];
    char values[4][VAL_CAP];
    char field[96];
    bdr_atomic_c_batch_result result = {0};
    size_t n = 0u;
    if (!handle || !slot || !metrics) return 0;
    snprintf(values[0], VAL_CAP, "%.17g", metrics->source_authority);
    snprintf(values[1], VAL_CAP, "%.17g", metrics->retrieval_relevance);
    snprintf(values[2], VAL_CAP, "%.17g", metrics->semantic_confidence);
    snprintf(values[3], VAL_CAP, "%.17g", metrics->freshness);
#define METRIC_PUT(name, value) do { \
    snprintf(field, sizeof(field), "source/%lu/%s", source_index, name); \
    if (!add_put(handle->persistence, ops, keys, &n, "external", slot, field, value)) return 0; \
} while (0)
    METRIC_PUT("source_authority", values[0]);
    METRIC_PUT("retrieval_relevance", values[1]);
    METRIC_PUT("semantic_confidence", values[2]);
    METRIC_PUT("freshness", values[3]);
#undef METRIC_PUT
    if (bdr_atomic_c_write_batch(handle->persistence->db, ops, n, &result) != BDR_ATOMIC_C_OK) return 0;
    return result.durable == 1 && result.operations == n;
}

memoria_mobile_status memoria_mobile_learn_external_knowledge_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    external_request external = {0};
    memoria_evidence_metrics metrics;
    memoria_mobile_status status;
    char memory_id[MEMORIA_PERSIST_MEMORY_ID_CAP] = {0};
    memory_ref ref = {0};
    size_t slot;
    unsigned long source_index;

    if (!handle || !response_json) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (!evidence_metrics_request(request_json, &external, &metrics))
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    status = memoria_mobile_learn_external_knowledge_json_post_v1_core(handle, request_json, response_json);
    if (status != MEMORIA_MOBILE_OK) { external_request_free(&external); return status; }

    if (!evidence_metrics_response_memory_id(*response_json, memory_id) ||
        !find_memory_ref(handle, memory_id, external.namespace_id, &ref) || !ref.turn) {
        external_request_free(&external);
        return MEMORIA_MOBILE_PERSISTENCE_ERROR;
    }
    slot = (size_t)(ref.turn - handle->turns) + 1u;
    if (!evidence_metrics_find_source_index(handle, slot, external.source_url, &source_index) ||
        !evidence_metrics_persist(handle, slot, source_index, &metrics)) {
        external_request_free(&external);
        return MEMORIA_MOBILE_PERSISTENCE_ERROR;
    }
    external_request_free(&external);
    return MEMORIA_MOBILE_OK;
}

memoria_mobile_status memoria_mobile_inspect_evidence_metrics_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *json = NULL, *memory_id = NULL, *namespace_id = NULL;
    memory_ref ref = {0};
    size_t slot;
    unsigned long source_count = 0, source_index = 0;
    char *requested_url = NULL;
    char *authority = NULL, *relevance = NULL, *semantic = NULL, *freshness = NULL;
    char field[96];
    external_builder b = {0};
    memoria_mobile_status status = MEMORIA_MOBILE_INTERNAL_ERROR;

    if (!handle || !response_json || !request_json.data || !request_json.size)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = buffer_to_string(request_json);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memory_id = json_string(json, "memory_id");
    namespace_id = json_string(json, "namespace");
    requested_url = json_string(json, "source_url");
    free(json);
    if (!namespace_id) namespace_id = dup_string("");
    if (!memory_id || !namespace_id ||
        !find_memory_ref(handle, memory_id, namespace_id, &ref) || !ref.turn) {
        status = MEMORIA_MOBILE_NOT_FOUND;
        goto done;
    }
    slot = (size_t)(ref.turn - handle->turns) + 1u;
    if (!external_slot_is_public(handle, slot) || !external_source_count(handle, slot, &source_count) || !source_count) {
        status = MEMORIA_MOBILE_NOT_FOUND;
        goto done;
    }
    if (requested_url) {
        if (!evidence_metrics_find_source_index(handle, slot, requested_url, &source_index)) {
            status = MEMORIA_MOBILE_NOT_FOUND;
            goto done;
        }
    }
#define METRIC_FETCH(name, target) do { \
    snprintf(field, sizeof(field), "source/%lu/%s", source_index, name); \
    if (!external_fetch_field(handle->persistence, slot, field, &target) || !target) { \
        status = MEMORIA_MOBILE_NOT_FOUND; goto done; \
    } \
} while (0)
    METRIC_FETCH("source_authority", authority);
    METRIC_FETCH("retrieval_relevance", relevance);
    METRIC_FETCH("semantic_confidence", semantic);
    METRIC_FETCH("freshness", freshness);
#undef METRIC_FETCH
    if (!external_builder_appendf(&b,
        "{\"status\":\"OK\",\"memory_id\":\"%s\",\"source_index\":%lu,"
        "\"source_authority\":%s,\"retrieval_relevance\":%s,"
        "\"semantic_confidence\":%s,\"freshness\":%s,"
        "\"legacy_validation_confidence_preserved\":true}",
        memory_id, source_index, authority, relevance, semantic, freshness)) {
        status = MEMORIA_MOBILE_INTERNAL_ERROR;
        goto done;
    }
    response_json->data = (const uint8_t *)b.data;
    response_json->size = b.size;
    b.data = NULL;
    status = MEMORIA_MOBILE_OK;
done:
    free(b.data);
    free(memory_id); free(namespace_id); free(requested_url);
    free(authority); free(relevance); free(semantic); free(freshness);
    return status;
}

static int episode_capture_nonblank(const char *s) {
    if (!s) return 0;
    while (*s) {
        if (!isspace((unsigned char)*s)) return 1;
        ++s;
    }
    return 0;
}

static void episode_capture_session_turn(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer turn_response
) {
    char *json = NULL, *session_id = NULL, *namespace_id = NULL;
    char *role = NULL, *text = NULL, *timestamp = NULL, *source_type = NULL;
    char *escaped_id = NULL, *escaped_session = NULL, *escaped_role = NULL;
    char *escaped_text = NULL, *escaped_time = NULL, *escaped_type = NULL, *escaped_root = NULL;
    char memory_id[MEMORIA_PERSIST_MEMORY_ID_CAP] = {0};
    char episode_id[MEMORIA_PERSIST_MEMORY_ID_CAP + 16u];
    char *episode_json = NULL;
    size_t needed;
    int id_written, json_written;
    long order;
    double authority;
    memoria_mobile_buffer episode_request, episode_response = {0};

    if (!handle || !request_json.data || !request_json.size ||
        !evidence_metrics_response_memory_id(turn_response, memory_id)) return;

    json = buffer_to_string(request_json);
    if (!json) return;
    session_id = json_string(json, "session_id");
    namespace_id = json_string(json, "namespace");
    role = json_string(json, "role");
    text = json_string(json, "text");
    timestamp = json_string(json, "timestamp");
    source_type = json_string(json, "source_type");
    order = json_long(json, "order", (long)handle->turn_count);
    authority = json_double(json, "source_authority", -1.0);
    free(json);

    if (!episode_capture_nonblank(session_id)) {
        free(session_id);
        session_id = namespace_id;
        namespace_id = NULL;
    }
    if (!episode_capture_nonblank(session_id) || !role || !text) goto done;
    if (!timestamp) timestamp = dup_string("");
    if (!source_type) source_type = dup_string(strcmp(role, "user") == 0 ? "user_assertion" : "assistant_generated");
    if (authority < 0.0)
        authority = (strcmp(source_type, "user_assertion") == 0 || strcmp(source_type, "user_correction") == 0) ? 1.0 : 0.35;
    if (!timestamp || !source_type) goto done;

    id_written = snprintf(episode_id, sizeof(episode_id), "turn:%s", memory_id);
    if (id_written < 0 || (size_t)id_written >= sizeof(episode_id)) goto done;

    escaped_id = json_escape(episode_id);
    escaped_session = json_escape(session_id);
    escaped_role = json_escape(role);
    escaped_text = json_escape(text);
    escaped_time = json_escape(timestamp);
    escaped_type = json_escape(source_type);
    escaped_root = json_escape(memory_id);
    if (!escaped_id || !escaped_session || !escaped_role || !escaped_text ||
        !escaped_time || !escaped_type || !escaped_root) goto done;

    needed = strlen(escaped_id) + strlen(escaped_session) + strlen(escaped_role) +
             strlen(escaped_text) + strlen(escaped_time) + strlen(escaped_type) +
             strlen(escaped_root) + 384u;
    episode_json = (char *)malloc(needed);
    if (!episode_json) goto done;
    json_written = snprintf(episode_json, needed,
        "{\"episode_id\":\"%s\",\"session_id\":\"%s\",\"role\":\"%s\","
        "\"text\":\"%s\",\"timestamp\":\"%s\",\"event_type\":\"conversation_turn\","
        "\"topics_csv\":\"\",\"source_type\":\"%s\",\"source_authority\":%.17g,"
        "\"ultimate_source_memory_id\":\"%s\",\"order\":%ld}",
        escaped_id, escaped_session, escaped_role, escaped_text, escaped_time,
        escaped_type, authority, escaped_root, order);
    if (json_written < 0 || (size_t)json_written >= needed) goto done;

    episode_request.data = (const uint8_t *)episode_json;
    episode_request.size = (size_t)json_written;
    (void)memoria_mobile_store_episode_json(handle, episode_request, &episode_response);
    if (episode_response.data) memoria_mobile_free_buffer(episode_response);

done:
    free(session_id); free(namespace_id); free(role); free(text); free(timestamp); free(source_type);
    free(escaped_id); free(escaped_session); free(escaped_role); free(escaped_text);
    free(escaped_time); free(escaped_type); free(escaped_root); free(episode_json);
}

static char *promotion_source_type_from_request(memoria_mobile_buffer request_json) {
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

    source_type = promotion_source_type_from_request(request_json);
    memoria_relation_promotion_set_source_type(source_type);
    status = memoria_mobile_learn_turn_json_post_v1_core(handle, request_json, response_json);
    memoria_relation_promotion_clear_source_type();
    free(source_type);

    if (status == MEMORIA_MOBILE_OK)
        episode_capture_session_turn(handle, request_json, *response_json);
    return status;
}
