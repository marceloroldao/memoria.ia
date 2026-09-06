#include "concept_relation_adapter.h"
#include "concept_relation_collection.h"
#include "concept_relation_traversal.h"
#include "concept_identity_kernel.h"

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

static int has_member(const memoria_concept_collection_member *members, size_t count, const char *key) {
    size_t i;
    for (i = 0; i < count; ++i) if (strcmp(members[i].member_key, key) == 0) return 1;
    return 0;
}

static int has_path_to(memoria_concept_relation_path *paths, size_t count, const char *target) {
    size_t i;
    for (i = 0; i < count; ++i) {
        if (paths[i].hops > 0 && strcmp(paths[i].node_keys[paths[i].hops], target) == 0) return 1;
    }
    return 0;
}

int main(void) {
    memoria_concept_index index;
    memoria_persist_turn turns[14];
    memoria_concept_relation_edge_storage storage[32];
    memoria_concept_relation_edge edges[32];
    memoria_concept_relation_path paths[8];
    memoria_concept_collection_member members[8];
    size_t edge_count = 0, path_count = 0, member_count = 0, i;

    memset(turns, 0, sizeof(turns));
    memoria_concept_index_init(&index);

    /* Animals */
    turns[0].namespace_id = "session-a"; turns[0].source_type = "user_assertion";
    set_relation(&turns[0], 0, "Alt", "is", "gato", 0.98, "e-alt-type");
    set_relation(&turns[0], 1, "Alt", "has_color", "preto", 0.96, "e-alt-color");
    turns[1].namespace_id = "session-a"; turns[1].source_type = "user_assertion";
    set_relation(&turns[1], 0, "Luna", "is", "gato", 0.97, "e-luna-type");
    set_relation(&turns[1], 1, "Luna", "has_color", "branco", 0.95, "e-luna-color");
    turns[2].namespace_id = "session-a"; turns[2].source_type = "direct_observation";
    set_relation(&turns[2], 0, "gato", "is", "animal", 0.99, "e-cat-animal");

    /* Vehicles */
    turns[3].namespace_id = "session-a"; turns[3].source_type = "user_assertion";
    set_relation(&turns[3], 0, "Kombi", "is", "veiculo", 0.97, "e-kombi-type");
    set_relation(&turns[3], 1, "Kombi", "has_color", "azul", 0.96, "e-kombi-color");
    turns[4].namespace_id = "session-a"; turns[4].source_type = "user_assertion";
    set_relation(&turns[4], 0, "Jetta", "is", "veiculo", 0.97, "e-jetta-type");
    set_relation(&turns[4], 1, "Jetta", "has_color", "preto", 0.99, "e-jetta-old-color");
    turns[4].superseded = 1;
    turns[5].namespace_id = "session-a"; turns[5].source_type = "user_correction";
    set_relation(&turns[5], 0, "Jetta", "is", "veiculo", 0.98, "e-jetta-type-new");
    set_relation(&turns[5], 1, "Jetta", "has_color", "vermelho", 1.00, "e-jetta-color-new");

    /* People / ownership */
    turns[6].namespace_id = "session-a"; turns[6].source_type = "user_assertion";
    set_relation(&turns[6], 0, "Marcelo", "owns", "Alt", 0.99, "e-owner-alt");
    turns[7].namespace_id = "session-a"; turns[7].source_type = "user_assertion";
    set_relation(&turns[7], 0, "Marcelo", "owns", "Kombi", 0.95, "e-owner-kombi");

    /* Foreign namespace contamination attempts */
    turns[8].namespace_id = "session-b"; turns[8].source_type = "user_assertion";
    set_relation(&turns[8], 0, "Alt", "has_color", "verde", 1.00, "e-alt-foreign-color");
    turns[9].namespace_id = "session-b"; turns[9].source_type = "user_assertion";
    set_relation(&turns[9], 0, "Rex", "is", "gato", 1.00, "e-rex-foreign");

    /* Weak and ambiguous noise */
    turns[10].namespace_id = "session-a"; turns[10].source_type = "derived_relation";
    set_relation(&turns[10], 0, "Alt", "similar_to", "Jetta", 0.30, "e-weak-noise");
    turns[11].namespace_id = "session-a"; turns[11].source_type = "user_assertion";
    set_relation(&turns[11], 0, "banco", "is", "financeiro", 0.95, "e-bank-fin");
    set_relation(&turns[11], 1, "banco", "is", "margem", 0.95, "e-bank-river");

    /* Superseded unrelated memory should never leak. */
    turns[12].namespace_id = "session-a"; turns[12].source_type = "user_assertion"; turns[12].superseded = 1;
    set_relation(&turns[12], 0, "Luna", "has_color", "rosa", 1.00, "e-luna-old");
    turns[13].namespace_id = "session-a"; turns[13].source_type = "user_assertion";
    set_relation(&turns[13], 0, "Corsa", "is", "veiculo", 0.91, "e-corsa-type");

    assert(memoria_concept_relation_build_edges(turns, 14, "session-a", &index, "semantic", storage, 32, &edge_count) == MEMORIA_CONCEPT_RELATION_ADAPTER_OK);
    for (i = 0; i < edge_count; ++i) edges[i] = storage[i].edge;

    /* RC5-G01: Alt color resolves correctly; foreign namespace color cannot contaminate. */
    assert(memoria_concept_relation_infer_paths("surface:alt", "surface:preto", edges, edge_count, 2, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(path_count >= 1);
    path_count = 0;
    assert(memoria_concept_relation_infer_paths("surface:alt", "surface:verde", edges, edge_count, 2, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);

    /* RC5-G02: correction wins because superseded old Jetta color is removed at adapter boundary. */
    path_count = 0;
    assert(memoria_concept_relation_infer_paths("surface:jetta", "surface:vermelho", edges, edge_count, 2, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(has_path_to(paths, path_count, "surface:vermelho"));
    path_count = 0;
    assert(memoria_concept_relation_infer_paths("surface:jetta", "surface:preto", edges, edge_count, 2, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);

    /* RC5-G03: taxonomy supports multi-hop Alt -> gato -> animal. */
    path_count = 0;
    assert(memoria_concept_relation_infer_paths("surface:alt", "surface:animal", edges, edge_count, 3, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(paths[0].hops == 2);

    /* RC5-G04: ownership path remains directional. */
    path_count = 0;
    assert(memoria_concept_relation_infer_paths("surface:marcelo", "surface:alt", edges, edge_count, 2, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    path_count = 0;
    assert(memoria_concept_relation_infer_paths("surface:alt", "surface:marcelo", edges, edge_count, 2, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);

    /* RC5-G05: collections remain type-clean in a mixed corpus. */
    assert(memoria_concept_relation_collect_type(turns, 14, "session-a", &index, "semantic", "gato", "", 0.80, members, 8, &member_count) == MEMORIA_CONCEPT_COLLECTION_HIT);
    assert(member_count == 2);
    assert(has_member(members, member_count, "surface:alt"));
    assert(has_member(members, member_count, "surface:luna"));
    assert(!has_member(members, member_count, "surface:rex"));
    assert(!has_member(members, member_count, "surface:animal"));

    member_count = 0;
    assert(memoria_concept_relation_collect_type(turns, 14, "session-a", &index, "semantic", "veiculo", "", 0.80, members, 8, &member_count) == MEMORIA_CONCEPT_COLLECTION_HIT);
    assert(member_count == 3);
    assert(has_member(members, member_count, "surface:kombi"));
    assert(has_member(members, member_count, "surface:jetta"));
    assert(has_member(members, member_count, "surface:corsa"));

    /* RC5-G06: weak noise below threshold does not create a false relation. */
    path_count = 0;
    assert(memoria_concept_relation_infer_paths("surface:alt", "surface:jetta", edges, edge_count, 2, 4, 0.80, paths, 8, &path_count) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);

    return 0;
}
