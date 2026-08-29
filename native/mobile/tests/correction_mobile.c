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
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static int assert_current(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call(h,0,"{\"query\":\"device alpha mode\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"memory_ids\":[\"m2\"]"));
    CHECK(contains(out,"device alpha mode is active"));
    CHECK(!contains(out,"device alpha mode is standby"));
    CHECK(contains(out,"\"source_type\":\"user_correction\""));
    memoria_mobile_free_buffer(out);
    return 0;
}

static int assert_history(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call(h,0,"{\"query\":\"what was device alpha mode before and what is current now?\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"temporal_state_used\":true"));
    CHECK(contains(out,"\"previous_memory_id\":\"m1\""));
    CHECK(contains(out,"\"current_memory_id\":\"m2\""));
    CHECK(contains(out,"\"previous_value\":\"standby\""));
    CHECK(contains(out,"\"current_value\":\"active\""));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    memoria_mobile_buffer req = {(const uint8_t *)"{}", 2};
    (void)system("rm -rf ./tmp-mobile-correction");

    CHECK(memoria_mobile_open("./tmp-mobile-correction","org-correction",&h) == MEMORIA_MOBILE_OK);
    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device alpha mode is standby\",\"memory_id\":\"m1\",\"order\":1}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"assistant\",\"text\":\"device alpha mode is standby\",\"memory_id\":\"echo\",\"order\":2,\"source_type\":\"assistant_generated\",\"source_authority\":0.35,\"ultimate_source_memory_id\":\"m1\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device alpha mode is active\",\"memory_id\":\"m2\",\"order\":3,\"corrects_memory_ids\":[\"m1\"]}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"correction_applied\":true"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(assert_current(h) == 0);
    CHECK(assert_history(h) == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"memory_id\":\"m1\",\"role\":\"user\",\"text\":\"device alpha mode is standby\",\"source_type\":\"user_assertion\",\"ultimate_source_memory_id\":\"m1\",\"source_authority\":1.000000,\"order\":1,\"superseded\":true"));
    CHECK(contains(out,"\"memory_id\":\"m2\",\"role\":\"user\",\"text\":\"device alpha mode is active\",\"source_type\":\"user_correction\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-correction","org-correction",&h) == MEMORIA_MOBILE_OK);
    CHECK(assert_current(h) == 0);
    CHECK(assert_history(h) == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"order\":1,\"superseded\":true"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-correction");
    return 0;
}
