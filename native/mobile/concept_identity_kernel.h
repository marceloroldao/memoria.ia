#ifndef MEMORIA_CONCEPT_IDENTITY_KERNEL_H
#define MEMORIA_CONCEPT_IDENTITY_KERNEL_H

#include <stddef.h>

#define MEMORIA_CONCEPT_MAX_CONCEPTS 32u
#define MEMORIA_CONCEPT_MAX_ALIASES 128u
#define MEMORIA_CONCEPT_MAX_CUES 8u
#define MEMORIA_CONCEPT_ID_CAP 64u
#define MEMORIA_CONCEPT_NAMESPACE_CAP 64u
#define MEMORIA_CONCEPT_SURFACE_CAP 128u

#define MEMORIA_CONCEPT_OK 0
#define MEMORIA_CONCEPT_INVALID_ARGUMENT 1
#define MEMORIA_CONCEPT_CAPACITY 2
#define MEMORIA_CONCEPT_IDENTITY_CONFLICT 3

typedef enum memoria_concept_resolution_status {
    MEMORIA_CONCEPT_UNRESOLVED = 0,
    MEMORIA_CONCEPT_HIT = 1
} memoria_concept_resolution_status;

typedef enum memoria_concept_resolution_reason {
    MEMORIA_CONCEPT_REASON_NONE = 0,
    MEMORIA_CONCEPT_REASON_EMPTY = 1,
    MEMORIA_CONCEPT_REASON_UNKNOWN = 2,
    MEMORIA_CONCEPT_REASON_AMBIGUOUS = 3,
    MEMORIA_CONCEPT_REASON_CONTEXT_CUE = 4,
    MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT = 5
} memoria_concept_resolution_reason;

typedef struct memoria_concept_definition {
    const char *concept_id;
    const char *namespace_name;
    const char *canonical_name;
    const char *sense_key;
    const char *const *aliases;
    size_t alias_count;
    const char *const *context_cues;
    size_t context_cue_count;
} memoria_concept_definition;

typedef struct memoria_concept_record {
    char concept_id[MEMORIA_CONCEPT_ID_CAP];
    char namespace_name[MEMORIA_CONCEPT_NAMESPACE_CAP];
    char canonical[MEMORIA_CONCEPT_SURFACE_CAP];
    char sense_key[MEMORIA_CONCEPT_SURFACE_CAP];
    char context_cues[MEMORIA_CONCEPT_MAX_CUES][MEMORIA_CONCEPT_SURFACE_CAP];
    size_t context_cue_count;
} memoria_concept_record;

typedef struct memoria_concept_alias_record {
    char namespace_name[MEMORIA_CONCEPT_NAMESPACE_CAP];
    char surface[MEMORIA_CONCEPT_SURFACE_CAP];
    char concept_id[MEMORIA_CONCEPT_ID_CAP];
} memoria_concept_alias_record;

typedef struct memoria_concept_index {
    memoria_concept_record concepts[MEMORIA_CONCEPT_MAX_CONCEPTS];
    size_t concept_count;
    memoria_concept_alias_record aliases[MEMORIA_CONCEPT_MAX_ALIASES];
    size_t alias_count;
} memoria_concept_index;

typedef struct memoria_concept_resolution {
    memoria_concept_resolution_status status;
    memoria_concept_resolution_reason reason;
    char normalized_query[MEMORIA_CONCEPT_SURFACE_CAP];
    char concept_id[MEMORIA_CONCEPT_ID_CAP];
    size_t candidate_count;
} memoria_concept_resolution;

void memoria_concept_index_init(memoria_concept_index *index);
int memoria_concept_normalize(const char *input, char *output, size_t output_cap);
int memoria_concept_register(memoria_concept_index *index, const memoria_concept_definition *definition);
memoria_concept_resolution memoria_concept_resolve(
    const memoria_concept_index *index,
    const char *namespace_name,
    const char *surface
);
memoria_concept_resolution memoria_concept_resolve_with_context(
    const memoria_concept_index *index,
    const char *namespace_name,
    const char *surface,
    const char *context
);

#endif
