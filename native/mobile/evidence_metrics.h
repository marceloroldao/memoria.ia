#ifndef MEMORIA_EVIDENCE_METRICS_H
#define MEMORIA_EVIDENCE_METRICS_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct memoria_evidence_metrics {
    double source_authority;
    double retrieval_relevance;
    double semantic_confidence;
    double freshness;
} memoria_evidence_metrics;

typedef struct memoria_evidence_metric_policy {
    double min_retrieval_relevance;
    double min_semantic_confidence;
} memoria_evidence_metric_policy;

typedef struct memoria_evidence_metric_result {
    memoria_evidence_metrics metrics;
    int eligible_for_persistence;
    int eligible_for_graph_promotion;
} memoria_evidence_metric_result;

int memoria_evidence_metrics_evaluate(
    const memoria_evidence_metrics *metrics,
    const memoria_evidence_metric_policy *policy,
    memoria_evidence_metric_result *out
);

#ifdef __cplusplus
}
#endif
#endif
