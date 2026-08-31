#include "subconscious_mobile.h"
#include "subconscious_kernel.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RUNTIME_SLOTS 16u
#define SUBCONSCIOUS_STATE_MAGIC "MSQ1"
#define SUBCONSCIOUS_STATE_CAP 49152u

typedef struct subconscious_runtime_slot {
    memoria_mobile_handle *handle;
    memoria_subconscious_state state;
    long observation_order;
    int persistence_loaded;
} subconscious_runtime_slot;

static subconscious_runtime_slot runtimes[RUNTIME_SLOTS];

static int hex_digit(unsigned value) {
    return value < 10u ? (int)('0' + value) : (int)('a' + (value - 10u));
}

static int unhex_digit(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int hex_encode(const char *src, char *dst, size_t cap) {
    size_t i, n;
    if (!src || !dst) return 0;
    n = strlen(src);
    if (n > (cap - 1u) / 2u) return 0;
    for (i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)src[i];
        dst[i * 2u] = (char)hex_digit((unsigned)(c >> 4));
        dst[i * 2u + 1u] = (char)hex_digit((unsigned)(c & 15u));
    }
    dst[n * 2u] = 0;
    return 1;
}

static int hex_decode(const char *src, char *dst, size_t cap) {
    size_t i, n;
    if (!src || !dst) return 0;
    n = strlen(src);
    if ((n & 1u) || n / 2u >= cap) return 0;
    for (i = 0; i < n; i += 2u) {
        int hi = unhex_digit(src[i]);
        int lo = unhex_digit(src[i + 1u]);
        if (hi < 0 || lo < 0) return 0;
        dst[i / 2u] = (char)((hi << 4) | lo);
    }
    dst[n / 2u] = 0;
    return 1;
}

static char *serialize_state(const subconscious_runtime_slot *slot) {
    char *out;
    size_t used = 0, i;
    int n;
    if (!slot) return NULL;
    out = (char *)malloc(SUBCONSCIOUS_STATE_CAP);
    if (!out) return NULL;
    n = snprintf(out, SUBCONSCIOUS_STATE_CAP, "%s|%ld|%zu\n",
                 SUBCONSCIOUS_STATE_MAGIC, slot->observation_order, slot->state.count);
    if (n < 0 || (size_t)n >= SUBCONSCIOUS_STATE_CAP) { free(out); return NULL; }
    used = (size_t)n;
    for (i = 0; i < slot->state.count; ++i) {
        const memoria_subconscious_candidate *c = &slot->state.candidates[i];
        char topic_hex[MEMORIA_SUBCONSCIOUS_TOPIC_CAP * 2u + 1u];
        if (!hex_encode(c->topic, topic_hex, sizeof(topic_hex))) { free(out); return NULL; }
        n = snprintf(out + used, SUBCONSCIOUS_STATE_CAP - used,
                     "%s|%u|%u|%u|%.17g|%ld|%.17g\n",
                     topic_hex, c->observations, c->unresolved_count,
                     c->low_confidence_count, c->confidence_deficit,
                     c->last_order, c->priority);
        if (n < 0 || (size_t)n >= SUBCONSCIOUS_STATE_CAP - used) { free(out); return NULL; }
        used += (size_t)n;
    }
    return out;
}

static int parse_unsigned(const char *s, unsigned *out) {
    char *end = NULL;
    unsigned long value;
    if (!s || !out) return 0;
    value = strtoul(s, &end, 10);
    if (end == s || *end || value > 0xfffffffful) return 0;
    *out = (unsigned)value;
    return 1;
}

static int deserialize_state(subconscious_runtime_slot *slot, const char *blob) {
    char *copy = NULL, *line, *next;
    long order = 0;
    size_t expected = 0, count = 0;
    if (!slot || !blob || !*blob) return 0;
    copy = (char *)malloc(strlen(blob) + 1u);
    if (!copy) return 0;
    strcpy(copy, blob);
    line = copy;
    next = strchr(line, '\n');
    if (next) *next++ = 0;
    {
        char magic[16];
        long parsed_order;
        unsigned long parsed_count;
        char tail;
        if (sscanf(line, "%15[^|]|%ld|%lu%c", magic, &parsed_order, &parsed_count, &tail) != 3 ||
            strcmp(magic, SUBCONSCIOUS_STATE_MAGIC) != 0 ||
            parsed_count > MEMORIA_SUBCONSCIOUS_MAX_CANDIDATES) {
            free(copy); return 0;
        }
        order = parsed_order;
        expected = (size_t)parsed_count;
    }
    memoria_subconscious_init(&slot->state);
    while (next && *next && count < expected) {
        memoria_subconscious_candidate candidate;
        char *fields[7];
        char *p;
        size_t f = 0;
        double deficit, priority;
        long last_order;
        memset(&candidate, 0, sizeof(candidate));
        line = next;
        next = strchr(line, '\n');
        if (next) *next++ = 0;
        fields[f++] = line;
        for (p = line; *p && f < 7u; ++p) {
            if (*p == '|') { *p = 0; fields[f++] = p + 1; }
        }
        if (f != 7u || !hex_decode(fields[0], candidate.topic, sizeof(candidate.topic)) ||
            !parse_unsigned(fields[1], &candidate.observations) ||
            !parse_unsigned(fields[2], &candidate.unresolved_count) ||
            !parse_unsigned(fields[3], &candidate.low_confidence_count)) {
            free(copy); return 0;
        }
        {
            char *end = NULL;
            deficit = strtod(fields[4], &end);
            if (end == fields[4] || *end) { free(copy); return 0; }
            last_order = strtol(fields[5], &end, 10);
            if (end == fields[5] || *end) { free(copy); return 0; }
            priority = strtod(fields[6], &end);
            if (end == fields[6] || *end) { free(copy); return 0; }
        }
        candidate.confidence_deficit = deficit;
        candidate.last_order = last_order;
        candidate.priority = priority;
        slot->state.candidates[count++] = candidate;
    }
    if (count != expected) { free(copy); return 0; }
    slot->state.count = count;
    slot->observation_order = order;
    free(copy);
    return 1;
}

static int persist_slot(subconscious_runtime_slot *slot) {
    char *blob;
    int ok;
    if (!slot || !slot->handle) return 0;
    blob = serialize_state(slot);
    if (!blob) return 0;
    ok = memoria_subconscious_mobile_persistence_save(slot->handle, blob);
    free(blob);
    return ok;
}

static void restore_slot(subconscious_runtime_slot *slot) {
    char *blob = NULL;
    if (!slot || slot->persistence_loaded) return;
    slot->persistence_loaded = 1;
    if (!memoria_subconscious_mobile_persistence_load(slot->handle, &blob) || !blob) {
        free(blob);
        return;
    }
    if (!deserialize_state(slot, blob)) {
        memoria_subconscious_init(&slot->state);
        slot->observation_order = 0;
    }
    free(blob);
}

static subconscious_runtime_slot *runtime_for(memoria_mobile_handle *handle, int create) {
    size_t i, empty = RUNTIME_SLOTS;
    if (!handle) return NULL;
    for (i = 0; i < RUNTIME_SLOTS; ++i) {
        if (runtimes[i].handle == handle) {
            restore_slot(&runtimes[i]);
            return &runtimes[i];
        }
        if (!runtimes[i].handle && empty == RUNTIME_SLOTS) empty = i;
    }
    if (!create || empty == RUNTIME_SLOTS) return NULL;
    memset(&runtimes[empty], 0, sizeof(runtimes[empty]));
    runtimes[empty].handle = handle;
    memoria_subconscious_init(&runtimes[empty].state);
    restore_slot(&runtimes[empty]);
    return &runtimes[empty];
}

static char *buffer_string(memoria_mobile_buffer in) {
    char *s;
    if (!in.data || !in.size) return NULL;
    s = (char *)malloc(in.size + 1u);
    if (!s) return NULL;
    memcpy(s, in.data, in.size);
    s[in.size] = 0;
    return s;
}

static char *json_string_value(const char *json, const char *key) {
    char pattern[96];
    const char *p, *q;
    char *out;
    size_t n, w = 0;
    if (!json || !key) return NULL;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p || !(p = strchr(p + strlen(pattern), ':'))) return NULL;
    ++p;
    while (*p && isspace((unsigned char)*p)) ++p;
    if (*p++ != '"') return NULL;
    q = p;
    while (*q && *q != '"') {
        if (*q == '\\' && q[1]) q += 2;
        else ++q;
    }
    if (*q != '"') return NULL;
    n = (size_t)(q - p);
    out = (char *)malloc(n + 1u);
    if (!out) return NULL;
    while (p < q) {
        if (*p == '\\' && p + 1 < q) {
            ++p;
            switch (*p) {
                case 'n': out[w++] = '\n'; ++p; break;
                case 'r': out[w++] = '\r'; ++p; break;
                case 't': out[w++] = '\t'; ++p; break;
                case '"': out[w++] = '"'; ++p; break;
                case '\\': out[w++] = '\\'; ++p; break;
                case '/': out[w++] = '/'; ++p; break;
                default: out[w++] = *p++; break;
            }
        } else out[w++] = *p++;
    }
    out[w] = 0;
    return out;
}

static double json_double_value(const char *json, const char *key, double fallback) {
    char pattern[96];
    const char *p;
    char *end = NULL;
    double value;
    if (!json || !key) return fallback;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p || !(p = strchr(p + strlen(pattern), ':'))) return fallback;
    value = strtod(p + 1, &end);
    return end == p + 1 ? fallback : value;
}

static char *json_escape_copy(const char *s) {
    size_t i, size = 0, w = 0;
    char *out;
    if (!s) s = "";
    for (i = 0; s[i]; ++i) size += (s[i] == '"' || s[i] == '\\' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t') ? 2u : 1u;
    out = (char *)malloc(size + 1u);
    if (!out) return NULL;
    for (i = 0; s[i]; ++i) {
        switch (s[i]) {
            case '"': out[w++]='\\'; out[w++]='"'; break;
            case '\\': out[w++]='\\'; out[w++]='\\'; break;
            case '\n': out[w++]='\\'; out[w++]='n'; break;
            case '\r': out[w++]='\\'; out[w++]='r'; break;
            case '\t': out[w++]='\\'; out[w++]='t'; break;
            default: out[w++]=s[i];
        }
    }
    out[w]=0;
    return out;
}

static memoria_mobile_status response(memoria_mobile_buffer *out, const char *json, memoria_mobile_status status) {
    size_t n;
    uint8_t *data;
    if (!out || !json) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    n = strlen(json);
    data = (uint8_t *)malloc(n + 1u);
    if (!data) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memcpy(data, json, n + 1u);
    out->data = data;
    out->size = n;
    return status;
}

void memoria_subconscious_mobile_observe_resolution(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_status status,
    memoria_mobile_buffer response_json
) {
    subconscious_runtime_slot *slot;
    char *request = NULL, *resolved_response = NULL, *query = NULL;
    double confidence = 0.0;
    int resolved;
    if (!handle || (status != MEMORIA_MOBILE_OK && status != MEMORIA_MOBILE_UNRESOLVED)) return;
    request = buffer_string(request_json);
    if (!request) return;
    query = json_string_value(request, "query");
    free(request);
    if (!query || !*query) { free(query); return; }
    resolved = status == MEMORIA_MOBILE_OK;
    if (resolved && response_json.data && response_json.size) {
        resolved_response = buffer_string(response_json);
        if (resolved_response) confidence = json_double_value(resolved_response, "confidence", 0.0);
        free(resolved_response);
    }
    if (resolved && confidence >= 0.75) { free(query); return; }
    slot = runtime_for(handle, 1);
    if (slot) {
        ++slot->observation_order;
        memoria_subconscious_observe(&slot->state, query, resolved, confidence, slot->observation_order);
        (void)persist_slot(slot);
    }
    free(query);
}

void memoria_subconscious_mobile_forget_handle(memoria_mobile_handle *handle) {
    size_t i;
    if (!handle) return;
    for (i = 0; i < RUNTIME_SLOTS; ++i) {
        if (runtimes[i].handle == handle) {
            (void)persist_slot(&runtimes[i]);
            memset(&runtimes[i], 0, sizeof(runtimes[i]));
            return;
        }
    }
}

memoria_mobile_status memoria_mobile_subconscious_peek_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *out
) {
    subconscious_runtime_slot *slot;
    const memoria_subconscious_candidate *candidate;
    char *topic = NULL;
    char json[768];
    (void)request_json;
    if (!handle || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    slot = runtime_for(handle, 1);
    candidate = slot ? memoria_subconscious_peek(&slot->state) : NULL;
    if (!candidate)
        return response(out, "{\"status\":\"OK\",\"pending\":false}", MEMORIA_MOBILE_OK);
    topic = json_escape_copy(candidate->topic);
    if (!topic) return MEMORIA_MOBILE_INTERNAL_ERROR;
    snprintf(json, sizeof(json),
        "{\"status\":\"OK\",\"pending\":true,\"topic\":\"%s\",\"priority\":%.6f,"
        "\"observations\":%u,\"unresolved_count\":%u,\"low_confidence_count\":%u}",
        topic, candidate->priority, candidate->observations,
        candidate->unresolved_count, candidate->low_confidence_count);
    free(topic);
    return response(out, json, MEMORIA_MOBILE_OK);
}

memoria_mobile_status memoria_mobile_subconscious_satisfy_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *out
) {
    subconscious_runtime_slot *slot;
    char *request = NULL, *topic = NULL;
    int removed = 0;
    if (!handle || !out || !request_json.data || !request_json.size) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    request = buffer_string(request_json);
    if (!request) return MEMORIA_MOBILE_INTERNAL_ERROR;
    topic = json_string_value(request, "topic");
    free(request);
    if (!topic || !*topic) { free(topic); return MEMORIA_MOBILE_INVALID_ARGUMENT; }
    slot = runtime_for(handle, 1);
    if (slot) {
        removed = memoria_subconscious_satisfy(&slot->state, topic);
        if (removed) (void)persist_slot(slot);
    }
    free(topic);
    return response(out,
        removed ? "{\"status\":\"OK\",\"removed\":true}" : "{\"status\":\"OK\",\"removed\":false}",
        MEMORIA_MOBILE_OK);
}
