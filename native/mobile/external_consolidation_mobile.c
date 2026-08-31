#include "memoria_mobile.h"
#include "external_consolidation_kernel.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CONSOLIDATION_DEFAULT_MIN_DOMAINS 2u
#define CONSOLIDATION_DEFAULT_MIN_CONFIDENCE 0.75
#define CONSOLIDATION_PAGE_SIZE 64u
#define CONSOLIDATION_MAX_RELATIONS 16u
#define CONSOLIDATION_TEXT_CAP 256u

typedef struct consolidation_relation {
    char subject[CONSOLIDATION_TEXT_CAP];
    char predicate[CONSOLIDATION_TEXT_CAP];
    char object[CONSOLIDATION_TEXT_CAP];
} consolidation_relation;

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

static int consolidation_json_string_copy(const char *json, const char *key, char *out, size_t cap) {
    char pattern[96];
    const char *p, *q;
    size_t n;
    if (!json || !key || !out || cap == 0u) return 0;
    snprintf(pattern, sizeof(pattern), "\"%s\":\"", key);
    p = strstr(json, pattern);
    if (!p) return 0;
    p += strlen(pattern);
    q = p;
    while (*q) {
        if (*q == '"' && (q == p || q[-1] != '\\')) break;
        ++q;
    }
    if (*q != '"') return 0;
    n = (size_t)(q - p);
    if (n + 1u > cap) return 0;
    memcpy(out, p, n);
    out[n] = 0;
    return 1;
}

static int consolidation_ci_equal(const char *a, const char *b) {
    unsigned char ca, cb;
    if (!a || !b) return a == b;
    while (*a && *b) {
        ca = (unsigned char)*a++;
        cb = (unsigned char)*b++;
        if (ca < 128u) ca = (unsigned char)tolower(ca);
        if (cb < 128u) cb = (unsigned char)tolower(cb);
        if (ca != cb) return 0;
    }
    return *a == 0 && *b == 0;
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

static const char *consolidation_turns_start(const char *snapshot) {
    const char *p = snapshot ? strstr(snapshot, "\"turns\":[") : NULL;
    return p ? p + strlen("\"turns\":[") : NULL;
}

static const char *consolidation_turn_end(const char *turn_start) {
    const char *next_turn, *episodes;
    if (!turn_start) return NULL;
    next_turn = strstr(turn_start + 1, "},{\"memory_id\":\"");
    episodes = strstr(turn_start + 1, "],\"episodes\":[");
    if (next_turn && (!episodes || next_turn < episodes)) return next_turn + 1;
    return episodes ? episodes : turn_start + strlen(turn_start);
}

static int consolidation_span_contains(const char *start, const char *end, const char *needle) {
    const char *p;
    if (!start || !end || !needle || end <= start) return 0;
    p = strstr(start, needle);
    return p && p < end;
}

static int consolidation_span_string(
    const char *start, const char *end, const char *key, char *out, size_t cap
) {
    char pattern[96];
    const char *p, *q;
    size_t n;
    if (!start || !end || !key || !out || cap == 0u || end <= start) return 0;
    snprintf(pattern, sizeof(pattern), "\"%s\":\"", key);
    p = strstr(start, pattern);
    if (!p || p >= end) return 0;
    p += strlen(pattern);
    q = p;
    while (q < end) {
        if (*q == '"' && (q == p || q[-1] != '\\')) break;
        ++q;
    }
    if (q >= end || *q != '"') return 0;
    n = (size_t)(q - p);
    if (n + 1u > cap) return 0;
    memcpy(out, p, n);
    out[n] = 0;
    return 1;
}

static size_t consolidation_span_relations(
    const char *start, const char *end, consolidation_relation *out, size_t cap
) {
    const char *p = start;
    size_t count = 0u;
    if (!start || !end || !out || end <= start) return 0u;
    while (count < cap && (p = strstr(p, "{\"subject\":\"")) != NULL && p < end) {
        const char *relation_end = strchr(p, '}');
        if (!relation_end || relation_end > end) break;
        if (!consolidation_span_string(p, relation_end, "subject", out[count].subject, sizeof(out[count].subject)) ||
            !consolidation_span_string(p, relation_end, "predicate", out[count].predicate, sizeof(out[count].predicate)) ||
            !consolidation_span_string(p, relation_end, "object", out[count].object, sizeof(out[count].object))) break;
        ++count;
        p = relation_end + 1;
    }
    return count;
}

static int consolidation_snapshot_page(
    memoria_mobile_handle *handle, size_t offset, char **out_json, size_t *out_total
) {
    char request[160];
    memoria_mobile_buffer response = {0};
    memoria_mobile_status status;
    char *json;
    const char *counts;
    long total;
    int written;
    if (!handle || !out_json || !out_total) return 0;
    written = snprintf(request, sizeof(request),
        "{\"turn_offset\":%zu,\"turn_limit\":%u,\"episode_offset\":0,\"episode_limit\":1}",
        offset, (unsigned)CONSOLIDATION_PAGE_SIZE);
    if (written < 0 || (size_t)written >= sizeof(request)) return 0;
    status = memoria_mobile_export_snapshot_json(handle,
        (memoria_mobile_buffer){(const uint8_t *)request, (size_t)written}, &response);
    if (status != MEMORIA_MOBILE_OK || !response.data) return 0;
    json = consolidation_buffer_string(response);
    memoria_mobile_free_buffer(response);
    if (!json) return 0;
    counts = strstr(json, "\"counts\":{\"turns\":");
    if (!counts) { free(json); return 0; }
    counts += strlen("\"counts\":{\"turns\":");
    total = strtol(counts, NULL, 10);
    if (total < 0) { free(json); return 0; }
    *out_json = json;
    *out_total = (size_t)total;
    return 1;
}

static int consolidation_find_target_relations(
    memoria_mobile_handle *handle,
    const char *memory_id,
    const char *namespace_id,
    consolidation_relation *relations,
    size_t *relation_count
) {
    size_t offset = 0u, total = 0u;
    int have_total = 0;
    if (!handle || !memory_id || !namespace_id || !relations || !relation_count) return 0;
    *relation_count = 0u;
    do {
        char *snapshot = NULL;
        const char *turn, *page_end;
        size_t page_total = 0u;
        if (!consolidation_snapshot_page(handle, offset, &snapshot, &page_total)) return 0;
        if (!have_total) { total = page_total; have_total = 1; }
        turn = consolidation_turns_start(snapshot);
        page_end = turn ? strstr(turn, "],\"episodes\":[") : NULL;
        while (turn && page_end && turn < page_end && *turn == '{') {
            const char *end = consolidation_turn_end(turn);
            char current_id[CONSOLIDATION_TEXT_CAP] = {0};
            char current_namespace[CONSOLIDATION_TEXT_CAP] = {0};
            if (end > page_end) end = page_end;
            if (consolidation_span_string(turn, end, "memory_id", current_id, sizeof(current_id)) &&
                consolidation_span_string(turn, end, "namespace", current_namespace, sizeof(current_namespace)) &&
                strcmp(current_id, memory_id) == 0 && strcmp(current_namespace, namespace_id) == 0) {
                *relation_count = consolidation_span_relations(turn, end, relations, CONSOLIDATION_MAX_RELATIONS);
                free(snapshot);
                return *relation_count > 0u;
            }
            turn = (*end == '}') ? end + 1 : page_end;
            if (turn < page_end && *turn == ',') ++turn;
        }
        free(snapshot);
        offset += CONSOLIDATION_PAGE_SIZE;
    } while (offset < total);
    return 0;
}

static int consolidation_has_semantic_conflict(
    memoria_mobile_handle *handle,
    const char *memory_id,
    const char *namespace_id
) {
    consolidation_relation target[CONSOLIDATION_MAX_RELATIONS];
    size_t target_count = 0u, offset = 0u, total = 0u, i;
    int have_total = 0;
    if (!consolidation_find_target_relations(handle, memory_id, namespace_id, target, &target_count)) return 0;
    do {
        char *snapshot = NULL;
        const char *turn, *page_end;
        size_t page_total = 0u;
        if (!consolidation_snapshot_page(handle, offset, &snapshot, &page_total)) return 0;
        if (!have_total) { total = page_total; have_total = 1; }
        turn = consolidation_turns_start(snapshot);
        page_end = turn ? strstr(turn, "],\"episodes\":[") : NULL;
        while (turn && page_end && turn < page_end && *turn == '{') {
            const char *end = consolidation_turn_end(turn);
            char current_id[CONSOLIDATION_TEXT_CAP] = {0};
            char current_namespace[CONSOLIDATION_TEXT_CAP] = {0};
            char source_type[CONSOLIDATION_TEXT_CAP] = {0};
            consolidation_relation other[CONSOLIDATION_MAX_RELATIONS];
            size_t other_count, j;
            if (end > page_end) end = page_end;
            if (consolidation_span_string(turn, end, "memory_id", current_id, sizeof(current_id)) &&
                strcmp(current_id, memory_id) != 0 &&
                consolidation_span_string(turn, end, "namespace", current_namespace, sizeof(current_namespace)) &&
                strcmp(current_namespace, namespace_id) == 0 &&
                consolidation_span_string(turn, end, "source_type", source_type, sizeof(source_type)) &&
                strcmp(source_type, "external_import") == 0 &&
                consolidation_span_contains(turn, end, "\"superseded\":false")) {
                other_count = consolidation_span_relations(turn, end, other, CONSOLIDATION_MAX_RELATIONS);
                for (i = 0; i < target_count; ++i) {
                    for (j = 0; j < other_count; ++j) {
                        if (consolidation_ci_equal(target[i].subject, other[j].subject) &&
                            consolidation_ci_equal(target[i].predicate, other[j].predicate) &&
                            !consolidation_ci_equal(target[i].object, other[j].object)) {
                            free(snapshot);
                            return 1;
                        }
                    }
                }
            }
            turn = (*end == '}') ? end + 1 : page_end;
            if (turn < page_end && *turn == ',') ++turn;
        }
        free(snapshot);
        offset += CONSOLIDATION_PAGE_SIZE;
    } while (offset < total);
    return 0;
}

static memoria_mobile_status consolidation_response(
    memoria_mobile_buffer *out,
    const memoria_external_consolidation_result *result,
    const memoria_external_consolidation_policy *policy,
    int semantic_conflict
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
        "\"durable_basis\":\"external_public_provenance+diagnostic_snapshot\","
        "\"semantic_conflict_checked\":true,\"semantic_conflict\":%s}",
        memoria_external_evidence_state_name(result->state),
        result->observed_sources,
        result->independent_domains,
        result->qualifying_independent_domains,
        result->weakest_qualifying_confidence,
        policy->min_independent_domains,
        policy->min_validation_confidence,
        semantic_conflict ? "true" : "false");
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
    char memory_id[CONSOLIDATION_TEXT_CAP] = {0};
    char namespace_id[CONSOLIDATION_TEXT_CAP] = {0};
    long min_domains;
    size_t source_count = 0u;
    int semantic_conflict;

    if (!handle || !response_json || !request_json.data || request_json.size == 0u)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    request = consolidation_buffer_string(request_json);
    if (!request) return MEMORIA_MOBILE_INTERNAL_ERROR;
    min_domains = consolidation_json_long(request, "min_independent_domains", (long)CONSOLIDATION_DEFAULT_MIN_DOMAINS);
    policy.min_independent_domains = min_domains > 0 ? (size_t)min_domains : 0u;
    policy.min_validation_confidence = consolidation_json_double(
        request, "min_validation_confidence", CONSOLIDATION_DEFAULT_MIN_CONFIDENCE);
    if (!consolidation_json_string_copy(request, "memory_id", memory_id, sizeof(memory_id))) {
        free(request);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    if (!consolidation_json_string_copy(request, "namespace", namespace_id, sizeof(namespace_id)))
        namespace_id[0] = 0;
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
    semantic_conflict = consolidation_has_semantic_conflict(handle, memory_id, namespace_id);
    if (!consolidation_parse_sources(provenance_json, sources, domains, &source_count) ||
        !memoria_external_consolidation_evaluate(sources, source_count, semantic_conflict, &policy, &result)) {
        free(provenance_json);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    free(provenance_json);
    return consolidation_response(response_json, &result, &policy, semantic_conflict);
}
