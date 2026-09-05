#include "concept_runtime_state.h"

#include <stdlib.h>
#include <string.h>

struct memoria_concept_runtime {
    memoria_concept_bdr *store;
    memoria_concept_index index;
    char fingerprint[MEMORIA_CONCEPT_FINGERPRINT_CAP];
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
        !memoria_concept_bdr_load_fingerprint(runtime->store, runtime->fingerprint, sizeof(runtime->fingerprint)) ||
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

const char *memoria_concept_runtime_fingerprint(const memoria_concept_runtime *runtime) {
    return runtime ? runtime->fingerprint : "";
}

int memoria_concept_runtime_apply_catalog(
    memoria_concept_runtime *runtime,
    const memoria_concept_state_row *rows,
    size_t row_count,
    const char *fingerprint,
    int *changed
) {
    memoria_concept_index *candidate = NULL;
    memoria_concept_state_row *canonical_rows = NULL;
    size_t canonical_count = 0;
    int ok = 0;
    if (changed) *changed = 0;
    if (!runtime || !runtime->store || (!rows && row_count) || row_count > MEMORIA_CONCEPT_MAX_CONCEPTS ||
        !fingerprint || !fingerprint[0] || strlen(fingerprint) >= MEMORIA_CONCEPT_FINGERPRINT_CAP) return 0;
    if (strcmp(runtime->fingerprint, fingerprint) == 0) return 1;
    candidate = (memoria_concept_index *)calloc(1, sizeof(*candidate));
    canonical_rows = (memoria_concept_state_row *)calloc(MEMORIA_CONCEPT_MAX_CONCEPTS, sizeof(*canonical_rows));
    if (!candidate || !canonical_rows) goto done;
    memoria_concept_index_init(candidate);
    if (memoria_concept_state_import(candidate, rows, row_count) != MEMORIA_CONCEPT_OK) goto done;
    if (memoria_concept_state_export(candidate, canonical_rows, MEMORIA_CONCEPT_MAX_CONCEPTS, &canonical_count) != MEMORIA_CONCEPT_OK) goto done;
    if (!memoria_concept_bdr_save_catalog(runtime->store, canonical_rows, canonical_count, fingerprint)) goto done;
    if (!memoria_concept_bdr_sync(runtime->store)) goto done;
    runtime->index = *candidate;
    memcpy(runtime->fingerprint, fingerprint, strlen(fingerprint) + 1u);
    if (changed) *changed = 1;
    ok = 1;
done:
    free(candidate);
    free(canonical_rows);
    return ok;
}

int memoria_concept_runtime_sync(memoria_concept_runtime *runtime) {
    return runtime && runtime->store && memoria_concept_bdr_sync(runtime->store);
}

void memoria_concept_runtime_close(memoria_concept_runtime *runtime) {
    if (!runtime) return;
    memoria_concept_bdr_close(runtime->store);
    free(runtime);
}
