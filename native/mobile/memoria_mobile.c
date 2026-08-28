#include "memoria_mobile.h"

#include <stdlib.h>
#include <string.h>

struct memoria_mobile_handle {
    char *data_dir;
    char *organization_id;
};

static char *dup_string(const char *value) {
    size_t size;
    char *copy;
    if (value == NULL) return NULL;
    size = strlen(value) + 1;
    copy = (char *)malloc(size);
    if (copy != NULL) memcpy(copy, value, size);
    return copy;
}

static memoria_mobile_status unresolved_not_ready(memoria_mobile_buffer *response_json) {
    static const char json[] = "{\"status\":\"UNRESOLVED\",\"reason\":\"native semantic backend not installed\"}";
    uint8_t *data;
    if (response_json == NULL) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    data = (uint8_t *)malloc(sizeof(json) - 1);
    if (data == NULL) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(data, json, sizeof(json) - 1);
    response_json->data = data;
    response_json->size = sizeof(json) - 1;
    return MEMORIA_MOBILE_UNRESOLVED;
}

uint32_t memoria_mobile_abi_version(void) {
    return MEMORIA_MOBILE_ABI_VERSION;
}

memoria_mobile_status memoria_mobile_open(
    const char *data_dir,
    const char *organization_id,
    memoria_mobile_handle **out_handle
) {
    memoria_mobile_handle *handle;
    if (data_dir == NULL || organization_id == NULL || out_handle == NULL || data_dir[0] == '\0' || organization_id[0] == '\0') {
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    handle = (memoria_mobile_handle *)calloc(1, sizeof(*handle));
    if (handle == NULL) return MEMORIA_MOBILE_INTERNAL_ERROR;
    handle->data_dir = dup_string(data_dir);
    handle->organization_id = dup_string(organization_id);
    if (handle->data_dir == NULL || handle->organization_id == NULL) {
        memoria_mobile_close(handle);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    *out_handle = handle;
    return MEMORIA_MOBILE_OK;
}

memoria_mobile_status memoria_mobile_learn_turn_json(memoria_mobile_handle *handle, memoria_mobile_buffer request_json, memoria_mobile_buffer *response_json) {
    if (handle == NULL || request_json.data == NULL || request_json.size == 0) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    return unresolved_not_ready(response_json);
}

memoria_mobile_status memoria_mobile_resolve_context_json(memoria_mobile_handle *handle, memoria_mobile_buffer request_json, memoria_mobile_buffer *response_json) {
    if (handle == NULL || request_json.data == NULL || request_json.size == 0) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    return unresolved_not_ready(response_json);
}

memoria_mobile_status memoria_mobile_store_episode_json(memoria_mobile_handle *handle, memoria_mobile_buffer request_json, memoria_mobile_buffer *response_json) {
    if (handle == NULL || request_json.data == NULL || request_json.size == 0) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    return unresolved_not_ready(response_json);
}

memoria_mobile_status memoria_mobile_recall_episode_json(memoria_mobile_handle *handle, memoria_mobile_buffer request_json, memoria_mobile_buffer *response_json) {
    if (handle == NULL || request_json.data == NULL || request_json.size == 0) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    return unresolved_not_ready(response_json);
}

memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *handle) {
    if (handle == NULL) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    return MEMORIA_MOBILE_OK;
}

void memoria_mobile_free_buffer(memoria_mobile_buffer buffer) {
    free((void *)buffer.data);
}

void memoria_mobile_close(memoria_mobile_handle *handle) {
    if (handle == NULL) return;
    free(handle->data_dir);
    free(handle->organization_id);
    free(handle);
}
