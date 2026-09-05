#ifndef MEMORIA_CONCEPT_RELATION_TRAVERSAL_H
#define MEMORIA_CONCEPT_RELATION_TRAVERSAL_H

#include <stddef.h>

#define MEMORIA_CONCEPT_PATH_MAX_HOPS 8u
#define MEMORIA_CONCEPT_PATH_KEY_CAP 160u
#define MEMORIA_CONCEPT_PATH_PREDICATE_CAP 96u
#define MEMORIA_CONCEPT_PATH_EVIDENCE_CAP 192u

typedef struct memoria_concept_relation_edge {
    const char *subject_key;
    const char *object_key;
    const char *predicate;
    const char *evidence_id;
    double confidence;
    int ambiguous;
} memoria_concept_relation_edge;

typedef struct memoria_concept_relation_path {
    char node_keys[MEMORIA_CONCEPT_PATH_MAX_HOPS + 1u][MEMORIA_CONCEPT_PATH_KEY_CAP];
    char predicates[MEMORIA_CONCEPT_PATH_MAX_HOPS][MEMORIA_CONCEPT_PATH_PREDICATE_CAP];
    char evidence_ids[MEMORIA_CONCEPT_PATH_MAX_HOPS][MEMORIA_CONCEPT_PATH_EVIDENCE_CAP];
    double confidence;
    size_t hops;
} memoria_concept_relation_path;

typedef enum memoria_concept_traversal_status {
    MEMORIA_CONCEPT_TRAVERSAL_INVALID = -1,
    MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED = 0,
    MEMORIA_CONCEPT_TRAVERSAL_HIT = 1
} memoria_concept_traversal_status;

memoria_concept_traversal_status memoria_concept_relation_infer_paths(
    const char *source_key,
    const char *target_key,
    const memoria_concept_relation_edge *edges,
    size_t edge_count,
    size_t max_hops,
    size_t max_paths,
    double min_confidence,
    memoria_concept_relation_path *out_paths,
    size_t out_capacity,
    size_t *out_count
);

#endif
