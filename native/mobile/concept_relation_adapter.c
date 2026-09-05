#include "concept_relation_adapter.h"

#include <stdio.h>
#include <string.h>

static int source_type_allowed(const char *source_type) {
    if (!source_type || !*source_type) return 0;
    return strcmp(source_type, "user_assertion") == 0 ||
           strcmp(source_type, "user_correction") == 0 ||
           strcmp(source_type, "direct_observation") == 0 ||
           strcmp(source_type, "external_import") == 0 ||
           strcmp(source_type, "derived_relation") == 0;
}

static int namespace_matches(const char *value, const char *expected) {
    if (!expected) return 1;
    if (!value) return 0;
    return strcmp(value, expected) == 0;
}

static int endpoint_key(
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    const char *surface,
    const char *context,
    char *out,
    size_t out_cap,
    int *ambiguous
) {
    memoria_concept_resolution resolution;
    char normalized[MEMORIA_CONCEPT_SURFACE_CAP];
    int n;
    if (!concept_index || !surface || !out || out_cap == 0 || !ambiguous) return 0;
    *ambiguous = 0;
    resolution = memoria_concept_resolve_with_context(
        concept_index,
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
        *ambiguous = 1;
    }
    if (memoria_concept_normalize(surface, normalized, sizeof(normalized)) != MEMORIA_CONCEPT_OK) return 0;
    if (!normalized[0]) return 0;
    n = snprintf(out, out_cap, "surface:%s", normalized);
    return n > 0 && (size_t)n < out_cap;
}

int memoria_concept_relation_build_edges(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_namespace,
    const memoria_concept_index *concept_index,
    const char *concept_namespace,
    memoria_concept_relation_edge_storage *out,
    size_t out_capacity,
    size_t *out_count
) {
    size_t i, j, count = 0;
    if (!turns || !concept_index || !out || !out_count) return MEMORIA_CONCEPT_RELATION_ADAPTER_INVALID;
    *out_count = 0;
    for (i = 0; i < turn_count; ++i) {
        const memoria_persist_turn *turn = &turns[i];
        if (turn->superseded) continue;
        if (!namespace_matches(turn->namespace_id, memory_namespace)) continue;
        if (!source_type_allowed(turn->source_type)) continue;
        for (j = 0; j < turn->relation_count; ++j) {
            memoria_concept_relation_edge_storage *slot;
            int subject_ambiguous = 0, object_ambiguous = 0;
            const char *evidence_id;
            if (count >= out_capacity) return MEMORIA_CONCEPT_RELATION_ADAPTER_CAPACITY;
            evidence_id = turn->relation_memory_ids[j];
            if (!evidence_id || !*evidence_id) continue;
            slot = &out[count];
            memset(slot, 0, sizeof(*slot));
            if (!endpoint_key(concept_index, concept_namespace, turn->relations[j].subject, turn->text,
                              slot->subject_key, sizeof(slot->subject_key), &subject_ambiguous)) continue;
            if (!endpoint_key(concept_index, concept_namespace, turn->relations[j].object, turn->text,
                              slot->object_key, sizeof(slot->object_key), &object_ambiguous)) continue;
            if (snprintf(slot->predicate, sizeof(slot->predicate), "%s", turn->relations[j].predicate) < 0) continue;
            if (snprintf(slot->evidence_id, sizeof(slot->evidence_id), "%s", evidence_id) < 0) continue;
            slot->edge.subject_key = slot->subject_key;
            slot->edge.object_key = slot->object_key;
            slot->edge.predicate = slot->predicate;
            slot->edge.evidence_id = slot->evidence_id;
            slot->edge.confidence = turn->relations[j].confidence;
            slot->edge.ambiguous = subject_ambiguous || object_ambiguous;
            ++count;
        }
    }
    *out_count = count;
    return MEMORIA_CONCEPT_RELATION_ADAPTER_OK;
}
