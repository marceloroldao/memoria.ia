#include "concept_relation_traversal.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double elapsed_ms(clock_t start, clock_t end) {
    return ((double)(end - start) * 1000.0) / (double)CLOCKS_PER_SEC;
}

static void run_case(size_t edge_count) {
    memoria_concept_relation_edge *edges = calloc(edge_count, sizeof(*edges));
    char **subjects = calloc(edge_count, sizeof(*subjects));
    char **objects = calloc(edge_count, sizeof(*objects));
    char **evidence = calloc(edge_count, sizeof(*evidence));
    memoria_concept_relation_path paths[2];
    size_t out_count = 0;
    size_t i;
    char target[64];
    clock_t t0, t1;

    assert(edges && subjects && objects && evidence);
    for (i = 0; i < edge_count; ++i) {
        subjects[i] = malloc(64);
        objects[i] = malloc(64);
        evidence[i] = malloc(64);
        assert(subjects[i] && objects[i] && evidence[i]);
        snprintf(subjects[i], 64, "surface:n%zu", i);
        snprintf(objects[i], 64, "surface:n%zu", i + 1u);
        snprintf(evidence[i], 64, "e%zu", i);
        edges[i].subject_key = subjects[i];
        edges[i].object_key = objects[i];
        edges[i].predicate = "next";
        edges[i].evidence_id = evidence[i];
        edges[i].confidence = 0.99;
        edges[i].ambiguous = 0;
    }

    snprintf(target, sizeof(target), "surface:n%zu", edge_count < 4u ? edge_count : 4u);
    t0 = clock();
    assert(memoria_concept_relation_infer_paths(
        "surface:n0", target, edges, edge_count,
        4u, 2u, 0.80, paths, 2u, &out_count
    ) == MEMORIA_CONCEPT_TRAVERSAL_HIT);
    t1 = clock();
    assert(out_count >= 1u);
    assert(paths[0].hops == (edge_count < 4u ? edge_count : 4u));

    printf("edges=%zu latency_ms=%.3f paths=%zu hops=%zu\n",
           edge_count, elapsed_ms(t0, t1), out_count, paths[0].hops);

    for (i = 0; i < edge_count; ++i) {
        free(subjects[i]);
        free(objects[i]);
        free(evidence[i]);
    }
    free(subjects);
    free(objects);
    free(evidence);
    free(edges);
}

int main(void) {
    const size_t sizes[] = {100u, 1000u, 10000u, 50000u};
    size_t i;
    for (i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) run_case(sizes[i]);
    return 0;
}
