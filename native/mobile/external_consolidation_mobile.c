#include "memoria_mobile.h"
#include "external_consolidation_kernel.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CONSOLIDATION_DEFAULT_MIN_DOMAINS 2u
#define CONSOLIDATION_DEFAULT_MIN_CONFIDENCE 0.75

static char *consolidation_buffer_string(memoria_mobile_buffer input) {
    char *s;
    if (!input.data || input.size == 0u) return NULL;
    s = (char *)malloc(input.size + 1u);
    if (!s) return NULL;
    memcpy(s, input.data, input.size);
    s[input.size] = 0;
    return s;
}

static long consolidation_json_long(const char *json, const char *key, long fallback) {
    char pattern[96];
    const char *p;
    char *end = NULL;
    long value;
    if (!json || !key) return fallback;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p || !(p = strchr(p + strlen(pattern), ':'))) return fallback;
    value = strtol(p + 1, &end, 10);
    return end == p + 1 ? fallback : value;
}

static double consolidation_json_double(const char *json, const char *key, double fallback) {
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

static int consolidation_parse_sources(
    const char *json,
    memoria_external_source_evidence *sources,
    char domains[][MEMORIA_EXTERNAL_DOMAIN_CAP],
    size_t *out_count
) {
    const char *p = json;
    const char *domain_marker = "\"source_domain\":\"";
    const char *confidence_marker = "\"validation_confidence\":";
    size_t count = 0u;
    if (!json || !sources || !domains || !out_count) return 0;
    while ((p = strstr(p, domain_marker)) != NULL) {
        const char *start, *end, *confidence_pos;
        char *confidence_end = NULL;
        double confidence;
        size_t n;
        if (count >= MEMORIA_EXTERNAL_CONSOLIDATION_MAX_SOURCES) return 0;
        start = p + strlen(domain_marker);
        end = strchr(start, '"');
        if (!end) return 0;
        n = (size_t)(end - start);
        if (n == 0u || n >= MEMORIA_EXTERNAL_DOMAIN_CAP) return 0;
        memcpy(domains[count], start, n);
        domains[count][n] = 0;
        confidence_pos = strstr(end, confidence_marker);
        if (!confidence_pos) return 0;
        confidence_pos += strlen(confidence_marker);
        confidence = strtod(confidence_pos, &confidence_end);
        if (confidence_end == confidence_pos || confidence < 0.0 || confidence > 1.0) return 0;
        sources[count].domain = domains[count];
        sources[count].validation_confidence = confidence;
        ++count;
        p = confidence_end;
    }
    *out_count = count;
    return count > 0u;
}

static memoria_mobile_status consolidation_response(
    memoria_mobile_buffer *out,
    const memoria_external_consolidation_result *result,
    const memoria_external_consolidation_policy *policy
) {
    char json[640];
    int written;
    uint8_t *data;
    if (!out || !result || !policy) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    written = snprintf(json, sizeof(json),
        "{\"status\":\"OK\",\"knowledge_class\":\"external_public\","
        "\"evidence_state\":\"%s\",\"observed_sources\":%zu,"
        "\"independent_domains\":%zu,\"qualifying_independent_domains\":%zu,"
        "\"weakest_qualifying_confidence\":%.6f,"
        "\"policy\":{\"min_independent_domains\":%zu,\"min_validation_confidence\":%.6f},"
        "\"durable_basis\":\"external_public_provenance\","
        "\"semantic_conflict_checked\":false}",
        memoria_external_evidence_state_name(result->state),
        result->observed_sources,
        result->independent_domains,
        result->qualifying_independent_domains,
        result->weakest_qualifying_confidence,
        policy->min_independent_domains,
        policy->min_validation_confidence);
    if (written < 0 || (size_t)written >= sizeof(json)) return MEMORIA_MOBILE_INTERNAL_ERROR;
    data = (uint8_t *)malloc((size_t)written + 1u);
    if (!data) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(data, json, (size_t)written + 1u);
    out->data = data;
    out->size = (size_t)written;
    return MEMORIA_MOBILE_OK;
}

memoria_mobile_status memoria_mobile_inspect_external_consolidation_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    memoria_mobile_buffer provenance = {0};
    memoria_external_source_evidence sources[MEMORIA_EXTERNAL_CONSOLIDATION_MAX_SOURCES];
    char domains[MEMORIA_EXTERNAL_CONSOLIDATION_MAX_SOURCES][MEMORIA_EXTERNAL_DOMAIN_CAP];
    memoria_external_consolidation_policy policy;
    memoria_external_consolidation_result result;
    memoria_mobile_status status;
    char *request = NULL, *provenance_json = NULL;
    long min_domains;
    size_t source_count = 0u;

    if (!handle || !response_json || !request_json.data || request_json.size == 0u)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    request = consolidation_buffer_string(request_json);
    if (!request) return MEMORIA_MOBILE_INTERNAL_ERROR;
    min_domains = consolidation_json_long(request, "min_independent_domains", (long)CONSOLIDATION_DEFAULT_MIN_DOMAINS);
    policy.min_independent_domains = min_domains > 0 ? (size_t)min_domains : 0u;
    policy.min_validation_confidence = consolidation_json_double(
        request, "min_validation_confidence", CONSOLIDATION_DEFAULT_MIN_CONFIDENCE);
    free(request);
    if (policy.min_independent_domains == 0u ||
        policy.min_validation_confidence < 0.0 || policy.min_validation_confidence > 1.0)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    status = memoria_mobile_inspect_external_knowledge_json(handle, request_json, &provenance);
    if (status != MEMORIA_MOBILE_OK) return status;
    provenance_json = consolidation_buffer_string(provenance);
    memoria_mobile_free_buffer(provenance);
    if (!provenance_json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memset(sources, 0, sizeof(sources));
    memset(domains, 0, sizeof(domains));
    if (!consolidation_parse_sources(provenance_json, sources, domains, &source_count) ||
        !memoria_external_consolidation_evaluate(sources, source_count, 0, &policy, &result)) {
        free(provenance_json);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    free(provenance_json);
    return consolidation_response(response_json, &result, &policy);
}
