#include "memoria_mobile.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PACKET_CAP 32768u

static const char *find_value_start(const char *json, const char *key) {
    char pattern[128];
    const char *p;
    if (!json || !key) return NULL;
    if (snprintf(pattern, sizeof(pattern), "\"%s\"", key) < 0) return NULL;
    p = strstr(json, pattern);
    if (!p) return NULL;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return NULL;
    ++p;
    while (*p && isspace((unsigned char)*p)) ++p;
    return *p ? p : NULL;
}

static const char *find_value_end(const char *start) {
    const char *p;
    int depth = 0;
    int in_string = 0;
    if (!start) return NULL;
    if (*start == '"') {
        p = start + 1;
        while (*p) {
            if (*p == '\\' && p[1]) { p += 2; continue; }
            if (*p == '"') return p + 1;
            ++p;
        }
        return NULL;
    }
    if (*start == '[' || *start == '{') {
        char open = *start;
        char close = open == '[' ? ']' : '}';
        for (p = start; *p; ++p) {
            if (in_string) {
                if (*p == '\\' && p[1]) { ++p; continue; }
                if (*p == '"') in_string = 0;
                continue;
            }
            if (*p == '"') { in_string = 1; continue; }
            if (*p == open) ++depth;
            else if (*p == close && --depth == 0) return p + 1;
        }
        return NULL;
    }
    p = start;
    while (*p && *p != ',' && *p != '}') ++p;
    while (p > start && isspace((unsigned char)p[-1])) --p;
    return p;
}

static int append_text(char *out, size_t cap, size_t *used, const char *text) {
    size_t n;
    if (!out || !used || !text) return 0;
    n = strlen(text);
    if (*used + n + 1u > cap) return 0;
    memcpy(out + *used, text, n);
    *used += n;
    out[*used] = 0;
    return 1;
}

static int append_slice(char *out, size_t cap, size_t *used, const char *start, const char *end) {
    size_t n;
    if (!out || !used || !start || !end || end < start) return 0;
    n = (size_t)(end - start);
    if (*used + n + 1u > cap) return 0;
    memcpy(out + *used, start, n);
    *used += n;
    out[*used] = 0;
    return 1;
}

static int append_value_or(char *out, size_t cap, size_t *used, const char *json, const char *key, const char *fallback) {
    const char *start = find_value_start(json, key);
    const char *end = find_value_end(start);
    if (!start || !end) return append_text(out, cap, used, fallback);
    return append_slice(out, cap, used, start, end);
}

static int append_field(char *out, size_t cap, size_t *used, const char *json, const char *key, const char *fallback) {
    char prefix[160];
    if (snprintf(prefix, sizeof(prefix), "\"%s\":", key) < 0) return 0;
    return append_text(out, cap, used, prefix) && append_value_or(out, cap, used, json, key, fallback);
}

static int append_existing_request_field(
    char *out,
    size_t cap,
    size_t *used,
    const char *json,
    const char *key,
    int *field_count
) {
    const char *start = find_value_start(json, key);
    const char *end = find_value_end(start);
    char prefix[160];
    if (!start || !end) return 1;
    if (*field_count > 0 && !append_text(out, cap, used, ",")) return 0;
    if (snprintf(prefix, sizeof(prefix), "\"%s\":", key) < 0) return 0;
    if (!append_text(out, cap, used, prefix) || !append_slice(out, cap, used, start, end)) return 0;
    ++(*field_count);
    return 1;
}

/*
 * Context Compiler precedence:
 *   1. persistent semantic/temporal/concept state without volatile trajectory;
 *   2. only when that is unresolved, retry the original request with conversation_window.
 *
 * This keeps a growing LLM conversation window from eclipsing an already justified
 * persistent fact. The legacy resolver ABI itself is not changed; trajectory callers
 * that explicitly use memoria_mobile_resolve_context_json retain their old behavior.
 */
static char *build_stable_request(const char *json) {
    static const char *keys[] = {
        "query", "namespace", "concept_namespace", "relation_source", "relation_target"
    };
    char *out;
    size_t used = 0, i;
    int field_count = 0;
    if (!json || !find_value_start(json, "query")) return NULL;
    out = (char *)malloc(PACKET_CAP);
    if (!out) return NULL;
    out[0] = 0;
    if (!append_text(out, PACKET_CAP, &used, "{")) { free(out); return NULL; }
    for (i = 0; i < sizeof(keys) / sizeof(keys[0]); ++i) {
        if (!append_existing_request_field(out, PACKET_CAP, &used, json, keys[i], &field_count)) {
            free(out);
            return NULL;
        }
    }
    if (!append_text(out, PACKET_CAP, &used, "}")) { free(out); return NULL; }
    return out;
}

static memoria_mobile_status set_owned_response(memoria_mobile_buffer *out, char *json, size_t used, memoria_mobile_status status) {
    if (!out || !json) { free(json); return MEMORIA_MOBILE_INVALID_ARGUMENT; }
    out->data = (const uint8_t *)json;
    out->size = used;
    return status;
}

memoria_mobile_status memoria_mobile_compile_context_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    memoria_mobile_buffer resolved = {0};
    memoria_mobile_buffer stable_buffer = {0};
    memoria_mobile_status status;
    char *request_source = NULL;
    char *stable_request = NULL;
    char *source = NULL;
    char *packet = NULL;
    size_t used = 0;

    if (!handle || !request_json.data || request_json.size == 0 || !response_json)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    request_source = (char *)malloc(request_json.size + 1u);
    if (!request_source) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(request_source, request_json.data, request_json.size);
    request_source[request_json.size] = 0;

    if (find_value_start(request_source, "conversation_window")) {
        stable_request = build_stable_request(request_source);
        if (!stable_request) { free(request_source); return MEMORIA_MOBILE_INTERNAL_ERROR; }
        stable_buffer.data = (const uint8_t *)stable_request;
        stable_buffer.size = strlen(stable_request);
        status = memoria_mobile_resolve_context_json(handle, stable_buffer, &resolved);
        if (status == MEMORIA_MOBILE_UNRESOLVED) {
            if (resolved.data) memoria_mobile_free_buffer(resolved);
            resolved = (memoria_mobile_buffer){0};
            status = memoria_mobile_resolve_context_json(handle, request_json, &resolved);
        }
    } else {
        status = memoria_mobile_resolve_context_json(handle, request_json, &resolved);
    }
    free(stable_request);
    free(request_source);

    if (!resolved.data || resolved.size == 0) return status;

    source = (char *)malloc(resolved.size + 1u);
    if (!source) { memoria_mobile_free_buffer(resolved); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    memcpy(source, resolved.data, resolved.size);
    source[resolved.size] = 0;
    memoria_mobile_free_buffer(resolved);

    if (status == MEMORIA_MOBILE_UNRESOLVED) {
        packet = (char *)malloc(PACKET_CAP);
        if (!packet) { free(source); return MEMORIA_MOBILE_INTERNAL_ERROR; }
        packet[0] = 0;
        if (!append_text(packet, PACKET_CAP, &used, "{\"status\":\"UNRESOLVED\",\"schema_version\":1,\"packet_schema\":\"memoria.cognitive.packet.v1\"," ) ||
            !append_field(packet, PACKET_CAP, &used, source, "reason", "\"unresolved\"") ||
            !append_text(packet, PACKET_CAP, &used, ",\"packet\":null}")) {
            free(source); free(packet); return MEMORIA_MOBILE_INTERNAL_ERROR;
        }
        free(source);
        return set_owned_response(response_json, packet, used, MEMORIA_MOBILE_UNRESOLVED);
    }
    if (status != MEMORIA_MOBILE_OK) { free(source); return status; }

    packet = (char *)malloc(PACKET_CAP);
    if (!packet) { free(source); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    packet[0] = 0;

    if (!append_text(packet, PACKET_CAP, &used, "{\"status\":\"HIT\",\"schema_version\":1,\"packet_schema\":\"memoria.cognitive.packet.v1\",\"packet\":{") ||
        !append_field(packet, PACKET_CAP, &used, source, "confidence", "0.0") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "memory_ids", "[]") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "relations", "[]") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "relations_by_memory", "[]") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "provenance", "[]") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "temporal_state_used", "false") ||
        !append_text(packet, PACKET_CAP, &used, ",\"temporal\":{") ||
        !append_field(packet, PACKET_CAP, &used, source, "previous_memory_id", "null") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "current_memory_id", "null") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "previous_order", "null") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "current_order", "null") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "previous_value", "null") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "current_value", "null") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "transition_detected", "false") ||
        !append_text(packet, PACKET_CAP, &used, "},\"activation\":{") ||
        !append_field(packet, PACKET_CAP, &used, source, "trajectory_used", "false") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "relation_inference_used", "false") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "relation_neighborhood_used", "false") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "neighbors", "[]") ||
        !append_text(packet, PACKET_CAP, &used, ",") ||
        !append_field(packet, PACKET_CAP, &used, source, "members", "[]") ||
        !append_text(packet, PACKET_CAP, &used, "}}}")) {
        free(source); free(packet); return MEMORIA_MOBILE_INTERNAL_ERROR;
    }

    free(source);
    return set_owned_response(response_json, packet, used, MEMORIA_MOBILE_OK);
}