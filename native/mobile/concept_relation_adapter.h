#ifndef MEMORIA_CONCEPT_RELATION_ADAPTER_H
#define MEMORIA_CONCEPT_RELATION_ADAPTER_H

#include "concept_identity_kernel.h"
#include "concept_relation_traversal.h"
#include "mobile_persistence.h"

#include <stddef.h>

#define MEMORIA_CONCEPT_RELATION_ADAPTER_OK 0
#define MEMORIA_CONCEPT_RELATION_ADAPTER_INVALID 1
#define MEMORIA_CONCEPT_RELATION_ADAPTER_CAPACITY 2

typedef struct memoria_concept_relation_edge_storage {
    char subject_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    char object_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    char predicate[MEMORIA_CONCEPT_PATH_PREDICATE_CAP];
    char evidence_id[MEMORIA_CONCEPT_PATH_EVIDENCE_CAP];
    memoria_concept_relation_edge edge;
} memoria_concept_relation_edge_storage;

int memoria_concept_relation_build_edges(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    memoria_concept_relation_edge_storage *out,
    size_t out_capacity,
    size_t *out_count
);

#endif
