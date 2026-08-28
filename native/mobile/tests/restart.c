#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status call(memoria_mobile_handle *h, int op, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    switch (op) {
        case 1: return memoria_mobile_learn_turn_json(h,in,out);
        case 2: return memoria_mobile_resolve_context_json(h,in,out);
        case 3: return memoria_mobile_store_episode_json(h,in,out);
        default: return memoria_mobile_recall_episode_json(h,in,out);
    }
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

int main(void) {
    const char *dir = "./tmp-mobile-restart";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};

    (void)system("rm -rf ./tmp-mobile-restart");
    CHECK(memoria_mobile_open(dir,"org-restart",&h) == MEMORIA_MOBILE_OK);

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"orion node is primary\",\"memory_id\":\"u1\",\"order\":1}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"durable\":true"));
    CHECK(contains(out,"\"subject\":\"orion node\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"assistant\",\"text\":\"orion node is primary\",\"memory_id\":\"a1\",\"order\":2,\"source_authority\":0.35,\"ultimate_source_memory_id\":\"u1\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,3,"{\"episode_id\":\"e1\",\"role\":\"assistant\",\"text\":\"first creation about routing\",\"timestamp\":\"2026-08-28T10:00:00Z\",\"order\":1,\"event_type\":\"creation\",\"topics_csv\":\"routing\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call(h,3,"{\"episode_id\":\"e2\",\"role\":\"assistant\",\"text\":\"second creation about routing\",\"timestamp\":\"2026-08-28T11:00:00Z\",\"order\":3,\"event_type\":\"creation\",\"topics_csv\":\"routing\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h=NULL;

    /* Process/app restart equivalent: a fresh handle reconstructs only from BDR. */
    CHECK(memoria_mobile_open(dir,"org-restart",&h) == MEMORIA_MOBILE_OK);
    CHECK(call(h,2,"{\"query\":\"orion node primary\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"memory_ids\":[\"u1\"]"));
    CHECK(contains(out,"\"source_type\":\"user_assertion\""));
    CHECK(contains(out,"\"ultimate_source_memory_id\":\"u1\""));
    CHECK(contains(out,"\"subject\":\"orion node\""));
    CHECK(contains(out,"\"predicate\":\"is\""));
    CHECK(contains(out,"\"object\":\"primary\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,4,"{\"query\":\"last creation about routing\",\"role\":\"assistant\",\"event_type\":\"creation\",\"topics_csv\":\"routing\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"episode_ids\":[\"e2\"]"));
    CHECK(contains(out,"\"order\":3"));
    CHECK(contains(out,"\"timestamp\":\"2026-08-28T11:00:00Z\""));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-restart");
    return 0;
}
