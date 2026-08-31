#include "external_consolidation_kernel.h"

#include <ctype.h>
#include <string.h>

typedef struct normalized_domain_evidence {
    char domain[MEMORIA_EXTERNAL_DOMAIN_CAP];
    double best_confidence;
} normalized_domain_evidence;

static int normalize_domain(const char *src, char *dst, size_t cap) {
    size_t n, i, start = 0, end;
    if (!src || !dst || cap < 2u) return 0;
    n = strlen(src);
    while (start < n && isspace((unsigned char)src[start])) ++start;
    end = n;
    while (end > start && isspace((unsigned char)src[end - 1u])) --end;
    if (end <= start) return 0;
    if (end - start >= 4u &&
        (src[start] == 'w' || src[start] == 'W') &&
        (src[start + 1u] == 'w' || src[start + 1u] == 'W') &&
        (src[start + 2u] == 'w' || src[start + 2u] == 'W') && src[start + 3u] == '.')
        start += 4u;
    while (end > start && src[end - 1u] == '.') --end;
    if (end <= start || end - start >= cap) return 0;
    for (i = start; i < end; ++i) {
        unsigned char c = (unsigned char)src[i];
        if (isspace(c) || c == '/' || c == '\\') return 0;
        dst[i - start] = c < 128u ? (char)tolower(c) : (char)c;
    }
    dst[end - start] = 0;
    return 1;
}

static int find_domain(const normalized_domain_evidence *domains, size_t count, const char *domain) {
    size_t i;
    for (i = 0; i < count; ++i)
        if (strcmp(domains[i].domain, domain) == 0) return (int)i;
    return -1;
}

int memoria_external_consolidation_evaluate(
    const memoria_external_source_evidence *sources,
    size_t source_count,
    int semantic_conflict,
    const memoria_external_consolidation_policy *policy,
    memoria_external_consolidation_result *out
) {
    normalized_domain_evidence domains[MEMORIA_EXTERNAL_CONSOLIDATION_MAX_SOURCES];
    size_t domain_count = 0, qualifying = 0, i;
    double weakest = 0.0;
    if (!out || !policy || (source_count && !sources) ||
        source_count > MEMORIA_EXTERNAL_CONSOLIDATION_MAX_SOURCES ||
        policy->min_independent_domains == 0u ||
        policy->min_validation_confidence < 0.0 || policy->min_validation_confidence > 1.0)
        return 0;
    memset(out, 0, sizeof(*out));
    memset(domains, 0, sizeof(domains));
    out->observed_sources = source_count;

    for (i = 0; i < source_count; ++i) {
        char normalized[MEMORIA_EXTERNAL_DOMAIN_CAP];
        int index;
        double confidence = sources[i].validation_confidence;
        if (confidence < 0.0 || confidence > 1.0 ||
            !normalize_domain(sources[i].domain, normalized, sizeof(normalized))) return 0;
        index = find_domain(domains, domain_count, normalized);
        if (index < 0) {
            if (domain_count >= MEMORIA_EXTERNAL_CONSOLIDATION_MAX_SOURCES) return 0;
            snprintf(domains[domain_count].domain, sizeof(domains[domain_count].domain), "%s", normalized);
            domains[domain_count].best_confidence = confidence;
            ++domain_count;
        } else if (confidence > domains[(size_t)index].best_confidence) {
            domains[(size_t)index].best_confidence = confidence;
        }
    }

    out->independent_domains = domain_count;
    for (i = 0; i < domain_count; ++i) {
        if (domains[i].best_confidence + 1e-12 >= policy->min_validation_confidence) {
            if (qualifying == 0u || domains[i].best_confidence < weakest)
                weakest = domains[i].best_confidence;
            ++qualifying;
        }
    }
    out->qualifying_independent_domains = qualifying;
    out->weakest_qualifying_confidence = qualifying ? weakest : 0.0;

    if (semantic_conflict) out->state = MEMORIA_EXTERNAL_EVIDENCE_CONFLICT;
    else if (qualifying >= policy->min_independent_domains)
        out->state = MEMORIA_EXTERNAL_EVIDENCE_CORROBORATED;
    else out->state = MEMORIA_EXTERNAL_EVIDENCE_RAW;
    return 1;
}

const char *memoria_external_evidence_state_name(memoria_external_evidence_state state) {
    switch (state) {
        case MEMORIA_EXTERNAL_EVIDENCE_RAW: return "raw";
        case MEMORIA_EXTERNAL_EVIDENCE_CORROBORATED: return "corroborated";
        case MEMORIA_EXTERNAL_EVIDENCE_CONFLICT: return "conflict";
        default: return "unknown";
    }
}
