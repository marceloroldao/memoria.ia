#include "concept_identity_kernel.h"
#include "concept_query_rewrite.h"

#include <stdio.h>
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

static const char *status_name(memoria_concept_rewrite_status status) {
    switch (status) {
        case MEMORIA_CONCEPT_REWRITE_UNCHANGED: return "UNCHANGED";
        case MEMORIA_CONCEPT_REWRITE_REWRITTEN: return "REWRITTEN";
        case MEMORIA_CONCEPT_REWRITE_UNRESOLVED: return "UNRESOLVED";
        default: return "UNKNOWN";
    }
}

static const char *reason_name(memoria_concept_rewrite_reason reason) {
    switch (reason) {
        case MEMORIA_CONCEPT_REWRITE_REASON_NONE: return "";
        case MEMORIA_CONCEPT_REWRITE_REASON_EMPTY: return "empty";
        case MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS: return "ambiguous_concept";
        case MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS_CONTEXT: return "ambiguous_context";
        case MEMORIA_CONCEPT_REWRITE_REASON_MISSING_CONCEPT: return "missing_concept";
        case MEMORIA_CONCEPT_REWRITE_REASON_CAPACITY: return "capacity";
        default: return "unknown";
    }
}

int main(int argc, char **argv) {
    memoria_concept_index index;
    memoria_concept_rewrite_result result;
    size_t i;
    const char *voltage_aliases[] = {"ddp", "diferença de potencial", "potential difference"};
    const char *finance_aliases[] = {"bank"};
    const char *finance_cues[] = {"loan", "credit"};
    const char *river_aliases[] = {"bank"};
    const char *river_cues[] = {"river", "water"};
    memoria_concept_definition voltage = defn(
        "concept:voltage", "semantic", "voltage", "electric potential",
        voltage_aliases, 3, NULL, 0
    );
    memoria_concept_definition finance = defn(
        "concept:bank-finance", "semantic", "financial bank", "finance",
        finance_aliases, 1, finance_cues, 2
    );
    memoria_concept_definition river = defn(
        "concept:bank-river", "semantic", "river bank", "geography",
        river_aliases, 1, river_cues, 2
    );

    if (argc != 2) return 2;
    memoria_concept_index_init(&index);
    if (memoria_concept_register(&index, &voltage) != MEMORIA_CONCEPT_OK ||
        memoria_concept_register(&index, &finance) != MEMORIA_CONCEPT_OK ||
        memoria_concept_register(&index, &river) != MEMORIA_CONCEPT_OK) return 3;

    result = memoria_concept_rewrite_query(&index, "semantic", argv[1], 6);
    printf("%s\t%s\t%s\t", status_name(result.status), reason_name(result.reason), result.rewritten_query);
    for (i = 0; i < result.concept_count; ++i) {
        if (i) putchar(',');
        fputs(result.concept_ids[i], stdout);
    }
    putchar('\n');
    return 0;
}
