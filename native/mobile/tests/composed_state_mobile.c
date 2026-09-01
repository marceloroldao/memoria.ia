#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status call(
    memoria_mobile_handle *h,
    int learn,
    const char *json,
    memoria_mobile_buffer *out
) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return learn
        ? memoria_mobile_learn_turn_json(h, in, out)
        : memoria_mobile_resolve_composed_state_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static int assert_alpha_state(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call(h, 0,
        "{\"entity\":\"device alpha\",\"properties\":[\"model\",\"mode\"],\"namespace\":\"s-alpha\"}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"status\":\"HIT\""));
    CHECK(contains(out, "\"composed_state_used\":true"));
    CHECK(contains(out, "\"entity\":\"device alpha\""));
    CHECK(contains(out, "\"property\":\"model\",\"value\":\"N7\""));
    CHECK(contains(out, "\"memory_id\":\"a-model-new#relation:0\""));
    CHECK(contains(out, "\"property\":\"mode\",\"value\":\"active\""));
    CHECK(contains(out, "\"memory_id\":\"a-mode-new#relation:0\""));
    CHECK(!contains(out, "N6"));
    CHECK(!contains(out, "standby"));
    CHECK(!contains(out, "device beta"));
    CHECK(!contains(out, "assistant-firmware#relation:0"));
    memoria_mobile_free_buffer(out);
    return 0;
}

static int assert_fail_closed(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};

    CHECK(call(h, 0,
        "{\"entity\":\"device alpha\",\"properties\":[\"model\",\"firmware\"],\"namespace\":\"s-alpha\"}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"UNRESOLVED\""));
    CHECK(contains(out, "\"composed_state_used\":true"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call(h, 0,
        "{\"entity\":\"device gamma\",\"properties\":[\"mode\"],\"namespace\":\"s-gamma\"}",
        &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"ambiguous\":true"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call(h, 0,
        "{\"entity\":\"device alpha\",\"properties\":[],\"namespace\":\"s-alpha\"}",
        &out) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    const char *dir = "./tmp-mobile-composed-state";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-composed-state");

    CHECK(memoria_mobile_open(dir, "org-composed-state", &h) == MEMORIA_MOBILE_OK);

    CHECK(call(h, 1,
        "{\"role\":\"user\",\"text\":\"device alpha model is N6\",\"memory_id\":\"a-model-old\",\"namespace\":\"s-alpha\",\"order\":5}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call(h, 1,
        "{\"role\":\"user\",\"text\":\"device alpha mode is standby\",\"memory_id\":\"a-mode-old\",\"namespace\":\"s-alpha\",\"order\":7}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call(h, 1,
        "{\"role\":\"user\",\"text\":\"device alpha model is N7\",\"memory_id\":\"a-model-new\",\"namespace\":\"s-alpha\",\"order\":10}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Assistant output is durable but should have no promoted relation after #140. */
    CHECK(call(h, 1,
        "{\"role\":\"assistant\",\"text\":\"device alpha firmware is broken\",\"memory_id\":\"assistant-firmware\",\"namespace\":\"s-alpha\",\"order\":15}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"relations\":[]"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call(h, 1,
        "{\"role\":\"user\",\"text\":\"device alpha mode is active\",\"memory_id\":\"a-mode-new\",\"namespace\":\"s-alpha\",\"order\":20}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call(h, 1,
        "{\"role\":\"user\",\"text\":\"device beta mode is running\",\"memory_id\":\"beta-mode\",\"namespace\":\"s-beta\",\"order\":30}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Same latest order + conflicting values must fail closed. */
    CHECK(call(h, 1,
        "{\"role\":\"user\",\"text\":\"device gamma mode is active\",\"memory_id\":\"gamma-a\",\"namespace\":\"s-gamma\",\"order\":40}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(call(h, 1,
        "{\"role\":\"user\",\"text\":\"device gamma mode is idle\",\"memory_id\":\"gamma-b\",\"namespace\":\"s-gamma\",\"order\":40}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(assert_alpha_state(h) == 0);
    CHECK(assert_fail_closed(h) == 0);

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open(dir, "org-composed-state", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_alpha_state(h) == 0);
    CHECK(assert_fail_closed(h) == 0);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-composed-state");
    return 0;
}
