#include "concept_relation_collection.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int resolve_type_key(
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *surface,
    const char *context,
    char *out,
    size_t out_cap
) {
    memoria_concept_resolution resolution;
    char normalized[MEMORIA_CONCEPT_SURFACE_CAP];
    int n;
    if (!concept_index || !surface || !out || !out_cap) return 0;
    resolution = memoria_concept_resolve_with_context(
        concept_index,
        concept_namespace ? concept_namespace : "",
        surface,
        context ? context : ""
    );
    if (resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS ||
        resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT) return 0;
    if (resolution.status == MEMORIA_CONCEPT_HIT && resolution.concept_id[0]) {
        n = snprintf(out, out_cap, "concept:%s", resolution.concept_id);
        return n > 0 && (size_t)n < out_cap;
    }
    if (memoria_concept_normalize(surface, normalized, sizeof(normalized)) != MEMORIA_CONCEPT_OK || !normalized[0]) return 0;
    n = snprintf(out, out_cap, "surface:%s", normalized);
    return n > 0 && (size_t)n < out_cap;
}

static int compare_members(const void *left, const void *right) {
    const memoria_concept_collection_member *a = (const memoria_concept_collection_member *)left;
    const memoria_concept_collection_member *b = (const memoria_concept_collection_member *)right;
    int cmp;
    if (a->confidence > b->confidence) return -1;
    if (a->confidence < b->confidence) return 1;
    cmp = strcmp(a->member_key, b->member_key);
    if (cmp != 0) return cmp;
    return strcmp(a->evidence_id, b->evidence_id);
}

memoria_concept_collection_status memoria_concept_relation_collect_type(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *type_surface,
    const char *context,
    double min_confidence,
    memoria_concept_collection_member *out,
    size_t out_capacity,
    size_t *out_count
) {
    memoria_concept_relation_edge_storage *storage = NULL;
    char type_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    size_t max_edges = 0, edge_count = 0, i, j, count = 0;
    int rc;

    if (!turns || !concept_index || !type_surface || !out || !out_count || !out_capacity ||
        min_confidence < 0.0 || min_confidence > 1.0)
        return MEMORIA_CONCEPT_COLLECTION_INVALID;
    *out_count = 0;
    if (!resolve_type_key(concept_index, concept_namespace, type_surface, context, type_key, sizeof(type_key)))
        return MEMORIA_CONCEPT_COLLECTION_UNRESOLVED;

    for (i = 0; i < turn_count; ++i) max_edges += turns[i].relation_count;
    if (!max_edges) return MEMORIA_CONCEPT_COLLECTION_UNRESOLVED;
    storage = (memoria_concept_relation_edge_storage *)calloc(max_edges, sizeof(*storage));
    if (!storage) return MEMORIA_CONCEPT_COLLECTION_INVALID;

    rc = memoria_concept_relation_build_edges(
        turns, turn_count, memory_namespace, concept_index, concept_namespace,
        storage, max_edges, &edge_count
    );
    if (rc != MEMORIA_CONCEPT_RELATION_ADAPTER_OK) {
        free(storage);
        return MEMORIA_CONCEPT_COLLECTION_UNRESOLVED;
    }

    for (i = 0; i < edge_count; ++i) {
        const memoria_concept_relation_edge *edge = &storage[i].edge;
        if (edge->ambiguous || edge->confidence < min_confidence) continue;
        if (strcmp(edge->predicate, "is") != 0) continue;
        if (strcmp(edge->object_key, type_key) != 0) continue;
        if (!edge->subject_key || !edge->subject_key[0]) continue;

        for (j = 0; j < count; ++j) {
            if (strcmp(out[j].member_key, edge->subject_key) == 0) {
                if (edge->confidence > out[j].confidence) {
                    out[j].confidence = edge->confidence;
                    snprintf(out[j].evidence_id, sizeof(out[j].evidence_id), "%s", edge->evidence_id ? edge->evidence_id : "");
                }
                break;
            }
        }
        if (j < count) continue;
        if (count >= out_capacity) break;
        snprintf(out[count].member_key, sizeof(out[count].member_key), "%s", edge->subject_key);
        snprintf(out[count].evidence_id, sizeof(out[count].evidence_id), "%s", edge->evidence_id ? edge->evidence_id : "");
        out[count].confidence = edge->confidence;
        ++count;
    }

    if (count > 1u) qsort(out, count, sizeof(*out), compare_members);
    free(storage);
    *out_count = count;
    return count ? MEMORIA_CONCEPT_COLLECTION_HIT : MEMORIA_CONCEPT_COLLECTION_UNRESOLVED;
}
