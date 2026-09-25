#ifndef MEMORIA_STRUCTURAL_TEXT_RUNTIME_H
#define MEMORIA_STRUCTURAL_TEXT_RUNTIME_H

#include "structural_text_kernel.h"

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct bdr_atomic_c_handle bdr_atomic_c_handle;
typedef struct memoria_structural_text_runtime memoria_structural_text_runtime;

typedef struct memoria_structural_text_occurrence {
    char *source_id;
    char *source_text;
    char *source_kind;
    unsigned long sequence;
} memoria_structural_text_occurrence;

typedef struct memoria_structural_text_context {
    char *source_text;
    char *source_id;
    char *source_kind;
    char **source_ids;
    size_t source_id_count;
    memoria_structural_text_occurrence *occurrences;
    size_t occurrence_count;
    unsigned long sequence;
    double score;
    size_t exact_overlap;
    size_t surface_overlap;
    double association_mass;
    size_t repetitions;
} memoria_structural_text_context;

/*
 * Open the structural text runtime over the SAME BDR handle already owned by
 * Memoria.ia mobile persistence. The runtime borrows db and never closes it.
 *
 * Raw observations are authoritative. Association fields are reconstructed by
 * replaying those observations on every cold open; no derived edge is promoted
 * into persisted fact state.
 */
int memoria_structural_text_runtime_open_shared(
    bdr_atomic_c_handle *db,
    const char *organization_id,
    size_t max_within_distance,
    size_t max_event_lag,
    double forgetting_rate,
    memoria_structural_text_runtime **out
);

int memoria_structural_text_runtime_observe(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id,
    const char *source_id,
    const char *source_kind,
    unsigned long sequence,
    const char *text,
    int *duplicate
);

/*
 * Read-only resolution. Query symbols are never observed and therefore cannot
 * reinforce their own result.
 */
int memoria_structural_text_runtime_resolve(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id,
    const char *query,
    size_t top_k,
    memoria_structural_text_context **out_contexts,
    size_t *out_count
);

/* Read-only grouping inside a conversation window. Repeated surface forms
 * with the same opaque symbol trail and source kind share one context slot,
 * retaining every source ID. This does not infer semantic facts. */
int memoria_structural_text_runtime_resolve_window_group(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id,
    const char *query,
    size_t top_k,
    memoria_structural_text_context **out_contexts,
    size_t *out_count
);

size_t memoria_structural_text_runtime_window_revision(
    const memoria_structural_text_runtime *runtime,
    const char *hierarchy_id
);

void memoria_structural_text_contexts_free(
    memoria_structural_text_context *contexts,
    size_t count
);

size_t memoria_structural_text_runtime_observation_count(
    const memoria_structural_text_runtime *runtime
);

size_t memoria_structural_text_runtime_hierarchy_count(
    const memoria_structural_text_runtime *runtime
);

size_t memoria_structural_text_runtime_edge_count(
    const memoria_structural_text_runtime *runtime,
    const char *hierarchy_id
);

int memoria_structural_text_runtime_sync(
    memoria_structural_text_runtime *runtime
);

void memoria_structural_text_runtime_close(
    memoria_structural_text_runtime *runtime
);

#ifdef __cplusplus
}
#endif

#endif
