#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

extern memoria_mobile_status memoria_mobile_infer_two_hop_json(
    memoria_mobile_handle *, memoria_mobile_buffer, memoria_mobile_buffer *
);

static memoria_mobile_status learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_turn_json(h, in, out);
}

static memoria_mobile_status infer(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_infer_two_hop_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static int assert_inference(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(infer(h, "{\"subject\":\"porto alegre\",\"predicate\":\"is\",\"namespace\":\"geo\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"resolution\":\"INFERRED\""));
    CHECK(contains(out, "\"answer\":\"brasil\""));
    CHECK(contains(out, "\"via\":\"rio grande do sul\""));
    CHECK(contains(out, "\"proof\":[\"rel-pa-rs\",\"rel-rs-br\"]"));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    const char *dir = "./tmp-mobile-resolutive-inference";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};

    (void)system("rm -rf ./tmp-mobile-resolutive-inference");
    CHECK(memoria_mobile_open(dir, "org-inference", &h) == MEMORIA_MOBILE_OK);

    /* The current relation contract uses explicit copular edges. The inference
       layer composes only identical predicates; it does not invent semantics. */
    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"porto alegre is rio grande do sul\",\"memory_id\":\"m-pa-rs\",\"namespace\":\"geo\",\"source_authority\":0.95,\"relation_memory_ids\":[\"rel-pa-rs\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"rio grande do sul is brasil\",\"memory_id\":\"m-rs-br\",\"namespace\":\"geo\",\"source_authority\":0.94,\"relation_memory_ids\":[\"rel-rs-br\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(assert_inference(h) == 0);

    /* Namespace isolation: the same query cannot borrow another graph. */
    CHECK(infer(h, "{\"subject\":\"porto alegre\",\"predicate\":\"is\",\"namespace\":\"other\"}", &out) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    /* Fresh handle reconstructs the relation graph only from durable BDR state. */
    CHECK(memoria_mobile_open(dir, "org-inference", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_inference(h) == 0);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-resolutive-inference");
    return 0;
}
