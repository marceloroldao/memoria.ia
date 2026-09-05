#include "concept_relation_neighborhood.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int resolve_source_key(
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *source,
    const char *context,
    char *out,
    size_t out_cap
) {
    memoria_concept_resolution resolution;
    char normalized[MEMORIA_CONCEPT_SURFACE_CAP];
    int n;
    if (!concept_index || !source || !out || !out_cap) return 0;
    resolution = memoria_concept_resolve_with_context(
        concept_index,
        concept_namespace ? concept_namespace : "",
        source,
        context ? context : ""
    );
    if (resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS ||
        resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT) return 0;
    if (resolution.status == MEMORIA_CONCEPT_HIT && resolution.concept_id[0]) {
        n = snprintf(out, out_cap, "concept:%s", resolution.concept_id);
        return n > 0 && (size_t)n < out_cap;
    }
    if (memoria_concept_normalize(source, normalized, sizeof(normalized)) != MEMORIA_CONCEPT_OK || !normalized[0]) return 0;
    n = snprintf(out, out_cap, "surface:%s", normalized);
    return n > 0 && (size_t)n < out_cap;
}

static int same_neighbor(
    const memoria_concept_relation_neighbor *a,
    const char *node_key,
    const char *predicate,
    const char *evidence_id
) {
    return strcmp(a->node_key, node_key) == 0 &&
           strcmp(a->predicate, predicate) == 0 &&
           strcmp(a->evidence_id, evidence_id) == 0;
}

memoria_concept_neighborhood_status memoria_concept_relation_neighborhood(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *source,
    const char *context,
    double min_confidence,
    memoria_concept_relation_neighbor *out,
    size_t out_capacity,
    size_t *out_count
) {
    memoria_concept_relation_edge_storage *storage = NULL;
    char source_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    size_t max_edges = 0, edge_count = 0, i, j, count = 0;
    int rc;

    if (!turns || !concept_index || !source || !out || !out_count || !out_capacity || min_confidence < 0.0 || min_confidence > 1.0)
        return MEMORIA_CONCEPT_NEIGHBORHOOD_INVALID;
    *out_count = 0;
    if (!resolve_source_key(concept_index, concept_namespace, source, context, source_key, sizeof(source_key)))
        return MEMORIA_CONCEPT_NEIGHBORHOOD_UNRESOLVED;

    for (i = 0; i < turn_count; ++i) max_edges += turns[i].relation_count;
    if (!max_edges) return MEMORIA_CONCEPT_NEIGHBORHOOD_UNRESOLVED;
    storage = (memoria_concept_relation_edge_storage *)calloc(max_edges, sizeof(*storage));
    if (!storage) return MEMORIA_CONCEPT_NEIGHBORHOOD_INVALID;

    rc = memoria_concept_relation_build_edges(
        turns, turn_count, memory_namespace, concept_index, concept_namespace,
        storage, max_edges, &edge_count
    );
    if (rc != MEMORIA_CONCEPT_RELATION_ADAPTER_OK) {
        free(storage);
        return MEMORIA_CONCEPT_NEIGHBORHOOD_UNRESOLVED;
    }

    for (i = 0; i < edge_count; ++i) {
        const memoria_concept_relation_edge *edge = &storage[i].edge;
        const char *neighbor_key = NULL;
        if (edge->ambiguous || edge->confidence < min_confidence) continue;
        if (strcmp(edge->subject_key, source_key) == 0) neighbor_key = edge->object_key;
        else if (strcmp(edge->object_key, source_key) == 0) neighbor_key = edge->subject_key;
        else continue;
        if (!neighbor_key || !neighbor_key[0]) continue;
        for (j = 0; j < count; ++j)
            if (same_neighbor(&out[j], neighbor_key, edge->predicate, edge->evidence_id)) break;
        if (j < count) continue;
        if (count >= out_capacity) break;
        snprintf(out[count].node_key, sizeof(out[count].node_key), "%s", neighbor_key);
        snprintf(out[count].predicate, sizeof(out[count].predicate), "%s", edge->predicate ? edge->predicate : "");
        snprintf(out[count].evidence_id, sizeof(out[count].evidence_id), "%s", edge->evidence_id ? edge->evidence_id : "");
        out[count].confidence = edge->confidence;
        ++count;
    }

    free(storage);
    *out_count = count;
    return count ? MEMORIA_CONCEPT_NEIGHBORHOOD_HIT : MEMORIA_CONCEPT_NEIGHBORHOOD_UNRESOLVED;
}
