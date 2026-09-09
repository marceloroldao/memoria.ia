#include "memoria_mobile.h"
#include "relation_extractor.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RV_MAX_RELATIONS 4u
#define RV_PACKET_CAP 32768u
#define RV_RESPONSE_CAP 32768u
#define RV_ID_CAP 384u

static char *rv_json_string(const char *json, const char *key) {
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
        } else {
            out[w++] = *p++;
        }
    }
    out[w] = 0;
    return out;
}

static char *rv_json_escape(const char *text) {
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

static int rv_append(char *out, size_t cap, size_t *used, const char *text) {
    size_t n;
    if (!out || !used || !text) return 0;
    n = strlen(text);
    if (*used + n + 1u > cap) return 0;
    memcpy(out + *used, text, n);
    *used += n;
    out[*used] = 0;
    return 1;
}

static int rv_append_json_string(char *out, size_t cap, size_t *used, const char *text) {
    char *escaped = rv_json_escape(text);
    int ok;
    if (!escaped) return 0;
    ok = rv_append(out, cap, used, "\"") && rv_append(out, cap, used, escaped) && rv_append(out, cap, used, "\"");
    free(escaped);
    return ok;
}

static long rv_json_long(const char *json, const char *key, long fallback) {
    char pattern[128];
    const char *p;
    char *end = NULL;
    long value;
    if (!json || !key) return fallback;
    if (snprintf(pattern, sizeof(pattern), "\"%s\"", key) < 0) return fallback;
    p = strstr(json, pattern);
    if (!p) return fallback;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return fallback;
    value = strtol(p + 1, &end, 10);
    return end == p + 1 ? fallback : value;
}

static int rv_memory_id_exists(memoria_mobile_handle *handle, const char *memory_id) {
    size_t offset = 0u;
    char request[128];
    char exact[RV_ID_CAP + 32u];
    if (!handle || !memory_id || !*memory_id) return 0;
    if (snprintf(exact, sizeof(exact), "\"memory_id\":\"%s\"", memory_id) < 0) return 0;
    for (;;) {
        memoria_mobile_buffer req, out = {0};
        memoria_mobile_status status;
        char *snapshot;
        long next;
        int found;
        int n = snprintf(request, sizeof(request), "{\"turn_offset\":%lu,\"turn_limit\":64,\"episode_limit\":1}", (unsigned long)offset);
        if (n < 0 || (size_t)n >= sizeof(request)) return 0;
        req.data = (const uint8_t *)request;
        req.size = strlen(request);
        status = memoria_mobile_export_snapshot_json(handle, req, &out);
        if (status != MEMORIA_MOBILE_OK || !out.data || !out.size) {
            if (out.data) memoria_mobile_free_buffer(out);
            return 0;
        }
        snapshot = (char *)malloc(out.size + 1u);
        if (!snapshot) { memoria_mobile_free_buffer(out); return 0; }
        memcpy(snapshot, out.data, out.size);
        snapshot[out.size] = 0;
        memoria_mobile_free_buffer(out);
        found = strstr(snapshot, exact) != NULL;
        next = rv_json_long(snapshot, "next_offset", -1);
        free(snapshot);
        if (found) return 1;
        if (next < 0 || (size_t)next <= offset) return 0;
        offset = (size_t)next;
    }
}

static const char *rv_claim_status(const char *packet, const memoria_relation *claim) {
    char *subject = NULL, *predicate = NULL, *object = NULL;
    char slot[512], exact[768];
    const char *status = "UNVERIFIED";
    if (!packet || !claim) return status;
    subject = rv_json_escape(claim->subject);
    predicate = rv_json_escape(claim->predicate);
    object = rv_json_escape(claim->object);
    if (!subject || !predicate || !object) goto done;
    if (snprintf(slot, sizeof(slot), "\"subject\":\"%s\",\"predicate\":\"%s\",\"object\":\"", subject, predicate) < 0) goto done;
    if (snprintf(exact, sizeof(exact), "\"subject\":\"%s\",\"predicate\":\"%s\",\"object\":\"%s\"", subject, predicate, object) < 0) goto done;
    if (strstr(packet, exact)) status = "SUPPORTED_BY_CONTEXT";
    else if (strstr(packet, slot)) status = "CONFLICTS_WITH_CONTEXT";
done:
    free(subject); free(predicate); free(object);
    return status;
}

static memoria_mobile_status rv_compile_packet(
    memoria_mobile_handle *handle,
    const char *query,
    const char *namespace_id,
    char **packet_out
) {
    char *q = NULL, *ns = NULL, *request = NULL, *packet = NULL;
    memoria_mobile_buffer req, out = {0};
    memoria_mobile_status status;
    int needed;
    if (!handle || !query || !packet_out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    *packet_out = NULL;
    q = rv_json_escape(query);
    ns = rv_json_escape(namespace_id ? namespace_id : "");
    if (!q || !ns) { free(q); free(ns); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    needed = snprintf(NULL, 0, "{\"query\":\"%s\",\"namespace\":\"%s\"}", q, ns);
    if (needed < 0) { free(q); free(ns); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    request = (char *)malloc((size_t)needed + 1u);
    if (!request) { free(q); free(ns); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    snprintf(request, (size_t)needed + 1u, "{\"query\":\"%s\",\"namespace\":\"%s\"}", q, ns);
    free(q); free(ns);
    req.data = (const uint8_t *)request;
    req.size = strlen(request);
    status = memoria_mobile_compile_context_json(handle, req, &out);
    free(request);
    if (status != MEMORIA_MOBILE_OK && status != MEMORIA_MOBILE_UNRESOLVED) {
        if (out.data) memoria_mobile_free_buffer(out);
        return status;
    }
    if (!out.data || !out.size) return MEMORIA_MOBILE_INTERNAL_ERROR;
    packet = (char *)malloc(out.size + 1u);
    if (!packet) { memoria_mobile_free_buffer(out); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    memcpy(packet, out.data, out.size);
    packet[out.size] = 0;
    memoria_mobile_free_buffer(out);
    *packet_out = packet;
    return status;
}

static memoria_mobile_status rv_persist_candidate(
    memoria_mobile_handle *handle,
    const char *candidate_id,
    const char *response_text,
    const char *namespace_id
) {
    char *id = NULL, *text = NULL, *ns = NULL, *request = NULL;
    memoria_mobile_buffer req, out = {0};
    memoria_mobile_status status;
    int needed;
    id = rv_json_escape(candidate_id);
    text = rv_json_escape(response_text);
    ns = rv_json_escape(namespace_id ? namespace_id : "");
    if (!id || !text || !ns) { free(id); free(text); free(ns); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    needed = snprintf(NULL, 0,
        "{\"role\":\"assistant\",\"text\":\"%s\",\"memory_id\":\"%s\",\"namespace\":\"%s\",\"source_type\":\"assistant_generated\",\"source_authority\":0.25}",
        text, id, ns);
    if (needed < 0) { free(id); free(text); free(ns); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    request = (char *)malloc((size_t)needed + 1u);
    if (!request) { free(id); free(text); free(ns); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    snprintf(request, (size_t)needed + 1u,
        "{\"role\":\"assistant\",\"text\":\"%s\",\"memory_id\":\"%s\",\"namespace\":\"%s\",\"source_type\":\"assistant_generated\",\"source_authority\":0.25}",
        text, id, ns);
    free(id); free(text); free(ns);
    req.data = (const uint8_t *)request;
    req.size = strlen(request);
    status = memoria_mobile_learn_turn_json(handle, req, &out);
    free(request);
    if (out.data) memoria_mobile_free_buffer(out);
    return status;
}

memoria_mobile_status memoria_mobile_validate_response_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *json = NULL, *query = NULL, *response_id = NULL, *model_id = NULL, *response_text = NULL, *namespace_id = NULL;
    char candidate_id[RV_ID_CAP];
    char *packet = NULL;
    memoria_relation claims[RV_MAX_RELATIONS];
    size_t claim_count, i, used = 0;
    char *result = NULL;
    memoria_mobile_status context_status, persist_status;
    const char *overall = "UNVERIFIED";
    int saw_supported = 0, saw_conflict = 0;

    if (!handle || !request_json.data || !request_json.size || !response_json)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = (char *)malloc(request_json.size + 1u);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(json, request_json.data, request_json.size);
    json[request_json.size] = 0;
    query = rv_json_string(json, "query");
    response_id = rv_json_string(json, "response_id");
    model_id = rv_json_string(json, "model_id");
    response_text = rv_json_string(json, "response_text");
    namespace_id = rv_json_string(json, "namespace");
    if (!namespace_id) namespace_id = (char *)calloc(1u, 1u);
    if (!query || !*query || !response_id || !*response_id || !model_id || !*model_id || !response_text || !*response_text || !namespace_id) {
        free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    if (snprintf(candidate_id, sizeof(candidate_id), "response:%s", response_id) < 0 || strlen(candidate_id) >= sizeof(candidate_id)) {
        free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    if (rv_memory_id_exists(handle, candidate_id)) {
        free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }

    context_status = rv_compile_packet(handle, query, namespace_id, &packet);
    if (context_status != MEMORIA_MOBILE_OK && context_status != MEMORIA_MOBILE_UNRESOLVED) {
        free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id); free(packet);
        return context_status;
    }

    memset(claims, 0, sizeof(claims));
    claim_count = memoria_extract_relations(response_text, claims, RV_MAX_RELATIONS);
    for (i = 0; i < claim_count; ++i) {
        const char *status = context_status == MEMORIA_MOBILE_OK ? rv_claim_status(packet, &claims[i]) : "UNVERIFIED";
        if (strcmp(status, "CONFLICTS_WITH_CONTEXT") == 0) saw_conflict = 1;
        else if (strcmp(status, "SUPPORTED_BY_CONTEXT") == 0) saw_supported = 1;
    }
    overall = saw_conflict ? "CONFLICTS_WITH_CONTEXT" : (saw_supported ? "SUPPORTED_BY_CONTEXT" : "UNVERIFIED");

    persist_status = rv_persist_candidate(handle, candidate_id, response_text, namespace_id);
    if (persist_status != MEMORIA_MOBILE_OK) {
        free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id); free(packet);
        return persist_status;
    }

    result = (char *)malloc(RV_RESPONSE_CAP);
    if (!result) {
        free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id); free(packet);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    result[0] = 0;
    if (!rv_append(result, RV_RESPONSE_CAP, &used, "{\"status\":\"OK\",\"response_id\":") ||
        !rv_append_json_string(result, RV_RESPONSE_CAP, &used, response_id) ||
        !rv_append(result, RV_RESPONSE_CAP, &used, ",\"model_id\":") ||
        !rv_append_json_string(result, RV_RESPONSE_CAP, &used, model_id) ||
        !rv_append(result, RV_RESPONSE_CAP, &used, ",\"candidate_memory_id\":") ||
        !rv_append_json_string(result, RV_RESPONSE_CAP, &used, candidate_id) ||
        !rv_append(result, RV_RESPONSE_CAP, &used, ",\"source_type\":\"assistant_generated\",\"promoted\":false,\"overall_status\":") ||
        !rv_append_json_string(result, RV_RESPONSE_CAP, &used, overall) ||
        !rv_append(result, RV_RESPONSE_CAP, &used, ",\"claims\":[")) goto build_fail;

    for (i = 0; i < claim_count; ++i) {
        const char *claim_status = context_status == MEMORIA_MOBILE_OK ? rv_claim_status(packet, &claims[i]) : "UNVERIFIED";
        char confidence[64];
        if (i && !rv_append(result, RV_RESPONSE_CAP, &used, ",")) goto build_fail;
        if (!rv_append(result, RV_RESPONSE_CAP, &used, "{\"subject\":") ||
            !rv_append_json_string(result, RV_RESPONSE_CAP, &used, claims[i].subject) ||
            !rv_append(result, RV_RESPONSE_CAP, &used, ",\"predicate\":") ||
            !rv_append_json_string(result, RV_RESPONSE_CAP, &used, claims[i].predicate) ||
            !rv_append(result, RV_RESPONSE_CAP, &used, ",\"object\":") ||
            !rv_append_json_string(result, RV_RESPONSE_CAP, &used, claims[i].object) ||
            !rv_append(result, RV_RESPONSE_CAP, &used, ",\"validation_status\":") ||
            !rv_append_json_string(result, RV_RESPONSE_CAP, &used, claim_status)) goto build_fail;
        if (snprintf(confidence, sizeof(confidence), ",\"confidence\":%.6f}", claims[i].confidence) < 0 ||
            !rv_append(result, RV_RESPONSE_CAP, &used, confidence)) goto build_fail;
    }
    if (!rv_append(result, RV_RESPONSE_CAP, &used, "]}")) goto build_fail;

    response_json->data = (const uint8_t *)result;
    response_json->size = used;
    free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id); free(packet);
    return MEMORIA_MOBILE_OK;

build_fail:
    free(result); free(json); free(query); free(response_id); free(model_id); free(response_text); free(namespace_id); free(packet);
    return MEMORIA_MOBILE_INTERNAL_ERROR;
}
