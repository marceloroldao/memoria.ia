#include "memoria_mobile.h"
#include "semantic_kernel.h"
#include "trajectory_json_adapter.h"
#include "episodic_kernel.h"
#include "relation_extractor.h"
#include "relation_adapter.h"
#include "mobile_persistence.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_TURNS 256
#define MAX_EPISODES 256
#define MAX_RELATIONS_PER_TURN MEMORIA_PERSIST_MAX_RELATIONS

typedef memoria_persist_turn turn_row;
typedef memoria_persist_episode episode_row;

struct memoria_mobile_handle {
    char *data_dir;
    char *organization_id;
    memoria_persistence *persistence;
    turn_row turns[MAX_TURNS];
    size_t turn_count;
    episode_row episodes[MAX_EPISODES];
    size_t episode_count;
    unsigned long sequence;
};

static char *dup_string(const char *value) {
    size_t size;
    char *copy;
    if (!value) return NULL;
    size = strlen(value) + 1;
    copy = (char *)malloc(size);
    if (copy) memcpy(copy, value, size);
    return copy;
}

static char *buffer_to_string(memoria_mobile_buffer input) {
    char *s;
    if (!input.data || input.size == 0) return NULL;
    s = (char *)malloc(input.size + 1);
    if (!s) return NULL;
    memcpy(s, input.data, input.size);
    s[input.size] = 0;
    return s;
}

static char *json_string(const char *json, const char *key) {
    char pattern[96];
    const char *p, *q;
    char *out;
    size_t n;
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
    out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, p, n);
    out[n] = 0;
    return out;
}

static long json_long(const char *json, const char *key, long fallback) {
    char pattern[96];
    const char *p;
    char *end = NULL;
    long v;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p) return fallback;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return fallback;
    v = strtol(p + 1, &end, 10);
    return end == p + 1 ? fallback : v;
}

static double json_double(const char *json, const char *key, double fallback) {
    char pattern[96];
    const char *p;
    char *end = NULL;
    double v;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p) return fallback;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return fallback;
    v = strtod(p + 1, &end);
    return end == p + 1 ? fallback : v;
}

static char *json_escape(const char *s) {
    size_t i, n = 0;
    char *out, *p;
    if (!s) return dup_string("");
    for (i = 0; s[i]; ++i)
        n += (s[i] == '\"' || s[i] == '\\' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t') ? 2 : 1;
    out = (char *)malloc(n + 1);
    if (!out) return NULL;
    p = out;
    for (i = 0; s[i]; ++i) {
        switch (s[i]) {
            case '\"': *p++ = '\\'; *p++ = '\"'; break;
            case '\\': *p++ = '\\'; *p++ = '\\'; break;
            case '\n': *p++ = '\\'; *p++ = 'n'; break;
            case '\r': *p++ = '\\'; *p++ = 'r'; break;
            case '\t': *p++ = '\\'; *p++ = 't'; break;
            default: *p++ = s[i];
        }
    }
    *p = 0;
    return out;
}

static memoria_mobile_status set_response(memoria_mobile_buffer *out, const char *json, memoria_mobile_status status) {
    size_t n;
    uint8_t *data;
    if (!out || !json) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    n = strlen(json);
    data = (uint8_t *)malloc(n + 1);
    if (!data) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(data, json, n + 1);
    out->data = data;
    out->size = n;
    return status;
}

static memoria_mobile_status set_responsef(memoria_mobile_buffer *out, memoria_mobile_status status, const char *fmt, ...) {
    va_list args;
    va_list measure;
    int needed;
    int written;
    uint8_t *data;
    if (!out || !fmt) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    va_start(args, fmt);
    va_copy(measure, args);
    needed = vsnprintf(NULL, 0, fmt, measure);
    va_end(measure);
    if (needed < 0) {
        va_end(args);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    data = (uint8_t *)malloc((size_t)needed + 1u);
    if (!data) {
        va_end(args);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    written = vsnprintf((char *)data, (size_t)needed + 1u, fmt, args);
    va_end(args);
    if (written != needed) {
        free(data);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    out->data = data;
    out->size = (size_t)needed;
    return status;
}

static memoria_mobile_status unresolved(memoria_mobile_buffer *out, const char *reason) {
    char *e = json_escape(reason);
    char buf[512];
    if (!e) return MEMORIA_MOBILE_INTERNAL_ERROR;
    snprintf(buf, sizeof(buf), "{\"status\":\"UNRESOLVED\",\"reason\":\"%s\"}", e);
    free(e);
    return set_response(out, buf, MEMORIA_MOBILE_UNRESOLVED);
}

static void free_turn(turn_row *r) { memoria_persistence_free_turn(r); }
static void free_episode(episode_row *r) { memoria_persistence_free_episode(r); }

uint32_t memoria_mobile_abi_version(void) { return MEMORIA_MOBILE_ABI_VERSION; }

memoria_mobile_status memoria_mobile_open(const char *data_dir, const char *organization_id, memoria_mobile_handle **out_handle) {
    memoria_mobile_handle *h;
    size_t turns = 0, episodes = 0, i;
    unsigned long sequence = 0;
    if (!data_dir || !organization_id || !out_handle || !*data_dir || !*organization_id)
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    *out_handle = NULL;
    h = (memoria_mobile_handle *)calloc(1, sizeof(*h));
    if (!h) return MEMORIA_MOBILE_INTERNAL_ERROR;
    h->data_dir = dup_string(data_dir);
    h->organization_id = dup_string(organization_id);
    if (!h->data_dir || !h->organization_id ||
        !memoria_persistence_open(data_dir, organization_id, &h->persistence) ||
        !memoria_persistence_meta(h->persistence, &turns, &episodes, &sequence) ||
        turns > MAX_TURNS || episodes > MAX_EPISODES) {
        memoria_mobile_close(h);
        return MEMORIA_MOBILE_PERSISTENCE_ERROR;
    }
    for (i = 0; i < turns; ++i) {
        if (!memoria_persistence_load_turn(h->persistence, i + 1, &h->turns[i])) {
            memoria_mobile_close(h);
            return MEMORIA_MOBILE_PERSISTENCE_ERROR;
        }
    }
    h->turn_count = turns;
    for (i = 0; i < episodes; ++i) {
        if (!memoria_persistence_load_episode(h->persistence, i + 1, &h->episodes[i])) {
            memoria_mobile_close(h);
            return MEMORIA_MOBILE_PERSISTENCE_ERROR;
        }
    }
    h->episode_count = episodes;
    h->sequence = sequence;
    *out_handle = h;
    return MEMORIA_MOBILE_OK;
}

memoria_mobile_status memoria_mobile_learn_turn_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {
    char *json, *text, *role, *id, *source_type, *root;
    char idbuf[64], relations_json[1536];
    turn_row candidate;
    long order;
    double authority;
    unsigned long next_sequence;
    memoria_mobile_status response_status;
    if (!h || !req.data || !req.size || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (h->turn_count >= MAX_TURNS) return unresolved(out, "native turn capacity reached");
    memset(&candidate, 0, sizeof(candidate));
    json = buffer_to_string(req);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    text = json_string(json, "text");
    role = json_string(json, "role");
    id = json_string(json, "memory_id");
    source_type = json_string(json, "source_type");
    root = json_string(json, "ultimate_source_memory_id");
    order = json_long(json, "order", (long)h->turn_count + 1);
    authority = json_double(json, "source_authority", -1.0);
    if (!text || !role) {
        free(json); free(text); free(role); free(id); free(source_type); free(root);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    next_sequence = h->sequence;
    if (!id) {
        ++next_sequence;
        snprintf(idbuf, sizeof(idbuf), "mobile:%lu", next_sequence);
        id = dup_string(idbuf);
    }
    if (!source_type) source_type = dup_string(strcmp(role, "user") == 0 ? "user_assertion" : "assistant_generated");
    if (authority < 0.0) authority = strcmp(source_type, "user_assertion") == 0 ? 1.0 : 0.35;
    if (!root) root = dup_string(id);
    if (!id || !source_type || !root) {
        free(json); free(text); free(role); free(id); free(source_type); free(root);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    candidate.memory_id = id;
    candidate.text = text;
    candidate.role = role;
    candidate.source_type = source_type;
    candidate.ultimate_source_memory_id = root;
    candidate.authority = authority;
    candidate.order = order;
    candidate.relation_count = memoria_extract_relations(text, candidate.relations, MAX_RELATIONS_PER_TURN);
    if (!memoria_relations_to_json(candidate.relations, candidate.relation_count, id, relations_json, sizeof(relations_json))) {
        free(json); free_turn(&candidate); return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    if (!memoria_persistence_save_turn(h->persistence, h->turn_count + 1, next_sequence, &candidate)) {
        free(json); free_turn(&candidate); return MEMORIA_MOBILE_PERSISTENCE_ERROR;
    }
    h->turns[h->turn_count++] = candidate;
    h->sequence = next_sequence;
    response_status = set_responsef(out, MEMORIA_MOBILE_OK,
             "{\"status\":\"OK\",\"stored_memory_ids\":[\"%s\"],\"relations\":%s,\"unresolved\":%s,\"native_relation_extraction\":true,\"durable\":true}",
             id, relations_json, candidate.relation_count ? "false" : "true");
    free(json);
    return response_status;
}

memoria_mobile_status memoria_mobile_resolve_context_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {
    char *json, *query, *ctx, *st, *root;
    char relations_json[1536];
    memoria_semantic_source sources[MAX_TURNS];
    memoria_semantic_result r;
    memoria_trajectory_result tr;
    size_t i, window_count = 0;
    int trajectory_mode;
    memoria_mobile_status response_status;
    if (!h || !req.data || !req.size || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = buffer_to_string(req);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    query = json_string(json, "query");
    if (!query) { free(json); return MEMORIA_MOBILE_INVALID_ARGUMENT; }
    for (i = 0; i < h->turn_count; ++i) {
        sources[i].memory_id = h->turns[i].memory_id;
        sources[i].text = h->turns[i].text;
        sources[i].authority = h->turns[i].authority;
        sources[i].order = h->turns[i].order;
        sources[i].source_type = h->turns[i].source_type;
        sources[i].ultimate_source_memory_id = h->turns[i].ultimate_source_memory_id;
    }
    trajectory_mode = memoria_trajectory_resolve_json(json, query, sources, h->turn_count, &tr, &window_count);
    if (trajectory_mode < 0) {
        free(query); free(json);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    if (trajectory_mode == 1) {
        if (!tr.hit) {
            free(query); free(json);
            return unresolved(out, "no justified active trajectory source");
        }
        for (i = 0; i < h->turn_count && strcmp(h->turns[i].memory_id, tr.memory_id) != 0; ++i) {}
        if (i == h->turn_count) {
            free(query); free(json);
            return unresolved(out, "selected trajectory source missing from native state");
        }
        r.hit = 1;
        r.memory_id = h->turns[i].memory_id;
        r.confidence = tr.confidence;
        r.source_type = h->turns[i].source_type;
        r.source_authority = h->turns[i].authority;
        r.ultimate_source_memory_id = h->turns[i].ultimate_source_memory_id;
    } else {
        r = memoria_semantic_resolve_sources(query, sources, h->turn_count);
    }
    free(query); free(json);
    if (!r.hit) return unresolved(out, "no justified native semantic source");
    for (i = 0; i < h->turn_count && strcmp(h->turns[i].memory_id, r.memory_id) != 0; ++i) {}
    if (i == h->turn_count) return unresolved(out, "selected source missing from native state");
    if (!memoria_relations_to_json(h->turns[i].relations, h->turns[i].relation_count,
                                   h->turns[i].memory_id, relations_json, sizeof(relations_json)))
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    ctx = json_escape(h->turns[i].text);
    st = json_escape(r.source_type ? r.source_type : "");
    root = json_escape(r.ultimate_source_memory_id ? r.ultimate_source_memory_id : "");
    if (!ctx || !st || !root) { free(ctx); free(st); free(root); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    response_status = set_responsef(out, MEMORIA_MOBILE_OK,
             "{\"status\":\"HIT\",\"confidence\":%.6f,\"memory_ids\":[\"%s\"],\"selected_context\":\"%s\",\"relations\":%s,\"trajectory_used\":%s,\"conversation_window_count\":%lu,\"provenance\":[{\"memory_id\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"}]}",
             r.confidence, r.memory_id, ctx, relations_json,
             trajectory_mode == 1 && tr.used_window ? "true" : "false",
             (unsigned long)(trajectory_mode == 1 ? window_count : 0),
             r.memory_id, st, r.source_authority, root);
    free(ctx); free(st); free(root);
    return response_status;
}

memoria_mobile_status memoria_mobile_store_episode_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {
    char *json, *id, *role, *text, *timestamp, *event_type, *topics, *source_type, *root;
    char idbuf[64];
    episode_row candidate;
    long order;
    double authority;
    unsigned long next_sequence;
    memoria_mobile_status response_status;
    if (!h || !req.data || !req.size || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (h->episode_count >= MAX_EPISODES) return unresolved(out, "native episode capacity reached");
    memset(&candidate, 0, sizeof(candidate));
    json = buffer_to_string(req);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    id = json_string(json, "episode_id");
    role = json_string(json, "role");
    text = json_string(json, "text");
    timestamp = json_string(json, "timestamp");
    event_type = json_string(json, "event_type");
    topics = json_string(json, "topics_csv");
    source_type = json_string(json, "source_type");
    root = json_string(json, "ultimate_source_memory_id");
    order = json_long(json, "order", (long)h->episode_count + 1);
    authority = json_double(json, "source_authority", -1.0);
    if (!role || !text) {
        free(json); free(id); free(role); free(text); free(timestamp); free(event_type); free(topics); free(source_type); free(root);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    next_sequence = h->sequence;
    if (!id) {
        ++next_sequence;
        snprintf(idbuf, sizeof(idbuf), "episode:%lu", next_sequence);
        id = dup_string(idbuf);
    }
    if (!source_type) source_type = dup_string(strcmp(role, "user") == 0 ? "user_assertion" : "assistant_generated");
    if (authority < 0.0) authority = strcmp(source_type, "user_assertion") == 0 ? 1.0 : 0.35;
    if (!root) root = dup_string(id);
    if (!timestamp) timestamp = dup_string("");
    if (!event_type) event_type = dup_string("");
    if (!topics) topics = dup_string("");
    if (!id || !source_type || !root || !timestamp || !event_type || !topics) {
        free(json); free(id); free(role); free(text); free(timestamp); free(event_type); free(topics); free(source_type); free(root);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    candidate.episode_id = id;
    candidate.role = role;
    candidate.text = text;
    candidate.timestamp = timestamp;
    candidate.event_type = event_type;
    candidate.topics_csv = topics;
    candidate.source_type = source_type;
    candidate.ultimate_source_memory_id = root;
    candidate.authority = authority;
    candidate.order = order;
    candidate.superseded = 0;
    if (!memoria_persistence_save_episode(h->persistence, h->episode_count + 1, next_sequence, &candidate)) {
        free(json); free_episode(&candidate); return MEMORIA_MOBILE_PERSISTENCE_ERROR;
    }
    h->episodes[h->episode_count++] = candidate;
    h->sequence = next_sequence;
    response_status = set_responsef(out, MEMORIA_MOBILE_OK,
        "{\"status\":\"OK\",\"episode_id\":\"%s\",\"durable\":true}", id);
    free(json);
    return response_status;
}

memoria_mobile_status memoria_mobile_recall_episode_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {
    char *json, *query, *role, *event_type, *topics, *ctx, *st, *root;
    memoria_episode_source eps[MAX_EPISODES];
    memoria_episode_result r;
    size_t i;
    memoria_mobile_status response_status;
    if (!h || !req.data || !req.size || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = buffer_to_string(req);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    query = json_string(json, "query");
    role = json_string(json, "role");
    event_type = json_string(json, "event_type");
    topics = json_string(json, "topics_csv");
    if (!query) { free(json); free(role); free(event_type); free(topics); return MEMORIA_MOBILE_INVALID_ARGUMENT; }
    for (i = 0; i < h->episode_count; ++i) {
        episode_row *e = &h->episodes[i];
        eps[i].episode_id = e->episode_id;
        eps[i].role = e->role;
        eps[i].text = e->text;
        eps[i].order = e->order;
        eps[i].timestamp = e->timestamp;
        eps[i].event_type = e->event_type;
        eps[i].topics_csv = e->topics_csv;
        eps[i].source_type = e->source_type;
        eps[i].source_authority = e->authority;
        eps[i].ultimate_source_memory_id = e->ultimate_source_memory_id;
        eps[i].superseded = e->superseded;
    }
    r = memoria_episode_recall_latest(query, role, event_type, topics, eps, h->episode_count);
    free(query); free(role); free(event_type); free(topics); free(json);
    if (!r.hit) return unresolved(out, "no justified native episode");
    ctx = json_escape(r.text);
    st = json_escape(r.source_type ? r.source_type : "");
    root = json_escape(r.ultimate_source_memory_id ? r.ultimate_source_memory_id : "");
    if (!ctx || !st || !root) { free(ctx); free(st); free(root); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    response_status = set_responsef(out, MEMORIA_MOBILE_OK,
             "{\"status\":\"HIT\",\"confidence\":%.6f,\"episode_ids\":[\"%s\"],\"selected_context\":\"%s\",\"order\":%ld,\"timestamp\":\"%s\",\"event_type\":\"%s\",\"topics_csv\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"}",
             r.confidence, r.episode_id, ctx, r.order, r.timestamp ? r.timestamp : "",
             r.event_type ? r.event_type : "", r.topics_csv ? r.topics_csv : "",
             st, r.source_authority, root);
    free(ctx); free(st); free(root);
    return response_status;
}

memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *h) {
    if (!h) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    return memoria_persistence_sync(h->persistence) ? MEMORIA_MOBILE_OK : MEMORIA_MOBILE_PERSISTENCE_ERROR;
}

void memoria_mobile_free_buffer(memoria_mobile_buffer b) { free((void *)b.data); }

void memoria_mobile_close(memoria_mobile_handle *h) {
    size_t i;
    if (!h) return;
    for (i = 0; i < h->turn_count; ++i) free_turn(&h->turns[i]);
    for (i = 0; i < h->episode_count; ++i) free_episode(&h->episodes[i]);
    memoria_persistence_close(h->persistence);
    free(h->data_dir);
    free(h->organization_id);
    free(h);
}
