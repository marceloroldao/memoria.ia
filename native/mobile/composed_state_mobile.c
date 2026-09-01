/*
 * Included by evidence_metrics_runtime.c after the post-v1/native core has been
 * composed. This file intentionally relies on private turn/index helpers from
 * that translation unit so the frozen v1 source does not need to be edited.
 */

#include "composed_state_kernel.h"

static void composed_free_properties(char **properties, size_t count) {
    size_t i;
    for (i = 0; i < count; ++i) free(properties[i]);
}

memoria_mobile_status memoria_mobile_resolve_composed_state_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *json = NULL;
    char *entity = NULL;
    char *namespace_id = NULL;
    char *properties[MEMORIA_COMPOSED_STATE_MAX_ITEMS + 1u] = {0};
    const char *property_ptrs[MEMORIA_COMPOSED_STATE_MAX_ITEMS] = {0};
    size_t property_count = 0u;
    size_t i, j, fact_count = 0u, fact_capacity;
    memoria_state_fact *facts = NULL;
    memoria_composed_state_result result;
    external_builder b = {0};
    char *escaped_entity = NULL;
    memoria_mobile_status status = MEMORIA_MOBILE_INTERNAL_ERROR;

    if (!handle || !response_json || !request_json.data || !request_json.size)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;

    json = buffer_to_string(request_json);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    entity = json_string(json, "entity");
    namespace_id = json_string(json, "namespace");
    if (!namespace_id) namespace_id = dup_string("");
    property_count = json_string_array(
        json, "properties", properties, MEMORIA_COMPOSED_STATE_MAX_ITEMS + 1u);
    free(json);
    json = NULL;

    if (!entity || !entity[0] || !namespace_id || property_count == 0u ||
        property_count > MEMORIA_COMPOSED_STATE_MAX_ITEMS) {
        status = MEMORIA_MOBILE_INVALID_ARGUMENT;
        goto done;
    }
    for (i = 0; i < property_count; ++i) {
        if (!properties[i] || !properties[i][0]) {
            status = MEMORIA_MOBILE_INVALID_ARGUMENT;
            goto done;
        }
        property_ptrs[i] = properties[i];
    }

    if (handle->turn_count > ((size_t)-1) / MAX_RELATIONS_PER_TURN) {
        status = MEMORIA_MOBILE_INTERNAL_ERROR;
        goto done;
    }
    fact_capacity = handle->turn_count * MAX_RELATIONS_PER_TURN;
    if (!fact_capacity) {
        status = set_responsef(
            response_json, MEMORIA_MOBILE_UNRESOLVED,
            "{\"status\":\"UNRESOLVED\",\"reason\":\"no promoted state facts\",\"composed_state_used\":true}");
        goto done;
    }
    facts = (memoria_state_fact *)calloc(fact_capacity, sizeof(*facts));
    if (!facts) {
        status = MEMORIA_MOBILE_INTERNAL_ERROR;
        goto done;
    }

    for (i = 0; i < handle->turn_count && fact_count < fact_capacity; ++i) {
        turn_row *turn = &handle->turns[i];
        lineage_root lineage = {0};
        if (!turn_namespace_matches(turn, namespace_id) ||
            !active_lineage_root(handle, turn->memory_id, namespace_id, &lineage))
            continue;
        for (j = 0; j < turn->relation_count && fact_count < fact_capacity; ++j) {
            const memoria_relation *relation = &turn->relations[j];
            if (!relation->subject[0] || !relation->predicate[0] || !relation->object[0]) continue;
            facts[fact_count].memory_id = turn->relation_memory_ids[j][0]
                ? turn->relation_memory_ids[j] : turn->memory_id;
            facts[fact_count].entity = relation->subject;
            facts[fact_count].property = relation->predicate;
            facts[fact_count].value = relation->object;
            facts[fact_count].order = turn->order;
            facts[fact_count].authority = lineage.authority;
            ++fact_count;
        }
    }

    result = memoria_composed_state_resolve(
        entity, property_ptrs, property_count, facts, fact_count);
    if (!result.hit) {
        status = set_responsef(
            response_json, MEMORIA_MOBILE_UNRESOLVED,
            "{\"status\":\"UNRESOLVED\",\"reason\":\"composed state is incomplete or ambiguous\","
            "\"composed_state_used\":true,\"ambiguous\":%s}",
            result.ambiguous ? "true" : "false");
        goto done;
    }

    escaped_entity = json_escape(result.entity);
    if (!escaped_entity || !external_builder_appendf(
            &b,
            "{\"status\":\"HIT\",\"entity\":\"%s\",\"confidence\":%.6f,"
            "\"composed_state_used\":true,\"items\":[",
            escaped_entity, result.confidence)) {
        status = MEMORIA_MOBILE_INTERNAL_ERROR;
        goto done;
    }

    for (i = 0; i < result.item_count; ++i) {
        char *ep = json_escape(result.items[i].property);
        char *ev = json_escape(result.items[i].value);
        char *em = json_escape(result.items[i].memory_id);
        int ok;
        if (!ep || !ev || !em) {
            free(ep); free(ev); free(em);
            status = MEMORIA_MOBILE_INTERNAL_ERROR;
            goto done;
        }
        ok = external_builder_appendf(
            &b,
            "%s{\"property\":\"%s\",\"value\":\"%s\",\"memory_id\":\"%s\","
            "\"order\":%ld,\"source_authority\":%.6f}",
            i ? "," : "", ep, ev, em,
            result.items[i].order, result.items[i].authority);
        free(ep); free(ev); free(em);
        if (!ok) {
            status = MEMORIA_MOBILE_INTERNAL_ERROR;
            goto done;
        }
    }

    if (!external_builder_append(&b, "]}")) {
        status = MEMORIA_MOBILE_INTERNAL_ERROR;
        goto done;
    }
    response_json->data = (const uint8_t *)b.data;
    response_json->size = b.size;
    b.data = NULL;
    status = MEMORIA_MOBILE_OK;

done:
    free(b.data);
    free(escaped_entity);
    free(facts);
    free(entity);
    free(namespace_id);
    composed_free_properties(properties, property_count);
    return status;
}
