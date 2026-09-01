/*
 * Additive post-v1 episode capture composition.
 *
 * Session-scoped conversation turns are mirrored into the existing durable
 * episode store after the primary turn has been accepted. The turn remains the
 * source of truth; episode capture is a secondary index/event view and never
 * promotes assistant-generated text into a trusted fact.
 */
#define memoria_mobile_learn_turn_json memoria_mobile_learn_turn_json_post_v1_core
#include "evidence_metrics_runtime.c"
#undef memoria_mobile_learn_turn_json

static int episode_capture_nonblank(const char *s) {
    if (!s) return 0;
    while (*s) {
        if (!isspace((unsigned char)*s)) return 1;
        ++s;
    }
    return 0;
}

static int episode_capture_response_memory_id(
    memoria_mobile_buffer response,
    char out[MEMORIA_PERSIST_MEMORY_ID_CAP]
) {
    return evidence_metrics_response_memory_id(response, out);
}

static void episode_capture_session_turn(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer turn_response
) {
    char *json = NULL, *session_id = NULL, *namespace_id = NULL;
    char *role = NULL, *text = NULL, *timestamp = NULL, *source_type = NULL;
    char *escaped_id = NULL, *escaped_session = NULL, *escaped_role = NULL;
    char *escaped_text = NULL, *escaped_time = NULL, *escaped_type = NULL;
    char memory_id[MEMORIA_PERSIST_MEMORY_ID_CAP] = {0};
    char episode_id[MEMORIA_PERSIST_MEMORY_ID_CAP + 16u];
    char *episode_json = NULL;
    size_t needed;
    long order;
    double authority;
    memoria_mobile_buffer episode_request, episode_response = {0};

    if (!handle || !request_json.data || !request_json.size ||
        !episode_capture_response_memory_id(turn_response, memory_id)) return;

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
    free(json); json = NULL;

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

    if (snprintf(episode_id, sizeof(episode_id), "turn:%s", memory_id) < 0 ||
        strlen(episode_id) >= sizeof(episode_id)) goto done;

    escaped_id = json_escape(episode_id);
    escaped_session = json_escape(session_id);
    escaped_role = json_escape(role);
    escaped_text = json_escape(text);
    escaped_time = json_escape(timestamp);
    escaped_type = json_escape(source_type);
    if (!escaped_id || !escaped_session || !escaped_role || !escaped_text || !escaped_time || !escaped_type) goto done;

    needed = strlen(escaped_id) + strlen(escaped_session) + strlen(escaped_role) +
             strlen(escaped_text) + strlen(escaped_time) + strlen(escaped_type) + 384u;
    episode_json = (char *)malloc(needed);
    if (!episode_json) goto done;
    if (snprintf(episode_json, needed,
        "{\"episode_id\":\"%s\",\"session_id\":\"%s\",\"role\":\"%s\","
        "\"text\":\"%s\",\"timestamp\":\"%s\",\"event_type\":\"conversation_turn\","
        "\"topics_csv\":\"\",\"source_type\":\"%s\",\"source_authority\":%.17g,"
        "\"ultimate_source_memory_id\":\"%s\",\"order\":%ld}",
        escaped_id, escaped_session, escaped_role, escaped_text, escaped_time,
        escaped_type, authority, memory_id, order) < 0) goto done;

    episode_request.data = (const uint8_t *)episode_json;
    episode_request.size = strlen(episode_json);
    if (memoria_mobile_store_episode_json(handle, episode_request, &episode_response) == MEMORIA_MOBILE_OK)
        memoria_mobile_free_buffer(episode_response);

done:
    free(session_id); free(namespace_id); free(role); free(text); free(timestamp); free(source_type);
    free(escaped_id); free(escaped_session); free(escaped_role); free(escaped_text); free(escaped_time); free(escaped_type);
    free(episode_json);
}

memoria_mobile_status memoria_mobile_learn_turn_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    memoria_mobile_status status;
    if (!handle || !response_json) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    status = memoria_mobile_learn_turn_json_post_v1_core(handle, request_json, response_json);
    if (status == MEMORIA_MOBILE_OK)
        episode_capture_session_turn(handle, request_json, *response_json);
    return status;
}
