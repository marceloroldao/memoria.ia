#ifndef MEMORIA_TEMPORAL_STATE_ADAPTER_H
#define MEMORIA_TEMPORAL_STATE_ADAPTER_H

#include <stddef.h>
#include "relation_extractor.h"
#include "temporal_state_kernel.h"

typedef struct memoria_temporal_relation_source {
    const char *memory_id;
    const memoria_relation *relations;
    size_t relation_count;
    long order;
    double authority;
} memoria_temporal_relation_source;

/*
 * Builds state facts from already extracted relations.
 * Structural mapping is intentionally domain-agnostic:
 *   relation.subject   -> entity key
 *   relation.predicate -> property key
 *   relation.object    -> value
 * Historical ordering comes from the owning memory turn.
 */
size_t memoria_temporal_build_facts(
    const memoria_temporal_relation_source *sources,
    size_t source_count,
    memoria_state_fact *out,
    size_t capacity
);

#endif
