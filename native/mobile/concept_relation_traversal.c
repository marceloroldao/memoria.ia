#include "concept_relation_traversal.h"

#include <stdlib.h>
#include <string.h>

typedef struct queue_state {
    char node_keys[MEMORIA_CONCEPT_PATH_MAX_HOPS + 1u][MEMORIA_CONCEPT_PATH_KEY_CAP];
    char predicates[MEMORIA_CONCEPT_PATH_MAX_HOPS][MEMORIA_CONCEPT_PATH_PREDICATE_CAP];
    char evidence_ids[MEMORIA_CONCEPT_PATH_MAX_HOPS][MEMORIA_CONCEPT_PATH_EVIDENCE_CAP];
    double confidences[MEMORIA_CONCEPT_PATH_MAX_HOPS];
    size_t hops;
} queue_state;

static int copy_text(char *dst, size_t cap, const char *src) {
    size_t n;
    if (!dst || cap == 0 || !src) return 0;
    n = strlen(src);
    if (n >= cap) return 0;
    memcpy(dst, src, n + 1u);
    return 1;
}

static int seen_node(const queue_state *state, const char *key) {
    size_t i;
    if (!state || !key) return 1;
    for (i = 0; i <= state->hops; ++i)
        if (strcmp(state->node_keys[i], key) == 0) return 1;
    return 0;
}

static double path_confidence(const queue_state *state) {
    size_t i;
    double value = 1.0;
    if (!state || state->hops == 0) return 0.0;
    for (i = 0; i < state->hops; ++i)
        if (state->confidences[i] < value) value = state->confidences[i];
    return value;
}

static int evidence_compare(const memoria_concept_relation_path *a, const memoria_concept_relation_path *b) {
    size_t i, limit;
    limit = a->hops < b->hops ? a->hops : b->hops;
    for (i = 0; i < limit; ++i) {
        int cmp = strcmp(a->evidence_ids[i], b->evidence_ids[i]);
        if (cmp != 0) return cmp;
    }
    if (a->hops < b->hops) return -1;
    if (a->hops > b->hops) return 1;
    return 0;
}

static int path_compare(const void *left, const void *right) {
    const memoria_concept_relation_path *a = (const memoria_concept_relation_path *)left;
    const memoria_concept_relation_path *b = (const memoria_concept_relation_path *)right;
    if (a->confidence > b->confidence) return -1;
    if (a->confidence < b->confidence) return 1;
    if (a->hops < b->hops) return -1;
    if (a->hops > b->hops) return 1;
    return evidence_compare(a, b);
}

static int write_path(memoria_concept_relation_path *out, const queue_state *state) {
    size_t i;
    if (!out || !state || state->hops == 0) return 0;
    memset(out, 0, sizeof(*out));
    out->hops = state->hops;
    out->confidence = path_confidence(state);
    for (i = 0; i <= state->hops; ++i)
        if (!copy_text(out->node_keys[i], sizeof(out->node_keys[i]), state->node_keys[i])) return 0;
    for (i = 0; i < state->hops; ++i) {
        if (!copy_text(out->predicates[i], sizeof(out->predicates[i]), state->predicates[i])) return 0;
        if (!copy_text(out->evidence_ids[i], sizeof(out->evidence_ids[i]), state->evidence_ids[i])) return 0;
    }
    return 1;
}

memoria_concept_traversal_status memoria_concept_relation_infer_paths(
    const char *source_key,
    const char *target_key,
    const memoria_concept_relation_edge *edges,
    size_t edge_count,
    size_t max_hops,
    size_t max_paths,
    double min_confidence,
    memoria_concept_relation_path *out_paths,
    size_t out_capacity,
    size_t *out_count
) {
    queue_state *queue = NULL;
    size_t queue_cap, head = 0, tail = 0, found = 0, i;
    if (out_count) *out_count = 0;
    if (!source_key || !*source_key || !target_key || !*target_key ||
        (!edges && edge_count) || !out_paths || !out_count || out_capacity == 0 ||
        max_hops < 1 || max_hops > MEMORIA_CONCEPT_PATH_MAX_HOPS || max_paths < 1 ||
        min_confidence < 0.0 || min_confidence > 1.0)
        return MEMORIA_CONCEPT_TRAVERSAL_INVALID;
    if (strcmp(source_key, target_key) == 0) return MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED;

    queue_cap = 1u + edge_count * max_hops * 2u;
    if (queue_cap < 8u) queue_cap = 8u;
    queue = (queue_state *)calloc(queue_cap, sizeof(*queue));
    if (!queue) return MEMORIA_CONCEPT_TRAVERSAL_INVALID;
    if (!copy_text(queue[0].node_keys[0], sizeof(queue[0].node_keys[0]), source_key)) {
        free(queue);
        return MEMORIA_CONCEPT_TRAVERSAL_INVALID;
    }
    tail = 1u;

    while (head < tail && found < max_paths && found < out_capacity) {
        queue_state state = queue[head++];
        if (state.hops >= max_hops) continue;
        for (i = 0; i < edge_count; ++i) {
            queue_state next;
            const memoria_concept_relation_edge *edge = &edges[i];
            if (!edge->subject_key || !edge->object_key || !edge->predicate || !edge->evidence_id) continue;
            if (edge->ambiguous || edge->confidence < min_confidence) continue;
            if (strcmp(edge->subject_key, state.node_keys[state.hops]) != 0) continue;
            if (seen_node(&state, edge->object_key)) continue;

            next = state;
            if (!copy_text(next.node_keys[state.hops + 1u], sizeof(next.node_keys[0]), edge->object_key) ||
                !copy_text(next.predicates[state.hops], sizeof(next.predicates[0]), edge->predicate) ||
                !copy_text(next.evidence_ids[state.hops], sizeof(next.evidence_ids[0]), edge->evidence_id)) {
                free(queue);
                return MEMORIA_CONCEPT_TRAVERSAL_INVALID;
            }
            next.confidences[state.hops] = edge->confidence;
            next.hops = state.hops + 1u;
            if (strcmp(edge->object_key, target_key) == 0) {
                if (!write_path(&out_paths[found], &next)) {
                    free(queue);
                    return MEMORIA_CONCEPT_TRAVERSAL_INVALID;
                }
                ++found;
            } else if (next.hops < max_hops) {
                if (tail >= queue_cap) {
                    size_t new_cap = queue_cap * 2u;
                    queue_state *grown = (queue_state *)realloc(queue, new_cap * sizeof(*grown));
                    if (!grown) {
                        free(queue);
                        return MEMORIA_CONCEPT_TRAVERSAL_INVALID;
                    }
                    memset(grown + queue_cap, 0, (new_cap - queue_cap) * sizeof(*grown));
                    queue = grown;
                    queue_cap = new_cap;
                }
                queue[tail++] = next;
            }
        }
    }
    free(queue);
    if (found == 0) return MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED;
    qsort(out_paths, found, sizeof(*out_paths), path_compare);
    *out_count = found;
    return MEMORIA_CONCEPT_TRAVERSAL_HIT;
}
