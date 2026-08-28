#ifndef MEMORIA_SEMANTIC_KERNEL_H
#define MEMORIA_SEMANTIC_KERNEL_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum memoria_kernel_status {
    MEMORIA_KERNEL_HIT = 0,
    MEMORIA_KERNEL_UNRESOLVED = 1
} memoria_kernel_status;

typedef struct memoria_kernel_candidate {
    const char *memory_id;
    const char *root_memory_id;
    const char *context;
    double source_authority;
    int created_order;
} memoria_kernel_candidate;

typedef struct memoria_kernel_result {
    memoria_kernel_status status;
    size_t selected_index;
    double relevance;
} memoria_kernel_result;

/*
 * Portable, domain-agnostic selection kernel.
 *
 * This slice intentionally consumes already-materialized candidate provenance.
 * Relation extraction, lineage construction and durable persistence remain
 * separate parity slices. Unsupported/ambiguous input fails closed.
 */
memoria_kernel_result memoria_kernel_resolve(
    const char *query,
    const memoria_kernel_candidate *candidates,
    size_t candidate_count
);

#ifdef __cplusplus
}
#endif

#endif
