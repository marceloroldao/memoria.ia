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

static int check_surface_collection(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:collection\",\"source_id\":\"cat-1\","
        "\"source_kind\":\"user_turn\",\"sequence\":1,"
        "\"text\":\"Tenho um gato chamado Alt.\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:collection\",\"source_id\":\"cat-2\","
        "\"source_kind\":\"user_turn\",\"sequence\":2,"
        "\"text\":\"Também conheço um gato chamado Nino.\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:collection\",\"source_id\":\"car-1\","
        "\"source_kind\":\"user_turn\",\"sequence\":3,"
        "\"text\":\"Meu carro é um Jetta azul.\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:collection\","
        "\"query\":\"Quais gatos eu mencionei?\",\"top_k\":3}", &out)
        == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"status\":\"HIT\""));
    CHECK(contains(out, "Tenho um gato chamado Alt."));
    CHECK(contains(out, "Também conheço um gato chamado Nino."));
    CHECK(!contains(out, "Jetta"));
    CHECK(contains(out, "\"surface_overlap\":1"));
    clear(&out);
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:collection\","
        "\"query\":\"Quais carros eu mencionei?\",\"top_k\":3}", &out)
        == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "Meu carro é um Jetta azul."));
    CHECK(!contains(out, "chamado Alt"));
    CHECK(!contains(out, "chamado Nino"));
    clear(&out);
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:collection\","
        "\"query\":\"Qual tensão há na fonte da bancada?\",\"top_k\":3}", &out)
        == MEMORIA_MOBILE_UNRESOLVED);
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
    CHECK(contains(out, "\"window_revision\":6"));
    CHECK(contains(out, "\"source_ids\":[\"region-q1\",\"region-q2\",\"region-q3\"]"));
    CHECK(!contains(out, "\"source_ids\":[\"region-q1\",\"region-q2\",\"region-q3\",\"region-assistant\"]"));
    CHECK(contains(out,
        "\"source_id\":\"region-q2\",\"source_text\":\"qual nome do meu pai?\","
        "\"source_kind\":\"user_turn\""));
    CHECK(contains(out,
        "\"source_id\":\"region-assistant\",\"source_text\":\"qual nome do meu pai?\","
        "\"source_kind\":\"assistant_generated\""));
    CHECK(contains(out, "\"trajectory_used\":false"));
    CHECK(!contains(out, "Meu carro é vermelho."));
    clear(&out);
    return 0;
}

static int check_window_region(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    char request[256];
    char token[17];
    const char *start;
    CHECK(call_json(memoria_mobile_read_structural_window_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"offset\":0,\"limit\":2}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"window_revision\":6"));
    CHECK(contains(out, "\"next_offset\":2"));
    CHECK(contains(out, "\"source_id\":\"region-fact\""));
    CHECK(contains(out, "\"next_source_id\":\"region-q1\""));
    CHECK(!contains(out, "\"source_id\":\"region-q2\""));
    start = strstr((const char *)out.data, "\"window_token\":\"");
    CHECK(start != NULL);
    start += strlen("\"window_token\":\"");
    CHECK(strlen(start) >= 16u);
    memcpy(token, start, 16u);
    token[16] = 0;
    clear(&out);
    snprintf(request, sizeof(request),
        "{\"hierarchy_id\":\"conversation:region\",\"offset\":2,"
        "\"limit\":2,\"expected_token\":\"%s\"}", token);
    CHECK(call_json(memoria_mobile_read_structural_window_json, h,
        request, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_id\":\"region-q2\""));
    CHECK(contains(out, "\"prev_source_id\":\"region-q1\""));
    CHECK(contains(out, "\"next_source_id\":\"region-q3\""));
    clear(&out);
    CHECK(call_json(memoria_mobile_read_structural_window_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"offset\":2,"
        "\"limit\":2,\"expected_token\":\"0000000000000000\"}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"STALE_WINDOW\""));
    CHECK(!contains(out, "\"source_id\""));
    clear(&out);
    CHECK(call_json(memoria_mobile_read_structural_window_json, h,
        "{\"hierarchy_id\":\"conversation:absent\"}", &out)
        == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"window_revision\":0"));
    CHECK(contains(out, "\"observations\":[]"));
    clear(&out);
    return 0;
}

static int check_personal_evidence(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    const char *facts[] = {
        "{\"hierarchy_id\":\"conversation:family-a\",\"source_id\":\"mother\",\"source_kind\":\"user_turn\",\"sequence\":1,\"text\":\"Minha mãe se chama PessoaM.\"}",
        "{\"hierarchy_id\":\"conversation:family-b\",\"source_id\":\"question\",\"source_kind\":\"user_assertion\",\"sequence\":1,\"text\":\"Qual nome da minha mãe?\"}",
        "{\"hierarchy_id\":\"conversation:family-c\",\"source_id\":\"sister\",\"source_kind\":\"user_turn\",\"sequence\":1,\"text\":\"Minha irmã se chama PessoaI.\"}",
        "{\"hierarchy_id\":\"conversation:family-a\",\"source_id\":\"assistant\",\"source_kind\":\"assistant_generated\",\"sequence\":2,\"text\":\"Minha mãe se chama Falsa.\"}",
        "{\"hierarchy_id\":\"conversation:family-d\",\"source_id\":\"vehicle\",\"source_kind\":\"user_turn\",\"sequence\":1,\"text\":\"Meu carro é azul.\"}"
    };
    size_t i;
    for (i = 0; i < sizeof(facts) / sizeof(*facts); ++i) {
        CHECK(call_json(memoria_mobile_observe_structural_text_json,
                        h, facts[i], &out) == MEMORIA_MOBILE_OK);
        clear(&out);
    }
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:new\",\"query\":\"Qual nome da minha mãe?\",\"top_k\":3,\"mode\":\"personal_evidence\"}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"CANDIDATES\""));
    CHECK(contains(out, "\"qualified\":false"));
    CHECK(contains(out, "Minha mãe se chama PessoaM."));
    CHECK(contains(out, "\"source_hierarchy_id\":\"conversation:family-a\""));
    CHECK(!contains(out, "Falsa"));
    CHECK(!contains(out, "\"source_id\":\"question\""));
    CHECK(!contains(out, "Meu carro é azul."));
    clear(&out);
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:new\",\"query\":\"Qual nome da minha irmã?\",\"top_k\":3,\"mode\":\"personal_evidence\"}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"CANDIDATES\""));
    CHECK(contains(out, "Minha irmã se chama PessoaI."));
    CHECK(!contains(out, "Minha mãe se chama PessoaM."));
    clear(&out);
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:new\",\"query\":\"Qual a tensão do transformador?\",\"top_k\":3,\"mode\":\"personal_evidence\"}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(!contains(out, "\"status\":\"HIT\""));
    clear(&out);
    return 0;
}

static int check_region_probe(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    const char *fact_region, *echo_region;
    CHECK(call_json(memoria_mobile_probe_structural_regions_json, h,
        "{\"query\":\"Qual nome da minha mãe?\",\"limit\":16}", &out)
        == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"CANDIDATES\""));
    CHECK(contains(out, "\"qualified\":false"));
    CHECK(contains(out, "\"trajectory_used\":false"));
    CHECK(contains(out, "\"unseen_query_symbols\":0"));
    fact_region = strstr((const char *)out.data,
        "\"hierarchy_id\":\"conversation:family-a\"");
    echo_region = strstr((const char *)out.data,
        "\"hierarchy_id\":\"conversation:family-b\"");
    CHECK(fact_region != NULL && echo_region != NULL && fact_region < echo_region);
    CHECK(strncmp(fact_region,
        "\"hierarchy_id\":\"conversation:family-a\",\"observation_count\":2,"
        "\"matching_count\":1,\"query_echo_count\":0,\"distinct_count\":1",
        strlen("\"hierarchy_id\":\"conversation:family-a\",\"observation_count\":2,"
               "\"matching_count\":1,\"query_echo_count\":0,\"distinct_count\":1")) == 0);
    CHECK(strncmp(echo_region,
        "\"hierarchy_id\":\"conversation:family-b\",\"observation_count\":1,"
        "\"matching_count\":1,\"query_echo_count\":1,\"distinct_count\":0",
        strlen("\"hierarchy_id\":\"conversation:family-b\",\"observation_count\":1,"
               "\"matching_count\":1,\"query_echo_count\":1,\"distinct_count\":0")) == 0);
    CHECK(!contains(out, "Falsa"));
    clear(&out);
    CHECK(call_json(memoria_mobile_probe_structural_regions_json, h,
        "{\"query\":\"transformador indutância\"}", &out)
        == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"UNRESOLVED\""));
    CHECK(contains(out, "\"unseen_query_symbols\":2"));
    CHECK(contains(out, "\"region_count\":0"));
    clear(&out);
    return 0;
}

static int check_near_echo_is_not_evidence(void) {
    const char *dir = "./tmp-mobile-near-echo";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-near-echo");
    CHECK(memoria_mobile_open(dir, "org-near-echo", &h) == MEMORIA_MOBILE_OK);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:questions\",\"source_id\":\"q1\","
        "\"source_kind\":\"user_assertion\",\"sequence\":1,"
        "\"text\":\"Qual nome da minha mãe?\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:questions\",\"source_id\":\"q2\","
        "\"source_kind\":\"user_assertion\",\"sequence\":2,"
        "\"text\":\"Qual o nome da minha mãe?\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:record\",\"source_id\":\"record\","
        "\"source_kind\":\"user_turn\",\"sequence\":1,"
        "\"text\":\"Minha mãe se chama PessoaM.\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(call_json(memoria_mobile_probe_structural_regions_json, h,
        "{\"query\":\"Qual nome da minha mãe?\"}", &out)
        == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"qualified\":false"));
    CHECK(contains(out, "\"hierarchy_id\":\"conversation:questions\","
        "\"observation_count\":2,\"matching_count\":2,"
        "\"query_echo_count\":1,\"distinct_count\":1"));
    clear(&out);
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:new\","
        "\"query\":\"Qual nome da minha mãe?\","
        "\"mode\":\"personal_evidence\"}", &out)
        == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(!contains(out, "\"status\":\"HIT\""));
    clear(&out);
    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-near-echo");
    return 0;
}

static int check_trail_recurrence(void) {
    const char *dir = "./tmp-mobile-trail-recurrence";
    const char *observations[] = {
        "{\"hierarchy_id\":\"conversation:a\",\"source_id\":\"f1\",\"source_kind\":\"user_turn\",\"sequence\":1,\"text\":\"Minha mãe se chama PessoaM.\"}",
        "{\"hierarchy_id\":\"conversation:a\",\"source_id\":\"f2\",\"source_kind\":\"user_turn\",\"sequence\":2,\"text\":\"Minha mãe se chama PessoaM.\"}",
        "{\"hierarchy_id\":\"conversation:b\",\"source_id\":\"f3\",\"source_kind\":\"user_turn\",\"sequence\":1,\"text\":\"Minha mãe se chama PessoaM.\"}",
        "{\"hierarchy_id\":\"conversation:c\",\"source_id\":\"alt\",\"source_kind\":\"user_turn\",\"sequence\":1,\"text\":\"Minha mãe se chama PessoaN.\"}",
        "{\"hierarchy_id\":\"conversation:d\",\"source_id\":\"extension\",\"source_kind\":\"user_turn\",\"sequence\":1,\"text\":\"Minha mãe se chama PessoaM hoje.\"}",
        "{\"hierarchy_id\":\"conversation:q\",\"source_id\":\"q1\",\"source_kind\":\"user_assertion\",\"sequence\":1,\"text\":\"Qual nome da minha mãe?\"}",
        "{\"hierarchy_id\":\"conversation:q\",\"source_id\":\"q2\",\"source_kind\":\"user_assertion\",\"sequence\":2,\"text\":\"Qual nome da minha mãe?\"}",
        "{\"hierarchy_id\":\"conversation:a\",\"source_id\":\"generated\",\"source_kind\":\"assistant_generated\",\"sequence\":3,\"text\":\"Minha mãe se chama Falsa.\"}"
    };
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    size_t i;
    (void)system("rm -rf ./tmp-mobile-trail-recurrence");
    CHECK(memoria_mobile_open(dir, "org-trail-recurrence", &h) == MEMORIA_MOBILE_OK);
    for (i = 0u; i < sizeof(observations) / sizeof(*observations); ++i) {
        CHECK(call_json(memoria_mobile_observe_structural_text_json,
            h, observations[i], &out) == MEMORIA_MOBILE_OK);
        clear(&out);
    }
    for (i = 0u; i < 2u; ++i) {
        CHECK(call_json(memoria_mobile_probe_structural_trails_json, h,
            "{\"query\":\"Qual nome da minha mãe?\",\"limit\":16}", &out)
            == MEMORIA_MOBILE_UNRESOLVED);
        CHECK(contains(out, "\"qualified\":false"));
        CHECK(contains(out, "\"group_count\":4"));
        CHECK(contains(out, "\"source_id\":\"f1\",\"hierarchy_id\":\"conversation:a\","
            "\"occurrences\":3,\"region_count\":2"));
        CHECK(contains(out, "\"region_ids\":[\"conversation:a\",\"conversation:b\"]"));
        CHECK(contains(out, "\"sources\":[{\"source_id\":\"f1\","
            "\"hierarchy_id\":\"conversation:a\",\"sequence\":1},"
            "{\"source_id\":\"f2\",\"hierarchy_id\":\"conversation:a\","
            "\"sequence\":2},{\"source_id\":\"f3\","
            "\"hierarchy_id\":\"conversation:b\",\"sequence\":1}]"));
        CHECK(contains(out, "\"sources_truncated\":false"));
        CHECK(contains(out, "\"source_id\":\"alt\",\"hierarchy_id\":\"conversation:c\","
            "\"occurrences\":1,\"region_count\":1"));
        CHECK(contains(out, "\"source_id\":\"extension\",\"hierarchy_id\":\"conversation:d\","
            "\"occurrences\":1,\"region_count\":1"));
        {
            const char *fact = strstr((const char *)out.data, "\"source_id\":\"f1\"");
            const char *alternative = strstr((const char *)out.data, "\"source_id\":\"alt\"");
            const char *fact_branch = fact ? strstr(fact, "\"branch_address\":\"") : NULL;
            const char *alt_branch = alternative ? strstr(alternative, "\"branch_address\":\"") : NULL;
            const size_t prefix_len = sizeof("\"branch_address\":\"") - 1u;
            CHECK(fact_branch && alt_branch);
            CHECK(strncmp(fact_branch + prefix_len, alt_branch + prefix_len, 16u) == 0);
            CHECK(strncmp(fact_branch + prefix_len + 16u,
                "\",\"branch_depth\":4,\"divergent_trail_count\":1",
                sizeof("\",\"branch_depth\":4,\"divergent_trail_count\":1") - 1u) == 0);
            CHECK(strncmp(alt_branch + prefix_len + 16u,
                "\",\"branch_depth\":4,\"divergent_trail_count\":2",
                sizeof("\",\"branch_depth\":4,\"divergent_trail_count\":2") - 1u) == 0);
            CHECK(fact_branch[prefix_len] != '"');
        }
        CHECK(contains(out, "\"source_id\":\"q1\",\"hierarchy_id\":\"conversation:q\","
            "\"occurrences\":2,\"region_count\":1"));
        CHECK(contains(out, "\"query_echo\":true"));
        CHECK(!contains(out, "generated"));
        clear(&out);
        if (i == 0u) {
            CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
            memoria_mobile_close(h);
            h = NULL;
            CHECK(memoria_mobile_open(dir, "org-trail-recurrence", &h)
                == MEMORIA_MOBILE_OK);
        }
    }
    for (i = 0u; i < 17u; ++i) {
        char request[256];
        snprintf(request, sizeof(request),
            "{\"hierarchy_id\":\"conversation:a\",\"source_id\":\"extra-%zu\","
            "\"source_kind\":\"user_turn\",\"sequence\":%zu,"
            "\"text\":\"Minha mãe se chama PessoaM.\"}", i, i + 4u);
        CHECK(call_json(memoria_mobile_observe_structural_text_json,
            h, request, &out) == MEMORIA_MOBILE_OK);
        clear(&out);
    }
    CHECK(call_json(memoria_mobile_probe_structural_trails_json, h,
        "{\"query\":\"Qual nome da minha mãe?\",\"limit\":1}", &out)
        == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"next_offset\":1"));
    CHECK(contains(out, "\"returned\":1"));
    CHECK(contains(out, "\"occurrences\":20,\"region_count\":2"));
    CHECK(contains(out, "\"sources_truncated\":true"));
    clear(&out);
    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-trail-recurrence");
    return 0;
}

int main(void) {
    const char *dir = "./tmp-mobile-structural-text";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};

    (void)system("rm -rf ./tmp-mobile-structural-text");
    CHECK(memoria_mobile_open(dir, "org-structural-mobile", &h) == MEMORIA_MOBILE_OK);
    CHECK(check_near_echo_is_not_evidence() == 0);
    CHECK(check_trail_recurrence() == 0);

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
    CHECK(check_surface_collection(h) == 0);
    CHECK(check_personal_evidence(h) == 0);
    CHECK(check_region_probe(h) == 0);

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
    /* Explicit assistant content must not be grouped with user evidence. */
    CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"source_id\":\"region-assistant\","
        "\"source_kind\":\"assistant_generated\",\"sequence\":6,"
        "\"text\":\"qual nome do meu pai?\"}", &out) == MEMORIA_MOBILE_OK);
    clear(&out);
    CHECK(check_window_group(h) == 0);
    CHECK(check_window_region(h) == 0);

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
    CHECK(contains(out, "\"observation_count\":21"));
    clear(&out);

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h);
    h = NULL;

    /* Full mobile-handle reopen reconstructs the derived field from shared BDR. */
    CHECK(memoria_mobile_open(dir, "org-structural-mobile", &h) == MEMORIA_MOBILE_OK);
    CHECK(resolve_alt(h) == 0);

    CHECK(check_context_scope(h) == 0);
    CHECK(check_window_group(h) == 0);
    CHECK(check_window_region(h) == 0);
    CHECK(check_personal_evidence(h) == 0);
    CHECK(check_region_probe(h) == 0);
    CHECK(call_json(memoria_mobile_resolve_structural_text_json, h,
        "{\"hierarchy_id\":\"conversation:collection\","
        "\"query\":\"Quais gatos eu mencionei?\",\"top_k\":3}", &out)
        == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "Tenho um gato chamado Alt."));
    CHECK(contains(out, "Também conheço um gato chamado Nino."));
    clear(&out);

    /* A new observation invalidates a token obtained before the mutation. */
    CHECK(call_json(memoria_mobile_read_structural_window_json, h,
        "{\"hierarchy_id\":\"conversation:region\",\"limit\":2}", &out)
        == MEMORIA_MOBILE_OK);
    {
        const char *start = strstr((const char *)out.data, "\"window_token\":\"");
        char old_token[17], request[256];
        CHECK(start != NULL);
        start += strlen("\"window_token\":\"");
        memcpy(old_token, start, 16u);
        old_token[16] = 0;
        clear(&out);
        CHECK(call_json(memoria_mobile_observe_structural_text_json, h,
            "{\"hierarchy_id\":\"conversation:region\","
            "\"source_id\":\"region-new\",\"source_kind\":\"user_turn\","
            "\"sequence\":7,\"text\":\"Outra observação.\"}", &out)
            == MEMORIA_MOBILE_OK);
        clear(&out);
        snprintf(request, sizeof(request),
            "{\"hierarchy_id\":\"conversation:region\",\"offset\":2,"
            "\"expected_token\":\"%s\"}", old_token);
        CHECK(call_json(memoria_mobile_read_structural_window_json, h,
            request, &out) == MEMORIA_MOBILE_UNRESOLVED);
        CHECK(contains(out, "\"status\":\"STALE_WINDOW\""));
        CHECK(contains(out, "\"window_revision\":7"));
        clear(&out);
    }

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
