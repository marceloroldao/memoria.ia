#include "evidence_metrics.h"
#include <assert.h>

int main(void) {
    memoria_evidence_metric_policy p = {0.60, 0.70};
    memoria_evidence_metric_result r;
    memoria_evidence_metrics m;

    m = (memoria_evidence_metrics){0.99, 0.20, 0.95, 1.0};
    assert(memoria_evidence_metrics_evaluate(&m, &p, &r));
    assert(r.eligible_for_persistence == 0);
    assert(r.eligible_for_graph_promotion == 0);

    m = (memoria_evidence_metrics){0.30, 0.90, 0.95, 0.50};
    assert(memoria_evidence_metrics_evaluate(&m, &p, &r));
    assert(r.eligible_for_persistence == 1);
    assert(r.eligible_for_graph_promotion == 1);

    m = (memoria_evidence_metrics){0.95, 0.90, 0.40, 1.0};
    assert(memoria_evidence_metrics_evaluate(&m, &p, &r));
    assert(r.eligible_for_persistence == 1);
    assert(r.eligible_for_graph_promotion == 0);

    m = (memoria_evidence_metrics){0.95, 0.90, 0.85, 0.10};
    assert(memoria_evidence_metrics_evaluate(&m, &p, &r));
    assert(r.eligible_for_persistence == 1);
    assert(r.eligible_for_graph_promotion == 1);
    assert(r.metrics.freshness == 0.10);

    return 0;
}
