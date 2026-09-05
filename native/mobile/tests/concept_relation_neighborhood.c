#include "concept_relation_neighborhood.h"

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
    const char *voltage_aliases[] = {"voltage", "ddp", "diferenca de potencial"};
    memoria_concept_definition voltage = {"voltage", "semantic", "voltage", "electric", voltage_aliases, 3u, NULL, 0u};
    memoria_persist_turn turns[5];
    memoria_concept_relation_neighbor neighbors[4];
    size_t count = 0;

    memset(turns, 0, sizeof(turns));
    memoria_concept_index_init(&index);
    assert(memoria_concept_register(&index, &voltage) == MEMORIA_CONCEPT_OK);

    turns[0].namespace_id = "session-a";
    turns[0].source_type = "user_assertion";
    turns[0].text = "charger has voltage";
    set_relation(&turns[0], 0u, "charger", "has", "voltage", 0.96, "e1");

    turns[1].namespace_id = "session-a";
    turns[1].source_type = "direct_observation";
    turns[1].text = "charger uses usb-c";
    set_relation(&turns[1], 0u, "charger", "uses", "usb-c", 0.93, "e2");

    turns[2].namespace_id = "session-a";
    turns[2].source_type = "user_assertion";
    turns[2].text = "charger maybe old";
    set_relation(&turns[2], 0u, "charger", "is", "old", 0.55, "e3");

    turns[3].namespace_id = "session-b";
    turns[3].source_type = "user_assertion";
    turns[3].text = "charger has secret";
    set_relation(&turns[3], 0u, "charger", "has", "secret", 0.99, "e4");

    turns[4].namespace_id = "session-a";
    turns[4].source_type = "user_assertion";
    turns[4].text = "charger obsolete relation";
    turns[4].superseded = 1;
    set_relation(&turns[4], 0u, "charger", "has", "obsolete", 1.0, "e5");

    assert(memoria_concept_relation_neighborhood(
        turns, 5u, "session-a", &index, "semantic", "charger", "charger relations",
        0.80, neighbors, 4u, &count
    ) == MEMORIA_CONCEPT_NEIGHBORHOOD_HIT);
    assert(count == 2u);
    assert(strcmp(neighbors[0].node_key, "concept:voltage") == 0);
    assert(strcmp(neighbors[0].evidence_id, "e1") == 0);
    assert(strcmp(neighbors[1].node_key, "surface:usb-c") == 0);
    assert(strcmp(neighbors[1].evidence_id, "e2") == 0);

    count = 0;
    assert(memoria_concept_relation_neighborhood(
        turns, 5u, "session-b", &index, "semantic", "charger", "charger relations",
        0.80, neighbors, 4u, &count
    ) == MEMORIA_CONCEPT_NEIGHBORHOOD_HIT);
    assert(count == 1u);
    assert(strcmp(neighbors[0].node_key, "surface:secret") == 0);

    count = 0;
    assert(memoria_concept_relation_neighborhood(
        turns, 5u, "session-a", &index, "semantic", "unknown", "",
        0.80, neighbors, 4u, &count
    ) == MEMORIA_CONCEPT_NEIGHBORHOOD_UNRESOLVED);
    assert(count == 0u);
    return 0;
}
