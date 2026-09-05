#define _XOPEN_SOURCE 700

#include "concept_identity_bdr.h"
#include "concept_identity_kernel.h"
#include "concept_identity_state.h"

#include <assert.h>
#include <stdlib.h>
#include <string.h>

static memoria_concept_definition definition(
    const char *id,
    const char *ns,
    const char *canonical,
    const char *sense,
    const char *const *aliases,
    size_t alias_count,
    const char *const *cues,
    size_t cue_count
) {
    memoria_concept_definition d;
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
    char path[] = "/tmp/memoria-concept-bdr-XXXXXX";
    memoria_concept_index original, restored;
    memoria_concept_state_row rows[MEMORIA_CONCEPT_MAX_CONCEPTS];
    memoria_concept_state_row loaded[MEMORIA_CONCEPT_MAX_CONCEPTS];
    memoria_concept_bdr *store = NULL;
    memoria_concept_bdr *other = NULL;
    memoria_concept_resolution result;
    size_t row_count = 0, loaded_count = 0, other_count = 99;
    const char *finance_aliases[] = {"bank", "financial bank"};
    const char *finance_cues[] = {"loan", "credit"};
    const char *river_aliases[] = {"bank", "river bank"};
    const char *river_cues[] = {"river", "water"};
    const char *voltage_aliases[] = {"ddp", "diferença de potencial"};
    memoria_concept_definition finance = definition(
        "concept:bank-finance", "semantic", "bank", "finance",
        finance_aliases, 2, finance_cues, 2
    );
    memoria_concept_definition river = definition(
        "concept:bank-river", "semantic", "bank", "river-edge",
        river_aliases, 2, river_cues, 2
    );
    memoria_concept_definition voltage = definition(
        "concept:voltage", "electronics", "voltage", "",
        voltage_aliases, 2, NULL, 0
    );

    assert(mkdtemp(path) != NULL);
    memoria_concept_index_init(&original);
    assert(memoria_concept_register(&original, &finance) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&original, &river) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&original, &voltage) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_state_export(&original, rows, MEMORIA_CONCEPT_MAX_CONCEPTS, &row_count) == MEMORIA_CONCEPT_OK);
    assert(row_count == 3);

    assert(memoria_concept_bdr_open(path, "org-a", &store));
    assert(memoria_concept_bdr_save(store, rows, row_count));
    assert(memoria_concept_bdr_sync(store));
    memoria_concept_bdr_close(store);
    store = NULL;

    /* Real durable restart: a new handle reconstructs a fresh concept index. */
    assert(memoria_concept_bdr_open(path, "org-a", &store));
    assert(memoria_concept_bdr_load(store, loaded, MEMORIA_CONCEPT_MAX_CONCEPTS, &loaded_count));
    assert(loaded_count == 3);
    memoria_concept_index_init(&restored);
    assert(memoria_concept_state_import(&restored, loaded, loaded_count) == MEMORIA_CONCEPT_OK);

    result = memoria_concept_resolve(&restored, "semantic", "bank");
    assert(result.status == MEMORIA_CONCEPT_UNRESOLVED);
    assert(result.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS);
    assert(result.candidate_count == 2);

    result = memoria_concept_resolve_with_context(&restored, "semantic", "bank", "loan approved");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(result.concept_id, "concept:bank-finance") == 0);

    result = memoria_concept_resolve_with_context(&restored, "semantic", "bank", "water near river");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(result.concept_id, "concept:bank-river") == 0);

    result = memoria_concept_resolve(&restored, "electronics", "diferença de potencial");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(result.concept_id, "concept:voltage") == 0);
    memoria_concept_bdr_close(store);

    /* Organization isolation: same physical BDR, different structural namespace. */
    assert(memoria_concept_bdr_open(path, "org-b", &other));
    assert(memoria_concept_bdr_load(other, loaded, MEMORIA_CONCEPT_MAX_CONCEPTS, &other_count));
    assert(other_count == 0);
    memoria_concept_bdr_close(other);
    return 0;
}
