#include "semantic_consolidation_state.h"

#include "lineage_state.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

static int direct_evidence_source(const char *source_type) {
    if (!source_type) return 0;
    return strcmp(source_type, "user_assertion") == 0 ||
           strcmp(source_type, "user_correction") == 0 ||
           strcmp(source_type, "direct_observation") == 0 ||
           strcmp(source_type, "external_import") == 0;
}

static int normalized_equal(const char *a, const char *b) {
    size_t ia = 0, ib = 0;
    if (!a || !b) return 0;
    for (;;) {
        while (a[ia] && isspace((unsigned char)a[ia])) ++ia;
        while (b[ib] && isspace((unsigned char)b[ib])) ++ib;
        if (!a[ia] || !b[ib]) return a[ia] == 0 && b[ib] == 0;
        if (tolower((unsigned char)a[ia]) != tolower((unsigned char)b[ib])) return 0;
        ++ia; ++ib;
    }
}

static int candidate_matches_relation(
    const memoria_semantic_candidate *candidate,
    const memoria_relation *relation,
    const char *namespace_id
) {
    return candidate && relation &&
           normalized_equal(candidate->namespace_id, namespace_id ? namespace_id : "") &&
           normalized_equal(candidate->subject, relation->subject) &&
           normalized_equal(candidate->predicate, relation->predicate) &&
           normalized_equal(candidate->object, relation->object);
}

static int active_derived_claim_exists(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const memoria_semantic_candidate *candidate
) {
    size_t i, j;
    for (i = 0; i < turn_count; ++i) {
        memoria_lineage_result lineage = {0};
        const memoria_persist_turn *turn = &turns[i];
        if (!turn->memory_id || !turn->source_type || strcmp(turn->source_type, "derived_relation") != 0)
            continue;
        if (!memoria_lineage_rows_resolve(
                turns, turn_count, turn->memory_id,
                turn->namespace_id ? turn->namespace_id : "", &lineage))
            continue;
        if (!lineage.factual_active) continue;
        for (j = 0; j < turn->relation_count; ++j)
            if (candidate_matches_relation(candidate, &turn->relations[j], turn->namespace_id))
                return 1;
    }
    return 0;
}

size_t memoria_semantic_consolidation_from_turns(
    const memoria_persist_turn *turns,
    size_t turn_count,
    size_t min_independent_roots,
    memoria_semantic_candidate *out,
    size_t out_capacity
) {
    memoria_semantic_support *supports = NULL;
    memoria_semantic_candidate *raw = NULL;
    size_t max_supports = 0, support_count = 0, raw_count, result_count = 0;
    size_t i, j;

    if (!turns || !turn_count || !out || !out_capacity || min_independent_roots < 2)
        return 0;

    for (i = 0; i < turn_count; ++i) {
        if (direct_evidence_source(turns[i].source_type))
            max_supports += turns[i].relation_count;
    }
    if (!max_supports) return 0;

    supports = (memoria_semantic_support *)calloc(max_supports, sizeof(*supports));
    raw = (memoria_semantic_candidate *)calloc(out_capacity, sizeof(*raw));
    if (!supports || !raw) goto cleanup;

    for (i = 0; i < turn_count; ++i) {
        const memoria_persist_turn *turn = &turns[i];
        if (!direct_evidence_source(turn->source_type)) continue;
        for (j = 0; j < turn->relation_count; ++j) {
            memoria_lineage_result lineage = {0};
            const char *support_id = turn->relation_memory_ids[j];
            if (!support_id || !*support_id) continue;
            if (!memoria_lineage_rows_resolve(
                    turns, turn_count, support_id,
                    turn->namespace_id ? turn->namespace_id : "", &lineage))
                continue;
            supports[support_count].namespace_id = turn->namespace_id ? turn->namespace_id : "";
            supports[support_count].subject = turn->relations[j].subject;
            supports[support_count].predicate = turn->relations[j].predicate;
            supports[support_count].object = turn->relations[j].object;
            supports[support_count].support_memory_id = support_id;
            supports[support_count].factual_root_id = lineage.representative_root_id;
            supports[support_count].confidence = turn->relations[j].confidence;
            supports[support_count].factual_active = lineage.factual_active;
            ++support_count;
        }
    }

    raw_count = memoria_semantic_consolidation_candidates(
        supports, support_count, min_independent_roots, raw, out_capacity);

    for (i = 0; i < raw_count && result_count < out_capacity; ++i) {
        if (active_derived_claim_exists(turns, turn_count, &raw[i])) continue;
        out[result_count++] = raw[i];
    }

cleanup:
    free(raw);
    free(supports);
    return result_count;
}
