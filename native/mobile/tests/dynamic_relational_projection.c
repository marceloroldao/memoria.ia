#include "concept_relation_collection.h"
#include "concept_relation_neighborhood.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void set_relation(
    memoria_persist_turn *turn,
    size_t idx,
    const char *subject,
    const char *predicate,
    const char *object,
    double confidence,
    const char *evidence_id
) {
    snprintf(turn->relations[idx].subject, sizeof(turn->relations[idx].subject), "%s", subject);
    snprintf(turn->relations[idx].predicate, sizeof(turn->relations[idx].predicate), "%s", predicate);
    snprintf(turn->relations[idx].object, sizeof(turn->relations[idx].object), "%s", object);
    turn->relations[idx].confidence = confidence;
    snprintf(turn->relation_memory_ids[idx], sizeof(turn->relation_memory_ids[idx]), "%s", evidence_id);
    turn->relation_count = idx + 1u;
}

int main(void) {
    memoria_concept_index index;
    memoria_persist_turn turns[4];
    memoria_concept_collection_member members[8];
    memoria_concept_relation_neighbor neighbors[8];
    size_t member_count = 0;
    size_t neighbor_count = 0;

    memset(turns, 0, sizeof(turns));
    memset(members, 0, sizeof(members));
    memset(neighbors, 0, sizeof(neighbors));
    memoria_concept_index_init(&index);

    /* Stable factual evidence. */
    turns[0].namespace_id = "projection";
    turns[0].source_type = "user_assertion";
    set_relation(&turns[0], 0u, "Vivi", "is", "gato", 0.95, "e-vivi-cat");

    turns[1].namespace_id = "projection";
    turns[1].source_type = "user_assertion";
    set_relation(&turns[1], 0u, "Lay", "is", "gato", 0.95, "e-lay-cat");

    /* A second factual relation exists but must not change type collection. */
    turns[2].namespace_id = "projection";
    turns[2].source_type = "user_assertion";
    set_relation(&turns[2], 0u, "Vivi", "cor", "preto", 0.90, "e-vivi-color");

    /* Generative output must never enter factual projection. */
    turns[3].namespace_id = "projection";
    turns[3].source_type = "assistant_generated";
    set_relation(&turns[3], 0u, "Vivi", "is", "assistente", 1.00, "e-llm-pollution");

    /* Projection A: type -> members. Same persisted evidence, query anchored on gato. */
    assert(memoria_concept_relation_collect_type(
        turns, 4u, "projection", &index, "semantic", "gato",
        "Quais gatos você conhece?", 0.80, members, 8u, &member_count
    ) == MEMORIA_CONCEPT_COLLECTION_HIT);
    assert(member_count == 2u);
    assert(strcmp(members[0].member_key, "surface:lay") == 0 || strcmp(members[0].member_key, "surface:vivi") == 0);
    assert(strcmp(members[1].member_key, "surface:lay") == 0 || strcmp(members[1].member_key, "surface:vivi") == 0);
    assert(strcmp(members[0].member_key, members[1].member_key) != 0);

    /* Projection B: entity -> neighborhood. No evidence is rewritten or promoted. */
    assert(memoria_concept_relation_neighborhood(
        turns, 4u, "projection", &index, "semantic", "Vivi",
        "Quem é Vivi?", 0.80, neighbors, 8u, &neighbor_count
    ) == MEMORIA_CONCEPT_NEIGHBORHOOD_HIT);
    assert(neighbor_count == 2u);

    {
        int saw_cat = 0;
        int saw_color = 0;
        int saw_llm_pollution = 0;
        size_t i;
        for (i = 0; i < neighbor_count; ++i) {
            if (strcmp(neighbors[i].node_key, "surface:gato") == 0 && strcmp(neighbors[i].predicate, "is") == 0)
                saw_cat = 1;
            if (strcmp(neighbors[i].node_key, "surface:preto") == 0 && strcmp(neighbors[i].predicate, "cor") == 0)
                saw_color = 1;
            if (strcmp(neighbors[i].node_key, "surface:assistente") == 0)
                saw_llm_pollution = 1;
        }
        assert(saw_cat);
        assert(saw_color);
        assert(!saw_llm_pollution);
    }

    /* Re-run Projection A after Projection B: the factual state is unchanged. */
    memset(members, 0, sizeof(members));
    member_count = 0;
    assert(memoria_concept_relation_collect_type(
        turns, 4u, "projection", &index, "semantic", "gato",
        "Quantos gatos você conhece?", 0.80, members, 8u, &member_count
    ) == MEMORIA_CONCEPT_COLLECTION_HIT);
    assert(member_count == 2u);

    return 0;
}
