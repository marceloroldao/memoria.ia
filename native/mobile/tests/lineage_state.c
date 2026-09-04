#include "lineage_state.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); return 1; } } while (0)

static void init_turn(
    memoria_persist_turn *turn,
    const char *memory_id,
    const char *namespace_id,
    const char *source_type,
    long order
) {
    memset(turn, 0, sizeof(*turn));
    turn->memory_id = (char *)memory_id;
    turn->namespace_id = (char *)namespace_id;
    turn->text = (char *)memory_id;
    turn->role = (char *)"user";
    turn->source_type = (char *)source_type;
    turn->ultimate_source_memory_id = (char *)memory_id;
    turn->authority = 1.0;
    turn->order = order;
}

static void add_relation(memoria_persist_turn *turn, const char *relation_id, double confidence) {
    turn->relation_count = 1;
    snprintf(turn->relation_memory_ids[0], sizeof(turn->relation_memory_ids[0]), "%s", relation_id);
    snprintf(turn->relations[0].subject, sizeof(turn->relations[0].subject), "%s", "device");
    snprintf(turn->relations[0].predicate, sizeof(turn->relations[0].predicate), "%s", "mode");
    snprintf(turn->relations[0].object, sizeof(turn->relations[0].object), "%s", "local");
    turn->relations[0].confidence = confidence;
}

static int resolve_expect(
    memoria_persistence *p,
    const char *memory_id,
    int expected_active
) {
    memoria_lineage_result r = {0};
    CHECK(memoria_lineage_state_resolve(p, memory_id, "s", &r) == 1);
    CHECK(r.factual_active == expected_active);
    return 0;
}

int main(void) {
    const char *path = "./tmp-mobile-lineage-state";
    memoria_persistence *p = NULL;
    memoria_persist_turn a, b, derived, correction;
    size_t superseded_slots[1] = {2};

    (void)system("rm -rf ./tmp-mobile-lineage-state");
    CHECK(memoria_persistence_open(path, "org-lineage-state", &p) == 1);

    init_turn(&a, "a", "s", "user_assertion", 1);
    add_relation(&a, "a-rel", 0.98);
    CHECK(memoria_persistence_save_turn(p, 1, 1, &a) == 1);

    init_turn(&b, "b", "s", "user_assertion", 2);
    add_relation(&b, "b-rel", 0.96);
    CHECK(memoria_persistence_save_turn(p, 2, 2, &b) == 1);

    init_turn(&derived, "derived", "s", "derived_relation", 3);
    derived.role = (char *)"assistant";
    derived.parent_count = 2;
    snprintf(derived.parent_memory_ids[0], sizeof(derived.parent_memory_ids[0]), "%s", "a-rel");
    snprintf(derived.parent_memory_ids[1], sizeof(derived.parent_memory_ids[1]), "%s", "b-rel");
    derived.ultimate_source_memory_id = (char *)"a";
    CHECK(memoria_persistence_save_turn(p, 3, 3, &derived) == 1);
    CHECK(memoria_persistence_sync(p) == 1);
    CHECK(resolve_expect(p, "derived", 1) == 0);

    init_turn(&correction, "b-new", "s", "user_correction", 4);
    add_relation(&correction, "b-new-rel", 1.0);
    correction.parent_count = 1;
    snprintf(correction.parent_memory_ids[0], sizeof(correction.parent_memory_ids[0]), "%s", "b");
    CHECK(memoria_persistence_save_turn_with_supersessions(
        p, 4, 4, &correction,
        superseded_slots, 1, "b-new") == 1);
    CHECK(memoria_persistence_sync(p) == 1);
    CHECK(resolve_expect(p, "derived", 0) == 0);

    memoria_persistence_close(p);
    p = NULL;

    CHECK(memoria_persistence_open(path, "org-lineage-state", &p) == 1);
    CHECK(resolve_expect(p, "derived", 0) == 0);
    CHECK(resolve_expect(p, "b-new", 1) == 0);

    memoria_persistence_close(p);
    (void)system("rm -rf ./tmp-mobile-lineage-state");
    return 0;
}
