#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status store(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_store_episode_json(h, in, out);
}

static memoria_mobile_status recall(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_recall_episode_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static int assert_scoped(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};

    CHECK(recall(h,"{\"query\":\"latest atlas status report\",\"session_id\":\"s1\",\"role\":\"assistant\",\"event_type\":\"report\",\"topics_csv\":\"atlas,status\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"episode_ids\":[\"s1-new\"]"));
    CHECK(contains(out,"atlas status report session one new"));
    CHECK(!contains(out,"session two"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(recall(h,"{\"query\":\"latest atlas status report\",\"session_id\":\"s2\",\"role\":\"assistant\",\"event_type\":\"report\",\"topics_csv\":\"atlas,status\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"episode_ids\":[\"s2\"]"));
    CHECK(contains(out,"atlas status report session two"));
    CHECK(!contains(out,"session one"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(recall(h,"{\"query\":\"latest atlas status report\",\"role\":\"assistant\",\"event_type\":\"report\",\"topics_csv\":\"atlas,status\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"episode_ids\":[\"s2\"]"));
    CHECK(contains(out,"atlas status report session two"));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    memoria_mobile_buffer snapshot_req = {(const uint8_t *)"{}", 2};
    (void)system("rm -rf ./tmp-mobile-episodic-session");

    CHECK(memoria_mobile_open("./tmp-mobile-episodic-session","org-session",&h) == MEMORIA_MOBILE_OK);

    CHECK(store(h,"{\"episode_id\":\"s1-old\",\"session_id\":\"s1\",\"role\":\"assistant\",\"text\":\"atlas status report session one old\",\"order\":10,\"event_type\":\"report\",\"topics_csv\":\"atlas,status\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(store(h,"{\"episode_id\":\"s2\",\"session_id\":\"s2\",\"role\":\"assistant\",\"text\":\"atlas status report session two\",\"order\":20,\"event_type\":\"report\",\"topics_csv\":\"atlas,status\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(store(h,"{\"episode_id\":\"s1-new\",\"session_id\":\"s1\",\"role\":\"assistant\",\"text\":\"atlas status report session one new\",\"order\":15,\"event_type\":\"report\",\"topics_csv\":\"atlas,status\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(assert_scoped(h) == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, snapshot_req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"episode_id\":\"s1-old\",\"session_id\":\"s1\""));
    CHECK(contains(out,"\"episode_id\":\"s2\",\"session_id\":\"s2\""));
    CHECK(contains(out,"\"episode_id\":\"s1-new\",\"session_id\":\"s1\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-episodic-session","org-session",&h) == MEMORIA_MOBILE_OK);
    CHECK(assert_scoped(h) == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, snapshot_req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"episode_id\":\"s1-new\",\"session_id\":\"s1\""));
    CHECK(contains(out,"\"episode_id\":\"s2\",\"session_id\":\"s2\""));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-episodic-session");
    return 0;
}
