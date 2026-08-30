#include "trajectory_json_adapter.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#define MAX_WINDOW 32

typedef struct owned_turn {
    char *session_id;
    char *role;
    char *text;
    long order;
} owned_turn;

static char *dup_range(const char *a, const char *b) {
    size_t n;
    char *out;
    if (!a || !b || b < a) return NULL;
    n = (size_t)(b - a);
    out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, a, n);
    out[n] = 0;
    return out;
}

static char *dup_string_local(const char *s) {
    if (!s) return NULL;
    return dup_range(s, s + strlen(s));
}

static const char *skip_ws(const char *p) {
    while (p && *p && isspace((unsigned char)*p)) ++p;
    return p;
}

static const char *find_key(const char *json, const char *key) {
    char pattern[96];
    const char *p;
    size_t k = strlen(key);
    if (k + 3 >= sizeof(pattern)) return NULL;
    pattern[0] = '"';
    memcpy(pattern + 1, key, k);
    pattern[k + 1] = '"';
    pattern[k + 2] = 0;
    p = strstr(json, pattern);
    if (!p) return NULL;
    p = strchr(p + k + 2, ':');
    if (!p) return NULL;
    return skip_ws(p + 1);
}

static char *object_string(const char *json, const char *key) {
    const char *p = find_key(json, key), *q;
    if (!p || *p != '"') return NULL;
    ++p;
    q = p;
    while (*q) {
        if (*q == '\\' && q[1]) { q += 2; continue; }
        if (*q == '"') return dup_range(p, q);
        ++q;
    }
    return NULL;
}

static long object_long(const char *json, const char *key, long fallback) {
    const char *p = find_key(json, key);
    char *end = NULL;
    long v;
    if (!p) return fallback;
    v = strtol(p, &end, 10);
    return end == p ? fallback : v;
}

static void free_owned(owned_turn *t) {
    if (!t) return;
    free(t->session_id);
    free(t->role);
    free(t->text);
    memset(t, 0, sizeof(*t));
}

int memoria_trajectory_resolve_json(
    const char *request_json,
    const char *query,
    const memoria_semantic_source *sources,
    size_t source_count,
    memoria_trajectory_result *out_result,
    size_t *out_window_count
) {
    const char *p, *arr_end;
    char *session_id = NULL;
    owned_turn owned[MAX_WINDOW];
    memoria_trajectory_turn turns[MAX_WINDOW];
    size_t count = 0, i;

    if (!request_json || !query || !sources || !out_result) return -1;
    memset(owned, 0, sizeof(owned));
    *out_result = (memoria_trajectory_result){0,0,0.0,0};
    if (out_window_count) *out_window_count = 0;

    p = find_key(request_json, "conversation_window");
    if (!p) return 0;
    if (*p != '[') return -1;
    ++p;
    arr_end = p;

    session_id = object_string(request_json, "session_id");

    while (*arr_end && *arr_end != ']') {
        const char *obj_start, *obj_end, *q;
        int depth = 0, in_string = 0, escaped = 0;
        char *obj;

        arr_end = skip_ws(arr_end);
        if (*arr_end == ',') { ++arr_end; continue; }
        if (*arr_end == ']') break;
        if (*arr_end != '{') { free(session_id); return -1; }
        obj_start = arr_end;
        q = arr_end;
        obj_end = NULL;
        while (*q) {
            char c = *q;
            if (in_string) {
                if (escaped) escaped = 0;
                else if (c == '\\') escaped = 1;
                else if (c == '"') in_string = 0;
            } else {
                if (c == '"') in_string = 1;
                else if (c == '{') ++depth;
                else if (c == '}') {
                    --depth;
                    if (depth == 0) { obj_end = q + 1; break; }
                }
            }
            ++q;
        }
        if (!obj_end || count >= MAX_WINDOW) {
            for (i = 0; i < count; ++i) free_owned(&owned[i]);
            free(session_id);
            return -1;
        }

        obj = dup_range(obj_start, obj_end);
        if (!obj) {
            for (i = 0; i < count; ++i) free_owned(&owned[i]);
            free(session_id);
            return -1;
        }
        owned[count].session_id = object_string(obj, "session_id");
        owned[count].role = object_string(obj, "role");
        owned[count].text = object_string(obj, "text");
        owned[count].order = object_long(obj, "order", (long)count + 1);
        free(obj);

        if (!owned[count].text) {
            for (i = 0; i <= count; ++i) free_owned(&owned[i]);
            free(session_id);
            return -1;
        }
        if (!owned[count].session_id && session_id)
            owned[count].session_id = dup_string_local(session_id);
        if (session_id && !owned[count].session_id) {
            for (i = 0; i <= count; ++i) free_owned(&owned[i]);
            free(session_id);
            return -1;
        }

        turns[count].session_id = owned[count].session_id;
        turns[count].role = owned[count].role;
        turns[count].text = owned[count].text;
        turns[count].order = owned[count].order;
        ++count;
        arr_end = obj_end;
    }

    if (*arr_end != ']') {
        for (i = 0; i < count; ++i) free_owned(&owned[i]);
        free(session_id);
        return -1;
    }

    *out_result = memoria_trajectory_resolve(query, session_id, turns, count, sources, source_count);
    if (out_window_count) *out_window_count = count;

    for (i = 0; i < count; ++i) free_owned(&owned[i]);
    free(session_id);
    return 1;
}
