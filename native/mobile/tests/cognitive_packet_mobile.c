#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status call_learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_turn_json(h, in, out);
}

static memoria_mobile_status call_compile(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_compile_context_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static int assert_packet(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call_compile(h, "{\"query\":\"what was device alpha mode before and what is current now?\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"packet_schema\":\"memoria.cognitive.packet.v1\""));
    CHECK(contains(out, "\"status\":\"HIT\""));
    CHECK(contains(out, "\"memory_ids\":[\"a1\",\"a2\"]"));
    CHECK(contains(out, "\"temporal_state_used\":true"));
    CHECK(contains(out, "\"previous_memory_id\":\"a1\""));
    CHECK(contains(out, "\"current_memory_id\":\"a2\""));
    CHECK(contains(out, "\"previous_value\":\"standby\""));
    CHECK(contains(out, "\"current_value\":\"active\""));
    CHECK(contains(out, "\"transition_detected\":true"));
    CHECK(!contains(out, "selected_context"));
    CHECK(!contains(out, "broken"));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-cognitive-packet");

    CHECK(memoria_mobile_open("./tmp-mobile-cognitive-packet", "org-cognitive", &h) == MEMORIA_MOBILE_OK);
    CHECK(call_learn(h, "{\"role\":\"user\",\"text\":\"device alpha mode is standby\",\"memory_id\":\"a1\",\"order\":10}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call_learn(h, "{\"role\":\"assistant\",\"text\":\"device alpha mode is broken\",\"memory_id\":\"echo\",\"order\":15,\"source_type\":\"assistant_generated\",\"source_authority\":0.35,\"ultimate_source_memory_id\":\"a1\"}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call_learn(h, "{\"role\":\"user\",\"text\":\"device alpha mode is active\",\"memory_id\":\"a2\",\"order\":20}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(assert_packet(h) == 0);

    CHECK(call_compile(h, "{\"query\":\"what is unknown device mode?\"}", &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"UNRESOLVED\""));
    CHECK(contains(out, "\"packet\":null"));
    CHECK(!contains(out, "selected_context"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-cognitive-packet", "org-cognitive", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_packet(h) == 0);
    memoria_mobile_close(h);

    (void)system("rm -rf ./tmp-mobile-cognitive-packet");
    return 0;
}
