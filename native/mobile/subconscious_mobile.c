#include "subconscious_mobile.h"
#include "subconscious_kernel.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RUNTIME_SLOTS 16u

typedef struct subconscious_runtime_slot {
    memoria_mobile_handle *handle;
    memoria_subconscious_state state;
    long observation_order;
} subconscious_runtime_slot;

static subconscious_runtime_slot runtimes[RUNTIME_SLOTS];

static subconscious_runtime_slot *runtime_for(memoria_mobile_handle *handle, int create) {
    size_t i, empty = RUNTIME_SLOTS;
    if (!handle) return NULL;
    for (i = 0; i < RUNTIME_SLOTS; ++i) {
        if (runtimes[i].handle == handle) return &runtimes[i];
        if (!runtimes[i].handle && empty == RUNTIME_SLOTS) empty = i;
    }
    if (!create || empty == RUNTIME_SLOTS) return NULL;
    memset(&runtimes[empty], 0, sizeof(runtimes[empty]));
    runtimes[empty].handle = handle;
    memoria_subconscious_init(&runtimes[empty].state);
    return &runtimes[empty];
}

static char *buffer_string(memoria_mobile_buffer in) {
    char *s;
    if (!in.data || !in.size) return NULL;
    s = (char *)malloc(in.size + 1u);
    if (!s) return NULL;
    memcpy(s, in.data, in.size);
    s[in.size] = 0;
    return s;
}

static char *json_string_value(const char *json, const char *key) {
    char pattern[96];
    const char *p, *q;
    char *out;
    size_t n, w = 0;
    if (!json || !key) return NULL;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p || !(p = strchr(p + strlen(pattern), ':'))) return NULL;
    ++p;
    while (*p && isspace((unsigned char)*p)) ++p;
    if (*p++ != '"') return NULL;
    q = p;
    while (*q && *q != '"') {
        if (*q == '\\' && q[1]) q += 2;
        else ++q;
    }
    if (*q != '"') return NULL;
    n = (size_t)(q - p);
    out = (char *)malloc(n + 1u);
    if (!out) return NULL;
    while (p < q) {
        if (*p == '\\' && p + 1 < q) {
            ++p;
            switch (*p) {
                case 'n': out[w++] = '\n'; ++p; break;
                case 'r': out[w++] = '\r'; ++p; break;
                case 't': out[w++] = '\t'; ++p; break;
                case '"': out[w++] = '"'; ++p; break;
                case '\\': out[w++] = '\\'; ++p; break;
                case '/': out[w++] = '/'; ++p; break;
                default: out[w++] = *p++; break;
            }
        } else out[w++] = *p++;
    }
    out[w] = 0;
    return out;
}

static double json_double_value(const char *json, const char *key, double fallback) {
    char pattern[96];
    const char *p;
    char *end = NULL;
    double value;
    if (!json || !key) return fallback;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p || !(p = strchr(p + strlen(pattern), ':'))) return fallback;
    value = strtod(p + 1, &end);
    return end == p + 1 ? fallback : value;
}

static char *json_escape_copy(const char *s) {
    size_t i, size = 0, w = 0;
    char *out;
    if (!s) s = "";
    for (i = 0; s[i]; ++i) size += (s[i] == '"' || s[i] == '\\' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t') ? 2u : 1u;
    out = (char *)malloc(size + 1u);
    if (!out) return NULL;
    for (i = 0; s[i]; ++i) {
        switch (s[i]) {
            case '"': out[w++]='\\'; out[w++]='"'; break;
            case '\\': out[w++]='\\'; out[w++]='\\'; break;
            case '\n': out[w++]='\\'; out[w++]='n'; break;
            case '\r': out[w++]='\\'; out[w++]='r'; break;
            case '\t': out[w++]='\\'; out[w++]='t'; break;
            default: out[w++]=s[i];
        }
    }
    out[w]=0;
    return out;
}

static memoria_mobile_status response(memoria_mobile_buffer *out, const char *json, memoria_mobile_status status) {
    size_t n;
    uint8_t *data;
    if (!out || !json) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    n = strlen(json);
    data = (uint8_t *)malloc(n + 1u);
    if (!data) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(data, json, n + 1u);
    out->data = data;
    out->size = n;
    return status;
}

void memoria_subconscious_mobile_observe_resolution(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_status status,
    memoria_mobile_buffer response_json
) {
    subconscious_runtime_slot *slot;
    char *request = NULL, *resolved_response = NULL, *query = NULL;
    double confidence = 0.0;
    int resolved;
    if (!handle || (status != MEMORIA_MOBILE_OK && status != MEMORIA_MOBILE_UNRESOLVED)) return;
    request = buffer_string(request_json);
    if (!request) return;
    query = json_string_value(request, "query");
    free(request);
    if (!query || !*query) { free(query); return; }
    resolved = status == MEMORIA_MOBILE_OK;
    if (resolved && response_json.data && response_json.size) {
        resolved_response = buffer_string(response_json);
        if (resolved_response) confidence = json_double_value(resolved_response, "confidence", 0.0);
        free(resolved_response);
    }
    slot = runtime_for(handle, 1);
    if (slot) {
        ++slot->observation_order;
        memoria_subconscious_observe(&slot->state, query, resolved, confidence, slot->observation_order);
    }
    free(query);
}

void memoria_subconscious_mobile_forget_handle(memoria_mobile_handle *handle) {
    size_t i;
    if (!handle) return;
    for (i = 0; i < RUNTIME_SLOTS; ++i) {
        if (runtimes[i].handle == handle) {
            memset(&runtimes[i], 0, sizeof(runtimes[i]));
            return;
        }
    }
}

memoria_mobile_status memoria_mobile_subconscious_peek_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *out
) {
    subconscious_runtime_slot *slot;
    const memoria_subconscious_candidate *candidate;
    char *topic = NULL;
    char json[768];
    (void)request_json;
    if (!handle || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    slot = runtime_for(handle, 0);
    candidate = slot ? memoria_subconscious_peek(&slot->state) : NULL;
    if (!candidate)
        return response(out, "{\"status\":\"OK\",\"pending\":false}", MEMORIA_MOBILE_OK);
    topic = json_escape_copy(candidate->topic);
    if (!topic) return MEMORIA_MOBILE_INTERNAL_ERROR;
    snprintf(json, sizeof(json),
        "{\"status\":\"OK\",\"pending\":true,\"topic\":\"%s\",\"priority\":%.6f,"
        "\"observations\":%u,\"unresolved_count\":%u,\"low_confidence_count\":%u}",
        topic, candidate->priority, candidate->observations,
        candidate->unresolved_count, candidate->low_confidence_count);
    free(topic);
    return response(out, json, MEMORIA_MOBILE_OK);
}

memoria_mobile_status memoria_mobile_subconscious_satisfy_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *out
) {
    subconscious_runtime_slot *slot;
    char *request = NULL, *topic = NULL;
    int removed = 0;
    if (!handle || !out || !request_json.data || !request_json.size) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    request = buffer_string(request_json);
    if (!request) return MEMORIA_MOBILE_INTERNAL_ERROR;
    topic = json_string_value(request, "topic");
    free(request);
    if (!topic || !*topic) { free(topic); return MEMORIA_MOBILE_INVALID_ARGUMENT; }
    slot = runtime_for(handle, 0);
    if (slot) removed = memoria_subconscious_satisfy(&slot->state, topic);
    free(topic);
    return response(out,
        removed ? "{\"status\":\"OK\",\"removed\":true}" : "{\"status\":\"OK\",\"removed\":false}",
        MEMORIA_MOBILE_OK);
}
