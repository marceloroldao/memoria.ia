#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status call(memoria_mobile_handle *h, int learn, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return learn ? memoria_mobile_learn_turn_json(h,in,out) : memoria_mobile_resolve_context_json(h,in,out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data,needle) != NULL;
}

static int assert_alpha_temporal(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call(h,0,"{\"query\":\"what was device alpha mode before and what is current now?\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"temporal_state_used\":true"));
    CHECK(contains(out,"\"memory_ids\":[\"a1\",\"a2\"]"));
    CHECK(contains(out,"\"previous_memory_id\":\"a1\""));
    CHECK(contains(out,"\"current_memory_id\":\"a2\""));
    CHECK(contains(out,"\"previous_order\":10"));
    CHECK(contains(out,"\"current_order\":20"));
    CHECK(contains(out,"\"previous_value\":\"standby\""));
    CHECK(contains(out,"\"current_value\":\"active\""));
    CHECK(contains(out,"\"transition_detected\":true"));
    CHECK(!contains(out,"broken"));
    memoria_mobile_free_buffer(out);
    return 0;
}

static int assert_beta_temporal(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call(h,0,"{\"query\":\"what was device beta mode before and what is current now?\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"temporal_state_used\":true"));
    CHECK(contains(out,"\"memory_ids\":[\"b1\",\"b2\"]"));
    CHECK(contains(out,"\"previous_value\":\"idle\""));
    CHECK(contains(out,"\"current_value\":\"running\""));
    memoria_mobile_free_buffer(out);
    return 0;
}

static int assert_session_trajectory_temporal(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};

    CHECK(call(h,0,
        "{\"query\":\"what was its mode before and what is current now?\",\"session_id\":\"s-alpha\",\"conversation_window\":["
        "{\"session_id\":\"s-alpha\",\"role\":\"user\",\"text\":\"device alpha mode is active\",\"order\":1}]}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"temporal_state_used\":true"));
    CHECK(contains(out,"\"memory_ids\":[\"a1\",\"a2\"]"));
    CHECK(contains(out,"\"previous_value\":\"standby\""));
    CHECK(contains(out,"\"current_value\":\"active\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,0,
        "{\"query\":\"what was its mode before and what is current now?\",\"session_id\":\"s-beta\",\"conversation_window\":["
        "{\"session_id\":\"s-beta\",\"role\":\"user\",\"text\":\"device beta mode is running\",\"order\":1}]}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"temporal_state_used\":true"));
    CHECK(contains(out,"\"memory_ids\":[\"b1\",\"b2\"]"));
    CHECK(contains(out,"\"previous_value\":\"idle\""));
    CHECK(contains(out,"\"current_value\":\"running\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    /* A trajectory-local antecedent from another session must not leak. */
    CHECK(call(h,0,
        "{\"query\":\"what was its mode before and what is current now?\",\"session_id\":\"s-beta\",\"conversation_window\":["
        "{\"session_id\":\"s-alpha\",\"role\":\"user\",\"text\":\"device alpha mode is active\",\"order\":1}]}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    /* Explicitly naming two temporal targets is ambiguous and must fail closed. */
    CHECK(call(h,0,
        "{\"query\":\"what was device alpha mode or device beta mode before and what is current now?\"}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out);
    return 0;
}

static int learn_portuguese_history(memoria_mobile_handle *h) {
    static const char *turns[] = {
        "{\"role\":\"user\",\"text\":\"A fonte Vega fornece 12 volts.\",\"memory_id\":\"vega-now\",\"order\":20}",
        "{\"role\":\"user\",\"text\":\"A fonte Vega fica no laboratório.\",\"memory_id\":\"vega-location\",\"order\":30}",
        "{\"role\":\"user\",\"text\":\"A fonte Vega fornece 24 volts.\",\"memory_id\":\"vega-old\",\"order\":10}",
        "{\"role\":\"assistant\",\"text\":\"A fonte Vega fornece 99 volts.\",\"memory_id\":\"vega-generated\",\"source_authority\":1.0,\"order\":40}",
        "{\"role\":\"user\",\"text\":\"A fonte Vega fornece 48 volts.\",\"memory_id\":\"vega-private\",\"namespace\":\"other\",\"order\":50}",
        "{\"role\":\"user\",\"text\":\"O sensor Polaris fica na garagem.\",\"memory_id\":\"polaris-a\",\"order\":100}",
        "{\"role\":\"user\",\"text\":\"O sensor Polaris fica no depósito.\",\"memory_id\":\"polaris-b\",\"order\":100}",
        "{\"role\":\"user\",\"text\":\"O projetor Aurora é branco.\",\"memory_id\":\"aurora-only\",\"order\":15}",
    };
    for (size_t i = 0; i < sizeof(turns) / sizeof(turns[0]); ++i) {
        memoria_mobile_buffer out = {0};
        CHECK(call(h, 1, turns[i], &out) == MEMORIA_MOBILE_OK);
        memoria_mobile_free_buffer(out);
    }
    return 0;
}

static int assert_portuguese_history(memoria_mobile_handle *h) {
    static const char *questions[] = {
        "{\"query\":\"Quantos volts a fonte Vega fornecia antes da mudança?\"}",
        "{\"query\":\"Qual é a tensão atual da fonte Vega?\"}",
    };
    static const char *unresolved_questions[] = {
        "{\"query\":\"Onde fica o sensor Polaris agora?\"}",
        "{\"query\":\"De que cor era o projetor Aurora antes?\"}",
        "{\"query\":\"De que cor é a fonte Vega agora?\"}",
    };
    for (size_t i = 0; i < sizeof(questions) / sizeof(questions[0]); ++i) {
        memoria_mobile_buffer out = {0};
        CHECK(call(h, 0, questions[i], &out) == MEMORIA_MOBILE_OK);
        CHECK(contains(out, "\"temporal_state_used\":true"));
        CHECK(contains(out, "\"previous_memory_id\":\"vega-old\""));
        CHECK(contains(out, "\"current_memory_id\":\"vega-now\""));
        CHECK(contains(out, "\"previous_value\":\"24 volts\""));
        CHECK(contains(out, "\"current_value\":\"12 volts\""));
        CHECK(contains(out, "\"property\":\"voltage\""));
        CHECK(contains(out, i == 0 ? "\"object\":\"24 volts\"" : "\"object\":\"12 volts\""));
        CHECK(contains(out, "\"previous_order\":10"));
        CHECK(contains(out, "\"current_order\":20"));
        memoria_mobile_free_buffer(out);
    }
    for (size_t i = 0; i < sizeof(unresolved_questions) / sizeof(unresolved_questions[0]); ++i) {
        memoria_mobile_buffer out = {0};
        CHECK(call(h, 0, unresolved_questions[i], &out) == MEMORIA_MOBILE_UNRESOLVED);
        memoria_mobile_free_buffer(out);
    }
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-temporal-state");

    CHECK(memoria_mobile_open("./tmp-mobile-temporal-state","org-temporal",&h) == MEMORIA_MOBILE_OK);
    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device alpha mode is standby\",\"memory_id\":\"a1\",\"order\":10}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"assistant\",\"text\":\"device alpha mode is broken\",\"memory_id\":\"echo\",\"order\":15,\"source_type\":\"assistant_generated\",\"source_authority\":0.35,\"ultimate_source_memory_id\":\"a1\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device alpha mode is active\",\"memory_id\":\"a2\",\"order\":20}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device beta mode is idle\",\"memory_id\":\"b1\",\"order\":30}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device beta mode is running\",\"memory_id\":\"b2\",\"order\":40}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(learn_portuguese_history(h) == 0);

    CHECK(assert_alpha_temporal(h) == 0);
    CHECK(assert_beta_temporal(h) == 0);
    CHECK(assert_session_trajectory_temporal(h) == 0);
    CHECK(assert_portuguese_history(h) == 0);

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-temporal-state","org-temporal",&h) == MEMORIA_MOBILE_OK);
    CHECK(assert_alpha_temporal(h) == 0);
    CHECK(assert_beta_temporal(h) == 0);
    CHECK(assert_session_trajectory_temporal(h) == 0);
    CHECK(assert_portuguese_history(h) == 0);

    CHECK(call(h,0,"{\"query\":\"what was unknown mode before and what is current now?\"}",&out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-temporal-state");
    return 0;
}
