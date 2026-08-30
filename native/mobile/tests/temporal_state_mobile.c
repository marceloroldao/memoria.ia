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

    CHECK(assert_alpha_temporal(h) == 0);
    CHECK(assert_beta_temporal(h) == 0);
    CHECK(assert_session_trajectory_temporal(h) == 0);

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-temporal-state","org-temporal",&h) == MEMORIA_MOBILE_OK);
    CHECK(assert_alpha_temporal(h) == 0);
    CHECK(assert_beta_temporal(h) == 0);
    CHECK(assert_session_trajectory_temporal(h) == 0);

    CHECK(call(h,0,"{\"query\":\"what was unknown mode before and what is current now?\"}",&out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-temporal-state");
    return 0;
}
