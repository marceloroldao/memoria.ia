#ifndef MEMORIA_SEMANTIC_CONSOLIDATION_REQUEST_H
#define MEMORIA_SEMANTIC_CONSOLIDATION_REQUEST_H

#include "semantic_consolidation_kernel.h"

#include <stddef.h>

/*
 * Build a deterministic internal learn-turn JSON request for one candidate.
 * The request is a derived_relation with explicit support-memory parents, so
 * normal native persistence, lineage, correction and restart semantics apply.
 */
int memoria_semantic_consolidation_request_json(
    const memoria_semantic_candidate *candidate,
    long order,
    char *out,
    size_t out_capacity
);

#endif
