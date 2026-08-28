#include "memoria_mobile.h"

#include <assert.h>
#include <string.h>

static memoria_mobile_status call(memoria_mobile_handle *h, int op, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    switch (op) {
        case 1: return memoria_mobile_learn_turn_json(h,in,out);
        case 2: return memoria_mobile_resolve_context_json(h,in,out);
        case 3: return memoria_mobile_store_episode_json(h,in,out);
        default: return memoria_mobile_recall_episode_json(h,in,out);
    }
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    assert(memoria_mobile_abi_version() == MEMORIA_MOBILE_ABI_VERSION);
    assert(memoria_mobile_open("./tmp-mobile","org-test",&h) == MEMORIA_MOBILE_OK);

    assert(call(h,1,"{\"role\":\"user\",\"text\":\"project atlas code is 4729\",\"memory_id\":\"u1\",\"order\":1}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out);
    assert(call(h,1,"{\"role\":\"assistant\",\"text\":\"the atlas code is 4729\",\"memory_id\":\"a1\",\"order\":2,\"source_authority\":0.35,\"ultimate_source_memory_id\":\"u1\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out);
    assert(call(h,2,"{\"query\":\"atlas code 4729\"}",&out) == MEMORIA_MOBILE_OK);
    assert(strstr((const char *)out.data,"\"memory_ids\":[\"u1\"]") != NULL);
    assert(strstr((const char *)out.data,"\"source_type\":\"user_assertion\"") != NULL);
    memoria_mobile_free_buffer(out);

    assert(call(h,2,"{\"query\":\"unknown satellite frequency\"}",&out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out);

    assert(call(h,3,"{\"episode_id\":\"e1\",\"role\":\"assistant\",\"text\":\"first creation about transport\",\"order\":1,\"event_type\":\"creation\",\"topics_csv\":\"transport\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out);
    assert(call(h,3,"{\"episode_id\":\"e2\",\"role\":\"assistant\",\"text\":\"second creation about transport\",\"order\":3,\"event_type\":\"creation\",\"topics_csv\":\"transport\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out);
    assert(call(h,4,"{\"query\":\"last creation about transport\",\"role\":\"assistant\",\"event_type\":\"creation\",\"topics_csv\":\"transport\"}",&out) == MEMORIA_MOBILE_OK);
    assert(strstr((const char *)out.data,"\"episode_ids\":[\"e2\"]") != NULL);
    assert(strstr((const char *)out.data,"\"order\":3") != NULL);
    memoria_mobile_free_buffer(out);

    assert(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h);
    return 0;
}
