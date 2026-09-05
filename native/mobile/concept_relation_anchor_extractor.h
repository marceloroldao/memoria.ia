#ifndef MEMORIA_CONCEPT_RELATION_ANCHOR_EXTRACTOR_H
#define MEMORIA_CONCEPT_RELATION_ANCHOR_EXTRACTOR_H

#include <stddef.h>

typedef enum memoria_relation_anchor_status {
    MEMORIA_RELATION_ANCHOR_INVALID = -1,
    MEMORIA_RELATION_ANCHOR_UNRESOLVED = 0,
    MEMORIA_RELATION_ANCHOR_HIT = 1
} memoria_relation_anchor_status;

memoria_relation_anchor_status memoria_relation_anchor_extract(
    const char *query,
    char *source,
    size_t source_cap,
    char *target,
    size_t target_cap
);

#endif
