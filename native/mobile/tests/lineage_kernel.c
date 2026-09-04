#include "lineage_kernel.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); return 1; } } while (0)

static int test_conjunctive_requires_all_parents(void) {
    memoria_lineage_node nodes[] = {
        {.memory_id="a", .namespace_id="s", .source_type="user_assertion", .authority=1.0, .order=1},
        {.memory_id="b", .namespace_id="s", .source_type="user_assertion", .authority=1.0, .order=2},
        {.memory_id="d", .namespace_id="s", .source_type="derived_relation", .parent_memory_ids={"a","b"}, .parent_count=2, .authority=0.9, .order=3},
    };
    memoria_lineage_result r = memoria_lineage_resolve(nodes, 3, "d", "s");
    CHECK(r.factual_active == 1);
    CHECK(r.required_parent_count == 2);
    CHECK(r.active_parent_count == 2);
    CHECK(r.representative_root_id != NULL);

    nodes[1].superseded = 1;
    r = memoria_lineage_resolve(nodes, 3, "d", "s");
    CHECK(r.factual_active == 0);
    return 0;
}

static int test_non_conjunctive_trace_can_use_one_parent(void) {
    memoria_lineage_node nodes[] = {
        {.memory_id="a", .namespace_id="s", .source_type="user_assertion", .authority=1.0, .order=1},
        {.memory_id="b", .namespace_id="s", .source_type="user_assertion", .authority=1.0, .order=2, .superseded=1},
        {.memory_id="echo", .namespace_id="s", .source_type="assistant_generated", .parent_memory_ids={"a","b"}, .parent_count=2, .authority=0.2, .order=3},
    };
    memoria_lineage_result r = memoria_lineage_resolve(nodes, 3, "echo", "s");
    CHECK(r.factual_active == 1);
    CHECK(strcmp(r.representative_root_id, "a") == 0);
    return 0;
}

static int test_namespace_isolation(void) {
    memoria_lineage_node nodes[] = {
        {.memory_id="a", .namespace_id="one", .source_type="user_assertion", .authority=1.0, .order=1},
        {.memory_id="d", .namespace_id="two", .source_type="derived_relation", .parent_memory_ids={"a"}, .parent_count=1, .authority=0.9, .order=2},
    };
    memoria_lineage_result r = memoria_lineage_resolve(nodes, 2, "d", "two");
    CHECK(r.factual_active == 0);
    return 0;
}

static int test_cycle_fails_closed(void) {
    memoria_lineage_node nodes[] = {
        {.memory_id="a", .namespace_id="s", .source_type="derived_relation", .parent_memory_ids={"b"}, .parent_count=1},
        {.memory_id="b", .namespace_id="s", .source_type="derived_relation", .parent_memory_ids={"a"}, .parent_count=1},
    };
    memoria_lineage_result r = memoria_lineage_resolve(nodes, 2, "a", "s");
    CHECK(r.factual_active == 0);
    return 0;
}

int main(void) {
    CHECK(test_conjunctive_requires_all_parents() == 0);
    CHECK(test_non_conjunctive_trace_can_use_one_parent() == 0);
    CHECK(test_namespace_isolation() == 0);
    CHECK(test_cycle_fails_closed() == 0);
    return 0;
}
