#include <stdlib.h>
#include <string.h>

static int resolution_mode_contains(memoria_mobile_buffer buffer, const char *needle) {
    return buffer.data && needle && strstr((const char *)buffer.data, needle) != NULL;
}

memoria_mobile_status memoria_mobile_resolve_mode_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *json = NULL;
    char *query = NULL;
    char *subject = NULL;
    char *predicate = NULL;
    char *namespace_id = NULL;
    memoria_mobile_buffer direct_request = {0};
    memoria_mobile_buffer direct_response = {0};
    memoria_mobile_buffer inference_response = {0};
    memoria_mobile_status direct_status;
    memoria_mobile_status inference_status;
    memoria_mobile_status status = MEMORIA_MOBILE_INTERNAL_ERROR;
    char *query_e = NULL;
    char *namespace_e = NULL;
    char *direct_json = NULL;
    size_t direct_json_size = 0u;

    if (!handle || !response_json || !request_json.data || !request_json.size)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    json = buffer_to_string(request_json);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    query = json_string(json, "query");
    subject = json_string(json, "subject");
    predicate = json_string(json, "predicate");
    namespace_id = json_string(json, "namespace");
    if (!namespace_id) namespace_id = dup_string("");
    if (!query || !query[0] || !namespace_id) {
        status = MEMORIA_MOBILE_INVALID_ARGUMENT;
        goto done;
    }

    query_e = json_escape(query);
    namespace_e = json_escape(namespace_id);
    if (!query_e || !namespace_e) goto done;
    direct_json_size = strlen(query_e) + strlen(namespace_e) + 64u;
    direct_json = (char *)malloc(direct_json_size);
    if (!direct_json) goto done;
    snprintf(direct_json, direct_json_size,
             "{\"query\":\"%s\",\"namespace\":\"%s\"}", query_e, namespace_e);
    direct_request.data = (const uint8_t *)direct_json;
    direct_request.size = strlen(direct_json);

    direct_status = memoria_mobile_resolve_context_json(handle, direct_request, &direct_response);
    if (direct_status == MEMORIA_MOBILE_OK) {
        status = set_responsef(response_json, MEMORIA_MOBILE_OK,
            "{\"status\":\"OK\",\"resolution\":\"DIRECT\",\"direct\":%s}",
            direct_response.data ? (const char *)direct_response.data : "{}");
        goto done;
    }
    if (direct_status != MEMORIA_MOBILE_UNRESOLVED) {
        status = direct_status;
        goto done;
    }

    if (!subject || !subject[0] || !predicate || !predicate[0]) {
        status = set_response(response_json,
            "{\"status\":\"UNRESOLVED\",\"resolution\":\"UNRESOLVED\",\"reason\":\"direct retrieval unresolved and no explicit inference path requested\"}",
            MEMORIA_MOBILE_UNRESOLVED);
        goto done;
    }

    inference_status = memoria_mobile_infer_two_hop_json(handle, request_json, &inference_response);
    if (inference_status == MEMORIA_MOBILE_OK) {
        status = set_response(response_json,
            inference_response.data ? (const char *)inference_response.data : "{\"status\":\"UNRESOLVED\",\"resolution\":\"UNRESOLVED\"}",
            MEMORIA_MOBILE_OK);
        goto done;
    }
    if (inference_status == MEMORIA_MOBILE_UNRESOLVED &&
        resolution_mode_contains(inference_response, "\"status\":\"CONFLICT\"")) {
        status = set_response(response_json,
            "{\"status\":\"CONFLICT\",\"resolution\":\"CONFLICT\",\"reason\":\"contradictory inference paths\"}",
            MEMORIA_MOBILE_UNRESOLVED);
        goto done;
    }
    if (inference_status == MEMORIA_MOBILE_UNRESOLVED) {
        status = set_response(response_json,
            "{\"status\":\"UNRESOLVED\",\"resolution\":\"UNRESOLVED\",\"reason\":\"no direct memory or conservative inference path\"}",
            MEMORIA_MOBILE_UNRESOLVED);
        goto done;
    }
    status = inference_status;

done:
    memoria_mobile_free_buffer(direct_response);
    memoria_mobile_free_buffer(inference_response);
    free(direct_json);
    free(query_e);
    free(namespace_e);
    free(query);
    free(subject);
    free(predicate);
    free(namespace_id);
    free(json);
    return status;
}
