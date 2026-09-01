#include "external_relevance_mobile.h"
#include "external_relevance_kernel.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RELEVANCE_MIN_QUERY_COVERAGE 0.60
#define RELEVANCE_MIN_ANCHOR_MATCHES 1u
#define RELEVANCE_EARLY_WINDOW_TOKENS 24u

static char *buffer_string(memoria_mobile_buffer input) {
    char *s;
    if (!input.data || input.size == 0u) return NULL;
    s = (char *)malloc(input.size + 1u);
    if (!s) return NULL;
    memcpy(s, input.data, input.size);
    s[input.size] = 0;
    return s;
}

static char *json_string_dup(const char *json, const char *key) {
    char pattern[96];
    const char *p, *q;
    char *out;
    size_t n;
    if (!json || !key) return NULL;
    snprintf(pattern, sizeof(pattern), "\"%s\":\"", key);
    p = strstr(json, pattern);
    if (!p) return NULL;
    p += strlen(pattern);
    q = p;
    while (*q) {
        if (*q == '"' && (q == p || q[-1] != '\\')) break;
        ++q;
    }
    if (*q != '"') return NULL;
    n = (size_t)(q - p);
    out = (char *)malloc(n + 1u);
    if (!out) return NULL;
    memcpy(out, p, n);
    out[n] = 0;
    return out;
}

static memoria_mobile_status set_rejection_response(
    memoria_mobile_buffer *out,
    memoria_mobile_status status,
    const memoria_external_relevance_result *r
) {
    char json[512];
    int written;
    uint8_t *data;
    if (!out || !r) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    written = snprintf(json, sizeof(json),
        "{\"status\":\"REJECTED\",\"reason\":\"external evidence below deterministic relevance gate\","
        "\"persisted\":false,\"retrieval_relevance\":%.6f,\"query_coverage\":%.6f,"
        "\"matched_query_tokens\":%zu,\"query_content_tokens\":%zu,\"early_match_ratio\":%.6f}",
        r->relevance_score, r->query_coverage, r->matched_query_tokens,
        r->query_content_tokens, r->early_match_ratio);
    if (written < 0 || (size_t)written >= sizeof(json)) return MEMORIA_MOBILE_INTERNAL_ERROR;
    data = (uint8_t *)malloc((size_t)written + 1u);
    if (!data) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(data, json, (size_t)written + 1u);
    out->data = data;
    out->size = (size_t)written;
    return status;
}

memoria_mobile_status memoria_mobile_learn_external_knowledge_guarded_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    memoria_external_relevance_policy policy;
    memoria_external_relevance_result result;
    char *request = NULL, *origin_query = NULL, *content = NULL;

    if (!handle || !response_json || !request_json.data || request_json.size == 0u)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    request = buffer_string(request_json);
    if (!request) return MEMORIA_MOBILE_INTERNAL_ERROR;
    origin_query = json_string_dup(request, "origin_query");
    content = json_string_dup(request, "content");
    free(request);
    if (!origin_query || !content || !*origin_query || !*content) {
        free(origin_query);
        free(content);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }

    policy.min_query_coverage = RELEVANCE_MIN_QUERY_COVERAGE;
    policy.min_anchor_matches = RELEVANCE_MIN_ANCHOR_MATCHES;
    policy.early_window_tokens = RELEVANCE_EARLY_WINDOW_TOKENS;
    if (!memoria_external_relevance_evaluate(origin_query, content, &policy, &result)) {
        free(origin_query);
        free(content);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    free(origin_query);
    free(content);

    if (!result.accepted)
        return set_rejection_response(response_json, MEMORIA_MOBILE_UNRESOLVED, &result);

    return memoria_mobile_learn_external_knowledge_json(handle, request_json, response_json);
}
