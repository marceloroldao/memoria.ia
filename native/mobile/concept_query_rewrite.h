#ifndef MEMORIA_CONCEPT_QUERY_REWRITE_H
#define MEMORIA_CONCEPT_QUERY_REWRITE_H

#include "concept_identity_kernel.h"

#include <stddef.h>

#define MEMORIA_CONCEPT_QUERY_CAP 512u
#define MEMORIA_CONCEPT_QUERY_MAX_IDS 16u

typedef enum memoria_concept_rewrite_status {
    MEMORIA_CONCEPT_REWRITE_UNCHANGED = 0,
    MEMORIA_CONCEPT_REWRITE_REWRITTEN = 1,
    MEMORIA_CONCEPT_REWRITE_UNRESOLVED = 2
} memoria_concept_rewrite_status;

typedef enum memoria_concept_rewrite_reason {
    MEMORIA_CONCEPT_REWRITE_REASON_NONE = 0,
    MEMORIA_CONCEPT_REWRITE_REASON_EMPTY = 1,
    MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS = 2,
    MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS_CONTEXT = 3,
    MEMORIA_CONCEPT_REWRITE_REASON_MISSING_CONCEPT = 4,
    MEMORIA_CONCEPT_REWRITE_REASON_CAPACITY = 5
} memoria_concept_rewrite_reason;

typedef struct memoria_concept_rewrite_result {
    memoria_concept_rewrite_status status;
    memoria_concept_rewrite_reason reason;
    char original_query[MEMORIA_CONCEPT_QUERY_CAP];
    char rewritten_query[MEMORIA_CONCEPT_QUERY_CAP];
    char concept_ids[MEMORIA_CONCEPT_QUERY_MAX_IDS][MEMORIA_CONCEPT_ID_CAP];
    size_t concept_count;
} memoria_concept_rewrite_result;

memoria_concept_rewrite_result memoria_concept_rewrite_query(
    const memoria_concept_index *index,
    const char *namespace_name,
    const char *query,
    size_t max_alias_words
);

#endif
