#include "concept_relation_collection.h"
#include "concept_relation_collection_query.h"

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
    memoria_persist_turn turns[6];
    memoria_concept_collection_member members[8];
    char type_surface[96];
    size_t count = 0;

    memset(turns, 0, sizeof(turns));
    memoria_concept_index_init(&index);

    turns[0].namespace_id = "session-a";
    turns[0].source_type = "user_assertion";
    set_relation(&turns[0], 0u, "Alt", "is", "gato", 0.95, "e-alt");

    turns[1].namespace_id = "session-a";
    turns[1].source_type = "user_assertion";
    set_relation(&turns[1], 0u, "Luna", "is", "gato", 0.93, "e-luna");

    /* Direction matters: this must not make animal a member of gato. */
    turns[2].namespace_id = "session-a";
    turns[2].source_type = "direct_observation";
    set_relation(&turns[2], 0u, "gato", "is", "animal", 0.99, "e-animal");

    /* Attribute-like relation must not be returned as a type member. */
    turns[3].namespace_id = "session-a";
    turns[3].source_type = "direct_observation";
    set_relation(&turns[3], 0u, "gato", "has", "pelos", 0.99, "e-fur");

    /* Other namespaces remain isolated. */
    turns[4].namespace_id = "session-b";
    turns[4].source_type = "user_assertion";
    set_relation(&turns[4], 0u, "Nina", "is", "gato", 1.00, "e-nina");

    /* Superseded evidence remains excluded by the relation adapter. */
    turns[5].namespace_id = "session-a";
    turns[5].source_type = "user_assertion";
    turns[5].superseded = 1;
    set_relation(&turns[5], 0u, "Milo", "is", "gato", 1.00, "e-milo");

    assert(memoria_collection_query_extract("Quais gatos você conhece?", type_surface, sizeof(type_surface)) == MEMORIA_COLLECTION_QUERY_HIT);
    assert(strcmp(type_surface, "gato") == 0);

    assert(memoria_concept_relation_collect_type(
        turns, 6u, "session-a", &index, "semantic", type_surface,
        "Quais gatos você conhece?", 0.80, members, 8u, &count
    ) == MEMORIA_CONCEPT_COLLECTION_HIT);
    assert(count == 2u);
    assert(strcmp(members[0].member_key, "surface:alt") == 0);
    assert(strcmp(members[0].evidence_id, "e-alt") == 0);
    assert(strcmp(members[1].member_key, "surface:luna") == 0);
    assert(strcmp(members[1].evidence_id, "e-luna") == 0);

    count = 0;
    assert(memoria_concept_relation_collect_type(
        turns, 6u, "session-b", &index, "semantic", "gato", "", 0.80,
        members, 8u, &count
    ) == MEMORIA_CONCEPT_COLLECTION_HIT);
    assert(count == 1u);
    assert(strcmp(members[0].member_key, "surface:nina") == 0);

    assert(memoria_collection_query_extract("Which cats do you know?", type_surface, sizeof(type_surface)) == MEMORIA_COLLECTION_QUERY_HIT);
    assert(strcmp(type_surface, "cat") == 0);
    assert(memoria_collection_query_extract("cats maybe", type_surface, sizeof(type_surface)) == MEMORIA_COLLECTION_QUERY_UNRESOLVED);

    return 0;
}
