#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed: %s:%d: %s\n", __FILE__, __LINE__, #x); return 1; } } while (0)

static memoria_mobile_status call_json(
    memoria_mobile_status (*fn)(memoria_mobile_handle *, memoria_mobile_buffer, memoria_mobile_buffer *),
    memoria_mobile_handle *h,
    const char *json,
    memoria_mobile_buffer *out
) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return fn(h, in, out);
}

static int contains(memoria_mobile_buffer out, const char *needle) {
    return out.data && strstr((const char *)out.data, needle) != NULL;
}

static void clear(memoria_mobile_buffer *out) {
    if (out->data) memoria_mobile_free_buffer(*out);
    out->data = NULL;
    out->size = 0u;
}

static int resolve_alt(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call_json(
        memoria_mobile_resolve_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s1\","
        "\"query\":\"Qual nome do meu gato?\",\"top_k\":3}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"status\":\"HIT\""));
    CHECK(contains(out, "\"semantic_projection\":false"));
    CHECK(contains(out, "\"source_text\":\"Meu gato se chama Alt.\""));
    CHECK(contains(out, "\"repetitions\":2"));
    CHECK(contains(out, "\"source_ids\":[\"m1\",\"m2\"]") ||
          contains(out, "\"source_ids\":[\"m2\",\"m1\"]"));
    CHECK(!contains(out, "Meu cachorro se chama Bolt."));
    clear(&out);
    return 0;
}

static int check_context_scope(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call_json(
        memoria_mobile_resolve_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:scope\","
        "\"query\":\"Como se chama meu gato?\",\"top_k\":3}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_text\":\"Meu gato se chama Alt.\""));
    CHECK(!contains(out, "Meu carro é um Jetta azul."));
    CHECK(!contains(out, "Minha bancada tem um osciloscópio."));
    clear(&out);
    return 0;
}

static int check_window_group(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call_json(
        memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:region\","
        "\"query\":\"meu pai\",\"top_k\":3,"
        "\"mode\":\"window_group\"}", &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "Meu pai se chama PessoaA."));
    CHECK(contains(out, "\"window_id\":\"conversation:region\""));
    CHECK(contains(out, "\"window_revision\":5"));
    CHECK(contains(out, "\"source_ids\":[\"region-q1\",\"region-q2\",\"region-q3\"]"));
    CHECK(contains(out, "\"trajectory_used\":false"));
    CHECK(!contains(out, "Meu carro é vermelho."));
    clear(&out);
    return 0;
}

int main(void) {
    const char *dir = "./tmp-mobile-structural-text";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};

    (void)system("rm -rf ./tmp-mobile-structural-text");
    CHECK(memoria_mobile_open(dir, "org-structural-mobile", &h) == MEMORIA_MOBILE_OK);

    /*
     * Existing conversation ingest MUST NOT auto-feed the structural trail.
     * In particular, assistant/LLM output remains outside this raw observation
     * path unless a caller explicitly observes it.
     */
    CHECK(call_json(
        memoria_mobile_learn_turn_json,
        h,
        "{\"role\":\"assistant\",\"text\":\"Meu cachorro se chama Bolt.\","
        "\"memory_id\":\"assistant-1\",\"namespace\":\"s1\","
        "\"source_type\":\"assistant_generated\",\"order\":1}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);

    CHECK(call_json(
        memoria_mobile_resolve_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s1\","
        "\"query\":\"Qual nome do meu cachorro?\"}",
        &out
    ) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"UNRESOLVED\""));
    CHECK(contains(out, "\"observation_count\":0"));
    clear(&out);

    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s1\",\"source_id\":\"m1\","
        "\"source_kind\":\"user_assertion\",\"sequence\":1,"
        "\"text\":\"Meu gato se chama Alt.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"duplicate\":false"));
    clear(&out);

    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s1\",\"source_id\":\"m2\","
        "\"source_kind\":\"user_assertion\",\"sequence\":2,"
        "\"text\":\"Meu gato se chama Alt.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);

    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s1\",\"source_id\":\"m3\","
        "\"source_kind\":\"user_assertion\",\"sequence\":3,"
        "\"text\":\"Meu gato dorme no sofa.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);

    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s2\",\"source_id\":\"x1\","
        "\"source_kind\":\"user_assertion\",\"sequence\":1,"
        "\"text\":\"Meu cachorro se chama Bolt.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);

    CHECK(resolve_alt(h) == 0);

    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:scope\",\"source_id\":\"scope-1\","
        "\"source_kind\":\"user_assertion\",\"sequence\":1,"
        "\"text\":\"Meu gato se chama Alt.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:scope\",\"source_id\":\"scope-2\","
        "\"source_kind\":\"user_assertion\",\"sequence\":2,"
        "\"text\":\"Meu carro é um Jetta azul.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:scope\",\"source_id\":\"scope-3\","
        "\"source_kind\":\"user_assertion\",\"sequence\":3,"
        "\"text\":\"Minha bancada tem um osciloscópio.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(check_context_scope(h) == 0);

    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"source_id\":\"region-fact\","
        "\"source_kind\":\"user_turn\",\"sequence\":1,"
        "\"text\":\"Meu pai se chama PessoaA.\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"source_id\":\"region-q1\","
        "\"source_kind\":\"user_turn\",\"sequence\":2,"
        "\"text\":\"qual nome do meu pai\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"source_id\":\"region-q2\","
        "\"source_kind\":\"user_turn\",\"sequence\":3,"
        "\"text\":\"qual nome do meu pai?\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"source_id\":\"region-q3\","
        "\"source_kind\":\"user_turn\",\"sequence\":4,"
        "\"text\":\"qual nome do meu pai \"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"source_id\":\"region-other\","
        "\"source_kind\":\"user_turn\",\"sequence\":5,"
        "\"text\":\"Meu carro é vermelho.\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(check_window_group(h) == 0);

    /* Exact retry is idempotent. */
    CHECK(call_json(
        memoria_mobile_observe_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s1\",\"source_id\":\"m2\","
        "\"source_kind\":\"user_assertion\",\"sequence\":2,"
        "\"text\":\"Meu gato se chama Alt.\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"duplicate\":true"));
    CHECK(contains(out, "\"observation_count\":12"));
    clear(&out);

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h);
    h = NULL;

    /* Full mobile-handle reopen reconstructs the derived field from shared BDR. */
    CHECK(memoria_mobile_open(dir, "org-structural-mobile", &h) == MEMORIA_MOBILE_OK);
    CHECK(resolve_alt(h) == 0);

    CHECK(check_context_scope(h) == 0);
    CHECK(check_window_group(h) == 0);

    /* Logical format clears raw observations and therefore derived recall too. */
    CHECK(call_json(
        memoria_mobile_format_json,
        h,
        "{\"confirm\":\"FORMATAR\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    clear(&out);

    CHECK(call_json(
        memoria_mobile_resolve_structural_text_json,
        h,
        "{\"hierarchy_id\":\"conversation:s1\","
        "\"query\":\"Qual nome do meu gato?\"}",
        &out
    ) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"observation_count\":0"));
    clear(&out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-structural-text");
    return 0;
}
