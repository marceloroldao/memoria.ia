#include "concept_relation_traversal.h"

#include <assert.h>
#include <stddef.h>
#include <string.h>

static void clear_paths(memoria_concept_relation_path *paths, size_t n, size_t *count) {
    memset(paths, 0, sizeof(*paths) * n);
    *count = 0;
}

int main(void) {
    memoria_concept_relation_path paths[8];
    size_t count = 0;

    /* RC5-B01: deterministic multi-hop traversal, confidence ordering and evidence preservation. */
    memoria_concept_relation_edge graph[] = {
        {"surface:alt", "concept:gato", "is", "e-alt-cat", 0.99, 0},
        {"concept:gato", "concept:animal", "is", "e-cat-animal", 0.97, 0},
        {"concept:animal", "concept:ser-vivo", "is", "e-animal-life", 0.96, 0},
        {"surface:alt", "concept:ser-vivo", "direct", "e-alt-life-direct", 0.70, 0},
        {"concept:animal", "surface:alt", "cycle", "e-cycle", 0.99, 0},
        {"surface:alt", "surface:ambiguous", "bad", "e-ambiguous", 1.00, 1},
        {"surface:alt", "surface:weak", "weak", "e-weak", 0.30, 0},
    };

    assert(memoria_concept_relation_infer_paths(
        "surface:alt", "concept:ser-vivo",
        graph, sizeof(graph) / sizeof(graph[0]),
        4, 8, 0.0, paths, 8, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(count == 2);
    assert(paths[0].hops == 3);
    assert(paths[0].confidence == 0.96);
    assert(strcmp(paths[0].evidence_ids[0], "e-alt-cat") == 0);
    assert(strcmp(paths[0].evidence_ids[1], "e-cat-animal") == 0);
    assert(strcmp(paths[0].evidence_ids[2], "e-animal-life") == 0);
    assert(paths[1].hops == 1);
    assert(paths[1].confidence == 0.70);

    /* RC5-B02: directionality must be preserved. Reverse traversal is not implicit. */
    clear_paths(paths, 8, &count);
    assert(memoria_concept_relation_infer_paths(
        "concept:ser-vivo", "surface:alt",
        graph, sizeof(graph) / sizeof(graph[0]),
        4, 8, 0.0, paths, 8, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(count == 0);

    /* RC5-B03: max-hop bound must fail closed instead of escaping the configured search radius. */
    clear_paths(paths, 8, &count);
    assert(memoria_concept_relation_infer_paths(
        "surface:alt", "concept:ser-vivo",
        graph, sizeof(graph) / sizeof(graph[0]),
        2, 8, 0.90, paths, 8, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(count == 0);

    /* RC5-B04: ambiguous edges must never produce a hit. */
    clear_paths(paths, 8, &count);
    assert(memoria_concept_relation_infer_paths(
        "surface:alt", "surface:ambiguous",
        graph, sizeof(graph) / sizeof(graph[0]),
        4, 8, 0.0, paths, 8, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(count == 0);

    /* RC5-B05: low-confidence evidence must fail closed above threshold. */
    clear_paths(paths, 8, &count);
    assert(memoria_concept_relation_infer_paths(
        "surface:alt", "surface:weak",
        graph, sizeof(graph) / sizeof(graph[0]),
        4, 8, 0.80, paths, 8, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_UNRESOLVED);
    assert(count == 0);

    /* RC5-B06: cycle protection must still allow the intended path and terminate deterministically. */
    clear_paths(paths, 8, &count);
    assert(memoria_concept_relation_infer_paths(
        "surface:alt", "concept:animal",
        graph, sizeof(graph) / sizeof(graph[0]),
        6, 8, 0.0, paths, 8, &count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    assert(count >= 1);
    assert(paths[0].hops == 2);
    assert(paths[0].confidence == 0.97);

    return 0;
}
