#include "evidence_metrics.h"

static int unit_interval(double value) {
    return value >= 0.0 && value <= 1.0;
}

int memoria_evidence_metrics_evaluate(
    const memoria_evidence_metrics *metrics,
    const memoria_evidence_metric_policy *policy,
    memoria_evidence_metric_result *out
) {
    if (!metrics || !policy || !out ||
        !unit_interval(metrics->source_authority) ||
        !unit_interval(metrics->retrieval_relevance) ||
        !unit_interval(metrics->semantic_confidence) ||
        !unit_interval(metrics->freshness) ||
        !unit_interval(policy->min_retrieval_relevance) ||
        !unit_interval(policy->min_semantic_confidence)) return 0;

    out->metrics = *metrics;
    out->eligible_for_persistence =
        metrics->retrieval_relevance >= policy->min_retrieval_relevance;
    out->eligible_for_graph_promotion =
        out->eligible_for_persistence &&
        metrics->semantic_confidence >= policy->min_semantic_confidence;
    return 1;
}
