#include "concept_runtime_state.h"

#include <stdlib.h>

struct memoria_concept_runtime {
    memoria_concept_bdr *store;
    memoria_concept_index index;
};

int memoria_concept_runtime_open(
    const char *data_dir,
    const char *organization_id,
    memoria_concept_runtime **out
) {
    memoria_concept_runtime *runtime;
    memoria_concept_state_row rows[MEMORIA_CONCEPT_MAX_CONCEPTS];
    size_t row_count = 0;
    if (!data_dir || !*data_dir || !organization_id || !*organization_id || !out) return 0;
    *out = NULL;
    runtime = (memoria_concept_runtime *)calloc(1, sizeof(*runtime));
    if (!runtime) return 0;
    memoria_concept_index_init(&runtime->index);
    if (!memoria_concept_bdr_open(data_dir, organization_id, &runtime->store) ||
        !memoria_concept_bdr_load(runtime->store, rows, MEMORIA_CONCEPT_MAX_CONCEPTS, &row_count) ||
        memoria_concept_state_import(&runtime->index, rows, row_count) != MEMORIA_CONCEPT_OK) {
        memoria_concept_runtime_close(runtime);
        return 0;
    }
    *out = runtime;
    return 1;
}

const memoria_concept_index *memoria_concept_runtime_index(const memoria_concept_runtime *runtime) {
    return runtime ? &runtime->index : NULL;
}

int memoria_concept_runtime_sync(memoria_concept_runtime *runtime) {
    return runtime && runtime->store && memoria_concept_bdr_sync(runtime->store);
}

void memoria_concept_runtime_close(memoria_concept_runtime *runtime) {
    if (!runtime) return;
    memoria_concept_bdr_close(runtime->store);
    free(runtime);
}
