#include "memoria_mobile.h"
#include "semantic_kernel.h"
#include "trajectory_json_adapter.h"
#include "episodic_kernel.h"
#include "relation_extractor.h"
#include "relation_adapter.h"
#include "temporal_state_adapter.h"
#include "mobile_persistence.h"
#include "diagnostic_export.h"

#include <ctype.h>
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

#define MAX_CORRECTIONS 16u

static size_t json_string_array(const char *json, const char *key, char **out, size_t cap) {
    char pattern[96];
    const char *p;
    size_t count = 0;
    if (!json || !key || !out || !cap) return 0;
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    p = strstr(json, pattern);
    if (!p) return 0;
    p = strchr(p + strlen(pattern), ':');
    if (!p) return 0;
    ++p;
    while (*p && isspace((unsigned char)*p)) ++p;
    if (*p != '[') return 0;
    ++p;
    while (*p) {
        const char *q;
        char *value;
        size_t n, w = 0;
        while (*p && (isspace((unsigned char)*p) || *p == ',')) ++p;
        if (*p == ']') break;
        if (*p != '"' || count >= cap) return 0;
        ++p;
        q = p;
        while (*q && *q != '"') {
            if (*q == '\\' && q[1]) q += 2;
            else ++q;
        }
        if (*q != '"') return 0;
        n = (size_t)(q - p);
        value = (char *)malloc(n + 1u);
        if (!value) return 0;
        while (p < q) {
            if (*p == '\\' && p + 1 < q) ++p;
            value[w++] = *p++;
        }
        value[w] = 0;
        out[count++] = value;
        p = q + 1;
    }
    return count;
}

static void free_string_array(char **values, size_t count) {
    size_t i;
    if (!values) return;
    for (i = 0; i < count; ++i) free(values[i]);
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

static int starts_word_ci(const char *s, const char *word) {
    size_t i = 0, j = 0;
    if (!s || !word) return 0;
    while (s[i] && isspace((unsigned char)s[i])) ++i;
    while (word[j]) {
        if (!s[i + j]) return 0;
        if (tolower((unsigned char)s[i + j]) != tolower((unsigned char)word[j])) return 0;
        ++j;
    }
    return s[i + j] == 0 || !isalnum((unsigned char)s[i + j]);
}

static int looks_like_question_text(const char *text) {
    static const char *question_starts[] = {
        "qual", "quais", "quem", "onde", "quando", "como", "quanto", "quantos", "quantas",
        "por que", "porque", "what", "which", "who", "where", "when", "how", "why",
        "can", "could", "would", "should", "do", "does", "did"
    };
    size_t i;
    if (!text) return 0;
    if (strchr(text, '?')) return 1;
    for (i = 0; i < sizeof(question_starts)/sizeof(question_starts[0]); ++i)
        if (starts_word_ci(text, question_starts[i])) return 1;
    return 0;
}

static int contains_ci(const char *text, const char *needle) {
    const char *p;
    if (!text || !needle || !*needle) return 0;
    for (p = text; *p; ++p) {
        const char *a = p;
        const char *b = needle;
        while (*a && *b && tolower((unsigned char)*a) == tolower((unsigned char)*b)) { ++a; ++b; }
        if (!*b) return 1;
    }
    return 0;
}

static int contains_word_ci(const char *text, const char *word) {
    size_t n;
    const char *p;
    if (!text || !word || !*word) return 0;
    n = strlen(word);
    for (p = text; *p; ++p) {
        if ((p == text || !isalnum((unsigned char)p[-1])) &&
            contains_ci(p, word) &&
            strlen(p) >= n &&
            (p[n] == 0 || !isalnum((unsigned char)p[n]))) return 1;
    }
    return 0;
}

static int temporal_query_flags(const char *query, int *wants_previous, int *wants_current) {
    static const char *previous_words[] = {"before", "previous", "prior", "earlier", "old", "antes", "anterior", "antigo", "era"};
    static const char *current_words[] = {"now", "current", "latest", "present", "agora", "atual", "ultimo"};
    size_t i;
    int p = 0, c = 0;
    if (!query) return 0;
    for (i = 0; i < sizeof(previous_words)/sizeof(previous_words[0]); ++i) if (contains_word_ci(query, previous_words[i])) { p = 1; break; }
    for (i = 0; i < sizeof(current_words)/sizeof(current_words[0]); ++i) if (contains_word_ci(query, current_words[i])) { c = 1; break; }
    if (wants_previous) *wants_previous = p;
    if (wants_current) *wants_current = c;
    return p || c;
}

static int temporal_turn_eligible(const turn_row *turn) {
    if (!turn || !turn->memory_id || !turn->text || turn->relation_count == 0) return 0;
    if (turn->authority < 0.5) return 0;
    if (turn->source_type && strcmp(turn->source_type, "user_query") == 0) return 0;
    if (turn->source_type && strcmp(turn->source_type, "user_assertion") == 0 && looks_like_question_text(turn->text)) return 0;
    return 1;
}

static turn_row *find_turn(memoria_mobile_handle *h, const char *memory_id) {
    size_t i;
    if (!h || !memory_id) return NULL;
    for (i = 0; i < h->turn_count; ++i) if (h->turns[i].memory_id && strcmp(h->turns[i].memory_id, memory_id) == 0) return &h->turns[i];
    return NULL;
}

static int turn_factual_active(memoria_mobile_handle *h, const turn_row *turn) {
    turn_row *root;
    if (!h || !turn || turn->superseded) return 0;
    if (!turn->ultimate_source_memory_id || !*turn->ultimate_source_memory_id) return 1;
    root = find_turn(h, turn->ultimate_source_memory_id);
    if (root && root->superseded) return 0;
    return 1;
}

static int same_relation_key(const memoria_relation *a, const memoria_relation *b) {
    if (!a || !b) return 0;
    return strcasecmp(a->subject, b->subject) == 0 && strcasecmp(a->predicate, b->predicate) == 0;
}

static int temporal_target_from_query(memoria_mobile_handle *h, const char *query, const memoria_relation **target) {
    size_t i, j;
    const memoria_relation *found = NULL;
    if (!h || !query || !target) return 0;
    for (i = 0; i < h->turn_count; ++i) {
        turn_row *turn = &h->turns[i];
        if (!temporal_turn_eligible(turn)) continue;
        for (j = 0; j < turn->relation_count; ++j) {
            const memoria_relation *rel = &turn->relations[j];
            if (!rel->subject[0] || !rel->predicate[0] || !contains_ci(query, rel->subject)) continue;
            if (!found) found = rel;
            else if (!same_relation_key(found, rel)) return -1;
        }
    }
    *target = found;
    return found ? 1 : 0;
}

static int try_temporal_response(
    memoria_mobile_handle *h,
    const char *query,
    turn_row *fallback_turn,
    memoria_mobile_buffer *out,
    memoria_mobile_status *status_out
) {
    int wants_previous = 0, wants_current = 0;
    const memoria_relation *target = NULL;
    int target_state;
    memoria_temporal_relation_source *sources = NULL;
    memoria_state_fact *facts = NULL;
    size_t source_count = 0, fact_capacity = 0, fact_count = 0, i;
    memoria_temporal_state_result state;
    turn_row *previous_turn = NULL, *current_turn = NULL;
    char relations_json[1536];
    char *prev_ctx = NULL, *curr_ctx = NULL, *entity = NULL, *property = NULL, *prev_value = NULL, *curr_value = NULL;
    char *prev_type = NULL, *prev_root = NULL, *curr_type = NULL, *curr_root = NULL;
    memoria_mobile_status response_status;

    if (!temporal_query_flags(query, &wants_previous, &wants_current)) return 0;
    target_state = temporal_target_from_query(h, query, &target);
    if (target_state < 0) {
        if (status_out) *status_out = unresolved(out, "temporal state target is ambiguous");
        return 1;
    }
    if (target_state == 0 && fallback_turn) {
        if (fallback_turn->relation_count != 1) {
            if (status_out) *status_out = unresolved(out, "temporal state target is not uniquely justified");
            return 1;
        }
        target = &fallback_turn->relations[0];
    }
    if (!target) return 0;

    for (i = 0; i < h->turn_count; ++i) if (temporal_turn_eligible(&h->turns[i])) {
        ++source_count;
        fact_capacity += h->turns[i].relation_count;
    }
    if (!source_count || !fact_capacity) {
        if (status_out) *status_out = unresolved(out, "no authoritative temporal state history");
        return 1;
    }
    sources = (memoria_temporal_relation_source *)calloc(source_count, sizeof(*sources));
    facts = (memoria_state_fact *)calloc(fact_capacity, sizeof(*facts));
    if (!sources || !facts) {
        free(sources); free(facts);
        if (status_out) *status_out = MEMORIA_MOBILE_INTERNAL_ERROR;
        return 1;
    }
    source_count = 0;
    for (i = 0; i < h->turn_count; ++i) {
        turn_row *turn = &h->turns[i];
        if (!temporal_turn_eligible(turn)) continue;
        sources[source_count].memory_id = turn->memory_id;
        sources[source_count].relations = turn->relations;
        sources[source_count].relation_count = turn->relation_count;
        sources[source_count].order = turn->order;
        sources[source_count].authority = turn->authority;
        ++source_count;
    }
    fact_count = memoria_temporal_build_facts(sources, source_count, facts, fact_capacity);
    state = memoria_temporal_state_resolve(target->subject, target->predicate, facts, fact_count);
    free(sources); free(facts);
    if (!state.hit) {
        if (status_out) *status_out = unresolved(out, "no justified temporal state for target");
        return 1;
    }
    if (wants_previous && !state.previous_memory_id) {
        if (status_out) *status_out = unresolved(out, "previous temporal state is unavailable");
        return 1;
    }
    current_turn = find_turn(h, state.current_memory_id);
    previous_turn = state.previous_memory_id ? find_turn(h, state.previous_memory_id) : NULL;
    if (!current_turn || (state.previous_memory_id && !previous_turn)) {
        if (status_out) *status_out = unresolved(out, "temporal source missing from native state");
        return 1;
    }
    if (!memoria_relations_to_json(current_turn->relations, current_turn->relation_count,
                                   current_turn->memory_id, relations_json, sizeof(relations_json))) {
        if (status_out) *status_out = MEMORIA_MOBILE_INTERNAL_ERROR;
        return 1;
    }

    prev_ctx = previous_turn ? json_escape(previous_turn->text) : NULL;
    curr_ctx = json_escape(current_turn->text);
    entity = json_escape(target->subject);
    property = json_escape(target->predicate);
    prev_value = state.previous_value ? json_escape(state.previous_value) : NULL;
    curr_value = json_escape(state.current_value ? state.current_value : "");
    curr_type = json_escape(current_turn->source_type ? current_turn->source_type : "");
    curr_root = json_escape(current_turn->ultimate_source_memory_id ? current_turn->ultimate_source_memory_id : "");
    if (previous_turn) {
        prev_type = json_escape(previous_turn->source_type ? previous_turn->source_type : "");
        prev_root = json_escape(previous_turn->ultimate_source_memory_id ? previous_turn->ultimate_source_memory_id : "");
    }
    if (!curr_ctx || !entity || !property || !curr_value || !curr_type || !curr_root ||
        (previous_turn && (!prev_ctx || !prev_value || !prev_type || !prev_root))) {
        free(prev_ctx); free(curr_ctx); free(entity); free(property); free(prev_value); free(curr_value);
        free(prev_type); free(prev_root); free(curr_type); free(curr_root);
        if (status_out) *status_out = MEMORIA_MOBILE_INTERNAL_ERROR;
        return 1;
    }

    if (previous_turn) {
        response_status = set_responsef(out, MEMORIA_MOBILE_OK,
            "{\"status\":\"HIT\",\"confidence\":%.6f,\"memory_ids\":[\"%s\",\"%s\"],\"selected_context\":\"PREVIOUS: %s\\nCURRENT: %s\",\"relations\":%s,\"trajectory_used\":false,\"conversation_window_count\":0,\"temporal_state_used\":true,\"entity\":\"%s\",\"property\":\"%s\",\"previous_memory_id\":\"%s\",\"current_memory_id\":\"%s\",\"previous_order\":%ld,\"current_order\":%ld,\"previous_value\":\"%s\",\"current_value\":\"%s\",\"transition_detected\":%s,\"provenance\":[{\"memory_id\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"},{\"memory_id\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"}]}",
            state.confidence, previous_turn->memory_id, current_turn->memory_id,
            prev_ctx, curr_ctx, relations_json, entity, property,
            previous_turn->memory_id, current_turn->memory_id,
            state.previous_order, state.current_order, prev_value, curr_value,
            state.transition_detected ? "true" : "false",
            previous_turn->memory_id, prev_type, previous_turn->authority, prev_root,
            current_turn->memory_id, curr_type, current_turn->authority, curr_root);
    } else {
        response_status = set_responsef(out, MEMORIA_MOBILE_OK,
            "{\"status\":\"HIT\",\"confidence\":%.6f,\"memory_ids\":[\"%s\"],\"selected_context\":\"CURRENT: %s\",\"relations\":%s,\"trajectory_used\":false,\"conversation_window_count\":0,\"temporal_state_used\":true,\"entity\":\"%s\",\"property\":\"%s\",\"previous_memory_id\":null,\"current_memory_id\":\"%s\",\"previous_order\":null,\"current_order\":%ld,\"previous_value\":null,\"current_value\":\"%s\",\"transition_detected\":false,\"provenance\":[{\"memory_id\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"}]}",
            state.confidence, current_turn->memory_id, curr_ctx, relations_json, entity, property,
            current_turn->memory_id, state.current_order, curr_value,
            current_turn->memory_id, curr_type, current_turn->authority, curr_root);
    }
    free(prev_ctx); free(curr_ctx); free(entity); free(property); free(prev_value); free(curr_value);
    free(prev_type); free(prev_root); free(curr_type); free(curr_root);
    if (status_out) *status_out = response_status;
    return 1;
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
    char *corrections[MAX_CORRECTIONS] = {0};
    size_t correction_slots[MAX_CORRECTIONS] = {0};
    char idbuf[64], relations_json[1536];
    turn_row candidate;
    size_t correction_count = 0, i, unique_count = 0;
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
    correction_count = json_string_array(json, "corrects_memory_ids", corrections, MAX_CORRECTIONS);
    order = json_long(json, "order", (long)h->turn_count + 1);
    authority = json_double(json, "source_authority", -1.0);
    if (!text || !role || (correction_count && strcmp(role, "user") != 0)) {
        free_string_array(corrections, correction_count);
        free(json); free(text); free(role); free(id); free(source_type); free(root);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    next_sequence = h->sequence;
    if (!id) {
        ++next_sequence;
        snprintf(idbuf, sizeof(idbuf), "mobile:%lu", next_sequence);
        id = dup_string(idbuf);
    }
    if (!source_type) {
        if (correction_count) source_type = dup_string("user_correction");
        else source_type = dup_string(strcmp(role, "user") == 0 ? "user_assertion" : "assistant_generated");
    }
    if (authority < 0.0)
        authority = (strcmp(source_type, "user_assertion") == 0 || strcmp(source_type, "user_correction") == 0) ? 1.0 : 0.35;
    if (!root) root = dup_string(id);
    if (!id || !source_type || !root) {
        free_string_array(corrections, correction_count);
        free(json); free(text); free(role); free(id); free(source_type); free(root);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    for (i = 0; i < correction_count; ++i) {
        size_t j;
        turn_row *prior = find_turn(h, corrections[i]);
        if (!prior) {
            free_string_array(corrections, correction_count);
            free(json); free(text); free(role); free(id); free(source_type); free(root);
            return MEMORIA_MOBILE_INVALID_ARGUMENT;
        }
        for (j = 0; j < h->turn_count && &h->turns[j] != prior; ++j) {}
        if (j == h->turn_count) {
            free_string_array(corrections, correction_count);
            free(json); free(text); free(role); free(id); free(source_type); free(root);
            return MEMORIA_MOBILE_INTERNAL_ERROR;
        }
        for (size_t k = 0; k < unique_count; ++k) if (correction_slots[k] == j + 1u) break;
        {
            size_t k;
            for (k = 0; k < unique_count; ++k) if (correction_slots[k] == j + 1u) break;
            if (k == unique_count) correction_slots[unique_count++] = j + 1u;
        }
    }
    candidate.memory_id = id;
    candidate.text = text;
    candidate.role = role;
    candidate.source_type = source_type;
    candidate.ultimate_source_memory_id = root;
    candidate.authority = authority;
    candidate.order = order;
    candidate.superseded = 0;
    candidate.relation_count = memoria_extract_relations(text, candidate.relations, MAX_RELATIONS_PER_TURN);
    if (!memoria_relations_to_json(candidate.relations, candidate.relation_count, id, relations_json, sizeof(relations_json))) {
        free_string_array(corrections, correction_count);
        free(json); free_turn(&candidate); return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    if (!memoria_persistence_save_turn_with_supersessions(
            h->persistence, h->turn_count + 1, next_sequence, &candidate,
            correction_slots, unique_count)) {
        free_string_array(corrections, correction_count);
        free(json); free_turn(&candidate); return MEMORIA_MOBILE_PERSISTENCE_ERROR;
    }
    for (i = 0; i < unique_count; ++i) h->turns[correction_slots[i] - 1u].superseded = 1;
    h->turns[h->turn_count++] = candidate;
    h->sequence = next_sequence;
    response_status = set_responsef(out, MEMORIA_MOBILE_OK,
             "{\"status\":\"OK\",\"stored_memory_ids\":[\"%s\"],\"relations\":%s,\"unresolved\":%s,\"native_relation_extraction\":true,\"durable\":true,\"correction_applied\":%s}",
             id, relations_json, candidate.relation_count ? "false" : "true", unique_count ? "true" : "false");
    free_string_array(corrections, correction_count);
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
    size_t source_count = 0;
    for (i = 0; i < h->turn_count; ++i) {
        if (!turn_factual_active(h, &h->turns[i])) continue;
        sources[source_count].memory_id = h->turns[i].memory_id;
        sources[source_count].text = h->turns[i].text;
        sources[source_count].authority = h->turns[i].authority;
        sources[source_count].order = h->turns[i].order;
        sources[source_count].source_type = h->turns[i].source_type;
        sources[source_count].ultimate_source_memory_id = h->turns[i].ultimate_source_memory_id;
        ++source_count;
    }
    if (try_temporal_response(h, query, NULL, out, &response_status)) {
        free(query); free(json);
        return response_status;
    }
    trajectory_mode = memoria_trajectory_resolve_json(json, query, sources, source_count, &tr, &window_count);
    if (trajectory_mode < 0) {
        free(query); free(json);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    if (trajectory_mode == 1 && tr.hit && tr.memory_count == 2) {
        turn_row *first_turn = find_turn(h, tr.memory_ids[0]);
        turn_row *second_turn = find_turn(h, tr.memory_ids[1]);
        char first_relations[1536], second_relations[1536];
        char *first_ctx = NULL, *second_ctx = NULL;
        char *first_id = NULL, *second_id = NULL;
        char *first_type = NULL, *second_type = NULL;
        char *first_root = NULL, *second_root = NULL;

        if (!first_turn || !second_turn) {
            free(query); free(json);
            return unresolved(out, "selected multi-source trajectory memory missing from native state");
        }
        if (!memoria_relations_to_json(first_turn->relations, first_turn->relation_count,
                                       first_turn->memory_id, first_relations, sizeof(first_relations)) ||
            !memoria_relations_to_json(second_turn->relations, second_turn->relation_count,
                                       second_turn->memory_id, second_relations, sizeof(second_relations))) {
            free(query); free(json);
            return MEMORIA_MOBILE_INTERNAL_ERROR;
        }

        first_ctx = json_escape(first_turn->text);
        second_ctx = json_escape(second_turn->text);
        first_id = json_escape(first_turn->memory_id);
        second_id = json_escape(second_turn->memory_id);
        first_type = json_escape(first_turn->source_type ? first_turn->source_type : "");
        second_type = json_escape(second_turn->source_type ? second_turn->source_type : "");
        first_root = json_escape(first_turn->ultimate_source_memory_id ? first_turn->ultimate_source_memory_id : "");
        second_root = json_escape(second_turn->ultimate_source_memory_id ? second_turn->ultimate_source_memory_id : "");
        if (!first_ctx || !second_ctx || !first_id || !second_id || !first_type || !second_type || !first_root || !second_root) {
            free(first_ctx); free(second_ctx); free(first_id); free(second_id);
            free(first_type); free(second_type); free(first_root); free(second_root);
            free(query); free(json);
            return MEMORIA_MOBILE_INTERNAL_ERROR;
        }

        response_status = set_responsef(out, MEMORIA_MOBILE_OK,
            "{\"status\":\"HIT\",\"confidence\":%.6f,\"memory_ids\":[\"%s\",\"%s\"],\"selected_context\":\"SOURCE_1: %s\\nSOURCE_2: %s\",\"relations\":[],\"relations_by_memory\":[{\"memory_id\":\"%s\",\"relations\":%s},{\"memory_id\":\"%s\",\"relations\":%s}],\"trajectory_used\":true,\"conversation_window_count\":%lu,\"temporal_state_used\":false,\"multi_source_used\":true,\"provenance\":[{\"memory_id\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"},{\"memory_id\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"}]}",
            tr.confidence, first_id, second_id, first_ctx, second_ctx,
            first_id, first_relations, second_id, second_relations,
            (unsigned long)window_count,
            first_id, first_type, first_turn->authority, first_root,
            second_id, second_type, second_turn->authority, second_root);

        free(first_ctx); free(second_ctx); free(first_id); free(second_id);
        free(first_type); free(second_type); free(first_root); free(second_root);
        free(query); free(json);
        return response_status;
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
        r = memoria_semantic_resolve_sources(query, sources, source_count);
    }
    if (!r.hit) {
        free(query); free(json);
        return unresolved(out, "no justified native semantic source");
    }
    for (i = 0; i < h->turn_count && strcmp(h->turns[i].memory_id, r.memory_id) != 0; ++i) {}
    if (i == h->turn_count) {
        free(query); free(json);
        return unresolved(out, "selected source missing from native state");
    }
    if (try_temporal_response(h, query, &h->turns[i], out, &response_status)) {
        free(query); free(json);
        return response_status;
    }
    free(query); free(json);
    if (!memoria_relations_to_json(h->turns[i].relations, h->turns[i].relation_count,
                                   h->turns[i].memory_id, relations_json, sizeof(relations_json)))
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    ctx = json_escape(h->turns[i].text);
    st = json_escape(r.source_type ? r.source_type : "");
    root = json_escape(r.ultimate_source_memory_id ? r.ultimate_source_memory_id : "");
    if (!ctx || !st || !root) { free(ctx); free(st); free(root); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    response_status = set_responsef(out, MEMORIA_MOBILE_OK,
             "{\"status\":\"HIT\",\"confidence\":%.6f,\"memory_ids\":[\"%s\"],\"selected_context\":\"%s\",\"relations\":%s,\"trajectory_used\":%s,\"conversation_window_count\":%lu,\"temporal_state_used\":false,\"provenance\":[{\"memory_id\":\"%s\",\"source_type\":\"%s\",\"source_authority\":%.6f,\"ultimate_source_memory_id\":\"%s\"}]}",
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

memoria_mobile_status memoria_mobile_export_snapshot_json(
    memoria_mobile_handle *h,
    memoria_mobile_buffer req,
    memoria_mobile_buffer *out
) {
    char *request = NULL;
    char *snapshot = NULL;
    long turn_offset, turn_limit, episode_offset, episode_limit;
    memoria_diagnostic_page page;
    memoria_mobile_status status;

    if (!h || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (req.data && req.size) request = buffer_to_string(req);
    else request = dup_string("{}");
    if (!request) return MEMORIA_MOBILE_INTERNAL_ERROR;

    turn_offset = json_long(request, "turn_offset", 0);
    turn_limit = json_long(request, "turn_limit", 0);
    episode_offset = json_long(request, "episode_offset", 0);
    episode_limit = json_long(request, "episode_limit", 0);
    if (turn_offset < 0 || turn_limit < 0 || episode_offset < 0 || episode_limit < 0) {
        free(request);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }

    page.turn_offset = (size_t)turn_offset;
    page.turn_limit = (size_t)turn_limit;
    page.episode_offset = (size_t)episode_offset;
    page.episode_limit = (size_t)episode_limit;

    snapshot = memoria_diagnostic_export_json(
        h->organization_id,
        h->sequence,
        h->turns,
        h->turn_count,
        h->episodes,
        h->episode_count,
        page
    );
    free(request);
    if (!snapshot) return MEMORIA_MOBILE_INTERNAL_ERROR;
    status = set_response(out, snapshot, MEMORIA_MOBILE_OK);
    free(snapshot);
    return status;
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
