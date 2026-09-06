#ifndef MEMORIA_CONCEPT_RELATION_COLLECTION_H
#define MEMORIA_CONCEPT_RELATION_COLLECTION_H

#include "concept_identity_kernel.h"
#include "concept_relation_adapter.h"
#include "mobile_persistence.h"

#include <stddef.h>

#define MEMORIA_CONCEPT_COLLECTION_KEY_CAP MEMORIA_CONCEPT_PATH_KEY_CAP
#define MEMORIA_CONCEPT_COLLECTION_EVIDENCE_CAP MEMORIA_CONCEPT_PATH_EVIDENCE_CAP

typedef struct memoria_concept_collection_member {
    char member_key[MEMORIA_CONCEPT_COLLECTION_KEY_CAP];
    char evidence_id[MEMORIA_CONCEPT_COLLECTION_EVIDENCE_CAP];
    double confidence;
} memoria_concept_collection_member;

typedef enum memoria_concept_collection_status {
    MEMORIA_CONCEPT_COLLECTION_INVALID = -1,
    MEMORIA_CONCEPT_COLLECTION_UNRESOLVED = 0,
    MEMORIA_CONCEPT_COLLECTION_HIT = 1
} memoria_concept_collection_status;

memoria_concept_collection_status memoria_concept_relation_collect_type(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *type_surface,
    const char *context,
    double min_confidence,
    memoria_concept_collection_member *out,
    size_t out_capacity,
    size_t *out_count
);

#endif
