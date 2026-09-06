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

static size_t build(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *ns,
    memoria_concept_index *index,
    memoria_concept_relation_edge_storage *storage,
    memoria_concept_relation_edge *edges,
    size_t cap
) {
    size_t count = 0, i;
    assert(memoria_concept_relation_build_edges(
        turns, turn_count, ns, index, "semantic", storage, cap, &count
    ) == MEMORIA_CONCEPT_RELATION_ADAPTER_OK);
    for (i = 0; i < count; ++i) edges[i] = storage[i].edge;
    return count;
}

int main(void) {
    memoria_concept_index index;
    memoria_persist_turn turns[8];
    memoria_concept_relation_edge_storage storage[16];
    memoria_concept_relation_edge edges[16];
    memoria_concept_relation_path paths[8];
    size_t edge_count, path_count = 0;

    memset(turns, 0, sizeof(turns));
    memoria_concept_index_init(&index);

    /* Same subject, contradictory values in different namespaces. */
    turns[0].namespace_id = "session-a";
    turns[0].source_type = "user_assertion";
    set_relation(&turns[0], 0u, "charger", "voltage", "34v", 0.95, "a-34");

    turns[1].namespace_id = "session-b";
    turns[1].source_type = "user_assertion";
    set_relation(&turns[1], 0u, "charger", "voltage", "99v", 0.99, "b-99");

    /* Superseded high-confidence evidence must never dominate. */
    turns[2].namespace_id = "session-a";
    turns[2].source_type = "user_assertion";
    turns[2].superseded = 1;
    set_relation(&turns[2], 0u, "charger", "state", "danger", 1.00, "a-danger-old");

    /* Active replacement after supersession. */
    turns[3].namespace_id = "session-a";
    turns[3].source_type = "direct_observation";
    set_relation(&turns[3], 0u, "charger", "state", "safe", 0.90, "a-safe-new");

    /* Duplicate semantic edge with weaker evidence in same namespace. */
    turns[4].namespace_id = "session-a";
    turns[4].source_type = "user_assertion";
    set_relation(&turns[4], 0u, "charger", "voltage", "34v", 0.82, "a-34-weak");

    /* Foreign namespace relation that could create a tempting false path. */
    turns[5].namespace_id = "session-b";
    turns[5].source_type = "direct_observation";
    set_relation(&turns[5], 0u, "99v", "means", "danger", 1.00, "b-danger");

    /* Empty namespace is intentionally distinct from session-a/session-b. */
    turns[6].namespace_id = "";
    turns[6].source_type = "user_assertion";
    set_relation(&turns[6], 0u, "charger", "voltage", "12v", 1.00, "root-12");

    /* Another superseded foreign relation. */
    turns[7].namespace_id = "session-b";
    turns[7].source_type = "user_assertion";
    turns[7].superseded = 1;
    set_relation(&turns[7], 0u, "charger", "voltage", "120v", 1.00, "b-120-old");

    edge_count = build(turns, 8u, "session-a", &index, storage, edges, 16u);
    assert(edge_count == 3u); /* a-34, a-safe-new, a-34-weak */

    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:34v", edges, edge_count,
        2u, 8u, 0.0, paths, 8u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(path_count == 2u);
    assert(strcmp(paths[0].evidence_ids[0], "a-34") == 0);
    assert(strcmp(paths[1].evidence_ids[0], "a-34-weak") == 0);

    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:99v", edges, edge_count,
        2u, 8u, 0.0, paths, 8u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(path_count == 0u);

    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:danger", edges, edge_count,
        3u, 8u, 0.0, paths, 8u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(path_count == 0u);

    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:safe", edges, edge_count,
        2u, 8u, 0.0, paths, 8u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(path_count == 1u);
    assert(strcmp(paths[0].evidence_ids[0], "a-safe-new") == 0);

    edge_count = build(turns, 8u, "session-b", &index, storage, edges, 16u);
    assert(edge_count == 2u); /* b-99 and b-danger; b-120-old excluded */

    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:danger", edges, edge_count,
        3u, 8u, 0.0, paths, 8u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(path_count == 1u);
    assert(paths[0].hops == 2u);
    assert(strcmp(paths[0].evidence_ids[0], "b-99") == 0);
    assert(strcmp(paths[0].evidence_ids[1], "b-danger") == 0);

    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:120v", edges, edge_count,
        2u, 8u, 0.0, paths, 8u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);

    edge_count = build(turns, 8u, "", &index, storage, edges, 16u);
    assert(edge_count == 1u);
    path_count = 0;
    assert(memoria_concept_relation_infer_paths(
        "surface:charger", "surface:12v", edges, edge_count,
        2u, 8u, 0.0, paths, 8u, &path_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(path_count == 1u);
    assert(strcmp(paths[0].evidence_ids[0], "root-12") == 0);

    return 0;
}
