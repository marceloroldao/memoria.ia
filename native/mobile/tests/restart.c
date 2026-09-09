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
        case 5: return memoria_mobile_compile_context_json(h,in,out);
        default: return memoria_mobile_recall_episode_json(h,in,out);
    }
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static char *copy_buffer(memoria_mobile_buffer b) {
    char *copy;
    if (!b.data) return NULL;
    copy = (char *)malloc(b.size + 1u);
    if (!copy) return NULL;
    memcpy(copy, b.data, b.size);
    copy[b.size] = 0;
    return copy;
}

static int same_buffer(memoria_mobile_buffer b, const char *expected) {
    size_t n;
    if (!b.data || !expected) return 0;
    n = strlen(expected);
    return b.size == n && memcmp(b.data, expected, n) == 0;
}

int main(void) {
    const char *dir = "./tmp-mobile-restart";
    const char *plural_query = "{\"query\":\"qual nome dos meus gatos?\"}";
    const char *window_before_answer =
        "{\"query\":\"qual nome dos meus gatos?\",\"session_id\":\"device-test\",\"conversation_window\":["
        "{\"session_id\":\"device-test\",\"role\":\"user\",\"text\":\"eu tenho um gato que se chama Lotus\",\"order\":1},"
        "{\"session_id\":\"device-test\",\"role\":\"assistant\",\"text\":\"Lotus é um gato.\",\"order\":2},"
        "{\"session_id\":\"device-test\",\"role\":\"user\",\"text\":\"ele tem um irmão, que se chama Vibe\",\"order\":3},"
        "{\"session_id\":\"device-test\",\"role\":\"assistant\",\"text\":\"Vibe é o irmão de Lotus.\",\"order\":4}]}";
    const char *window_after_answer =
        "{\"query\":\"qual nome dos meus gatos?\",\"session_id\":\"device-test\",\"conversation_window\":["
        "{\"session_id\":\"device-test\",\"role\":\"user\",\"text\":\"eu tenho um gato que se chama Lotus\",\"order\":1},"
        "{\"session_id\":\"device-test\",\"role\":\"assistant\",\"text\":\"Lotus é um gato.\",\"order\":2},"
        "{\"session_id\":\"device-test\",\"role\":\"user\",\"text\":\"ele tem um irmão, que se chama Vibe\",\"order\":3},"
        "{\"session_id\":\"device-test\",\"role\":\"assistant\",\"text\":\"Vibe é o irmão de Lotus.\",\"order\":4},"
        "{\"session_id\":\"device-test\",\"role\":\"user\",\"text\":\"qual nome dos meus gatos?\",\"order\":5},"
        "{\"session_id\":\"device-test\",\"role\":\"assistant\",\"text\":\"Os meus gatos são Lotus e Vibe.\",\"order\":6}]}";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char *before_restart_packet = NULL;
    char *after_restart_packet = NULL;
    int i;

    (void)system("rm -rf ./tmp-mobile-restart");
    CHECK(memoria_mobile_open(dir,"org-restart",&h) == MEMORIA_MOBILE_OK);

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"orion node is primary\",\"memory_id\":\"u1\",\"order\":1}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"durable\":true"));
    CHECK(contains(out,"\"subject\":\"orion node\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"assistant\",\"text\":\"orion node is primary\",\"memory_id\":\"a1\",\"order\":2,\"source_authority\":0.35,\"ultimate_source_memory_id\":\"u1\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"eu tenho um gato que se chama Lotus\",\"memory_id\":\"cat1\",\"order\":3}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"subject\":\"Lotus\""));
    CHECK(contains(out,"\"predicate\":\"is\""));
    CHECK(contains(out,"\"object\":\"gato\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,1,"{\"role\":\"user\",\"text\":\"ele tem um irmão, que se chama Vibe\",\"memory_id\":\"cat2\",\"order\":4}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"subject\":\"Vibe\""));
    CHECK(contains(out,"\"predicate\":\"is\""));
    CHECK(contains(out,"\"object\":\"irmão\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    /* Stable persistent collection must answer without any live conversation window. */
    CHECK(call(h,5,plural_query,&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"packet_schema\":\"memoria.cognitive.packet.v1\""));
    CHECK(contains(out,"\"members\":[{\"member_key\":\"surface:lotus\""));
    CHECK(!contains(out,"surface:vibe"));
    CHECK(!contains(out,"\"source_type\":\"assistant_generated\""));
    before_restart_packet = copy_buffer(out);
    CHECK(before_restart_packet != NULL);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    for (i = 0; i < 5; ++i) {
        CHECK(call(h,5,plural_query,&out) == MEMORIA_MOBILE_OK);
        CHECK(same_buffer(out,before_restart_packet));
        memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    }

    /* Growing OFF.IA trajectory windows cannot eclipse the persistent collection HIT. */
    CHECK(call(h,5,window_before_answer,&out) == MEMORIA_MOBILE_OK);
    CHECK(same_buffer(out,before_restart_packet));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call(h,5,window_after_answer,&out) == MEMORIA_MOBILE_OK);
    CHECK(same_buffer(out,before_restart_packet));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,3,"{\"episode_id\":\"e1\",\"role\":\"assistant\",\"text\":\"first creation about routing\",\"timestamp\":\"2026-08-28T10:00:00Z\",\"order\":1,\"event_type\":\"creation\",\"topics_csv\":\"routing\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call(h,3,"{\"episode_id\":\"e2\",\"role\":\"assistant\",\"text\":\"second creation about routing\",\"timestamp\":\"2026-08-28T11:00:00Z\",\"order\":3,\"event_type\":\"creation\",\"topics_csv\":\"routing\"}",&out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h=NULL;

    CHECK(memoria_mobile_open(dir,"org-restart",&h) == MEMORIA_MOBILE_OK);
    CHECK(call(h,2,"{\"query\":\"orion node primary\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"memory_ids\":[\"u1\"]"));
    CHECK(contains(out,"\"source_type\":\"user_assertion\""));
    CHECK(contains(out,"\"ultimate_source_memory_id\":\"u1\""));
    CHECK(contains(out,"\"subject\":\"orion node\""));
    CHECK(contains(out,"\"predicate\":\"is\""));
    CHECK(contains(out,"\"object\":\"primary\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,5,plural_query,&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"packet_schema\":\"memoria.cognitive.packet.v1\""));
    CHECK(contains(out,"\"members\":[{\"member_key\":\"surface:lotus\""));
    CHECK(!contains(out,"surface:vibe"));
    CHECK(!contains(out,"\"source_type\":\"assistant_generated\""));
    after_restart_packet = copy_buffer(out);
    CHECK(after_restart_packet != NULL);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    for (i = 0; i < 5; ++i) {
        CHECK(call(h,5,plural_query,&out) == MEMORIA_MOBILE_OK);
        CHECK(same_buffer(out,after_restart_packet));
        memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    }

    CHECK(strcmp(before_restart_packet,after_restart_packet) == 0);

    CHECK(call(h,5,window_before_answer,&out) == MEMORIA_MOBILE_OK);
    CHECK(same_buffer(out,after_restart_packet));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};
    CHECK(call(h,5,window_after_answer,&out) == MEMORIA_MOBILE_OK);
    CHECK(same_buffer(out,after_restart_packet));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call(h,4,"{\"query\":\"last creation about routing\",\"role\":\"assistant\",\"event_type\":\"creation\",\"topics_csv\":\"routing\"}",&out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out,"\"episode_ids\":[\"e2\"]"));
    CHECK(contains(out,"\"order\":3"));
    CHECK(contains(out,"\"timestamp\":\"2026-08-28T11:00:00Z\""));
    memoria_mobile_free_buffer(out);

    free(before_restart_packet);
    free(after_restart_packet);
    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-restart");
    return 0;
}
