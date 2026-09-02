#include "resolutive_inference_kernel.h"

#include <stdlib.h>
#include <string.h>

static int inference_turn_eligible(const turn_row *turn, const char *namespace_id) {
    if (!turn || turn->superseded || !turn_namespace_matches(turn, namespace_id)) return 0;
    if (!turn->memory_id || !turn->source_type || turn->relation_count == 0u) return 0;
    if (strcmp(turn->source_type, "assistant_generated") == 0) return 0;
    if (turn->authority < 0.50) return 0;
    return 1;
}

static memoria_mobile_status inference_result_json(
    const memoria_inference_result_t *result,
    memoria_mobile_buffer *response_json
) {
    char *answer = NULL, *via = NULL, *m1 = NULL, *m2 = NULL;
    memoria_mobile_status status;
    if (!result || !response_json) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (result->status == MEMORIA_INFERENCE_UNRESOLVED)
        return unresolved(response_json, "no conservative 2-hop path");
    if (result->status == MEMORIA_INFERENCE_CONFLICT)
        return set_response(response_json,
            "{\"status\":\"CONFLICT\",\"inference\":\"two_hop_same_predicate\",\"proof\":[]}",
            MEMORIA_MOBILE_UNRESOLVED);

    answer = json_escape(result->answer);
    via = json_escape(result->via);
    m1 = json_escape(result->evidence_memory_id_1);
    m2 = json_escape(result->evidence_memory_id_2);
    if (!answer || !via || !m1 || !m2) {
        free(answer); free(via); free(m1); free(m2);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    status = set_responsef(response_json, MEMORIA_MOBILE_OK,
        "{\"status\":\"OK\",\"resolution\":\"INFERRED\","
        "\"inference\":\"two_hop_same_predicate\",\"answer\":\"%s\","
        "\"via\":\"%s\",\"path_confidence\":%.17g,"
        "\"proof\":[\"%s\",\"%s\"]}",
        answer, via, result->path_confidence, m1, m2);
    free(answer); free(via); free(m1); free(m2);
    return status;
}

memoria_mobile_status memoria_mobile_infer_two_hop_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *json = NULL, *subject = NULL, *predicate = NULL, *namespace_id = NULL;
    memoria_inference_edge_t *edges = NULL;
    size_t i, j, edge_count = 0u, edge_capacity = 0u;
    memoria_inference_result_t result;
    memoria_mobile_status status = MEMORIA_MOBILE_INTERNAL_ERROR;

    if (!handle || !response_json || !request_json.data || !request_json.size)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = buffer_to_string(request_json);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    subject = json_string(json, "subject");
    predicate = json_string(json, "predicate");
    namespace_id = json_string(json, "namespace");
    free(json);
    if (!namespace_id) namespace_id = dup_string("");
    if (!subject || !predicate || !namespace_id || !subject[0] || !predicate[0]) {
        status = MEMORIA_MOBILE_INVALID_ARGUMENT;
        goto done;
    }

    for (i = 0; i < handle->turn_count; ++i)
        if (inference_turn_eligible(&handle->turns[i], namespace_id))
            edge_capacity += handle->turns[i].relation_count;
    if (!edge_capacity) {
        status = unresolved(response_json, "no eligible persisted relations");
        goto done;
    }
    edges = (memoria_inference_edge_t *)calloc(edge_capacity, sizeof(*edges));
    if (!edges) goto done;

    for (i = 0; i < handle->turn_count; ++i) {
        turn_row *turn = &handle->turns[i];
        if (!inference_turn_eligible(turn, namespace_id)) continue;
        for (j = 0; j < turn->relation_count; ++j) {
            memoria_relation *relation = &turn->relations[j];
            edges[edge_count].subject = relation->subject;
            edges[edge_count].predicate = relation->predicate;
            edges[edge_count].object = relation->object;
            edges[edge_count].memory_id = turn->relation_memory_ids[j][0]
                ? turn->relation_memory_ids[j] : turn->memory_id;
            edges[edge_count].authority = turn->authority;
            edges[edge_count].semantic_confidence = relation->confidence;
            edges[edge_count].active = 1;
            ++edge_count;
        }
    }

    if (memoria_infer_two_hop_same_predicate(edges, edge_count, subject, predicate, &result) != 0)
        goto done;
    status = inference_result_json(&result, response_json);

done:
    free(edges); free(subject); free(predicate); free(namespace_id);
    return status;
}
