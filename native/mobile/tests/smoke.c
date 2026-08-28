#include "memoria_mobile.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_mobile_handle *handle = NULL;
    memoria_mobile_buffer request;
    memoria_mobile_buffer response = {0};
    const char payload[] = "{\"message\":\"probe\"}";

    assert(memoria_mobile_abi_version() == MEMORIA_MOBILE_ABI_VERSION);
    assert(memoria_mobile_open("./tmp-mobile", "org-test", &handle) == MEMORIA_MOBILE_OK);
    assert(handle != NULL);

    request.data = (const uint8_t *)payload;
    request.size = strlen(payload);
    assert(memoria_mobile_resolve_context_json(handle, request, &response) == MEMORIA_MOBILE_UNRESOLVED);
    assert(response.data != NULL);
    assert(response.size > 0);
    memoria_mobile_free_buffer(response);

    assert(memoria_mobile_flush(handle) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(handle);
    return 0;
}
