#include "concept_relation_traversal.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_concept_relation_edge edges[] = {
        {"concept:charger", "concept:voltage", "has_property", "e1", 0.95, 0},
        {"concept:voltage", "surface:34v", "has_value", "e2", 0.92, 0},
        {"concept:charger", "surface:34v", "direct", "e3", 0.80, 0},
        {"concept:voltage", "concept:charger", "cycle", "e4", 0.99, 0},
        {"concept:charger", "surface:hidden", "weak", "e5", 0.40, 0},
        {"concept:charger", "surface:ambiguous", "bad", "e6", 0.99, 1},
    };
    memoria_concept_relation_path paths[4];
    size_t count = 0;

    assert(memoria_concept_relation_infer_paths(
        "concept:charger", "surface:34v",
        edges, sizeof(edges) / sizeof(edges[0]),
        3, 4, 0.0, paths, 4, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(count == 2);
    assert(paths[0].hops == 2);
    assert(paths[0].confidence == 0.92);
    assert(strcmp(paths[0].evidence_ids[0], "e1") == 0);
    assert(strcmp(paths[0].evidence_ids[1], "e2") == 0);
    assert(paths[1].hops == 1);
    assert(paths[1].confidence == 0.80);
    assert(strcmp(paths[1].evidence_ids[0], "e3") == 0);

    memset(paths, 0, sizeof(paths));
    count = 0;
    assert(memoria_concept_relation_infer_paths(
        "concept:charger", "surface:34v",
        edges, sizeof(edges) / sizeof(edges[0]),
        3, 4, 0.90, paths, 4, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(count == 1);
    assert(paths[0].hops == 2);
    assert(paths[0].confidence == 0.92);

    memset(paths, 0, sizeof(paths));
    count = 0;
    assert(memoria_concept_relation_infer_paths(
        "concept:charger", "surface:hidden",
        edges, sizeof(edges) / sizeof(edges[0]),
        3, 4, 0.90, paths, 4, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(count == 0);

    memset(paths, 0, sizeof(paths));
    count = 0;
    assert(memoria_concept_relation_infer_paths(
        "concept:charger", "surface:ambiguous",
        edges, sizeof(edges) / sizeof(edges[0]),
        3, 4, 0.0, paths, 4, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(count == 0);

    return 0;
}
