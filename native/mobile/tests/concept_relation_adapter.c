#include "concept_relation_adapter.h"
#include "concept_relation_traversal.h"

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
    const char *bank_aliases[] = {"bank"};
    const char *loan_cues[] = {"loan"};
    const char *river_cues[] = {"river"};
    memoria_concept_definition voltage = {"voltage", "semantic", "voltage", "electric", voltage_aliases, 3u, NULL, 0u};
    memoria_concept_definition bank_fin = {"bank-fin", "semantic", "financial bank", "finance", bank_aliases, 1u, loan_cues, 1u};
    memoria_concept_definition bank_river = {"bank-river", "semantic", "river bank", "geography", bank_aliases, 1u, river_cues, 1u};
    memoria_persist_turn turns[5];
    memoria_concept_relation_edge_storage storage[8];
    memoria_concept_relation_edge edges[8];
    memoria_concept_relation_path paths[4];
    size_t edge_count = 0, path_count = 0, i;

    memset(turns, 0, sizeof(turns));
    memoria_concept_index_init(&index);
    assert(memoria_concept_register(&index, &voltage) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&index, &bank_fin) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_register(&index, &bank_river) == MEMORIA_CONCEPT_OK);

    turns[0].namespace_id = "session-a";
    turns[0].source_type = "user_assertion";
    turns[0].text = "charger has diferenca de potencial";
    set_relation(&turns[0], 0u, "charger", "has", "diferenca de potencial", 0.96, "e1");

    turns[1].namespace_id = "session-a";
    turns[1].source_type = "direct_observation";
    turns[1].text = "voltage equals 34v";
    set_relation(&turns[1], 0u, "voltage", "equals", "34v", 0.94, "e2");

    turns[2].namespace_id = "session-b";
    turns[2].source_type = "user_assertion";
    turns[2].text = "voltage equals 99v";
    set_relation(&turns[2], 0u, "voltage", "equals", "99v", 0.99, "e3");

    turns[3].namespace_id = "session-a";
    turns[3].source_type = "user_assertion";
    turns[3].text = "obsolete relation";
    turns[3].superseded = 1;
    set_relation(&turns[3], 0u, "34v", "obsolete", "danger", 1.0, "e4");

    turns[4].namespace_id = "session-a";
    turns[4].source_type = "user_assertion";
    turns[4].text = "bank is nearby";
    set_relation(&turns[4], 0u, "bank", "is", "nearby", 0.95, "e5");

    assert(memoria_concept_relation_build_edges(
        turns, 5u, "session-a", &index, "semantic", storage, 8u, &edge_count
    ) == MEMORIA_CONCEPT_RELATION_ADAPTER_OK);
    assert(edge_count == 3u);
    for (i = 0; i < edge_count; ++i) edges[i] = storage[i].edge;

    assert(strcmp(storage[0].subject_key, "surface:charger") == 0);
    assert(strcmp(storage[0].object_key, "concept:voltage") == 0);
    assert(strcmp(storage[1].subject_key, "concept:voltage") == 0);
    assert(strcmp(storage[1].object_key, "surface:34v") == 0);
    assert(storage[2].edge.ambiguous == 1);

    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:34v", edges, edge_count,
        3u, 4u, 0.90, paths, 4u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(path_count == 1u);
    assert(paths[0].hops == 2u);
    assert(paths[0].confidence == 0.94);
    assert(strcmp(paths[0].evidence_ids[0], "e1") == 0);
    assert(strcmp(paths[0].evidence_ids[1], "e2") == 0);

    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "concept:bank-fin", "surface:nearby", edges, edge_count,
        2u, 2u, 0.0, paths, 4u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(path_count == 0u);
    return 0;
}
