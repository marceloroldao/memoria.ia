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

static int run_pair_recall(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    const char *request =
        "{\"query\":\"what are both models\",\"session_id\":\"s-pair\",\"conversation_window\":["
        "{\"session_id\":\"s-pair\",\"role\":\"user\",\"text\":\"device alpha model is N7\",\"order\":1},"
        "{\"session_id\":\"s-pair\",\"role\":\"user\",\"text\":\"device beta model is Q4\",\"order\":2}]}";

    CHECK(call(h,0,request,&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"memory_ids\":[\"m1\",\"m2\"]"));
    CHECK(contains(out,"\"multi_source_used\":true"));
    CHECK(contains(out,"\"trajectory_used\":true"));
    CHECK(contains(out,"SOURCE_1: device alpha model is N7"));
    CHECK(contains(out,"SOURCE_2: device beta model is Q4"));
    CHECK(contains(out,"\"memory_id\":\"m1\""));
    CHECK(contains(out,"\"memory_id\":\"m2\""));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-trajectory-multisource");

    CHECK(memoria_mobile_open("./tmp-mobile-trajectory-multisource","org-trajectory-multisource",&h) == MEMORIA_MOBILE_OK);
    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device alpha model is N7\",\"memory_id\":\"m1\",\"order\":1}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"device beta model is Q4\",\"memory_id\":\"m2\",\"order\":2}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(run_pair_recall(h) == 0);
    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-trajectory-multisource","org-trajectory-multisource",&h) == MEMORIA_MOBILE_OK);
    CHECK(run_pair_recall(h) == 0);

    /* Singular reference to two equally grounded roots must still fail closed. */
    CHECK(call(h,0,
        "{\"query\":\"what is its model\",\"session_id\":\"s-pair\",\"conversation_window\":["
        "{\"session_id\":\"s-pair\",\"role\":\"user\",\"text\":\"device alpha model is N7\",\"order\":1},"
        "{\"session_id\":\"s-pair\",\"role\":\"user\",\"text\":\"device beta model is Q4\",\"order\":2}]}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-trajectory-multisource");
    return 0;
}
