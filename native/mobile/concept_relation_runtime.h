#ifndef MEMORIA_CONCEPT_RELATION_RUNTIME_H
#define MEMORIA_CONCEPT_RELATION_RUNTIME_H

#include "concept_identity_kernel.h"
#include "concept_relation_traversal.h"
#include "mobile_persistence.h"

#include <stddef.h>

typedef enum memoria_concept_relation_runtime_status {
    MEMORIA_CONCEPT_RELATION_RUNTIME_INVALID = -1,
    MEMORIA_CONCEPT_RELATION_RUNTIME_UNRESOLVED = 0,
    MEMORIA_CONCEPT_RELATION_RUNTIME_HIT = 1
} memoria_concept_relation_runtime_status;

memoria_concept_relation_runtime_status memoria_concept_relation_runtime_infer(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *source,
    const char *target,
    const char *context,
    size_t max_hops,
    size_t max_paths,
    double min_confidence,
    memoria_concept_relation_path *out_paths,
    size_t out_capacity,
    size_t *out_count
);

#endif
