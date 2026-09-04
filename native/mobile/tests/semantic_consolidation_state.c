#include "semantic_consolidation_state.h"

#include <assert.h>
#include <string.h>

static void factual_turn(
    memoria_persist_turn *turn,
    const char *memory_id,
    const char *relation_id,
    const char *source_type,
    long order
) {
    memset(turn, 0, sizeof(*turn));
    turn->memory_id = (char *)memory_id;
    turn->namespace_id = "s";
    turn->text = "sensor is active";
    turn->role = "user";
    turn->source_type = (char *)source_type;
    turn->ultimate_source_memory_id = (char *)memory_id;
    turn->authority = 1.0;
    turn->order = order;
    strcpy(turn->relations[0].subject, "sensor");
    strcpy(turn->relations[0].predicate, "is");
    strcpy(turn->relations[0].object, "active");
    turn->relations[0].confidence = 0.95;
    strcpy(turn->relation_memory_ids[0], relation_id);
    turn->relation_count = 1;
}

static void derived_turn(memoria_persist_turn *turn) {
    memset(turn, 0, sizeof(*turn));
    turn->memory_id = "derived-a-b";
    turn->namespace_id = "s";
    turn->text = "sensor is active";
    turn->role = "assistant";
    turn->source_type = "derived_relation";
    turn->ultimate_source_memory_id = "root-a";
    turn->authority = 0.95;
    turn->order = 3;
    strcpy(turn->parent_memory_ids[0], "root-a-rel");
    strcpy(turn->parent_memory_ids[1], "root-b-rel");
    turn->parent_count = 2;
    strcpy(turn->relations[0].subject, "sensor");
    strcpy(turn->relations[0].predicate, "is");
    strcpy(turn->relations[0].object, "active");
    turn->relations[0].confidence = 0.95;
    strcpy(turn->relation_memory_ids[0], "derived-a-b-rel");
    turn->relation_count = 1;
}

int main(void) {
    memoria_persist_turn turns[5];
    memoria_semantic_candidate out[4];
    size_t n;

    factual_turn(&turns[0], "root-a", "root-a-rel", "user_assertion", 1);
    factual_turn(&turns[1], "root-b", "root-b-rel", "direct_observation", 2);

    n = memoria_semantic_consolidation_from_turns(turns, 2, 2, out, 4);
    assert(n == 1);
    assert(strcmp(out[0].subject, "sensor") == 0);
    assert(strcmp(out[0].object, "active") == 0);
    assert(out[0].support_count == 2);

    /* Once the same exact claim already has an active factual derivation,
       retries must not emit another candidate. */
    derived_turn(&turns[2]);
    n = memoria_semantic_consolidation_from_turns(turns, 3, 2, out, 4);
    assert(n == 0);

    /* Correcting one support invalidates both that support and the old
       conjunctive derivation. A new independent root may then reconsolidate
       the claim with the surviving root. */
    turns[1].superseded = 1;
    strcpy(turns[1].superseded_by, "root-b-fix");
    factual_turn(&turns[3], "root-b-fix", "root-b-fix-rel", "user_correction", 4);
    strcpy(turns[3].relations[0].object, "inactive");

    n = memoria_semantic_consolidation_from_turns(turns, 4, 2, out, 4);
    assert(n == 0);

    factual_turn(&turns[4], "root-c", "root-c-rel", "external_import", 5);
    n = memoria_semantic_consolidation_from_turns(turns, 5, 2, out, 4);
    assert(n == 1);
    assert(out[0].support_count == 2);
    assert(strcmp(out[0].factual_root_ids[0], "root-a") == 0 || strcmp(out[0].factual_root_ids[1], "root-a") == 0);
    assert(strcmp(out[0].factual_root_ids[0], "root-c") == 0 || strcmp(out[0].factual_root_ids[1], "root-c") == 0);

    /* Generated memories never become independent evidence. */
    factual_turn(&turns[4], "generated", "generated-rel", "assistant_generated", 6);
    n = memoria_semantic_consolidation_from_turns(turns + 3, 2, 2, out, 4);
    assert(n == 0);

    return 0;
}
