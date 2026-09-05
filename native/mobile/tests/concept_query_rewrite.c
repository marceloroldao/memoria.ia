#include "concept_identity_kernel.h"
#include "concept_query_rewrite.h"

#include <assert.h>
#include <string.h>

static memoria_concept_definition defn(
    const char *id, const char *ns, const char *canonical, const char *sense,
    const char *const *aliases, size_t alias_count,
    const char *const *cues, size_t cue_count
) {
    memoria_concept_definition d;
    memset(&d, 0, sizeof(d));
    d.concept_id = id;
    d.namespace_name = ns;
    d.canonical_name = canonical;
    d.sense_key = sense;
    d.aliases = aliases;
    d.alias_count = alias_count;
    d.context_cues = cues;
    d.context_cue_count = cue_count;
    return d;
}

int main(void) {
    memoria_concept_index index;
    memoria_concept_rewrite_result r;
    const char *voltage_aliases[] = {"ddp", "diferença de potencial"};
    const char *finance_aliases[] = {"bank", "financial bank"};
    const char *finance_cues[] = {"loan", "credit"};
    const char *river_aliases[] = {"bank", "river bank"};
    const char *river_cues[] = {"river", "water"};
    memoria_concept_definition voltage = defn("concept:voltage", "semantic", "voltage", "", voltage_aliases, 2, NULL, 0);
    memoria_concept_definition finance = defn("concept:bank-finance", "semantic", "bank", "finance", finance_aliases, 2, finance_cues, 2);
    memoria_concept_definition river = defn("concept:bank-river", "semantic", "river bank", "river-edge", river_aliases, 2, river_cues, 2);

    memoria_concept_index_init(&index);
    assert(memoria_concept_register(&index, &voltage) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&index, &finance) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&index, &river) == MEMORIA_CONCEPT_OK);

    r = memoria_concept_rewrite_query(&index, "semantic", "qual a DDP do charger", 6);
    assert(r.status == MEMORIA_CONCEPT_REWRITE_REWRITTEN);
    assert(strcmp(r.rewritten_query, "qual a voltage do charger") == 0);
    assert(r.concept_count == 1);
    assert(strcmp(r.concept_ids[0], "concept:voltage") == 0);

    r = memoria_concept_rewrite_query(&index, "semantic", "qual a diferença de potencial do charger", 6);
    assert(r.status == MEMORIA_CONCEPT_REWRITE_REWRITTEN);
    assert(strcmp(r.rewritten_query, "qual a voltage do charger") == 0);

    r = memoria_concept_rewrite_query(&index, "semantic", "voltage status", 6);
    assert(r.status == MEMORIA_CONCEPT_REWRITE_UNCHANGED);
    assert(strcmp(r.rewritten_query, "voltage status") == 0);

    r = memoria_concept_rewrite_query(&index, "semantic", "bank status", 6);
    assert(r.status == MEMORIA_CONCEPT_REWRITE_UNRESOLVED);
    assert(r.reason == MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS);

    r = memoria_concept_rewrite_query(&index, "semantic", "loan status for bank", 6);
    assert(r.status == MEMORIA_CONCEPT_REWRITE_UNCHANGED);
    assert(strcmp(r.rewritten_query, "loan status for bank") == 0);
    assert(r.concept_count == 1);
    assert(strcmp(r.concept_ids[0], "concept:bank-finance") == 0);

    r = memoria_concept_rewrite_query(&index, "semantic", "loan and river context for bank status", 6);
    assert(r.status == MEMORIA_CONCEPT_REWRITE_UNRESOLVED);
    assert(r.reason == MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS_CONTEXT);

    return 0;
}
