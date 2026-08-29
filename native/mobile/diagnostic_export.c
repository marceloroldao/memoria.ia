#include "diagnostic_export.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define DIAGNOSTIC_DEFAULT_PAGE 32u
#define DIAGNOSTIC_MAX_PAGE 64u

typedef struct json_builder {
    char *data;
    size_t length;
    size_t capacity;
    int ok;
} json_builder;

static int reserve(json_builder *b, size_t extra) {
    size_t needed, cap;
    char *next;
    if (!b || !b->ok) return 0;
    if (extra > (size_t)-1 - b->length - 1u) { b->ok = 0; return 0; }
    needed = b->length + extra + 1u;
    if (needed <= b->capacity) return 1;
    cap = b->capacity ? b->capacity : 1024u;
    while (cap < needed) {
        if (cap > (size_t)-1 / 2u) { cap = needed; break; }
        cap *= 2u;
    }
    next = (char *)realloc(b->data, cap);
    if (!next) { b->ok = 0; return 0; }
    b->data = next;
    b->capacity = cap;
    return 1;
}

static int append_n(json_builder *b, const char *s, size_t n) {
    if (!s || !reserve(b, n)) return 0;
    memcpy(b->data + b->length, s, n);
    b->length += n;
    b->data[b->length] = 0;
    return 1;
}

static int append(json_builder *b, const char *s) {
    return s ? append_n(b, s, strlen(s)) : 0;
}

static int appendf(json_builder *b, const char *fmt, ...) {
    va_list args, measure;
    int needed, written;
    if (!b || !fmt || !b->ok) return 0;
    va_start(args, fmt);
    va_copy(measure, args);
    needed = vsnprintf(NULL, 0, fmt, measure);
    va_end(measure);
    if (needed < 0 || !reserve(b, (size_t)needed)) { va_end(args); b->ok = 0; return 0; }
    written = vsnprintf(b->data + b->length, b->capacity - b->length, fmt, args);
    va_end(args);
    if (written != needed) { b->ok = 0; return 0; }
    b->length += (size_t)written;
    return 1;
}

static int append_json_string(json_builder *b, const char *s) {
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    if (!append(b, "\"")) return 0;
    while (*p) {
        char esc[7];
        switch (*p) {
            case '\"': if (!append(b, "\\\"")) return 0; break;
            case '\\': if (!append(b, "\\\\")) return 0; break;
            case '\b': if (!append(b, "\\b")) return 0; break;
            case '\f': if (!append(b, "\\f")) return 0; break;
            case '\n': if (!append(b, "\\n")) return 0; break;
            case '\r': if (!append(b, "\\r")) return 0; break;
            case '\t': if (!append(b, "\\t")) return 0; break;
            default:
                if (*p < 0x20u) {
                    snprintf(esc, sizeof(esc), "\\u%04x", (unsigned int)*p);
                    if (!append(b, esc)) return 0;
                } else {
                    if (!append_n(b, (const char *)p, 1u)) return 0;
                }
        }
        ++p;
    }
    return append(b, "\"");
}

static size_t normalized_limit(size_t limit) {
    if (limit == 0u) return DIAGNOSTIC_DEFAULT_PAGE;
    if (limit > DIAGNOSTIC_MAX_PAGE) return DIAGNOSTIC_MAX_PAGE;
    return limit;
}

static size_t page_end(size_t offset, size_t limit, size_t total) {
    size_t remaining;
    if (offset >= total) return total;
    remaining = total - offset;
    return offset + (limit < remaining ? limit : remaining);
}

static int append_relation(json_builder *b, const memoria_relation *r, const char *relation_memory_id, const char *source_memory_id) {
    if (!append(b, "{\"subject\":")) return 0;
    if (!append_json_string(b, r->subject)) return 0;
    if (!append(b, ",\"predicate\":")) return 0;
    if (!append_json_string(b, r->predicate)) return 0;
    if (!append(b, ",\"object\":")) return 0;
    if (!append_json_string(b, r->object)) return 0;
    if (!append(b, ",\"memory_id\":")) return 0;
    if (!append_json_string(b, relation_memory_id)) return 0;
    if (!appendf(b, ",\"confidence\":%.6f,\"source_memory_id\":", r->confidence)) return 0;
    if (!append_json_string(b, source_memory_id)) return 0;
    return append(b, "}");
}

static int append_turn(json_builder *b, const memoria_persist_turn *t) {
    size_t i;
    if (!append(b, "{\"memory_id\":")) return 0;
    if (!append_json_string(b, t->memory_id)) return 0;
    if (!append(b, ",\"role\":")) return 0;
    if (!append_json_string(b, t->role)) return 0;
    if (!append(b, ",\"text\":")) return 0;
    if (!append_json_string(b, t->text)) return 0;
    if (!append(b, ",\"source_type\":")) return 0;
    if (!append_json_string(b, t->source_type)) return 0;
    if (!append(b, ",\"ultimate_source_memory_id\":")) return 0;
    if (!append_json_string(b, t->ultimate_source_memory_id)) return 0;
    if (!appendf(b, ",\"source_authority\":%.6f,\"order\":%ld,\"superseded\":%s,\"namespace\":", t->authority, t->order, t->superseded ? "true" : "false")) return 0;
    if (!append_json_string(b, t->namespace_id)) return 0;
    if (!append(b, ",\"relations\":[")) return 0;
    for (i = 0; i < t->relation_count; ++i) {
        if (i && !append(b, ",")) return 0;
        if (!append_relation(b, &t->relations[i], t->relation_memory_ids[i], t->memory_id)) return 0;
    }
    return append(b, "]}");
}

static int append_episode(json_builder *b, const memoria_persist_episode *e) {
    if (!append(b, "{\"episode_id\":")) return 0;
    if (!append_json_string(b, e->episode_id)) return 0;
    if (!append(b, ",\"session_id\":")) return 0;
    if (!append_json_string(b, e->session_id)) return 0;
    if (!append(b, ",\"role\":")) return 0;
    if (!append_json_string(b, e->role)) return 0;
    if (!append(b, ",\"text\":")) return 0;
    if (!append_json_string(b, e->text)) return 0;
    if (!append(b, ",\"timestamp\":")) return 0;
    if (!append_json_string(b, e->timestamp)) return 0;
    if (!append(b, ",\"event_type\":")) return 0;
    if (!append_json_string(b, e->event_type)) return 0;
    if (!append(b, ",\"topics_csv\":")) return 0;
    if (!append_json_string(b, e->topics_csv)) return 0;
    if (!append(b, ",\"source_type\":")) return 0;
    if (!append_json_string(b, e->source_type)) return 0;
    if (!append(b, ",\"ultimate_source_memory_id\":")) return 0;
    if (!append_json_string(b, e->ultimate_source_memory_id)) return 0;
    return appendf(b, ",\"source_authority\":%.6f,\"order\":%ld,\"superseded\":%s}",
                   e->authority, e->order, e->superseded ? "true" : "false");
}

static int append_next_offset(json_builder *b, size_t end, size_t total) {
    if (end < total) return appendf(b, "%lu", (unsigned long)end);
    return append(b, "null");
}

char *memoria_diagnostic_export_json(
    const char *organization_id,
    unsigned long sequence,
    const memoria_persist_turn *turns,
    size_t turn_count,
    const memoria_persist_episode *episodes,
    size_t episode_count,
    memoria_diagnostic_page page
) {
    json_builder b = {0,0,0,1};
    size_t i, turn_end, episode_end;
    size_t turn_limit = normalized_limit(page.turn_limit);
    size_t episode_limit = normalized_limit(page.episode_limit);
    long long generated_at = (long long)time(NULL);

    if ((!turns && turn_count) || (!episodes && episode_count)) return NULL;
    if (page.turn_offset > turn_count) page.turn_offset = turn_count;
    if (page.episode_offset > episode_count) page.episode_offset = episode_count;
    turn_end = page_end(page.turn_offset, turn_limit, turn_count);
    episode_end = page_end(page.episode_offset, episode_limit, episode_count);

    if (!append(&b, "{\"status\":\"OK\",\"format\":\"memoria.mobile.diagnostic.v1\",\"abi_version\":1,\"state_schema\":")) goto fail;
    if (!appendf(&b, "%u,\"generated_at_unix\":%lld,\"organization_id\":", MEMORIA_MOBILE_STATE_SCHEMA, generated_at)) goto fail;
    if (!append_json_string(&b, organization_id)) goto fail;
    if (!appendf(&b, ",\"sequence\":%lu,\"counts\":{\"turns\":%lu,\"episodes\":%lu},", sequence,
                 (unsigned long)turn_count, (unsigned long)episode_count)) goto fail;

    if (!appendf(&b, "\"turn_page\":{\"offset\":%lu,\"limit\":%lu,\"returned\":%lu,\"next_offset\":",
                 (unsigned long)page.turn_offset, (unsigned long)turn_limit,
                 (unsigned long)(turn_end - page.turn_offset))) goto fail;
    if (!append_next_offset(&b, turn_end, turn_count) || !append(&b, "},")) goto fail;
    if (!appendf(&b, "\"episode_page\":{\"offset\":%lu,\"limit\":%lu,\"returned\":%lu,\"next_offset\":",
                 (unsigned long)page.episode_offset, (unsigned long)episode_limit,
                 (unsigned long)(episode_end - page.episode_offset))) goto fail;
    if (!append_next_offset(&b, episode_end, episode_count) || !append(&b, "},\"turns\":[")) goto fail;

    for (i = page.turn_offset; i < turn_end; ++i) {
        if (i > page.turn_offset && !append(&b, ",")) goto fail;
        if (!append_turn(&b, &turns[i])) goto fail;
    }
    if (!append(&b, "],\"episodes\":[")) goto fail;
    for (i = page.episode_offset; i < episode_end; ++i) {
        if (i > page.episode_offset && !append(&b, ",")) goto fail;
        if (!append_episode(&b, &episodes[i])) goto fail;
    }
    if (!append(&b, "]}")) goto fail;
    return b.data;

fail:
    free(b.data);
    return NULL;
}
