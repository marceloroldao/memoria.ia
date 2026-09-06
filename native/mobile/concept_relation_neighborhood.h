#ifndef MEMORIA_CONCEPT_RELATION_NEIGHBORHOOD_H
#define MEMORIA_CONCEPT_RELATION_NEIGHBORHOOD_H

#include "concept_identity_kernel.h"
#include "concept_relation_adapter.h"
#include "mobile_persistence.h"

#include <stddef.h>

#define MEMORIA_CONCEPT_NEIGHBOR_KEY_CAP MEMORIA_CONCEPT_PATH_KEY_CAP
#define MEMORIA_CONCEPT_NEIGHBOR_PREDICATE_CAP MEMORIA_CONCEPT_PATH_PREDICATE_CAP
#define MEMORIA_CONCEPT_NEIGHBOR_EVIDENCE_CAP MEMORIA_CONCEPT_PATH_EVIDENCE_CAP

typedef struct memoria_concept_relation_neighbor {
    char node_key[MEMORIA_CONCEPT_NEIGHBOR_KEY_CAP];
    char predicate[MEMORIA_CONCEPT_NEIGHBOR_PREDICATE_CAP];
    char evidence_id[MEMORIA_CONCEPT_NEIGHBOR_EVIDENCE_CAP];
    double confidence;
} memoria_concept_relation_neighbor;

typedef enum memoria_concept_neighborhood_status {
    MEMORIA_CONCEPT_NEIGHBORHOOD_INVALID = -1,
    MEMORIA_CONCEPT_NEIGHBORHOOD_UNRESOLVED = 0,
    MEMORIA_CONCEPT_NEIGHBORHOOD_HIT = 1
} memoria_concept_neighborhood_status;

memoria_concept_neighborhood_status memoria_concept_relation_neighborhood(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *source,
    const char *context,
    double min_confidence,
    memoria_concept_relation_neighbor *out,
    size_t out_capacity,
    size_t *out_count
);

#endif
