#include "concept_relation_runtime.h"
#include "concept_relation_adapter.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int endpoint_key(
    const memoria_concept_index *index,
    const char *concept_namespace,
    const char *surface,
    const char *context,
    char *out,
    size_t out_cap
) {
    memoria_concept_resolution resolution;
    char normalized[MEMORIA_CONCEPT_SURFACE_CAP];
    int n;
    if (!index || !surface || !out || out_cap == 0) return 0;
    resolution = memoria_concept_resolve_with_context(
        index,
        concept_namespace ? concept_namespace : "",
        surface,
        context ? context : ""
    );
    if (resolution.status == MEMORIA_CONCEPT_HIT && resolution.concept_id[0]) {
        n = snprintf(out, out_cap, "concept:%s", resolution.concept_id);
        return n > 0 && (size_t)n < out_cap;
    }
    if (resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS ||
        resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT) {
        return 0;
    }
    if (memoria_concept_normalize(surface, normalized, sizeof(normalized)) != MEMORIA_CONCEPT_OK) return 0;
    if (!normalized[0]) return 0;
    n = snprintf(out, out_cap, "surface:%s", normalized);
    return n > 0 && (size_t)n < out_cap;
}

memoria_concept_relation_runtime_status memoria_concept_relation_runtime_infer(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *source,
    const char *target,
    const char *context,
    size_t max_hops,
    size_t max_paths,
    double min_confidence,
    memoria_concept_relation_path *out_paths,
    size_t out_capacity,
    size_t *out_count
) {
    memoria_concept_relation_edge_storage *storage = NULL;
    memoria_concept_relation_edge *edges = NULL;
    size_t capacity, edge_count = 0, i;
    char source_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    char target_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    memoria_concept_traversal_status status;
    if (!turns || !concept_index || !source || !target || !out_paths || !out_count) {
        return MEMORIA_CONCEPT_RELATION_RUNTIME_INVALID;
    }
    *out_count = 0;
    if (!endpoint_key(concept_index, concept_namespace, source, context, source_key, sizeof(source_key)) ||
        !endpoint_key(concept_index, concept_namespace, target, context, target_key, sizeof(target_key))) {
        return MEMORIA_CONCEPT_RELATION_RUNTIME_UNRESOLVED;
    }
    capacity = turn_count * MEMORIA_PERSIST_MAX_RELATIONS;
    if (capacity == 0) return MEMORIA_CONCEPT_RELATION_RUNTIME_UNRESOLVED;
    storage = (memoria_concept_relation_edge_storage *)calloc(capacity, sizeof(*storage));
    edges = (memoria_concept_relation_edge *)calloc(capacity, sizeof(*edges));
    if (!storage || !edges) {
        free(storage);
        free(edges);
        return MEMORIA_CONCEPT_RELATION_RUNTIME_INVALID;
    }
    if (memoria_concept_relation_build_edges(
            turns, turn_count, memory_namespace, concept_index, concept_namespace,
            storage, capacity, &edge_count
        ) != MEMORIA_CONCEPT_RELATION_ADAPTER_OK) {
        free(storage);
        free(edges);
        return MEMORIA_CONCEPT_RELATION_RUNTIME_INVALID;
    }
    for (i = 0; i < edge_count; ++i) edges[i] = storage[i].edge;
    status = memoria_concept_relation_infer_paths(
        source_key, target_key, edges, edge_count,
        max_hops, max_paths, min_confidence,
        out_paths, out_capacity, out_count
    );
    free(storage);
    free(edges);
    if (status == MEMORIA_CONCEPT_TRAVERSAL_HIT) return MEMORIA_CONCEPT_RELATION_RUNTIME_HIT;
    if (status == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED) return MEMORIA_CONCEPT_RELATION_RUNTIME_UNRESOLVED;
    return MEMORIA_CONCEPT_RELATION_RUNTIME_INVALID;
}
