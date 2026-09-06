#include "memoria_mobile.h"
#include "concept_identity_kernel.h"
#include "concept_relation_adapter.h"
#include "concept_runtime_state.h"
#include "mobile_persistence.h"
#include "semantic_kernel.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ACTIVATION_MAX_EPISODES 256
#define ACTIVATION_MAX_DEPTH 2u
#define ACTIVATION_MAX_FRONTIER 16u
#define ACTIVATION_MAX_RESULTS 16u
#define ACTIVATION_CONTEXT_CAP 8192u

typedef struct activation_memory_index_slot {
    uint64_t hash;
    size_t turn_index;
    int relation_index;
    unsigned char occupied;
} activation_memory_index_slot;

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
    activation_memory_index_slot *memory_index;
    size_t memory_index_capacity;
    size_t memory_index_count;
    memoria_persist_episode episodes[ACTIVATION_MAX_EPISODES];
    size_t episode_count;
    unsigned long sequence;
};

typedef struct activation_item {
    char node_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    unsigned depth;
} activation_item;

static char *activation_strdup(const char *s) {
    size_t n;
    char *out;
    if (!s) return NULL;
    n = strlen(s);
    out = (char *)malloc(n + 1u);
    if (!out) return NULL;
    memcpy(out, s, n + 1u);
    return out;
}

static char *buffer_to_string_activation(memoria_mobile_buffer input) {
    char *s;
    if (!input.data || input.size == 0) return NULL;
    s = (char *)malloc(input.size + 1u);
    if (!s) return NULL;
    memcpy(s, input.data, input.size);
    s[input.size] = 0;
    return s;
}

static char *json_string_activation(const char *json, const char *key) {
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

static long json_long_activation(const char *json, const char *key, long fallback) {
    char pattern[96];
    const char *p;
    char *end = NULL;
    long value;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p) return fallback;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return fallback;
    value = strtol(p + 1, &end, 10);
    return end == p + 1 ? fallback : value;
}

static double json_double_activation(const char *json, const char *key, double fallback) {
    char pattern[96];
    const char *p;
    char *end = NULL;
    double value;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p) return fallback;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return fallback;
    value = strtod(p + 1, &end);
    return end == p + 1 ? fallback : value;
}

static int resolve_activation_key(const memoria_concept_index *concept_index, const char *concept_namespace, const char *surface, char *out, size_t cap) {
    memoria_concept_resolution resolution;
    char normalized[MEMORIA_CONCEPT_SURFACE_CAP];
    int n;
    if (!concept_index || !surface || !*surface || !out || !cap) return 0;
    resolution = memoria_concept_resolve_with_context(concept_index, concept_namespace ? concept_namespace : "", surface, "");
    if (resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS || resolution.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT) return 0;
    if (resolution.status == MEMORIA_CONCEPT_HIT && resolution.concept_id[0]) {
        n = snprintf(out, cap, "concept:%s", resolution.concept_id);
        return n > 0 && (size_t)n < cap;
    }
    if (memoria_concept_normalize(surface, normalized, sizeof(normalized)) != MEMORIA_CONCEPT_OK || !normalized[0]) return 0;
    n = snprintf(out, cap, "surface:%s", normalized);
    return n > 0 && (size_t)n < cap;
}

static const char *display_key(const char *key) {
    if (!key) return "";
    if (strncmp(key, "surface:", 8u) == 0) return key + 8u;
    if (strncmp(key, "concept:", 8u) == 0) return key + 8u;
    return key;
}

static int append_text(char *out, size_t cap, size_t *used, const char *text) {
    size_t n;
    if (!out || !used || !text) return 0;
    n = strlen(text);
    if (*used + n + 1u > cap) return 0;
    memcpy(out + *used, text, n);
    *used += n;
    out[*used] = 0;
    return 1;
}

static int append_json_string(char *out, size_t cap, size_t *used, const char *text) {
    const unsigned char *p = (const unsigned char *)(text ? text : "");
    char one[3] = {0, 0, 0};
    if (!append_text(out, cap, used, "\"")) return 0;
    while (*p) {
        if (*p == '\"' || *p == '\\') { one[0] = '\\'; one[1] = (char)*p; }
        else if (*p == '\n' || *p == '\r' || *p == '\t') { one[0] = '\\'; one[1] = *p == '\n' ? 'n' : (*p == '\r' ? 'r' : 't'); }
        else { one[0] = (char)*p; one[1] = 0; }
        if (!append_text(out, cap, used, one)) return 0;
        ++p;
    }
    return append_text(out, cap, used, "\"");
}

static int seen_node(const activation_item *items, size_t count, const char *node_key) {
    size_t i;
    for (i = 0; i < count; ++i) if (strcmp(items[i].node_key, node_key) == 0) return 1;
    return 0;
}

static double hop_factor(unsigned hop, double hop_decay) {
    double factor = 1.0;
    unsigned i;
    for (i = 1u; i < hop; ++i) factor *= hop_decay;
    return factor;
}

static memoria_mobile_status set_activation_response(memoria_mobile_buffer *out, const char *status, const char *concept, const char *context, const char *relations_json, size_t relation_count, unsigned max_depth, double confidence) {
    char *json;
    size_t cap, used = 0;
    if (!out || !status || !concept) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    cap = (context ? strlen(context) : 0u) * 2u + (relations_json ? strlen(relations_json) : 0u) + 1024u;
    json = (char *)calloc(cap, 1u);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    if (!append_text(json, cap, &used, "{\"status\":") || !append_json_string(json, cap, &used, status) || !append_text(json, cap, &used, ",\"concept\":") || !append_json_string(json, cap, &used, concept) || !append_text(json, cap, &used, ",\"selected_context\":") || !append_json_string(json, cap, &used, context ? context : "")) {
        free(json); return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    {
        char tail[512];
        snprintf(tail, sizeof(tail), ",\"relations\":%s,\"relation_count\":%zu,\"max_depth\":%u,\"confidence\":%.6f,\"native_structural_activation\":true}", relations_json ? relations_json : "[]", relation_count, max_depth, confidence);
        if (!append_text(json, cap, &used, tail)) { free(json); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    }
    out->data = (const uint8_t *)json;
    out->size = used;
    return strcmp(status, "HIT") == 0 ? MEMORIA_MOBILE_OK : MEMORIA_MOBILE_UNRESOLVED;
}

memoria_mobile_status memoria_mobile_activate_relations_json(memoria_mobile_handle *h, memoria_mobile_buffer request_json, memoria_mobile_buffer *response_json) {
    char *json = NULL, *concept = NULL, *namespace_id = NULL, *concept_namespace = NULL;
    long depth_raw, budget_raw;
    unsigned max_depth;
    size_t budget, max_edges = 0, edge_count = 0, i;
    double hop_decay, min_confidence;
    memoria_concept_relation_edge_storage *storage = NULL;
    unsigned char *selected_edges = NULL;
    activation_item frontier[ACTIVATION_MAX_FRONTIER], visited[ACTIVATION_MAX_FRONTIER];
    size_t frontier_count = 0, frontier_index = 0, visited_count = 0;
    char start_key[MEMORIA_CONCEPT_PATH_KEY_CAP];
    char context[ACTIVATION_CONTEXT_CAP], relations[ACTIVATION_CONTEXT_CAP];
    size_t context_used = 0, relations_used = 0, result_count = 0;
    double result_confidence = 1.0;
    memoria_mobile_status status = MEMORIA_MOBILE_INVALID_ARGUMENT;

    if (!h || !h->concept_runtime || !response_json || !request_json.data || !request_json.size) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    response_json->data = NULL; response_json->size = 0;
    json = buffer_to_string_activation(request_json);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    concept = json_string_activation(json, "concept");
    namespace_id = json_string_activation(json, "namespace");
    concept_namespace = json_string_activation(json, "concept_namespace");
    if (!namespace_id) namespace_id = activation_strdup("");
    if (!concept_namespace) concept_namespace = activation_strdup("");
    depth_raw = json_long_activation(json, "depth", 2);
    budget_raw = json_long_activation(json, "budget", 1200);
    hop_decay = json_double_activation(json, "hop_decay", 0.72);
    min_confidence = json_double_activation(json, "min_confidence", 0.45);
    if (!concept || !*concept || !namespace_id || !concept_namespace || depth_raw < 1 || depth_raw > (long)ACTIVATION_MAX_DEPTH || budget_raw < 1 || budget_raw > (long)(ACTIVATION_CONTEXT_CAP - 1u) || hop_decay <= 0.0 || hop_decay > 1.0 || min_confidence < 0.0 || min_confidence > 1.0) goto done;
    max_depth = (unsigned)depth_raw;
    budget = (size_t)budget_raw;
    if (!resolve_activation_key(memoria_concept_runtime_index(h->concept_runtime), concept_namespace, concept, start_key, sizeof(start_key))) {
        status = set_activation_response(response_json, "UNRESOLVED", concept, "", "[]", 0u, max_depth, 0.0); goto done;
    }
    for (i = 0; i < h->turn_count; ++i) max_edges += h->turns[i].relation_count;
    if (!max_edges) { status = set_activation_response(response_json, "UNRESOLVED", concept, "", "[]", 0u, max_depth, 0.0); goto done; }
    storage = (memoria_concept_relation_edge_storage *)calloc(max_edges, sizeof(*storage));
    selected_edges = (unsigned char *)calloc(max_edges, sizeof(*selected_edges));
    if (!storage || !selected_edges) { status = MEMORIA_MOBILE_INTERNAL_ERROR; goto done; }
    if (memoria_concept_relation_build_edges(h->turns, h->turn_count, namespace_id, memoria_concept_runtime_index(h->concept_runtime), concept_namespace, storage, max_edges, &edge_count) != MEMORIA_CONCEPT_RELATION_ADAPTER_OK) {
        status = set_activation_response(response_json, "UNRESOLVED", concept, "", "[]", 0u, max_depth, 0.0); goto done;
    }

    snprintf(frontier[0].node_key, sizeof(frontier[0].node_key), "%s", start_key);
    frontier[0].depth = 0u; frontier_count = 1u; visited[0] = frontier[0]; visited_count = 1u;
    context[0] = 0; relations[0] = 0;
    if (!append_text(relations, sizeof(relations), &relations_used, "[")) { status = MEMORIA_MOBILE_INTERNAL_ERROR; goto done; }

    while (frontier_index < frontier_count) {
        activation_item current = frontier[frontier_index++];
        unsigned hop = current.depth + 1u;
        if (current.depth >= max_depth) continue;
        for (i = 0; i < edge_count; ++i) {
            const memoria_concept_relation_edge *edge = &storage[i].edge;
            const char *next_key = NULL;
            double effective;
            char line[1024], relation_json[2048];
            size_t line_len, extra;
            if (edge->ambiguous || selected_edges[i]) continue;
            if (strcmp(edge->subject_key, current.node_key) == 0) next_key = edge->object_key;
            else if (strcmp(edge->object_key, current.node_key) == 0) next_key = edge->subject_key;
            else continue;
            effective = edge->confidence * hop_factor(hop, hop_decay);
            if (effective < min_confidence || !next_key || !*next_key) continue;
            snprintf(line, sizeof(line), "%s | %s | %s", display_key(edge->subject_key), edge->predicate ? edge->predicate : "", display_key(edge->object_key));
            line_len = strlen(line);
            extra = line_len + (result_count ? 1u : 0u);
            if (context_used + extra > budget) continue;
            if (result_count && !append_text(context, budget + 1u, &context_used, "\n")) continue;
            if (!append_text(context, budget + 1u, &context_used, line)) continue;
            snprintf(relation_json, sizeof(relation_json), "%s{\"subject_key\":\"%s\",\"predicate\":\"%s\",\"object_key\":\"%s\",\"evidence_id\":\"%s\",\"hop\":%u,\"confidence\":%.6f}", result_count ? "," : "", edge->subject_key, edge->predicate ? edge->predicate : "", edge->object_key, edge->evidence_id ? edge->evidence_id : "", hop, effective);
            if (!append_text(relations, sizeof(relations), &relations_used, relation_json)) { status = MEMORIA_MOBILE_INTERNAL_ERROR; goto done; }
            selected_edges[i] = 1u;
            ++result_count;
            if (effective < result_confidence) result_confidence = effective;
            if (hop < max_depth && frontier_count < ACTIVATION_MAX_FRONTIER && !seen_node(visited, visited_count, next_key)) {
                snprintf(frontier[frontier_count].node_key, sizeof(frontier[frontier_count].node_key), "%s", next_key);
                frontier[frontier_count].depth = hop;
                visited[visited_count] = frontier[frontier_count];
                ++visited_count; ++frontier_count;
            }
            if (result_count >= ACTIVATION_MAX_RESULTS) goto traversal_done;
        }
    }

traversal_done:
    if (!append_text(relations, sizeof(relations), &relations_used, "]")) { status = MEMORIA_MOBILE_INTERNAL_ERROR; goto done; }
    status = set_activation_response(response_json, result_count ? "HIT" : "UNRESOLVED", concept, context, relations, result_count, max_depth, result_count ? result_confidence : 0.0);

done:
    free(selected_edges); free(storage); free(concept); free(namespace_id); free(concept_namespace); free(json);
    return status;
}
