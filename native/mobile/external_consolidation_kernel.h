#ifndef MEMORIA_EXTERNAL_CONSOLIDATION_KERNEL_H
#define MEMORIA_EXTERNAL_CONSOLIDATION_KERNEL_H

#include <stddef.h>

#define MEMORIA_EXTERNAL_CONSOLIDATION_MAX_SOURCES 64u
#define MEMORIA_EXTERNAL_DOMAIN_CAP 192u

typedef enum memoria_external_evidence_state {
    MEMORIA_EXTERNAL_EVIDENCE_RAW = 0,
    MEMORIA_EXTERNAL_EVIDENCE_CORROBORATED = 1,
    MEMORIA_EXTERNAL_EVIDENCE_CONFLICT = 2
} memoria_external_evidence_state;

typedef struct memoria_external_source_evidence {
    const char *domain;
    double validation_confidence;
} memoria_external_source_evidence;

typedef struct memoria_external_consolidation_policy {
    size_t min_independent_domains;
    double min_validation_confidence;
} memoria_external_consolidation_policy;

typedef struct memoria_external_consolidation_result {
    memoria_external_evidence_state state;
    size_t observed_sources;
    size_t independent_domains;
    size_t qualifying_independent_domains;
    double weakest_qualifying_confidence;
} memoria_external_consolidation_result;

/*
 * Deterministically classify external/public evidence without declaring it
 * "true". Multiple URLs from the same source_domain count as one independent
 * domain. A known semantic conflict always yields CONFLICT. CORROBORATED means
 * only that the configured independent-source policy was satisfied.
 *
 * Returns non-zero on a valid evaluation. The function performs no I/O, LLM,
 * embedding, network lookup or domain-specific inference.
 */
int memoria_external_consolidation_evaluate(
    const memoria_external_source_evidence *sources,
    size_t source_count,
    int semantic_conflict,
    const memoria_external_consolidation_policy *policy,
    memoria_external_consolidation_result *out
);

const char *memoria_external_evidence_state_name(memoria_external_evidence_state state);

#endif
