#ifndef MEMORIA_SEMANTIC_CONSOLIDATION_KERNEL_H
#define MEMORIA_SEMANTIC_CONSOLIDATION_KERNEL_H

#include <stddef.h>

#define MEMORIA_SEMANTIC_CONSOLIDATION_MAX_SUPPORTS 16u
#define MEMORIA_SEMANTIC_CONSOLIDATION_TEXT_CAP 96u
#define MEMORIA_SEMANTIC_CONSOLIDATION_PREDICATE_CAP 32u
#define MEMORIA_SEMANTIC_CONSOLIDATION_ID_CAP 384u

typedef struct memoria_semantic_support {
    const char *namespace_id;
    const char *subject;
    const char *predicate;
    const char *object;
    const char *support_memory_id;
    const char *factual_root_id;
    double confidence;
    int factual_active;
} memoria_semantic_support;

typedef struct memoria_semantic_candidate {
    char namespace_id[MEMORIA_SEMANTIC_CONSOLIDATION_ID_CAP];
    char subject[MEMORIA_SEMANTIC_CONSOLIDATION_TEXT_CAP];
    char predicate[MEMORIA_SEMANTIC_CONSOLIDATION_PREDICATE_CAP];
    char object[MEMORIA_SEMANTIC_CONSOLIDATION_TEXT_CAP];
    char support_memory_ids[MEMORIA_SEMANTIC_CONSOLIDATION_MAX_SUPPORTS][MEMORIA_SEMANTIC_CONSOLIDATION_ID_CAP];
    char factual_root_ids[MEMORIA_SEMANTIC_CONSOLIDATION_MAX_SUPPORTS][MEMORIA_SEMANTIC_CONSOLIDATION_ID_CAP];
    size_t support_count;
    double confidence;
} memoria_semantic_candidate;

/*
 * Build conservative repeated-fact candidates from already lineage-resolved
 * supports. The caller remains responsible for determining factual lineage and
 * persistence. This kernel only enforces exact normalized claim equality,
 * namespace isolation, distinct factual-root counting and deterministic support
 * selection.
 */
size_t memoria_semantic_consolidation_candidates(
    const memoria_semantic_support *supports,
    size_t support_count,
    size_t min_independent_roots,
    memoria_semantic_candidate *out,
    size_t out_capacity
);

#endif
