#include "concept_relation_runtime.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void set_relation(memoria_persist_turn *turn, size_t idx, const char *s, const char *p, const char *o, double c, const char *eid) {
    snprintf(turn->relations[idx].subject, sizeof(turn->relations[idx].subject), "%s", s);
    snprintf(turn->relations[idx].predicate, sizeof(turn->relations[idx].predicate), "%s", p);
    snprintf(turn->relations[idx].object, sizeof(turn->relations[idx].object), "%s", o);
    turn->relations[idx].confidence = c;
    snprintf(turn->relation_memory_ids[idx], sizeof(turn->relation_memory_ids[idx]), "%s", eid);
    turn->relation_count = idx + 1u;
}

int main(void) {
    memoria_concept_index index;
    const char *aliases[] = {"voltage", "ddp", "diferenca de potencial"};
    memoria_concept_definition voltage = {"voltage", "semantic", "voltage", "electric", aliases, 3u, NULL, 0u};
    memoria_persist_turn turns[2];
    memoria_concept_relation_path paths[4];
    size_t count = 0;

    memset(turns, 0, sizeof(turns));
    memoria_concept_index_init(&index);
    assert(memoria_concept_register(&index, &voltage) == MEMORIA_CONCEPT_OK);

    turns[0].namespace_id = "session-a";
    turns[0].source_type = "user_assertion";
    turns[0].text = "charger has diferenca de potencial";
    set_relation(&turns[0], 0u, "charger", "has", "diferenca de potencial", 0.96, "e1");

    turns[1].namespace_id = "session-a";
    turns[1].source_type = "direct_observation";
    turns[1].text = "voltage equals 34v";
    set_relation(&turns[1], 0u, "voltage", "equals", "34v", 0.94, "e2");

    assert(memoria_concept_relation_runtime_infer(
        turns, 2u, "session-a", &index, "semantic",
        "charger", "34v", "charger 34v",
        3u, 4u, 0.90, paths, 4u, &count
    ) == MEMORIA_CONCEPT_RELATION_RUNTIME_HIT);
    assert(count == 1u);
    assert(paths[0].hops == 2u);
    assert(strcmp(paths[0].node_keys[1], "concept:voltage") == 0);
    assert(strcmp(paths[0].evidence_ids[0], "e1") == 0);
    assert(strcmp(paths[0].evidence_ids[1], "e2") == 0);

    count = 0;
    assert(memoria_concept_relation_runtime_infer(
        turns, 2u, "other", &index, "semantic",
        "charger", "34v", "charger 34v",
        3u, 4u, 0.90, paths, 4u, &count
    ) == MEMORIA_CONCEPT_RELATION_RUNTIME_UNRESOLVED);
    assert(count == 0u);
    return 0;
}
