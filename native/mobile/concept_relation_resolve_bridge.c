#include "memoria_mobile.h"
#include "concept_relation_runtime.h"
#include "concept_relation_anchor_extractor.h"
#include "concept_runtime_state.h"
#include "semantic_kernel.h"
#include "mobile_persistence.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BRIDGE_MAX_EPISODES 256
#define BRIDGE_MAX_PATHS 2u
#define BRIDGE_MAX_HOPS 4u
#define BRIDGE_MIN_CONFIDENCE 0.80
#define BRIDGE_ANCHOR_CAP 192u

typedef struct bridge_memory_index_slot {
    uint64_t hash;
    size_t turn_index;
    int relation_index;
    unsigned char occupied;
} bridge_memory_index_slot;

struct memoria_mobile_handle {
    char *data_dir;
    char *organization_id;
    memoria_persistence *persistence;
    memoria_concept_runtime *concept_runtime;
    memoria_persist_turn *turns;
    size_t turn_count;
    size_t turn_capacity;
    memoria_semantic_source *semantic_sources;
    size_t semantic_capacity;
    bridge_memory_index_slot *memory_index;
    size_t memory_index_capacity;
    size_t memory_index_count;
    memoria_persist_episode episodes[BRIDGE_MAX_EPISODES];
    size_t episode_count;
    unsigned long sequence;
};

memoria_mobile_status memoria_mobile_resolve_context_json_base(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

static char *bridge_json_string(const char *json, const char *key) {
    char pattern[96];
    const char *p, *q;
    char *out;
    size_t n;
    if (!json || !key) return NULL;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p) return NULL;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return NULL;
    ++p;
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') ++p;
    if (*p != '\"') return NULL;
    ++p;
    q = p;
    while (*q && *q != '\"') {
        if (*q == '\\' && q[1]) q += 2;
        else ++q;
    }
    if (*q != '\"') return NULL;
    n = (size_t)(q - p);
    out = (char *)malloc(n + 1u);
    if (!out) return NULL;
    memcpy(out, p, n);
    out[n] = 0;
    return out;
}

static int bridge_append(char *out, size_t cap, size_t *used, const char *text) {
    size_t n;
    if (!out || !used || !text) return 0;
    n = strlen(text);
    if (*used + n + 1u > cap) return 0;
    memcpy(out + *used, text, n);
    *used += n;
    out[*used] = 0;
    return 1;
}

static int bridge_append_json_string(char *out, size_t cap, size_t *used, const char *text) {
    const unsigned char *p = (const unsigned char *)(text ? text : "");
    char one[3] = {0, 0, 0};
    if (!bridge_append(out, cap, used, "\"")) return 0;
    while (*p) {
        if (*p == '\"' || *p == '\\') {
            one[0] = '\\'; one[1] = (char)*p;
            if (!bridge_append(out, cap, used, one)) return 0;
        } else if (*p == '\n' || *p == '\r' || *p == '\t') {
            one[0] = '\\'; one[1] = *p == '\n' ? 'n' : (*p == '\r' ? 'r' : 't');
            if (!bridge_append(out, cap, used, one)) return 0;
        } else {
            one[0] = (char)*p; one[1] = 0;
            if (!bridge_append(out, cap, used, one)) return 0;
        }
        ++p;
    }
    return bridge_append(out, cap, used, "\"");
}

static int bridge_build_path_context(const memoria_concept_relation_path *path, char *out, size_t cap) {
    size_t i, used = 0;
    if (!path || !out || !cap || path->hops == 0) return 0;
    out[0] = 0;
    if (!bridge_append(out, cap, &used, "INFERRED_RELATION_PATH: ")) return 0;
    if (!bridge_append(out, cap, &used, path->node_keys[0])) return 0;
    for (i = 0; i < path->hops; ++i) {
        if (!bridge_append(out, cap, &used, " --")) return 0;
        if (!bridge_append(out, cap, &used, path->predicates[i])) return 0;
        if (!bridge_append(out, cap, &used, "--> ")) return 0;
        if (!bridge_append(out, cap, &used, path->node_keys[i + 1u])) return 0;
    }
    return 1;
}

static int bridge_build_evidence_json(const memoria_concept_relation_path *path, char *out, size_t cap) {
    size_t i, used = 0;
    if (!path || !out || !cap) return 0;
    out[0] = 0;
    if (!bridge_append(out, cap, &used, "[")) return 0;
    for (i = 0; i < path->hops; ++i) {
        if (i && !bridge_append(out, cap, &used, ",")) return 0;
        if (!bridge_append_json_string(out, cap, &used, path->evidence_ids[i])) return 0;
    }
    return bridge_append(out, cap, &used, "]");
}

static char *bridge_escape(const char *text) {
    size_t i, cap, used = 0;
    char *out;
    const char *src = text ? text : "";
    cap = strlen(src) * 2u + 1u;
    out = (char *)malloc(cap ? cap : 1u);
    if (!out) return NULL;
    out[0] = 0;
    for (i = 0; src[i]; ++i) {
        char one[3] = {0, 0, 0};
        unsigned char c = (unsigned char)src[i];
        if (c == '\"' || c == '\\') { one[0] = '\\'; one[1] = (char)c; }
        else if (c == '\n' || c == '\r' || c == '\t') { one[0] = '\\'; one[1] = c == '\n' ? 'n' : (c == '\r' ? 'r' : 't'); }
        else one[0] = (char)c;
        if (!bridge_append(out, cap, &used, one)) { free(out); return NULL; }
    }
    return out;
}

static memoria_mobile_status bridge_set_hit(memoria_mobile_buffer *out, const memoria_concept_relation_path *path, int anchors_inferred) {
    char context[4096], evidence[2048];
    char *escaped = NULL;
    char *json = NULL;
    int needed;
    if (!out || !path) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (!bridge_build_path_context(path, context, sizeof(context)) || !bridge_build_evidence_json(path, evidence, sizeof(evidence)))
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    escaped = bridge_escape(context);
    if (!escaped) return MEMORIA_MOBILE_INTERNAL_ERROR;
    needed = snprintf(NULL, 0,
        "{\"status\":\"HIT\",\"confidence\":%.6f,\"memory_ids\":%s,"
        "\"selected_context\":\"%s\",\"relations\":[],\"provenance\":[],"
        "\"relation_inference_used\":true,\"relation_anchors_inferred\":%s,"
        "\"inference_hops\":%zu,\"inference_evidence_ids\":%s}",
        path->confidence, evidence, escaped, anchors_inferred ? "true" : "false", path->hops, evidence);
    if (needed < 0) { free(escaped); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    json = (char *)malloc((size_t)needed + 1u);
    if (!json) { free(escaped); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    snprintf(json, (size_t)needed + 1u,
        "{\"status\":\"HIT\",\"confidence\":%.6f,\"memory_ids\":%s,"
        "\"selected_context\":\"%s\",\"relations\":[],\"provenance\":[],"
        "\"relation_inference_used\":true,\"relation_anchors_inferred\":%s,"
        "\"inference_hops\":%zu,\"inference_evidence_ids\":%s}",
        path->confidence, evidence, escaped, anchors_inferred ? "true" : "false", path->hops, evidence);
    free(escaped);
    out->data = (const uint8_t *)json;
    out->size = (size_t)needed;
    return MEMORIA_MOBILE_OK;
}

memoria_mobile_status memoria_mobile_resolve_context_json(memoria_mobile_handle *handle, memoria_mobile_buffer request_json, memoria_mobile_buffer *response_json) {
    memoria_mobile_status base_status;
    char *json = NULL, *source = NULL, *target = NULL, *namespace_id = NULL;
    char *concept_namespace = NULL, *query = NULL;
    char inferred_source[BRIDGE_ANCHOR_CAP], inferred_target[BRIDGE_ANCHOR_CAP];
    const char *effective_source = NULL, *effective_target = NULL;
    int anchors_inferred = 0;
    memoria_concept_relation_path paths[BRIDGE_MAX_PATHS];
    size_t path_count = 0;
    memoria_concept_relation_runtime_status relation_status;

    base_status = memoria_mobile_resolve_context_json_base(handle, request_json, response_json);
    if (base_status != MEMORIA_MOBILE_UNRESOLVED) return base_status;
    if (!handle || !response_json || !request_json.data || !request_json.size) return base_status;

    json = (char *)malloc(request_json.size + 1u);
    if (!json) return base_status;
    memcpy(json, request_json.data, request_json.size);
    json[request_json.size] = 0;
    source = bridge_json_string(json, "relation_source");
    target = bridge_json_string(json, "relation_target");
    concept_namespace = bridge_json_string(json, "concept_namespace");
    namespace_id = bridge_json_string(json, "namespace");
    query = bridge_json_string(json, "query");

    if (!concept_namespace || !concept_namespace[0] || !handle->concept_runtime || !query || !query[0]) goto done;

    if (source && source[0] && target && target[0]) {
        effective_source = source;
        effective_target = target;
    } else if (memoria_relation_anchor_extract(query, inferred_source, sizeof(inferred_source), inferred_target, sizeof(inferred_target)) == MEMORIA_RELATION_ANCHOR_HIT) {
        effective_source = inferred_source;
        effective_target = inferred_target;
        anchors_inferred = 1;
    } else goto done;

    relation_status = memoria_concept_relation_runtime_infer(
        handle->turns, handle->turn_count, namespace_id ? namespace_id : "",
        memoria_concept_runtime_index(handle->concept_runtime), concept_namespace,
        effective_source, effective_target, query,
        BRIDGE_MAX_HOPS, BRIDGE_MAX_PATHS, BRIDGE_MIN_CONFIDENCE,
        paths, BRIDGE_MAX_PATHS, &path_count
    );
    if (relation_status == MEMORIA_CONCEPT_RELATION_RUNTIME_HIT && path_count == 1u) {
        if (response_json->data) memoria_mobile_free_buffer(*response_json);
        response_json->data = NULL;
        response_json->size = 0;
        base_status = bridge_set_hit(response_json, &paths[0], anchors_inferred);
    }

done:
    free(query); free(namespace_id); free(concept_namespace); free(target); free(source); free(json);
    return base_status;
}
