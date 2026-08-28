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

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-trajectory");
    CHECK(memoria_mobile_open("./tmp-mobile-trajectory","org-trajectory",&h) == MEMORIA_MOBILE_OK);

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device alpha model is N7\",\"memory_id\":\"m1\",\"order\":1}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device beta model is Q4\",\"memory_id\":\"m2\",\"order\":2}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,0,"{\"query\":\"and its model\",\"session_id\":\"s1\",\"conversation_window\":[{\"role\":\"user\",\"text\":\"we are discussing device alpha\",\"order\":1},{\"role\":\"assistant\",\"text\":\"device alpha is the cobalt unit\",\"order\":2}]}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"memory_ids\":[\"m1\"]"));
    CHECK(contains(out,"\"trajectory_used\":true"));
    CHECK(contains(out,"\"conversation_window_count\":2"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,0,"{\"query\":\"and its model\",\"session_id\":\"s2\",\"conversation_window\":[{\"session_id\":\"s1\",\"role\":\"user\",\"text\":\"device alpha\",\"order\":1}]}",&out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,0,"{\"query\":\"device beta model\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"memory_ids\":[\"m2\"]"));
    CHECK(contains(out,"\"trajectory_used\":false"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-trajectory");
    return 0;
}
