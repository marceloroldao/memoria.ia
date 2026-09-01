#include "external_relevance_mobile.h"

#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static int downstream_calls = 0;

memoria_mobile_status memoria_mobile_learn_external_knowledge_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    static const char ok[] = "{\"status\":\"OK\",\"persisted\":true}";
    uint8_t *data;
    (void)handle;
    (void)request_json;
    ++downstream_calls;
    data = (uint8_t *)malloc(sizeof(ok));
    assert(data != NULL);
    memcpy(data, ok, sizeof(ok));
    response_json->data = data;
    response_json->size = sizeof(ok) - 1u;
    return MEMORIA_MOBILE_OK;
}

static memoria_mobile_buffer b(const char *s) {
    memoria_mobile_buffer out = {(const uint8_t *)s, strlen(s)};
    return out;
}

int main(void) {
    memoria_mobile_handle *fake = (memoria_mobile_handle *)(uintptr_t)1u;
    memoria_mobile_buffer response = {0};
    memoria_mobile_status status;

    status = memoria_mobile_learn_external_knowledge_guarded_json(
        fake,
        b("{\"origin_query\":\"informacoes sobre o pais china\",\"content\":\"Air China anunciou novos voos e resultados financeiros da companhia aerea.\"}"),
        &response);
    assert(status == MEMORIA_MOBILE_UNRESOLVED);
    assert(downstream_calls == 0);
    assert(response.data != NULL);
    assert(strstr((const char *)response.data, "\"persisted\":false") != NULL);
    free((void *)response.data);
    response = (memoria_mobile_buffer){0};

    status = memoria_mobile_learn_external_knowledge_guarded_json(
        fake,
        b("{\"origin_query\":\"informacoes sobre o pais china\",\"content\":\"China e um pais do leste asiatico, com populacao e territorio extensos.\"}"),
        &response);
    assert(status == MEMORIA_MOBILE_OK);
    assert(downstream_calls == 1);
    assert(response.data != NULL);
    assert(strstr((const char *)response.data, "\"persisted\":true") != NULL);
    free((void *)response.data);

    response = (memoria_mobile_buffer){0};
    status = memoria_mobile_learn_external_knowledge_guarded_json(
        fake,
        b("{\"content\":\"China e um pais do leste asiatico.\"}"),
        &response);
    assert(status == MEMORIA_MOBILE_INVALID_ARGUMENT);
    assert(downstream_calls == 1);

    return 0;
}
