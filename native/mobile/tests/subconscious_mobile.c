#include "memoria_mobile.h"
#include "subconscious_mobile.h"

#include <assert.h>
#include <stdint.h>
#include <string.h>

static memoria_mobile_buffer buf(const char *s) {
    memoria_mobile_buffer b;
    b.data = (const uint8_t *)s;
    b.size = strlen(s);
    return b;
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != 0;
}

int main(void) {
    memoria_mobile_handle *h = (memoria_mobile_handle *)(uintptr_t)0x1234;
    memoria_mobile_buffer out = {0};

    memoria_subconscious_mobile_observe_resolution(
        h, buf("{\"query\":\"me fale sobre a China\"}"),
        MEMORIA_MOBILE_UNRESOLVED,
        buf("{\"status\":\"UNRESOLVED\"}"));
    memoria_subconscious_mobile_observe_resolution(
        h, buf("{\"query\":\"fale mais sobre China\"}"),
        MEMORIA_MOBILE_UNRESOLVED,
        buf("{\"status\":\"UNRESOLVED\"}"));

    assert(memoria_mobile_subconscious_peek_json(h, buf("{}"), &out) == MEMORIA_MOBILE_OK);
    assert(contains(out, "\"pending\":true"));
    assert(contains(out, "\"topic\":\"china\""));
    assert(contains(out, "\"observations\":2"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    assert(memoria_mobile_subconscious_satisfy_json(h, buf("{\"topic\":\"China\"}"), &out) == MEMORIA_MOBILE_OK);
    assert(contains(out, "\"removed\":true"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    assert(memoria_mobile_subconscious_peek_json(h, buf("{}"), &out) == MEMORIA_MOBILE_OK);
    assert(contains(out, "\"pending\":false"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Strongly resolved context is not a knowledge gap. */
    memoria_subconscious_mobile_observe_resolution(
        h, buf("{\"query\":\"o que é a Lua\"}"),
        MEMORIA_MOBILE_OK,
        buf("{\"status\":\"HIT\",\"confidence\":0.79}"));
    assert(memoria_mobile_subconscious_peek_json(h, buf("{}"), &out) == MEMORIA_MOBILE_OK);
    assert(contains(out, "\"pending\":false"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Low-confidence HIT does become a background research candidate. */
    memoria_subconscious_mobile_observe_resolution(
        h, buf("{\"query\":\"capital da China\"}"),
        MEMORIA_MOBILE_OK,
        buf("{\"status\":\"HIT\",\"confidence\":0.51}"));
    assert(memoria_mobile_subconscious_peek_json(h, buf("{}"), &out) == MEMORIA_MOBILE_OK);
    assert(contains(out, "\"topic\":\"capital china\""));
    memoria_mobile_free_buffer(out);

    memoria_subconscious_mobile_forget_handle(h);
    return 0;
}
