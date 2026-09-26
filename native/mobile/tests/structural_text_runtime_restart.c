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
    CHECK(context_weight == base_weight && context_edges > base_edges);

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

static int read_stored_row(
    bdr_atomic_c_handle *db, const char *org, size_t index,
    char **out, size_t *out_size
) {
    char key[256];
    bdr_atomic_c_buffer value = {0};
    int written = snprintf(key, sizeof(key),
        "memoria-mobile/v1/%s/structural-text/observation/%012zu", org, index);
    if (written <= 0 || (size_t)written >= sizeof(key) ||
        bdr_atomic_c_get(db, key, strlen(key), &value) != BDR_ATOMIC_C_OK)
        return 0;
    *out = (char *)malloc(value.size + 1u);
    if (!*out) {
        bdr_atomic_c_free_buffer(value);
        return 0;
    }
    memcpy(*out, value.data, value.size);
    (*out)[value.size] = 0;
    *out_size = value.size;
    bdr_atomic_c_free_buffer(value);
    return 1;
}

static int check_durable_payload_references(void) {
    const char *dir = "./tmp-structural-text-reference";
    const char *org = "org-reference";
    const char *region = "conversation:reference";
    const char *base = "qual nome do meu pai?";
    const char *context = "Poderia me dizer qual nome do meu pai?";
    const char *nested = "Hoje, Poderia me dizer qual nome do meu pai?";
    bdr_atomic_c_handle *db = NULL;
    memoria_structural_text_runtime *runtime = NULL;
    memoria_structural_text_observation_view raw = {0};
    char *row = NULL;
    size_t row_size = 0u;
    uint64_t qual = 0u, nome = 0u, dizer = 0u;
    double base_weight;
    int duplicate = 0;
    (void)system("rm -rf ./tmp-structural-text-reference");
    CHECK(memoria_structural_text_symbol("qual", 4u, &qual));
    CHECK(memoria_structural_text_symbol("nome", 4u, &nome));
    CHECK(memoria_structural_text_symbol("dizer", 5u, &dizer));
    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(
        db, org, 8u, 4u, 0.0, &runtime));
    CHECK(memoria_structural_text_runtime_observe(runtime, region,
        "base", "user_turn", 1ul, base, &duplicate));
    base_weight = memoria_structural_text_runtime_association(runtime, region,
        qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN);
    CHECK(base_weight == 1.0);
    CHECK(memoria_structural_text_runtime_observe(runtime, region,
        "repeat", "user_turn", 2ul, base, &duplicate));
    CHECK(memoria_structural_text_runtime_observe(runtime, region,
        "context", "user_turn", 3ul, context, &duplicate));
    CHECK(memoria_structural_text_runtime_observe(runtime, region,
        "nested", "user_turn", 4ul, nested, &duplicate));
    CHECK(memoria_structural_text_runtime_observe(runtime,
        "conversation:other", "cross-region", "user_turn", 5ul,
        base, &duplicate));
    CHECK(memoria_structural_text_runtime_observe(runtime, region,
        "case-variant", "user_turn", 6ul,
        "QUAL NOME DO MEU PAI?", &duplicate));
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 6u);
    CHECK(memoria_structural_text_runtime_distinct_trail_count(runtime, region) == 3u);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) == base_weight);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        dizer, qual, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) == 1.0);
    CHECK(read_stored_row(db, org, 1u, &row, &row_size));
    CHECK(strstr(row, base) != NULL);
    free(row);
    CHECK(read_stored_row(db, org, 2u, &row, &row_size));
    CHECK(strncmp(row, "R2:", 3u) == 0 && strstr(row, base) == NULL);
    free(row);
    CHECK(read_stored_row(db, org, 3u, &row, &row_size));
    CHECK(strncmp(row, "R2:", 3u) == 0 && strstr(row, base) == NULL);
    CHECK(strstr(row, "Poderia me dizer ") != NULL);
    free(row);
    CHECK(read_stored_row(db, org, 4u, &row, &row_size));
    CHECK(strncmp(row, "R2:", 3u) == 0 && strstr(row, context) == NULL);
    free(row);
    CHECK(read_stored_row(db, org, 5u, &row, &row_size));
    CHECK(strncmp(row, "R2:", 3u) == 0 && strstr(row, base) == NULL);
    free(row);
    CHECK(read_stored_row(db, org, 6u, &row, &row_size));
    CHECK(strncmp(row, "R2:", 3u) != 0 &&
        strstr(row, "QUAL NOME DO MEU PAI?") != NULL);
    free(row);
    CHECK(memoria_structural_text_runtime_sync(runtime));
    memoria_structural_text_runtime_close(runtime);
    bdr_atomic_c_close(db);

    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(
        db, org, 8u, 4u, 0.0, &runtime));
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 6u);
    CHECK(memoria_structural_text_runtime_distinct_trail_count(runtime, region) == 3u);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        qual, nome, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) == base_weight);
    CHECK(memoria_structural_text_runtime_association(runtime, region,
        dizer, qual, MEMORIA_STRUCTURAL_CHANNEL_WITHIN) == 1.0);
    CHECK(memoria_structural_text_runtime_observation_at(runtime, 1u, &raw));
    CHECK(strcmp(raw.source_id, "repeat") == 0 && strcmp(raw.text, base) == 0);
    CHECK(memoria_structural_text_runtime_observation_at(runtime, 2u, &raw));
    CHECK(strcmp(raw.source_id, "context") == 0 && strcmp(raw.text, context) == 0);
    CHECK(memoria_structural_text_runtime_observation_at(runtime, 3u, &raw));
    CHECK(strcmp(raw.source_id, "nested") == 0 && strcmp(raw.text, nested) == 0);
    CHECK(memoria_structural_text_runtime_observation_at(runtime, 4u, &raw));
    CHECK(strcmp(raw.source_id, "cross-region") == 0 && strcmp(raw.text, base) == 0);
    memoria_structural_text_runtime_close(runtime);
    bdr_atomic_c_close(db);
    (void)system("rm -rf ./tmp-structural-text-reference");
    return 0;
}

static int check_legacy_schema_upgrade(void) {
    const char *dir = "./tmp-structural-text-v1-upgrade";
    const char *org = "org-legacy-upgrade";
    const char *base = "qual nome do meu pai?";
    const char *schema_key =
        "memoria-mobile/v1/org-legacy-upgrade/structural-text/meta/schema";
    bdr_atomic_c_handle *db = NULL;
    memoria_structural_text_runtime *runtime = NULL;
    memoria_structural_text_observation_view raw = {0};
    bdr_atomic_c_operation op = {0};
    bdr_atomic_c_batch_result result = {0};
    bdr_atomic_c_buffer schema = {0};
    char *row = NULL;
    size_t row_size = 0u;
    int duplicate = 0;
    (void)system("rm -rf ./tmp-structural-text-v1-upgrade");
    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(db, org,
        8u, 4u, 0.0, &runtime));
    CHECK(memoria_structural_text_runtime_observe(runtime,
        "conversation:legacy", "old", "user_turn", 1ul, base, &duplicate));
    memoria_structural_text_runtime_close(runtime);
    CHECK(read_stored_row(db, org, 1u, &row, &row_size));
    CHECK(strncmp(row, "R2:", 3u) != 0);
    free(row);
    /* Row one uses the unchanged v1 inline encoding. Mark this fixture as
     * an existing v1 database, then append a v2 reference atomically. */
    op.type = BDR_ATOMIC_C_PUT;
    op.key = schema_key; op.key_size = strlen(schema_key);
    op.value = "1"; op.value_size = 1u;
    CHECK(bdr_atomic_c_write_batch(db, &op, 1u, &result) == BDR_ATOMIC_C_OK);
    bdr_atomic_c_close(db);

    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(db, org,
        8u, 4u, 0.0, &runtime));
    CHECK(memoria_structural_text_runtime_observe(runtime,
        "conversation:legacy", "new", "user_turn", 2ul, base, &duplicate));
    CHECK(bdr_atomic_c_get(db, schema_key, strlen(schema_key), &schema)
        == BDR_ATOMIC_C_OK);
    CHECK(schema.size == 1u && schema.data[0] == '2');
    bdr_atomic_c_free_buffer(schema);
    CHECK(read_stored_row(db, org, 2u, &row, &row_size));
    CHECK(strncmp(row, "R2:", 3u) == 0 && strstr(row, base) == NULL);
    free(row);
    memoria_structural_text_runtime_close(runtime);
    bdr_atomic_c_close(db);

    CHECK(bdr_atomic_c_open(dir, &db) == BDR_ATOMIC_C_OK);
    CHECK(memoria_structural_text_runtime_open_shared(db, org,
        8u, 4u, 0.0, &runtime));
    CHECK(memoria_structural_text_runtime_observation_count(runtime) == 2u);
    CHECK(memoria_structural_text_runtime_observation_at(runtime, 1u, &raw));
    CHECK(strcmp(raw.source_id, "new") == 0 && strcmp(raw.text, base) == 0);
    memoria_structural_text_runtime_close(runtime);
    bdr_atomic_c_close(db);
    (void)system("rm -rf ./tmp-structural-text-v1-upgrade");
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
    CHECK(check_durable_payload_references() == 0);
    CHECK(check_legacy_schema_upgrade() == 0);

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
