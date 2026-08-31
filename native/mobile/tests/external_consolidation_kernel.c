#include "external_consolidation_kernel.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_external_consolidation_policy policy = {2u, 0.70};
    memoria_external_consolidation_result result;

    /* One source remains RAW even when confidence is high. */
    memoria_external_source_evidence one[] = {{"example.org", 0.95}};
    assert(memoria_external_consolidation_evaluate(one, 1u, 0, &policy, &result));
    assert(result.state == MEMORIA_EXTERNAL_EVIDENCE_RAW);
    assert(result.independent_domains == 1u);
    assert(result.qualifying_independent_domains == 1u);

    /* Two URLs/samples attributed to the same domain are not corroboration. */
    memoria_external_source_evidence same_domain[] = {
        {"Example.org", 0.80}, {"www.example.org.", 0.93}
    };
    assert(memoria_external_consolidation_evaluate(same_domain, 2u, 0, &policy, &result));
    assert(result.state == MEMORIA_EXTERNAL_EVIDENCE_RAW);
    assert(result.observed_sources == 2u);
    assert(result.independent_domains == 1u);
    assert(result.qualifying_independent_domains == 1u);

    /* Independent domains above policy threshold create corroborated evidence. */
    memoria_external_source_evidence independent[] = {
        {"source-a.org", 0.91}, {"source-b.net", 0.83}
    };
    assert(memoria_external_consolidation_evaluate(independent, 2u, 0, &policy, &result));
    assert(result.state == MEMORIA_EXTERNAL_EVIDENCE_CORROBORATED);
    assert(result.independent_domains == 2u);
    assert(result.qualifying_independent_domains == 2u);
    assert(result.weakest_qualifying_confidence > 0.82 && result.weakest_qualifying_confidence < 0.84);
    assert(strcmp(memoria_external_evidence_state_name(result.state), "corroborated") == 0);

    /* Low-confidence independent evidence does not satisfy the policy. */
    memoria_external_source_evidence weak[] = {
        {"source-a.org", 0.91}, {"source-b.net", 0.42}, {"source-b.net", 0.65}
    };
    assert(memoria_external_consolidation_evaluate(weak, 3u, 0, &policy, &result));
    assert(result.state == MEMORIA_EXTERNAL_EVIDENCE_RAW);
    assert(result.independent_domains == 2u);
    assert(result.qualifying_independent_domains == 1u);

    /* Conflict dominates corroboration: disagreement is never promoted away. */
    assert(memoria_external_consolidation_evaluate(independent, 2u, 1, &policy, &result));
    assert(result.state == MEMORIA_EXTERNAL_EVIDENCE_CONFLICT);
    assert(strcmp(memoria_external_evidence_state_name(result.state), "conflict") == 0);

    /* Empty evidence is valid RAW state; malformed policy/source is rejected. */
    assert(memoria_external_consolidation_evaluate(NULL, 0u, 0, &policy, &result));
    assert(result.state == MEMORIA_EXTERNAL_EVIDENCE_RAW);
    policy.min_validation_confidence = 1.1;
    assert(!memoria_external_consolidation_evaluate(one, 1u, 0, &policy, &result));

    return 0;
}
