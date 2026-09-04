#include "concept_identity_kernel.h"

#include <assert.h>
#include <string.h>

static void register_voltage(memoria_concept_index *index) {
    const char *aliases[] = {"DDP", "diferença de potencial"};
    memoria_concept_definition def = {
        "concept:voltage-stable",
        "electronics",
        "Voltage",
        NULL,
        aliases,
        2,
        NULL,
        0
    };
    assert(memoria_concept_register(index, &def) == MEMORIA_CONCEPT_OK);
}

static void test_normalization_and_alias_identity(void) {
    memoria_concept_index index;
    memoria_concept_resolution result;
    char normalized[MEMORIA_CONCEPT_SURFACE_CAP];
    memoria_concept_index_init(&index);
    register_voltage(&index);

    assert(memoria_concept_normalize(" Diferença   de POTENCIAL! ", normalized, sizeof(normalized)) == MEMORIA_CONCEPT_OK);
    assert(strcmp(normalized, "diferenca de potencial") == 0);

    result = memoria_concept_resolve(&index, "electronics", "DDP");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(result.concept_id, "concept:voltage-stable") == 0);

    result = memoria_concept_resolve(&index, "electronics", "diferença de potencial");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(result.concept_id, "concept:voltage-stable") == 0);

    result = memoria_concept_resolve(&index, "other", "DDP");
    assert(result.status == MEMORIA_CONCEPT_UNRESOLVED);
    assert(result.reason == MEMORIA_CONCEPT_REASON_UNKNOWN);
}

static void test_polysemy_fails_closed_and_context_can_select_one(void) {
    memoria_concept_index index;
    memoria_concept_resolution result;
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
    memoria_concept_index_init(&index);
    assert(memoria_concept_register(&index, &finance) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&index, &river) == MEMORIA_CONCEPT_OK);

    result = memoria_concept_resolve(&index, "en", "bank");
    assert(result.status == MEMORIA_CONCEPT_UNRESOLVED);
    assert(result.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS);
    assert(result.candidate_count == 2);

    result = memoria_concept_resolve_with_context(&index, "en", "bank", "loan approval");
    assert(result.status == MEMORIA_CONCEPT_HIT);
    assert(result.reason == MEMORIA_CONCEPT_REASON_CONTEXT_CUE);
    assert(strcmp(result.concept_id, "concept:bank-finance") == 0);

    result = memoria_concept_resolve_with_context(&index, "en", "bank", "loan near river");
    assert(result.status == MEMORIA_CONCEPT_UNRESOLVED);
    assert(result.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT);

    result = memoria_concept_resolve_with_context(&index, "en", "bank", "status");
    assert(result.status == MEMORIA_CONCEPT_UNRESOLVED);
    assert(result.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS);
}

static void test_existing_identity_can_merge_aliases_but_not_change_meaning(void) {
    memoria_concept_index index;
    const char *first_aliases[] = {"ddp"};
    const char *second_aliases[] = {"tensão"};
    memoria_concept_definition first = {
        "concept:v", "pt", "voltagem", NULL, first_aliases, 1, NULL, 0
    };
    memoria_concept_definition second = {
        "concept:v", "pt", "voltagem", NULL, second_aliases, 1, NULL, 0
    };
    memoria_concept_definition conflict = {
        "concept:v", "pt", "corrente", NULL, NULL, 0, NULL, 0
    };
    memoria_concept_index_init(&index);
    assert(memoria_concept_register(&index, &first) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&index, &second) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_resolve(&index, "pt", "tensão").status == MEMORIA_CONCEPT_HIT);
    assert(memoria_concept_register(&index, &conflict) == MEMORIA_CONCEPT_IDENTITY_CONFLICT);
}

int main(void) {
    test_normalization_and_alias_identity();
    test_polysemy_fails_closed_and_context_can_select_one();
    test_existing_identity_can_merge_aliases_but_not_change_meaning();
    return 0;
}
