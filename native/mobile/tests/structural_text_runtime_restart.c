#include "structural_text_runtime.h"
#include "bdr/atomic_c_api.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed: %s:%d: %s\n", __FILE__, __LINE__, #x); return 1; } } while (0)

static int has_text(
    const memoria_structural_text_context *contexts,
    size_t count,
    const char *text
) {
    size_t i;
    for (i = 0; i < count; ++i) {
        if (contexts[i].source_text && strcmp(contexts[i].source_text, text) == 0)
            return 1;
    }
    return 0;
}

static int context_has_source_id(
    const memoria_structural_text_context *contexts,
    size_t count,
    const char *text,
    const char *source_id
) {
    size_t i;
    for (i = 0; i < count; ++i) {
        size_t j;
        if (!contexts[i].source_text || strcmp(contexts[i].source_text, text) != 0)
            continue;
        for (j = 0; j < contexts[i].source_id_count; ++j)
            if (strcmp(contexts[i].source_ids[j], source_id) == 0) return 1;
    }
    return 0;
}

static size_t find_repetitions(
    const memoria_structural_text_context *contexts,
    size_t count,
    const char *text
) {
    size_t i;
    for (i = 0; i < count; ++i) {
        if (contexts[i].source_text && strcmp(contexts[i].source_text, text) == 0)
            return contexts[i].repetitions;
    }
    return 0u;
}

static int check_identical_payload_is_occurrence_only(void) {
    const char *dir = "./tmp-structural-text-composition";
    const char *region = "conversation:composition";
    bdr_atomic_c_handle *db = NULL;
    memoria_structural_text_runtime *runtime = NULL;
    memoria_structural_text_observation_view raw = {0};
    uint64_t dizer = 0u, qual = 0u, nome = 0u;
    double base_weight, context_weight;
    size_t base_edges, context_edges;
    int duplicate = 0;
    (void)system("rm -rf ./tmp-structural-text-composition");
    CHECK(memoria_structural_text_symbol("dizer", 5u, &dizer));
    CHECK(memoria_structural_text_symbol("qual", 4u, &qual));
    CHECK(memoria_structural_text_symbol("nome", 4u, &nome));
    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(
        db, "org-composition", 8u, 4u, 0.0, &runtime));

    CHECK(memoria_structural_text_runtime_observe(runtime, region, "q1",
        "user_turn", 1ul, "Qual nome do meu pai?", &duplicate));
    CHECK(!duplicate);
    CHECK(memoria_structural_text_runtime_distinct_trail_count(runtime, region) == 1u);
    CHECK(memoria_structural_text_runtime_field_tick(runtime, region) == 1u);
    base_weight = memoria_structural_text_runtime_association(runtime, region,
        qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN);
    base_edges = memoria_structural_text_runtime_edge_count(runtime, region);
    CHECK(base_weight > 0.0 && base_edges > 0u);

    /* Different source, same normalized payload: keep the raw occurrence,
     * but do not advance the association field or its temporal recent set. */
    CHECK(memoria_structural_text_runtime_observe(runtime, region, "q2",
        "user_turn", 2ul, "QUAL NOME DO MEU PAI!!!", &duplicate));
    CHECK(!duplicate);
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 2u);
    CHECK(memoria_structural_text_runtime_distinct_trail_count(runtime, region) == 1u);
    CHECK(memoria_structural_text_runtime_field_tick(runtime, region) == 1u);
    CHECK(memoria_structural_text_runtime_edge_count(runtime, region) == base_edges);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) == base_weight);
    CHECK(memoria_structural_text_runtime_observe(runtime, region, "q2",
        "user_turn", 2ul, "QUAL NOME DO MEU PAI!!!", &duplicate));
    CHECK(duplicate);
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 2u);

    CHECK(memoria_structural_text_runtime_observe(runtime, region, "context",
        "user_turn", 3ul, "Poderia me dizer qual nome do meu pai?", &duplicate));
    CHECK(!duplicate);
    CHECK(memoria_structural_text_runtime_distinct_trail_count(runtime, region) == 2u);
    CHECK(memoria_structural_text_runtime_field_tick(runtime, region) == 2u);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        dizer, qual, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) > 0.0);
    context_weight = memoria_structural_text_runtime_association(runtime,
        region, qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN);
    context_edges = memoria_structural_text_runtime_edge_count(runtime, region);
    CHECK(context_weight > base_weight && context_edges > base_edges);

    CHECK(memoria_structural_text_runtime_observe(runtime, region, "context-copy",
        "user_turn", 4ul, "PODERIA ME DIZER QUAL NOME DO MEU PAI?", &duplicate));
    CHECK(!duplicate);
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 4u);
    CHECK(memoria_structural_text_runtime_distinct_trail_count(runtime, region) == 2u);
    CHECK(memoria_structural_text_runtime_field_tick(runtime, region) == 2u);
    CHECK(memoria_structural_text_runtime_edge_count(runtime, region) == context_edges);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) == context_weight);

    CHECK(memoria_structural_text_runtime_observation_at(runtime, 1u, &raw));
    CHECK(strcmp(raw.source_id, "q2") == 0 && raw.sequence == 2ul);
    CHECK(memoria_structural_text_runtime_observation_at(runtime, 3u, &raw));
    CHECK(strcmp(raw.source_id, "context-copy") == 0);
    CHECK(memoria_structural_text_runtime_sync(runtime));
    memoria_structural_text_runtime_close(runtime);
    bdr_atomic_c_close(db);

    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(
        db, "org-composition", 8u, 4u, 0.0, &runtime));
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 4u);
    CHECK(memoria_structural_text_runtime_distinct_trail_count(runtime, region) == 2u);
    CHECK(memoria_structural_text_runtime_field_tick(runtime, region) == 2u);
    CHECK(memoria_structural_text_runtime_edge_count(runtime, region) == context_edges);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) == context_weight);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        dizer, qual, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) > 0.0);
    memoria_structural_text_runtime_close(runtime);
    bdr_atomic_c_close(db);
    (void)system("rm -rf ./tmp-structural-text-composition");
    return 0;
}

int main(void) {
    const char *dir = "./tmp-structural-text-runtime-restart";
    bdr_atomic_c_handle *db = NULL;
    memoria_structural_text_runtime *runtime = NULL;
    memoria_structural_text_context *contexts = NULL;
    size_t context_count = 0u;
    size_t edges_before = 0u;
    size_t edges_after = 0u;
    int duplicate = 0;

    CHECK(check_identical_payload_is_occurrence_only() == 0);

    (void)system("rm -rf ./tmp-structural-text-runtime-restart");
    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);

    CHECK(memoria_structural_text_runtime_open_shared(
        db, "org-structural", 8u, 4u, 0.0, &runtime
    ));

    CHECK(memoria_structural_text_runtime_observe(
        runtime, "conversation:main", "m1", "user_assertion", 1ul,
        "Meu gato se chama Alt.", &duplicate
    ));
    CHECK(!duplicate);
    CHECK(memoria_structural_text_runtime_observe(
        runtime, "conversation:main", "m2", "user_assertion", 2ul,
        "Meu gato se chama Alt.", &duplicate
    ));
    CHECK(!duplicate);
    CHECK(memoria_structural_text_runtime_observe(
        runtime, "conversation:main", "m3", "user_assertion", 3ul,
        "Meu gato dorme no sofa.", &duplicate
    ));
    CHECK(!duplicate);

    CHECK(memoria_structural_text_runtime_observe(
        runtime, "conversation:other", "o1", "user_assertion", 1ul,
        "Meu cachorro se chama Bolt.", &duplicate
    ));
    CHECK(!duplicate);

    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 4u);
    CHECK(memoria_structural_text_runtime_hierarchy_count(runtime) == 2u);

    edges_before = memoria_structural_text_runtime_edge_count(
        runtime, "conversation:main"
    );
    CHECK(edges_before > 0u);

    CHECK(memoria_structural_text_runtime_resolve(
        runtime,
        "conversation:main",
        "Qual nome do meu gato?",
        4u,
        &contexts,
        &context_count
    ));
    CHECK(context_count >= 1u);
    CHECK(has_text(contexts, context_count, "Meu gato se chama Alt."));
    CHECK(!has_text(contexts, context_count, "Meu cachorro se chama Bolt."));
    CHECK(find_repetitions(
        contexts, context_count, "Meu gato se chama Alt."
    ) == 2u);
    CHECK(context_has_source_id(
        contexts, context_count, "Meu gato se chama Alt.", "m1"
    ));
    CHECK(context_has_source_id(
        contexts, context_count, "Meu gato se chama Alt.", "m2"
    ));
    memoria_structural_text_contexts_free(contexts, context_count);
    contexts = NULL;
    context_count = 0u;

    /* Querying must not mutate/reinforce the field. */
    edges_after = memoria_structural_text_runtime_edge_count(
        runtime, "conversation:main"
    );
    CHECK(edges_after == edges_before);

    /* Same logical observation is idempotent. */
    CHECK(memoria_structural_text_runtime_observe(
        runtime, "conversation:main", "m2", "user_assertion", 2ul,
        "Meu gato se chama Alt.", &duplicate
    ));
    CHECK(duplicate);
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 4u);

    /* Reusing an identity with different content is rejected. */
    CHECK(!memoria_structural_text_runtime_observe(
        runtime, "conversation:main", "m2", "user_assertion", 2ul,
        "Meu gato se chama Outro.", &duplicate
    ));

    CHECK(memoria_structural_text_runtime_sync(runtime));
    memoria_structural_text_runtime_close(runtime);
    runtime = NULL;

    /* Same open BDR handle: derived fields must rebuild from raw observations. */
    CHECK(memoria_structural_text_runtime_open_shared(
        db, "org-structural", 8u, 4u, 0.0, &runtime
    ));
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 4u);
    CHECK(memoria_structural_text_runtime_hierarchy_count(runtime) == 2u);
    CHECK(memoria_structural_text_runtime_edge_count(
        runtime, "conversation:main"
    ) == edges_before);

    CHECK(memoria_structural_text_runtime_resolve(
        runtime,
        "conversation:main",
        "Qual nome do meu gato?",
        4u,
        &contexts,
        &context_count
    ));
    CHECK(has_text(contexts, context_count, "Meu gato se chama Alt."));
    CHECK(find_repetitions(
        contexts, context_count, "Meu gato se chama Alt."
    ) == 2u);
    memoria_structural_text_contexts_free(contexts, context_count);
    contexts = NULL;
    context_count = 0u;

    memoria_structural_text_runtime_close(runtime);
    runtime = NULL;
    bdr_atomic_c_close(db);
    db = NULL;

    /* Real cold reopen: close the DB process handle and reconstruct again. */
    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(
        db, "org-structural", 8u, 4u, 0.0, &runtime
    ));
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 4u);
    CHECK(memoria_structural_text_runtime_edge_count(
        runtime, "conversation:main"
    ) == edges_before);
    CHECK(memoria_structural_text_runtime_resolve(
        runtime,
        "conversation:main",
        "Qual nome do meu gato?",
        4u,
        &contexts,
        &context_count
    ));
    CHECK(has_text(contexts, context_count, "Meu gato se chama Alt."));
    CHECK(!has_text(contexts, context_count, "Meu cachorro se chama Bolt."));
    memoria_structural_text_contexts_free(contexts, context_count);

    memoria_structural_text_runtime_close(runtime);
    bdr_atomic_c_close(db);
    (void)system("rm -rf ./tmp-structural-text-runtime-restart");
    return 0;
}
