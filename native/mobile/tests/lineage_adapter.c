#include "lineage_adapter.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); return 1; } } while (0)

static void set_turn(
    memoria_persist_turn *turn,
    const char *memory_id,
    const char *namespace_id,
    const char *source_type,
    long order
) {
    memset(turn, 0, sizeof(*turn));
    turn->memory_id = (char *)memory_id;
    turn->namespace_id = (char *)namespace_id;
    turn->source_type = (char *)source_type;
    turn->ultimate_source_memory_id = (char *)memory_id;
    turn->authority = 1.0;
    turn->order = order;
}

static int test_relation_ids_trace_to_turn_roots_and_conjoin(void) {
    memoria_persist_turn turns[3];
    memoria_lineage_graph graph = {0};
    memoria_lineage_result r;

    set_turn(&turns[0], "a", "s", "user_assertion", 1);
    turns[0].relation_count = 1;
    snprintf(turns[0].relation_memory_ids[0], sizeof(turns[0].relation_memory_ids[0]), "%s", "a-rel");
    turns[0].relations[0].confidence = 0.95;

    set_turn(&turns[1], "b", "s", "user_assertion", 2);
    turns[1].relation_count = 1;
    snprintf(turns[1].relation_memory_ids[0], sizeof(turns[1].relation_memory_ids[0]), "%s", "b-rel");
    turns[1].relations[0].confidence = 0.90;

    set_turn(&turns[2], "derived", "s", "derived_relation", 3);
    turns[2].parent_count = 2;
    snprintf(turns[2].parent_memory_ids[0], sizeof(turns[2].parent_memory_ids[0]), "%s", "a-rel");
    snprintf(turns[2].parent_memory_ids[1], sizeof(turns[2].parent_memory_ids[1]), "%s", "b-rel");

    CHECK(memoria_lineage_graph_build(turns, 3, &graph) == 1);
    r = memoria_lineage_graph_resolve(&graph, "derived", "s");
    CHECK(r.factual_active == 1);
    CHECK(r.required_parent_count == 2);
    CHECK(r.active_parent_count == 2);
    memoria_lineage_graph_free(&graph);

    turns[1].superseded = 1;
    snprintf(turns[1].superseded_by, sizeof(turns[1].superseded_by), "%s", "b-new");
    CHECK(memoria_lineage_graph_build(turns, 3, &graph) == 1);
    r = memoria_lineage_graph_resolve(&graph, "derived", "s");
    CHECK(r.factual_active == 0);
    memoria_lineage_graph_free(&graph);
    return 0;
}

static int test_namespace_stays_closed(void) {
    memoria_persist_turn turns[2];
    memoria_lineage_graph graph = {0};
    memoria_lineage_result r;

    set_turn(&turns[0], "root", "one", "user_assertion", 1);
    turns[0].relation_count = 1;
    snprintf(turns[0].relation_memory_ids[0], sizeof(turns[0].relation_memory_ids[0]), "%s", "root-rel");
    turns[0].relations[0].confidence = 1.0;

    set_turn(&turns[1], "derived", "two", "derived_relation", 2);
    turns[1].parent_count = 1;
    snprintf(turns[1].parent_memory_ids[0], sizeof(turns[1].parent_memory_ids[0]), "%s", "root-rel");

    CHECK(memoria_lineage_graph_build(turns, 2, &graph) == 1);
    r = memoria_lineage_graph_resolve(&graph, "derived", "two");
    CHECK(r.factual_active == 0);
    memoria_lineage_graph_free(&graph);
    return 0;
}

static int test_missing_relation_id_fails_closed(void) {
    memoria_persist_turn turn;
    memoria_lineage_graph graph = {0};
    memoria_lineage_result r;

    set_turn(&turn, "root", "s", "user_assertion", 1);
    turn.relation_count = 1;
    turn.relations[0].confidence = 1.0;

    CHECK(memoria_lineage_graph_build(&turn, 1, &graph) == 1);
    r = memoria_lineage_graph_resolve(&graph, "", "s");
    CHECK(r.factual_active == 0);
    memoria_lineage_graph_free(&graph);
    return 0;
}

int main(void) {
    CHECK(test_relation_ids_trace_to_turn_roots_and_conjoin() == 0);
    CHECK(test_namespace_stays_closed() == 0);
    CHECK(test_missing_relation_id_fails_closed() == 0);
    return 0;
}
