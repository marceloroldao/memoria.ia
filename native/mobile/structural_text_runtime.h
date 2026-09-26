#ifndef MEMORIA_STRUCTURAL_TEXT_RUNTIME_H
#define MEMORIA_STRUCTURAL_TEXT_RUNTIME_H

#include "structural_text_kernel.h"

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct bdr_atomic_c_handle bdr_atomic_c_handle;
typedef struct memoria_structural_text_runtime memoria_structural_text_runtime;

typedef struct memoria_structural_text_observation_view {
    const char *hierarchy_id;
    const char *source_id;
    const char *source_kind;
    const char *text;
    unsigned long sequence;
} memoria_structural_text_observation_view;

typedef struct memoria_structural_text_occurrence {
    char *source_id;
    char *source_text;
    char *source_kind;
    unsigned long sequence;
} memoria_structural_text_occurrence;

typedef struct memoria_structural_text_context {
    char *source_hierarchy_id;
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

typedef struct memoria_structural_region_activation {
    char *hierarchy_id;
    size_t observation_count;
    size_t matching_count;
    size_t query_echo_count;
    size_t embedded_query_count;
    size_t distinct_count;
    size_t max_exact_overlap;
    size_t max_ordered_span;
    /* Borrowed from the runtime until its next mutation or close. */
    const char *witness_source_id;
    const char *witness_source_kind;
    unsigned long witness_sequence;
    unsigned long first_sequence;
    unsigned long last_sequence;
} memoria_structural_region_activation;

typedef struct memoria_structural_trail_source {
    char *source_id;
    char *hierarchy_id;
    unsigned long sequence;
} memoria_structural_trail_source;

typedef struct memoria_structural_trail_recurrence {
    char fingerprint[17];
    char branch_address[17];
    size_t branch_depth;
    size_t divergent_trail_count;
    char *source_id;
    char *hierarchy_id;
    size_t occurrences;
    size_t region_count;
    size_t exact_overlap;
    int query_echo;
    int contains_query_trail;
    /* Owned by this read-only result; used to verify hash collisions. */
    uint64_t *symbols;
    size_t symbol_count;
    const char **region_ids;
    size_t region_capacity;
    memoria_structural_trail_source *sources;
    size_t source_count;
    size_t source_capacity;
} memoria_structural_trail_recurrence;

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

/* Read-only evidence across conversation windows. Each result retains its
 * originating hierarchy; this does not assign an epistemic role to the text. */
int memoria_structural_text_runtime_resolve_personal_evidence(
    memoria_structural_text_runtime *runtime,
    const char *current_hierarchy_id,
    const char *query,
    size_t top_k,
    memoria_structural_text_context **out_contexts,
    size_t *out_count
);

/* Read-only region comparison. An exact query trail is counted as an echo,
 * while other matching observations remain unqualified candidates. This API
 * does not decide whether a region contains an answer or a fact. */
int memoria_structural_text_runtime_activate_regions(
    const memoria_structural_text_runtime *runtime,
    const char *query,
    memoria_structural_region_activation **out_regions,
    size_t *out_count,
    size_t *out_unseen_query_symbols
);

void memoria_structural_text_region_activations_free(
    memoria_structural_region_activation *regions,
    size_t count
);

/* Groups identical observed symbol trails. A second source ID in one region
 * increases occurrences, not region_count. Neither count proves truth. */
int memoria_structural_text_runtime_trail_recurrence(
    const memoria_structural_text_runtime *runtime,
    const char *query,
    memoria_structural_trail_recurrence **out_groups,
    size_t *out_count
);

void memoria_structural_text_trail_recurrences_free(
    memoria_structural_trail_recurrence *groups,
    size_t count
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

/* Borrowed read-only view, valid until the next mutation or close. */
int memoria_structural_text_runtime_observation_at(
    const memoria_structural_text_runtime *runtime,
    size_t index,
    memoria_structural_text_observation_view *out
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
