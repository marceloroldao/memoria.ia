#ifndef MEMORIA_CONCEPT_RUNTIME_STATE_H
#define MEMORIA_CONCEPT_RUNTIME_STATE_H

#include "concept_identity_bdr.h"
#include "concept_identity_kernel.h"
#include "concept_identity_state.h"

#define MEMORIA_CONCEPT_FINGERPRINT_CAP 96u

typedef struct memoria_concept_runtime memoria_concept_runtime;

int memoria_concept_runtime_open(
    const char *data_dir,
    const char *organization_id,
    memoria_concept_runtime **out
);

const memoria_concept_index *memoria_concept_runtime_index(const memoria_concept_runtime *runtime);
const char *memoria_concept_runtime_fingerprint(const memoria_concept_runtime *runtime);
int memoria_concept_runtime_apply_catalog(
    memoria_concept_runtime *runtime,
    const memoria_concept_state_row *rows,
    size_t row_count,
    const char *fingerprint,
    int *changed
);
int memoria_concept_runtime_sync(memoria_concept_runtime *runtime);
void memoria_concept_runtime_close(memoria_concept_runtime *runtime);

#endif
