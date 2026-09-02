#include "resolutive_inference_kernel.h"

#include <math.h>
#include <string.h>

static int nonempty(const char *s) { return s && s[0] != '\0'; }
static double min2(double a, double b) { return a < b ? a : b; }

int memoria_infer_two_hop_same_predicate(
    const memoria_inference_edge_t *edges,
    size_t edge_count,
    const char *subject,
    const char *predicate,
    memoria_inference_result_t *result
) {
    size_t i, j;
    double best = -1.0;
    const char *best_answer = NULL;
    const char *best_via = NULL;
    const char *best_m1 = NULL;
    const char *best_m2 = NULL;
    int conflict = 0;

    if (!result) return -1;
    memset(result, 0, sizeof(*result));
    result->status = MEMORIA_INFERENCE_UNRESOLVED;
    if (!edges || !nonempty(subject) || !nonempty(predicate)) return 0;

    for (i = 0; i < edge_count; ++i) {
        const memoria_inference_edge_t *a = &edges[i];
        if (!a->active || !nonempty(a->subject) || !nonempty(a->predicate) || !nonempty(a->object)) continue;
        if (strcmp(a->subject, subject) != 0 || strcmp(a->predicate, predicate) != 0) continue;

        for (j = 0; j < edge_count; ++j) {
            const memoria_inference_edge_t *b = &edges[j];
            double score;
            if (!b->active || !nonempty(b->subject) || !nonempty(b->predicate) || !nonempty(b->object)) continue;
            if (strcmp(b->subject, a->object) != 0 || strcmp(b->predicate, predicate) != 0) continue;
            if (strcmp(b->object, subject) == 0) continue;

            score = min2(min2(a->authority, b->authority), min2(a->semantic_confidence, b->semantic_confidence));
            if (score > best + 1e-12) {
                best = score;
                best_answer = b->object;
                best_via = a->object;
                best_m1 = a->memory_id;
                best_m2 = b->memory_id;
                conflict = 0;
            } else if (fabs(score - best) <= 1e-12 && best_answer && strcmp(best_answer, b->object) != 0) {
                conflict = 1;
            }
        }
    }

    if (!best_answer) return 0;
    if (conflict) {
        result->status = MEMORIA_INFERENCE_CONFLICT;
        result->path_confidence = best;
        return 0;
    }

    result->status = MEMORIA_INFERENCE_RESOLVED;
    result->answer = best_answer;
    result->via = best_via;
    result->evidence_memory_id_1 = best_m1;
    result->evidence_memory_id_2 = best_m2;
    result->path_confidence = best;
    return 0;
}
