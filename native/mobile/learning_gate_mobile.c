#include "memoria_mobile.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LG_ID_CAP 384u
#define LG_PAGE_CAP 65536u

static char *lg_json_string(const char *json, const char *key) {
    char pattern[128];
    const char *p, *q;
    char *out;
    size_t n, w = 0;
    if (!json || !key) return NULL;
    if (snprintf(pattern, sizeof(pattern), "\"%s\"", key) < 0) return NULL;
    p = strstr(json, pattern);
    if (!p) return NULL;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return NULL;
    ++p;
    while (*p && isspace((unsigned char)*p)) ++p;
    if (*p != '"') return NULL;
    ++p;
    q = p;
    while (*q) {
        if (*q == '\\' && q[1]) { q += 2; continue; }
        if (*q == '"') break;
        ++q;
    }
    if (*q != '"') return NULL;
    n = (size_t)(q - p);
    out = (char *)malloc(n + 1u);
    if (!out) return NULL;
    while (p < q) {
        if (*p == '\\' && p + 1 < q) {
            ++p;
            switch (*p) {
                case 'n': out[w++] = '\n'; break;
                case 'r': out[w++] = '\r'; break;
                case 't': out[w++] = '\t'; break;
                default: out[w++] = *p; break;
            }
            ++p;
        } else out[w++] = *p++;
    }
    out[w] = 0;
    return out;
}

static int lg_json_bool(const char *json, const char *key, int *out) {
    char pattern[128];
    const char *p;
    if (!json || !key || !out) return 0;
    if (snprintf(pattern, sizeof(pattern), "\"%s\"", key) < 0) return 0;
    p = strstr(json, pattern);
    if (!p) return 0;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return 0;
    ++p;
    while (*p && isspace((unsigned char)*p)) ++p;
    if (strncmp(p, "true", 4) == 0) { *out = 1; return 1; }
    if (strncmp(p, "false", 5) == 0) { *out = 0; return 1; }
    return 0;
}

static long lg_json_long(const char *json, const char *key, long fallback) {
    char pattern[128];
    const char *p;
    char *end = NULL;
    long v;
    if (!json || !key) return fallback;
    if (snprintf(pattern, sizeof(pattern), "\"%s\"", key) < 0) return fallback;
    p = strstr(json, pattern);
    if (!p) return fallback;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return fallback;
    v = strtol(p + 1, &end, 10);
    return end == p + 1 ? fallback : v;
}

static char *lg_json_escape(const char *text) {
    const unsigned char *p = (const unsigned char *)(text ? text : "");
    size_t cap = strlen(text ? text : "") * 2u + 1u;
    char *out = (char *)malloc(cap ? cap : 1u);
    size_t used = 0;
    if (!out) return NULL;
    while (*p) {
        const char *esc = NULL;
        char one[2] = {(char)*p, 0};
        switch (*p) {
            case '"': esc = "\\\""; break;
            case '\\': esc = "\\\\"; break;
            case '\n': esc = "\\n"; break;
            case '\r': esc = "\\r"; break;
            case '\t': esc = "\\t"; break;
            default: esc = one; break;
        }
        {
            size_t n = strlen(esc);
            if (used + n + 1u > cap) { free(out); return NULL; }
            memcpy(out + used, esc, n);
            used += n;
        }
        ++p;
    }
    out[used] = 0;
    return out;
}

static int lg_safe_id(const char *value) {
    const unsigned char *p = (const unsigned char *)value;
    size_t n = 0;
    if (!value || !*value) return 0;
    while (*p) {
        if (!(isalnum(*p) || *p == '-' || *p == '_' || *p == '.' || *p == ':')) return 0;
        ++p; ++n;
        if (n >= 300u) return 0;
    }
    return 1;
}

static const char *lg_find_object_end(const char *start) {
    const char *p;
    int depth = 0, in_string = 0;
    if (!start || *start != '{') return NULL;
    for (p = start; *p; ++p) {
        if (in_string) {
            if (*p == '\\' && p[1]) { ++p; continue; }
            if (*p == '"') in_string = 0;
            continue;
        }
        if (*p == '"') { in_string = 1; continue; }
        if (*p == '{') ++depth;
        else if (*p == '}' && --depth == 0) return p + 1;
    }
    return NULL;
}

static char *lg_find_turn_object(const char *snapshot, const char *memory_id) {
    char marker[LG_ID_CAP + 32u];
    const char *hit, *start, *end;
    size_t n;
    if (!snapshot || !memory_id) return NULL;
    if (snprintf(marker, sizeof(marker), "\"memory_id\":\"%s\"", memory_id) < 0) return NULL;
    hit = strstr(snapshot, marker);
    if (!hit) return NULL;
    start = hit;
    while (start > snapshot && *start != '{') --start;
    if (*start != '{') return NULL;
    end = lg_find_object_end(start);
    if (!end) return NULL;
    n = (size_t)(end - start);
    if (n >= LG_PAGE_CAP) return NULL;
    {
        char *out = (char *)malloc(n + 1u);
        if (!out) return NULL;
        memcpy(out, start, n);
        out[n] = 0;
        return out;
    }
}

static char *lg_load_turn(memoria_mobile_handle *handle, const char *memory_id) {
    size_t offset = 0u;
    char request[128];
    for (;;) {
        memoria_mobile_buffer req, out = {0};
        memoria_mobile_status status;
        char *snapshot, *turn;
        long next;
        int n = snprintf(request, sizeof(request), "{\"turn_offset\":%lu,\"turn_limit\":64,\"episode_limit\":1}", (unsigned long)offset);
        if (n < 0 || (size_t)n >= sizeof(request)) return NULL;
        req.data = (const uint8_t *)request;
        req.size = strlen(request);
        status = memoria_mobile_export_snapshot_json(handle, req, &out);
        if (status != MEMORIA_MOBILE_OK || !out.data || !out.size) {
            if (out.data) memoria_mobile_free_buffer(out);
            return NULL;
        }
        snapshot = (char *)malloc(out.size + 1u);
        if (!snapshot) { memoria_mobile_free_buffer(out); return NULL; }
        memcpy(snapshot, out.data, out.size);
        snapshot[out.size] = 0;
        memoria_mobile_free_buffer(out);
        turn = lg_find_turn_object(snapshot, memory_id);
        next = lg_json_long(snapshot, "next_offset", -1);
        free(snapshot);
        if (turn) return turn;
        if (next < 0 || (size_t)next <= offset) return NULL;
        offset = (size_t)next;
    }
}

static memoria_mobile_status lg_write_turn(
    memoria_mobile_handle *handle,
    const char *memory_id,
    const char *text,
    const char *namespace_id,
    const char *source_type,
    double authority,
    const char *parent_memory_id,
    const char *role
) {
    char *id = NULL, *tx = NULL, *ns = NULL, *st = NULL, *parent = NULL, *request = NULL;
    memoria_mobile_buffer req, out = {0};
    memoria_mobile_status status;
    int needed;
    id = lg_json_escape(memory_id);
    tx = lg_json_escape(text ? text : "");
    ns = lg_json_escape(namespace_id ? namespace_id : "");
    st = lg_json_escape(source_type);
    parent = lg_json_escape(parent_memory_id ? parent_memory_id : "");
    if (!id || !tx || !ns || !st || !parent) goto fail;
    needed = snprintf(NULL, 0,
        "{\"role\":\"%s\",\"text\":\"%s\",\"memory_id\":\"%s\",\"namespace\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"parent_memory_ids\":[\"%s\"]}",
        role, tx, id, ns, st, authority, parent);
    if (needed < 0) goto fail;
    request = (char *)malloc((size_t)needed + 1u);
    if (!request) goto fail;
    snprintf(request, (size_t)needed + 1u,
        "{\"role\":\"%s\",\"text\":\"%s\",\"memory_id\":\"%s\",\"namespace\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"parent_memory_ids\":[\"%s\"]}",
        role, tx, id, ns, st, authority, parent);
    req.data = (const uint8_t *)request;
    req.size = strlen(request);
    status = memoria_mobile_learn_turn_json(handle, req, &out);
    if (out.data) memoria_mobile_free_buffer(out);
    free(id); free(tx); free(ns); free(st); free(parent); free(request);
    return status;
fail:
    free(id); free(tx); free(ns); free(st); free(parent); free(request);
    return MEMORIA_MOBILE_INTERNAL_ERROR;
}

memoria_mobile_status memoria_mobile_decide_learning_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *json = NULL, *decision_id = NULL, *candidate_id = NULL, *validator_source = NULL;
    char *validator_id = NULL, *namespace_id = NULL, *candidate = NULL, *candidate_text = NULL;
    char *candidate_source = NULL, *candidate_namespace = NULL;
    char learning_id[LG_ID_CAP];
    char response[2048];
    int accepted = 0, n;
    const char *trusted_source = NULL, *trusted_role = NULL;
    memoria_mobile_status status;

    if (!handle || !request_json.data || !request_json.size || !response_json)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = (char *)malloc(request_json.size + 1u);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(json, request_json.data, request_json.size);
    json[request_json.size] = 0;
    decision_id = lg_json_string(json, "decision_id");
    candidate_id = lg_json_string(json, "candidate_memory_id");
    validator_source = lg_json_string(json, "validator_source");
    validator_id = lg_json_string(json, "validator_id");
    namespace_id = lg_json_string(json, "namespace");
    if (!namespace_id) namespace_id = (char *)calloc(1u, 1u);
    if (!decision_id || !candidate_id || !validator_source || !validator_id || !namespace_id ||
        !lg_json_bool(json, "accepted", &accepted) || !lg_safe_id(decision_id) || !lg_safe_id(candidate_id)) {
        status = MEMORIA_MOBILE_INVALID_ARGUMENT; goto done;
    }
    if (strcmp(validator_source, "USER_CONFIRMED") == 0) {
        trusted_source = "user_assertion"; trusted_role = "user";
    } else if (strcmp(validator_source, "SENSOR_OBSERVED") == 0) {
        trusted_source = "direct_observation"; trusted_role = "sensor";
    } else {
        status = MEMORIA_MOBILE_INVALID_ARGUMENT; goto done;
    }
    n = snprintf(learning_id, sizeof(learning_id), "learning:%s", decision_id);
    if (n < 0 || (size_t)n >= sizeof(learning_id)) { status = MEMORIA_MOBILE_INVALID_ARGUMENT; goto done; }
    if (lg_load_turn(handle, learning_id)) { status = MEMORIA_MOBILE_INVALID_ARGUMENT; goto done; }

    candidate = lg_load_turn(handle, candidate_id);
    if (!candidate) { status = MEMORIA_MOBILE_NOT_FOUND; goto done; }
    candidate_text = lg_json_string(candidate, "text");
    candidate_source = lg_json_string(candidate, "source_type");
    candidate_namespace = lg_json_string(candidate, "namespace");
    if (!candidate_text || !candidate_source || !candidate_namespace ||
        strcmp(candidate_source, "assistant_generated") != 0 || strcmp(candidate_namespace, namespace_id) != 0) {
        status = MEMORIA_MOBILE_INVALID_ARGUMENT; goto done;
    }

    if (accepted) {
        status = lg_write_turn(handle, learning_id, candidate_text, namespace_id, trusted_source, 1.0, candidate_id, trusted_role);
    } else {
        status = lg_write_turn(handle, learning_id, "learning decision rejected", namespace_id, "learning_decision", 0.0, candidate_id, "system");
    }
    if (status != MEMORIA_MOBILE_OK) goto done;

    n = snprintf(response, sizeof(response),
        "{\"status\":\"OK\",\"decision_id\":\"%s\",\"candidate_memory_id\":\"%s\",\"accepted\":%s,\"validator_source\":\"%s\",\"validator_id\":\"%s\",\"learning_memory_id\":\"%s\",\"promoted\":%s,\"original_candidate_source\":\"assistant_generated\"}",
        decision_id, candidate_id, accepted ? "true" : "false", validator_source, validator_id,
        learning_id, accepted ? "true" : "false");
    if (n < 0 || (size_t)n >= sizeof(response)) { status = MEMORIA_MOBILE_INTERNAL_ERROR; goto done; }
    {
        uint8_t *buffer = (uint8_t *)malloc((size_t)n + 1u);
        if (!buffer) { status = MEMORIA_MOBILE_INTERNAL_ERROR; goto done; }
        memcpy(buffer, response, (size_t)n + 1u);
        response_json->data = buffer;
        response_json->size = (size_t)n;
    }
    status = MEMORIA_MOBILE_OK;

done:
    free(json); free(decision_id); free(candidate_id); free(validator_source); free(validator_id); free(namespace_id);
    free(candidate); free(candidate_text); free(candidate_source); free(candidate_namespace);
    return status;
}
