#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status call(memoria_mobile_handle *h, int resolve, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return resolve ? memoria_mobile_resolve_context_json(h, in, out)
                   : memoria_mobile_learn_turn_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

int main(void) {
    const char *dir = "./tmp-mobile-dynamic-capacity";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char request[512];
    int i;

    (void)system("rm -rf ./tmp-mobile-dynamic-capacity");
    CHECK(memoria_mobile_open(dir, "org-dynamic-capacity", &h) == MEMORIA_MOBILE_OK);

    for (i = 0; i < 300; ++i) {
        snprintf(
            request,
            sizeof(request),
            "{\"role\":\"user\",\"text\":\"item%03d is value%03d\",\"memory_id\":\"scale:%03d\",\"order\":%d}",
            i, i, i, i
        );
        CHECK(call(h, 0, request, &out) == MEMORIA_MOBILE_OK);
        memoria_mobile_free_buffer(out);
        out = (memoria_mobile_buffer){0};
    }

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h);
    h = NULL;

    CHECK(memoria_mobile_open(dir, "org-dynamic-capacity", &h) == MEMORIA_MOBILE_OK);
    CHECK(call(h, 1, "{\"query\":\"item299\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"scale:299\"]"));
    CHECK(contains(out, "item299 is value299"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-dynamic-capacity");
    return 0;
}
