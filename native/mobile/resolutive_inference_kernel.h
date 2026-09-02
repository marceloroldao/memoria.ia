#ifndef MEMORIA_RESOLUTIVE_INFERENCE_KERNEL_H
#define MEMORIA_RESOLUTIVE_INFERENCE_KERNEL_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *subject;
    const char *predicate;
    const char *object;
    const char *memory_id;
    double authority;
    double semantic_confidence;
    int active;
} memoria_inference_edge_t;

typedef enum {
    MEMORIA_INFERENCE_UNRESOLVED = 0,
    MEMORIA_INFERENCE_RESOLVED = 1,
    MEMORIA_INFERENCE_CONFLICT = 2
} memoria_inference_status_t;

typedef struct {
    memoria_inference_status_t status;
    const char *answer;
    const char *via;
    const char *evidence_memory_id_1;
    const char *evidence_memory_id_2;
    double path_confidence;
} memoria_inference_result_t;

/* Explicit ontology policy. Generic copulas such as `is` are deliberately not
 * considered transitive. Only typed predicates admitted here may be used by
 * the policy-enforced inference entry point. */
int memoria_inference_predicate_is_transitive(const char *predicate);

/* Legacy bounded compositor kept for compatibility/diagnostics. It composes
 * identical predicates but does not itself decide whether the predicate is
 * ontologically transitive. */
int memoria_infer_two_hop_same_predicate(
    const memoria_inference_edge_t *edges,
    size_t edge_count,
    const char *subject,
    const char *predicate,
    memoria_inference_result_t *result
);

/* Policy-enforced compositor used by the next inference stage. If `predicate`
 * is not explicitly transitive, the result is UNRESOLVED and no path is tried. */
int memoria_infer_two_hop_transitive(
    const memoria_inference_edge_t *edges,
    size_t edge_count,
    const char *subject,
    const char *predicate,
    memoria_inference_result_t *result
);

#ifdef __cplusplus
}
#endif

#endif
