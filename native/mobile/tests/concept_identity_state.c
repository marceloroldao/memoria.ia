#include "concept_identity_state.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_concept_index original;
    memoria_concept_index restored;
    memoria_concept_state_row rows[MEMORIA_CONCEPT_MAX_CONCEPTS];
    memoria_concept_resolution result;
    size_t row_count = 0;
    const char *finance_aliases[] = {"bank"};
    const char *finance_cues[] = {"loan", "money"};
    const char *river_aliases[] = {"bank"};
    const char *river_cues[] = {"river", "water"};
    memoria_concept_definition finance = {
        "concept:bank-finance", "en", "financial bank", "finance",
        finance_aliases, 1, finance_cues, 2
    };
    memoria_concept_definition river = {
        "concept:bank-river", "en", "river bank", "geography",
        river_aliases, 1, river_cues, 2
    };

    memoria_concept_index_init(&original);
    assert(memoria_concept_register(&original, &finance) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&original, &river) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_state_export(&original, rows, MEMORIA_CONCEPT_MAX_CONCEPTS, &row_count) == MEMORIA_CONCEPT_OK);
    assert(row_count == 2);

    memset(&restored, 0xA5, sizeof(restored));
    assert(memoria_concept_state_import(&restored, rows, row_count) == MEMORIA_CONCEPT_OK);

    result = memoria_concept_resolve(&restored, "en", "bank");
    assert(result.status == MEMORIA_CONCEPT_UNRESOLVED);
    assert(result.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS);
    assert(result.candidate_count == 2);

    result = memoria_concept_resolve_with_context(&restored, "en", "bank", "loan approval");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(result.concept_id, "concept:bank-finance") == 0);

    result = memoria_concept_resolve_with_context(&restored, "en", "bank", "water level");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(result.concept_id, "concept:bank-river") == 0);

    result = memoria_concept_resolve(&restored, "other", "bank");
    assert(result.status == MEMORIA_CONCEPT_UNRESOLVED);
    assert(result.reason == MEMORIA_CONCEPT_REASON_UNKNOWN);
    return 0;
}
