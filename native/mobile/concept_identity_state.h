#ifndef MEMORIA_CONCEPT_IDENTITY_STATE_H
#define MEMORIA_CONCEPT_IDENTITY_STATE_H

#include "concept_identity_kernel.h"

#include <stddef.h>

#define MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT 16u

typedef struct memoria_concept_state_row {
    char concept_id[MEMORIA_CONCEPT_ID_CAP];
    char namespace_name[MEMORIA_CONCEPT_NAMESPACE_CAP];
    char canonical[MEMORIA_CONCEPT_SURFACE_CAP];
    char sense_key[MEMORIA_CONCEPT_SURFACE_CAP];
    char aliases[MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT][MEMORIA_CONCEPT_SURFACE_CAP];
    size_t alias_count;
    char context_cues[MEMORIA_CONCEPT_MAX_CUES][MEMORIA_CONCEPT_SURFACE_CAP];
    size_t context_cue_count;
} memoria_concept_state_row;

int memoria_concept_state_export(
    const memoria_concept_index *index,
    memoria_concept_state_row *rows,
    size_t row_capacity,
    size_t *row_count
);

int memoria_concept_state_import(
    memoria_concept_index *index,
    const memoria_concept_state_row *rows,
    size_t row_count
);

#endif
