#include "structural_text_runtime.h"
#include "bdr/atomic_c_api.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STRUCTURAL_TEXT_RUNTIME_SCHEMA 1u
#define KEY_CAP 512u

typedef struct runtime_observation {
    char *hierarchy_id;
    char *source_id;
    char *source_kind;
    char *text;
    unsigned long sequence;
} runtime_observation;

typedef struct runtime_hierarchy {
    char *hierarchy_id;
    memoria_structural_text_field *field;
} runtime_hierarchy;

struct memoria_structural_text_runtime {
    bdr_atomic_c_handle *db;
    char *org;
    size_t max_within_distance;
    size_t max_event_lag;
    double forgetting_rate;
    runtime_observation *observations;
    size_t observation_count;
    size_t observation_capacity;
    runtime_hierarchy *hierarchies;
    size_t hierarchy_count;
    size_t hierarchy_capacity;
};

typedef struct dynbuf {
    char *data;
    size_t size;
    size_t capacity;
} dynbuf;

static char *dup_text(const char *value) {
    size_t n;
    char *copy;
    if (!value) value = "";
    n = strlen(value) + 1u;
    copy = (char *)malloc(n);
    if (copy) memcpy(copy, value, n);
    return copy;
}

static int make_key(
    const memoria_structural_text_runtime *runtime,
    char *dst,
    size_t cap,
    const char *suffix
) {
    int n;
    if (!runtime || !dst || !suffix) return 0;
    n = snprintf(
        dst,
        cap,
        "memoria-mobile/v1/%s/structural-text/%s",
        runtime->org,
        suffix
    );
    return n > 0 && (size_t)n < cap;
}

static int fetch_value(
    const memoria_structural_text_runtime *runtime,
    const char *suffix,
    char **out,
    size_t *out_size
) {
    char key[KEY_CAP];
    bdr_atomic_c_buffer value = {0};
    bdr_atomic_c_status status;
    char *copy;
    if (!runtime || !suffix || !out ||
        !make_key(runtime, key, sizeof(key), suffix)) return 0;
    *out = NULL;
    if (out_size) *out_size = 0u;
    status = bdr_atomic_c_get(runtime->db, key, strlen(key), &value);
    if (status == BDR_ATOMIC_C_NOT_FOUND) return 1;
    if (status != BDR_ATOMIC_C_OK) return 0;
    copy = (char *)malloc(value.size + 1u);
    if (!copy) {
        bdr_atomic_c_free_buffer(value);
        return 0;
    }
    if (value.size) memcpy(copy, value.data, value.size);
    copy[value.size] = 0;
    if (out_size) *out_size = value.size;
    bdr_atomic_c_free_buffer(value);
    *out = copy;
    return 1;
}

static int dynbuf_reserve(dynbuf *buffer, size_t need) {
    char *grown;
    size_t capacity;
    if (!buffer) return 0;
    if (need <= buffer->capacity) return 1;
    capacity = buffer->capacity ? buffer->capacity : 128u;
    while (capacity < need) {
        if (capacity > ((size_t)-1) / 2u) return 0;
        capacity *= 2u;
    }
    grown = (char *)realloc(buffer->data, capacity);
    if (!grown) return 0;
    buffer->data = grown;
    buffer->capacity = capacity;
    return 1;
}

static int dynbuf_append(dynbuf *buffer, const char *data, size_t size) {
    if (!buffer || (!data && size)) return 0;
    if (!dynbuf_reserve(buffer, buffer->size + size + 1u)) return 0;
    if (size) memcpy(buffer->data + buffer->size, data, size);
    buffer->size += size;
    buffer->data[buffer->size] = 0;
    return 1;
}

static int dynbuf_append_field(dynbuf *buffer, const char *value) {
    char length[64];
    size_t n = strlen(value ? value : "");
    int written = snprintf(length, sizeof(length), "%zu:", n);
    if (written <= 0 || (size_t)written >= sizeof(length)) return 0;
    return dynbuf_append(buffer, length, (size_t)written) &&
           dynbuf_append(buffer, value ? value : "", n);
}

static int serialize_observation(
    const runtime_observation *observation,
    char **out,
    size_t *out_size
) {
    dynbuf buffer = {0};
    char sequence[64];
    int written;
    if (!observation || !out || !out_size) return 0;
    *out = NULL;
    *out_size = 0u;
    written = snprintf(sequence, sizeof(sequence), "%lu:", observation->sequence);
    if (written <= 0 || (size_t)written >= sizeof(sequence) ||
        !dynbuf_append(&buffer, sequence, (size_t)written) ||
        !dynbuf_append_field(&buffer, observation->hierarchy_id) ||
        !dynbuf_append_field(&buffer, observation->source_id) ||
        !dynbuf_append_field(&buffer, observation->source_kind) ||
        !dynbuf_append_field(&buffer, observation->text)) {
        free(buffer.data);
        return 0;
    }
    *out = buffer.data;
    *out_size = buffer.size;
    return 1;
}

static int parse_size_token(
    const char **cursor,
    size_t *remaining,
    size_t *value
) {
    const char *p;
    size_t result = 0u;
    size_t digits = 0u;
    if (!cursor || !*cursor || !remaining || !value) return 0;
    p = *cursor;
    while (*remaining && *p >= '0' && *p <= '9') {
        size_t digit = (size_t)(*p - '0');
        if (result > (((size_t)-1) - digit) / 10u) return 0;
        result = result * 10u + digit;
        ++p;
        --(*remaining);
        ++digits;
    }
    if (!digits || !*remaining || *p != ':') return 0;
    ++p;
    --(*remaining);
    *cursor = p;
    *value = result;
    return 1;
}

static int parse_ulong_token(
    const char **cursor,
    size_t *remaining,
    unsigned long *value
) {
    const char *p;
    unsigned long result = 0ul;
    size_t digits = 0u;
    if (!cursor || !*cursor || !remaining || !value) return 0;
    p = *cursor;
    while (*remaining && *p >= '0' && *p <= '9') {
        unsigned long digit = (unsigned long)(*p - '0');
        if (result > (~0ul - digit) / 10ul) return 0;
        result = result * 10ul + digit;
        ++p;
        --(*remaining);
        ++digits;
    }
    if (!digits || !*remaining || *p != ':') return 0;
    ++p;
    --(*remaining);
    *cursor = p;
    *value = result;
    return 1;
}

static int parse_alloc_field(
    const char **cursor,
    size_t *remaining,
    char **out
) {
    size_t n;
    char *value;
    if (!cursor || !remaining || !out ||
        !parse_size_token(cursor, remaining, &n) || n > *remaining) return 0;
    value = (char *)malloc(n + 1u);
    if (!value) return 0;
    if (n) memcpy(value, *cursor, n);
    value[n] = 0;
    *cursor += n;
    *remaining -= n;
    *out = value;
    return 1;
}

static void free_observation(runtime_observation *observation) {
    if (!observation) return;
    free(observation->hierarchy_id);
    free(observation->source_id);
    free(observation->source_kind);
    free(observation->text);
    memset(observation, 0, sizeof(*observation));
}

static int deserialize_observation(
    const char *value,
    size_t value_size,
    runtime_observation *out
) {
    const char *cursor = value;
    size_t remaining = value_size;
    runtime_observation parsed = {0};
    if (!value || !out ||
        !parse_ulong_token(&cursor, &remaining, &parsed.sequence) ||
        !parse_alloc_field(&cursor, &remaining, &parsed.hierarchy_id) ||
        !parse_alloc_field(&cursor, &remaining, &parsed.source_id) ||
        !parse_alloc_field(&cursor, &remaining, &parsed.source_kind) ||
        !parse_alloc_field(&cursor, &remaining, &parsed.text) ||
        remaining != 0u ||
        !parsed.hierarchy_id[0] ||
        !parsed.source_id[0] ||
        !parsed.source_kind[0] ||
        !parsed.text[0]) {
        free_observation(&parsed);
        return 0;
    }
    *out = parsed;
    return 1;
}

static int reserve_observations(
    memoria_structural_text_runtime *runtime,
    size_t need
) {
    runtime_observation *grown;
    size_t capacity;
    if (need <= runtime->observation_capacity) return 1;
    capacity = runtime->observation_capacity ? runtime->observation_capacity * 2u : 32u;
    while (capacity < need) {
        if (capacity > ((size_t)-1) / 2u) return 0;
        capacity *= 2u;
    }
    grown = (runtime_observation *)realloc(
        runtime->observations,
        capacity * sizeof(*grown)
    );
    if (!grown) return 0;
    runtime->observations = grown;
    runtime->observation_capacity = capacity;
    return 1;
}

static int reserve_hierarchies(
    memoria_structural_text_runtime *runtime,
    size_t need
) {
    runtime_hierarchy *grown;
    size_t capacity;
    if (need <= runtime->hierarchy_capacity) return 1;
    capacity = runtime->hierarchy_capacity ? runtime->hierarchy_capacity * 2u : 8u;
    while (capacity < need) {
        if (capacity > ((size_t)-1) / 2u) return 0;
        capacity *= 2u;
    }
    grown = (runtime_hierarchy *)realloc(
        runtime->hierarchies,
        capacity * sizeof(*grown)
    );
    if (!grown) return 0;
    runtime->hierarchies = grown;
    runtime->hierarchy_capacity = capacity;
    return 1;
}

static runtime_hierarchy *find_hierarchy(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id
) {
    size_t i;
    if (!runtime || !hierarchy_id) return NULL;
    for (i = 0; i < runtime->hierarchy_count; ++i) {
        if (strcmp(runtime->hierarchies[i].hierarchy_id, hierarchy_id) == 0)
            return &runtime->hierarchies[i];
    }
    return NULL;
}

static const runtime_hierarchy *find_hierarchy_const(
    const memoria_structural_text_runtime *runtime,
    const char *hierarchy_id
) {
    size_t i;
    if (!runtime || !hierarchy_id) return NULL;
    for (i = 0; i < runtime->hierarchy_count; ++i) {
        if (strcmp(runtime->hierarchies[i].hierarchy_id, hierarchy_id) == 0)
            return &runtime->hierarchies[i];
    }
    return NULL;
}

static runtime_hierarchy *get_or_create_hierarchy(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id
) {
    runtime_hierarchy *existing;
    runtime_hierarchy *slot;
    char *id_copy;
    memoria_structural_text_field *field;
    existing = find_hierarchy(runtime, hierarchy_id);
    if (existing) return existing;
    if (!reserve_hierarchies(runtime, runtime->hierarchy_count + 1u)) return NULL;
    id_copy = dup_text(hierarchy_id);
    field = memoria_structural_text_field_create(
        runtime->max_within_distance,
        runtime->max_event_lag,
        runtime->forgetting_rate
    );
    if (!id_copy || !field) {
        free(id_copy);
        memoria_structural_text_field_destroy(field);
        return NULL;
    }
    slot = &runtime->hierarchies[runtime->hierarchy_count++];
    slot->hierarchy_id = id_copy;
    slot->field = field;
    return slot;
}

static int tokenize_alloc(
    const char *text,
    uint64_t **out_symbols,
    size_t *out_count
) {
    size_t count = 0u;
    uint64_t *symbols;
    if (!text || !*text || !out_symbols || !out_count) return 0;
    *out_symbols = NULL;
    *out_count = 0u;
    if (!memoria_structural_text_tokenize(
        text, strlen(text), NULL, 0u, &count
    ) || count == 0u) return 0;
    symbols = (uint64_t *)malloc(count * sizeof(*symbols));
    if (!symbols) return 0;
    if (!memoria_structural_text_tokenize(
        text, strlen(text), symbols, count, &count
    )) {
        free(symbols);
        return 0;
    }
    *out_symbols = symbols;
    *out_count = count;
    return 1;
}

static int replay_observation(
    memoria_structural_text_runtime *runtime,
    const runtime_observation *observation
) {
    runtime_hierarchy *hierarchy;
    uint64_t *symbols = NULL;
    size_t symbol_count = 0u;
    if (!runtime || !observation ||
        !tokenize_alloc(observation->text, &symbols, &symbol_count)) return 0;
    hierarchy = get_or_create_hierarchy(runtime, observation->hierarchy_id);
    if (!hierarchy ||
        !memoria_structural_text_field_observe(
            hierarchy->field, symbols, symbol_count
        )) {
        free(symbols);
        return 0;
    }
    free(symbols);
    return 1;
}

static int append_loaded_observation(
    memoria_structural_text_runtime *runtime,
    runtime_observation *observation
) {
    if (!reserve_observations(runtime, runtime->observation_count + 1u))
        return 0;
    if (!replay_observation(runtime, observation))
        return 0;
    runtime->observations[runtime->observation_count++] = *observation;
    memset(observation, 0, sizeof(*observation));
    return 1;
}

static int parse_size_text(const char *text, size_t *out) {
    char *end = NULL;
    unsigned long long value;
    if (!text || !out) return 0;
    value = strtoull(text, &end, 10);
    if (end == text || *end || value > (unsigned long long)((size_t)-1))
        return 0;
    *out = (size_t)value;
    return 1;
}

static int parse_double_text(const char *text, double *out) {
    char *end = NULL;
    double value;
    if (!text || !out) return 0;
    value = strtod(text, &end);
    if (end == text || *end || !isfinite(value)) return 0;
    *out = value;
    return 1;
}

static int load_persisted(
    memoria_structural_text_runtime *runtime
) {
    char *schema = NULL;
    char *count_text = NULL;
    char *within_text = NULL;
    char *lag_text = NULL;
    char *forget_text = NULL;
    size_t count = 0u;
    size_t within = 0u;
    size_t lag = 0u;
    double forgetting = 0.0;
    size_t i;
    int ok = 0;

    if (!fetch_value(runtime, "meta/schema", &schema, NULL) ||
        !fetch_value(runtime, "meta/count", &count_text, NULL) ||
        !fetch_value(runtime, "meta/max_within_distance", &within_text, NULL) ||
        !fetch_value(runtime, "meta/max_event_lag", &lag_text, NULL) ||
        !fetch_value(runtime, "meta/forgetting_rate", &forget_text, NULL))
        goto done;

    if (!schema && !count_text && !within_text && !lag_text && !forget_text) {
        ok = 1;
        goto done;
    }
    if (!schema || !count_text || !within_text || !lag_text || !forget_text)
        goto done;
    {
        size_t schema_value = 0u;
        if (!parse_size_text(schema, &schema_value) ||
            schema_value != STRUCTURAL_TEXT_RUNTIME_SCHEMA ||
            !parse_size_text(count_text, &count) ||
            !parse_size_text(within_text, &within) ||
            !parse_size_text(lag_text, &lag) ||
            !parse_double_text(forget_text, &forgetting) ||
            within != runtime->max_within_distance ||
            lag != runtime->max_event_lag ||
            fabs(forgetting - runtime->forgetting_rate) > 1e-15)
            goto done;
    }

    for (i = 0; i < count; ++i) {
        char suffix[64];
        char *row = NULL;
        size_t row_size = 0u;
        runtime_observation observation = {0};
        snprintf(suffix, sizeof(suffix), "observation/%012zu", i + 1u);
        if (!fetch_value(runtime, suffix, &row, &row_size) ||
            !row ||
            !deserialize_observation(row, row_size, &observation) ||
            !append_loaded_observation(runtime, &observation)) {
            free(row);
            free_observation(&observation);
            goto done;
        }
        free(row);
    }
    ok = runtime->observation_count == count;

done:
    free(schema);
    free(count_text);
    free(within_text);
    free(lag_text);
    free(forget_text);
    return ok;
}

static int same_identity(
    const runtime_observation *observation,
    const char *hierarchy_id,
    const char *source_id,
    unsigned long sequence
) {
    return observation &&
           observation->sequence == sequence &&
           strcmp(observation->hierarchy_id, hierarchy_id) == 0 &&
           strcmp(observation->source_id, source_id) == 0;
}

static int persist_observation(
    memoria_structural_text_runtime *runtime,
    const runtime_observation *observation
) {
    bdr_atomic_c_operation ops[6];
    char keys[6][KEY_CAP];
    char schema[32];
    char count[64];
    char within[64];
    char lag[64];
    char forgetting[96];
    char suffix[64];
    char *row = NULL;
    size_t row_size = 0u;
    bdr_atomic_c_batch_result result = {0};
    size_t i;

    if (!runtime || !observation ||
        !serialize_observation(observation, &row, &row_size))
        return 0;

    snprintf(schema, sizeof(schema), "%u", STRUCTURAL_TEXT_RUNTIME_SCHEMA);
    snprintf(count, sizeof(count), "%zu", runtime->observation_count + 1u);
    snprintf(within, sizeof(within), "%zu", runtime->max_within_distance);
    snprintf(lag, sizeof(lag), "%zu", runtime->max_event_lag);
    snprintf(forgetting, sizeof(forgetting), "%.17g", runtime->forgetting_rate);
    snprintf(
        suffix,
        sizeof(suffix),
        "observation/%012zu",
        runtime->observation_count + 1u
    );

    if (!make_key(runtime, keys[0], KEY_CAP, "meta/schema") ||
        !make_key(runtime, keys[1], KEY_CAP, "meta/count") ||
        !make_key(runtime, keys[2], KEY_CAP, "meta/max_within_distance") ||
        !make_key(runtime, keys[3], KEY_CAP, "meta/max_event_lag") ||
        !make_key(runtime, keys[4], KEY_CAP, "meta/forgetting_rate") ||
        !make_key(runtime, keys[5], KEY_CAP, suffix)) {
        free(row);
        return 0;
    }

    for (i = 0; i < 6u; ++i) {
        ops[i].type = BDR_ATOMIC_C_PUT;
        ops[i].key = keys[i];
        ops[i].key_size = strlen(keys[i]);
    }
    ops[0].value = schema; ops[0].value_size = strlen(schema);
    ops[1].value = count; ops[1].value_size = strlen(count);
    ops[2].value = within; ops[2].value_size = strlen(within);
    ops[3].value = lag; ops[3].value_size = strlen(lag);
    ops[4].value = forgetting; ops[4].value_size = strlen(forgetting);
    ops[5].value = row; ops[5].value_size = row_size;

    i = bdr_atomic_c_write_batch(
        runtime->db, ops, 6u, &result
    ) == BDR_ATOMIC_C_OK &&
        result.durable == 1 &&
        result.operations == 6u;
    free(row);
    return (int)i;
}

int memoria_structural_text_runtime_open_shared(
    bdr_atomic_c_handle *db,
    const char *organization_id,
    size_t max_within_distance,
    size_t max_event_lag,
    double forgetting_rate,
    memoria_structural_text_runtime **out
) {
    memoria_structural_text_runtime *runtime;
    if (!db || !organization_id || !*organization_id ||
        max_within_distance < 1u || max_event_lag < 1u ||
        forgetting_rate < 0.0 || !isfinite(forgetting_rate) || !out)
        return 0;
    *out = NULL;
    if (bdr_atomic_c_abi_version() != BDR_ATOMIC_C_ABI_VERSION ||
        bdr_atomic_c_integrity_check(db) != BDR_ATOMIC_C_OK)
        return 0;
    runtime = (memoria_structural_text_runtime *)calloc(1u, sizeof(*runtime));
    if (!runtime) return 0;
    runtime->db = db;
    runtime->org = dup_text(organization_id);
    runtime->max_within_distance = max_within_distance;
    runtime->max_event_lag = max_event_lag;
    runtime->forgetting_rate = forgetting_rate;
    if (!runtime->org || !load_persisted(runtime)) {
        memoria_structural_text_runtime_close(runtime);
        return 0;
    }
    *out = runtime;
    return 1;
}

int memoria_structural_text_runtime_observe(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id,
    const char *source_id,
    const char *source_kind,
    unsigned long sequence,
    const char *text,
    int *duplicate
) {
    runtime_observation observation = {0};
    uint64_t *symbols = NULL;
    size_t symbol_count = 0u;
    size_t i;
    runtime_hierarchy *hierarchy;
    if (duplicate) *duplicate = 0;
    if (!runtime || !hierarchy_id || !*hierarchy_id ||
        !source_id || !*source_id ||
        !source_kind || !*source_kind ||
        !text || !*text ||
        !tokenize_alloc(text, &symbols, &symbol_count))
        return 0;
    free(symbols);

    for (i = 0; i < runtime->observation_count; ++i) {
        const runtime_observation *existing = &runtime->observations[i];
        if (!same_identity(existing, hierarchy_id, source_id, sequence))
            continue;
        if (strcmp(existing->text, text) == 0 &&
            strcmp(existing->source_kind, source_kind) == 0) {
            if (duplicate) *duplicate = 1;
            return 1;
        }
        return 0;
    }

    observation.hierarchy_id = dup_text(hierarchy_id);
    observation.source_id = dup_text(source_id);
    observation.source_kind = dup_text(source_kind);
    observation.text = dup_text(text);
    observation.sequence = sequence;
    if (!observation.hierarchy_id || !observation.source_id ||
        !observation.source_kind || !observation.text ||
        !reserve_observations(runtime, runtime->observation_count + 1u)) {
        free_observation(&observation);
        return 0;
    }

    hierarchy = get_or_create_hierarchy(runtime, hierarchy_id);
    if (!hierarchy || !persist_observation(runtime, &observation)) {
        free_observation(&observation);
        return 0;
    }

    if (!tokenize_alloc(text, &symbols, &symbol_count) ||
        !memoria_structural_text_field_observe(
            hierarchy->field, symbols, symbol_count
        )) {
        free(symbols);
        free_observation(&observation);
        /*
         * Durable raw observation already exists. Cold reopen deterministically
         * repairs this process-local failure by replaying the persisted suffix.
         */
        return 0;
    }
    free(symbols);
    runtime->observations[runtime->observation_count++] = observation;
    return 1;
}

static void free_context(memoria_structural_text_context *context) {
    size_t i;
    if (!context) return;
    free(context->source_hierarchy_id);
    free(context->source_text);
    free(context->source_id);
    free(context->source_kind);
    for (i = 0; i < context->source_id_count; ++i)
        free(context->source_ids[i]);
    free(context->source_ids);
    for (i = 0; i < context->occurrence_count; ++i) {
        free(context->occurrences[i].source_id);
        free(context->occurrences[i].source_text);
        free(context->occurrences[i].source_kind);
    }
    free(context->occurrences);
    memset(context, 0, sizeof(*context));
}

void memoria_structural_text_contexts_free(
    memoria_structural_text_context *contexts,
    size_t count
) {
    size_t i;
    if (!contexts) return;
    for (i = 0; i < count; ++i) free_context(&contexts[i]);
    free(contexts);
}

static int context_add_source_id(
    memoria_structural_text_context *context,
    const runtime_observation *observation,
    int include_occurrence
) {
    char **grown;
    char *copy;
    memoria_structural_text_occurrence occurrence = {0};
    memoria_structural_text_occurrence *grown_occurrences;
    size_t i;
    const char *source_id;
    if (!context || !observation || !observation->source_id ||
        !*observation->source_id) return 0;
    source_id = observation->source_id;
    for (i = 0; i < context->source_id_count; ++i)
        if (strcmp(context->source_ids[i], source_id) == 0) return 1;
    copy = dup_text(source_id);
    if (!copy) return 0;
    if (include_occurrence) {
        occurrence.source_id = dup_text(source_id);
        occurrence.source_text = dup_text(observation->text);
        occurrence.source_kind = dup_text(observation->source_kind);
        occurrence.sequence = observation->sequence;
        if (!occurrence.source_id || !occurrence.source_text ||
            !occurrence.source_kind) goto fail;
    }
    grown = (char **)realloc(
        context->source_ids,
        (context->source_id_count + 1u) * sizeof(*grown)
    );
    if (!grown) goto fail;
    context->source_ids = grown;
    if (include_occurrence) {
        grown_occurrences = (memoria_structural_text_occurrence *)realloc(
            context->occurrences,
            (context->occurrence_count + 1u) * sizeof(*grown_occurrences)
        );
        if (!grown_occurrences) goto fail;
        context->occurrences = grown_occurrences;
        context->occurrences[context->occurrence_count++] = occurrence;
    }
    context->source_ids[context->source_id_count++] = copy;
    return 1;
fail:
    free(copy);
    free(occurrence.source_id);
    free(occurrence.source_text);
    free(occurrence.source_kind);
    return 0;
}

static int context_set_source(
    memoria_structural_text_context *context,
    const runtime_observation *observation
) {
    char *text = dup_text(observation->text);
    char *source_id = dup_text(observation->source_id);
    char *source_kind = dup_text(observation->source_kind);
    char *source_hierarchy_id = dup_text(observation->hierarchy_id);
    if (!text || !source_id || !source_kind || !source_hierarchy_id) {
        free(text);
        free(source_id);
        free(source_kind);
        free(source_hierarchy_id);
        return 0;
    }
    free(context->source_text);
    free(context->source_id);
    free(context->source_kind);
    free(context->source_hierarchy_id);
    context->source_text = text;
    context->source_id = source_id;
    context->source_kind = source_kind;
    context->source_hierarchy_id = source_hierarchy_id;
    context->sequence = observation->sequence;
    return 1;
}

static int context_compare(const void *a, const void *b) {
    const memoria_structural_text_context *left =
        (const memoria_structural_text_context *)a;
    const memoria_structural_text_context *right =
        (const memoria_structural_text_context *)b;
    if (left->score < right->score) return 1;
    if (left->score > right->score) return -1;
    if (left->exact_overlap < right->exact_overlap) return 1;
    if (left->exact_overlap > right->exact_overlap) return -1;
    if (left->surface_overlap < right->surface_overlap) return 1;
    if (left->surface_overlap > right->surface_overlap) return -1;
    if (left->association_mass < right->association_mass) return 1;
    if (left->association_mass > right->association_mass) return -1;
    return strcmp(left->source_text, right->source_text);
}

static int same_symbol_trail(
    const char *text,
    const uint64_t *symbols,
    size_t symbol_count
) {
    uint64_t *previous = NULL;
    size_t previous_count = 0u;
    int same;
    if (!tokenize_alloc(text, &previous, &previous_count)) return -1;
    same = previous_count == symbol_count &&
        memcmp(previous, symbols, symbol_count * sizeof(*symbols)) == 0;
    free(previous);
    return same;
}

static size_t count_symbol_spans(
    const uint64_t *trail, size_t trail_count,
    const uint64_t *span, size_t span_count, size_t *first
) {
    size_t start, matches = 0u;
    if (!span_count || trail_count < span_count) return 0;
    for (start = 0u; start <= trail_count - span_count; ++start)
        if (memcmp(trail + start, span, span_count * sizeof(*span)) == 0) {
            if (!matches && first) *first = start;
            ++matches;
        }
    return matches;
}

static int contains_symbol_span(
    const uint64_t *trail, size_t trail_count,
    const uint64_t *span, size_t span_count
) {
    return count_symbol_spans(trail, trail_count, span, span_count, NULL) > 0u;
}

void memoria_structural_text_region_activations_free(
    memoria_structural_region_activation *regions, size_t count
) {
    size_t i;
    if (!regions) return;
    for (i = 0u; i < count; ++i) free(regions[i].hierarchy_id);
    free(regions);
}

static int region_activation_compare(const void *a, const void *b) {
    const memoria_structural_region_activation *left = a, *right = b;
    if (left->max_exact_overlap != right->max_exact_overlap)
        return left->max_exact_overlap < right->max_exact_overlap ? 1 : -1;
    if (left->distinct_count != right->distinct_count)
        return left->distinct_count < right->distinct_count ? 1 : -1;
    if (left->query_echo_count != right->query_echo_count)
        return left->query_echo_count > right->query_echo_count ? 1 : -1;
    return strcmp(left->hierarchy_id, right->hierarchy_id);
}

static int region_id_compare(const void *a, const void *b) {
    const memoria_structural_region_activation *left = a, *right = b;
    return strcmp(left->hierarchy_id, right->hierarchy_id);
}

static memoria_structural_region_activation *find_region(
    memoria_structural_region_activation *regions, size_t count,
    const char *hierarchy_id
) {
    size_t low = 0u, high = count;
    while (low < high) {
        size_t mid = low + (high - low) / 2u;
        int order = strcmp(regions[mid].hierarchy_id, hierarchy_id);
        if (order < 0) low = mid + 1u;
        else if (order > 0) high = mid;
        else return &regions[mid];
    }
    return NULL;
}

int memoria_structural_text_runtime_activate_regions(
    const memoria_structural_text_runtime *runtime,
    const char *query,
    memoria_structural_region_activation **out_regions,
    size_t *out_count,
    size_t *out_unseen_query_symbols
) {
    uint64_t *query_symbols = NULL;
    unsigned char *query_seen = NULL;
    size_t *ordered_runs = NULL;
    size_t query_count = 0u, count = 0u, i, retained = 0u;
    memoria_structural_region_activation *regions = NULL;
    if (!runtime || !query || !*query || !out_regions || !out_count ||
        !out_unseen_query_symbols)
        return 0;
    *out_regions = NULL;
    *out_count = 0u;
    *out_unseen_query_symbols = 0u;
    if (!tokenize_alloc(query, &query_symbols, &query_count)) return 0;
    query_seen = calloc(query_count, sizeof(*query_seen));
    ordered_runs = calloc(query_count + 1u, sizeof(*ordered_runs));
    regions = calloc(runtime->hierarchy_count ? runtime->hierarchy_count : 1u,
                     sizeof(*regions));
    if (!regions || !query_seen || !ordered_runs) goto fail;
    for (i = 0u; i < runtime->hierarchy_count; ++i) {
        const char *id = runtime->hierarchies[i].hierarchy_id;
        if (strncmp(id, "conversation:", 13) != 0) continue;
        regions[count].hierarchy_id = dup_text(id);
        if (!regions[count].hierarchy_id) goto fail;
        ++count;
    }
    qsort(regions, count, sizeof(*regions), region_id_compare);
    for (i = 0u; i < runtime->observation_count; ++i) {
        const runtime_observation *item = &runtime->observations[i];
        memoria_structural_region_activation *region =
            find_region(regions, count, item->hierarchy_id);
        uint64_t *symbols = NULL;
        size_t symbol_count = 0u, q, s, overlap = 0u;
        if (!region) continue;
        if (!region->observation_count || item->sequence < region->first_sequence)
            region->first_sequence = item->sequence;
        if (!region->observation_count || item->sequence > region->last_sequence)
            region->last_sequence = item->sequence;
        ++region->observation_count;
        if (strcmp(item->source_kind, "user_turn") != 0 &&
            strcmp(item->source_kind, "user_assertion") != 0) continue;
        if (!tokenize_alloc(item->text, &symbols, &symbol_count)) goto fail;
        for (q = 0u; q < query_count; ++q) {
            for (s = 0u; s < symbol_count; ++s)
                if (query_symbols[q] == symbols[s]) break;
            if (s < symbol_count) {
                ++overlap;
                query_seen[q] = 1u;
            }
        }
        if (overlap) {
            ++region->matching_count;
            if (symbol_count == query_count &&
                memcmp(symbols, query_symbols,
                       query_count * sizeof(*symbols)) == 0) {
                ++region->query_echo_count;
            } else {
                size_t span = 0u, candidate_index;
                ++region->distinct_count;
                if (symbol_count > query_count && contains_symbol_span(
                        symbols, symbol_count, query_symbols, query_count))
                    ++region->embedded_query_count;
                memset(ordered_runs, 0,
                       (query_count + 1u) * sizeof(*ordered_runs));
                for (candidate_index = 0u; candidate_index < symbol_count;
                     ++candidate_index) {
                    size_t query_index = query_count;
                    while (query_index > 0u) {
                        ordered_runs[query_index] =
                            symbols[candidate_index] == query_symbols[query_index - 1u] ?
                            ordered_runs[query_index - 1u] + 1u : 0u;
                        if (ordered_runs[query_index] > span)
                            span = ordered_runs[query_index];
                        --query_index;
                    }
                }
                if (span > region->max_ordered_span ||
                    (span == region->max_ordered_span &&
                     (!region->witness_source_id ||
                      item->sequence < region->witness_sequence ||
                      (item->sequence == region->witness_sequence &&
                       strcmp(item->source_id, region->witness_source_id) < 0)))) {
                    region->max_ordered_span = span;
                    region->witness_source_id = item->source_id;
                    region->witness_source_kind = item->source_kind;
                    region->witness_sequence = item->sequence;
                }
                if (overlap > region->max_exact_overlap)
                    region->max_exact_overlap = overlap;
            }
        }
        free(symbols);
    }
    for (i = 0u; i < count; ++i) {
        if (regions[i].matching_count) {
            if (retained != i) regions[retained] = regions[i];
            ++retained;
        } else {
            free(regions[i].hierarchy_id);
        }
    }
    for (i = 0u; i < query_count; ++i)
        if (!query_seen[i]) ++*out_unseen_query_symbols;
    free(query_seen);
    free(ordered_runs);
    free(query_symbols);
    qsort(regions, retained, sizeof(*regions), region_activation_compare);
    *out_regions = regions;
    *out_count = retained;
    return 1;
fail:
    free(query_seen);
    free(ordered_runs);
    free(query_symbols);
    memoria_structural_text_region_activations_free(regions, count);
    return 0;
}

void memoria_structural_text_trail_recurrences_free(
    memoria_structural_trail_recurrence *groups, size_t count
) {
    size_t i, j;
    if (!groups) return;
    for (i = 0u; i < count; ++i) {
        free(groups[i].source_id);
        free(groups[i].hierarchy_id);
        free(groups[i].symbols);
        free(groups[i].region_ids);
        for (j = 0u; j < groups[i].source_count; ++j) {
            free(groups[i].sources[j].source_id);
            free(groups[i].sources[j].hierarchy_id);
        }
        free(groups[i].sources);
    }
    free(groups);
}

static int recurrence_add_source(
    memoria_structural_trail_recurrence *group,
    const runtime_observation *item
) {
    memoria_structural_trail_source *grown, *source;
    size_t next;
    if (group->source_count >= 16u) return 1;
    if (group->source_count == group->source_capacity) {
        next = group->source_capacity ? group->source_capacity * 2u : 2u;
        grown = realloc(group->sources, next * sizeof(*grown));
        if (!grown) return 0;
        group->sources = grown;
        group->source_capacity = next;
    }
    source = &group->sources[group->source_count];
    source->source_id = dup_text(item->source_id);
    source->hierarchy_id = dup_text(item->hierarchy_id);
    source->sequence = item->sequence;
    if (!source->source_id || !source->hierarchy_id) {
        free(source->source_id);
        free(source->hierarchy_id);
        memset(source, 0, sizeof(*source));
        return 0;
    }
    ++group->source_count;
    return 1;
}

static void recurrence_fingerprint(
    const uint64_t *symbols, size_t count, char out[17]
) {
    uint64_t hash = UINT64_C(14695981039346656037);
    size_t i, byte;
    for (i = 0u; i < count; ++i)
        for (byte = 0u; byte < 8u; ++byte) {
            hash ^= (symbols[i] >> (byte * 8u)) & UINT64_C(0xff);
            hash *= UINT64_C(1099511628211);
        }
    snprintf(out, 17u, "%016llx", (unsigned long long)hash);
}

int memoria_structural_text_runtime_trail_recurrence(
    const memoria_structural_text_runtime *runtime,
    const char *query,
    memoria_structural_trail_recurrence **out_groups,
    size_t *out_count
) {
    uint64_t *query_symbols = NULL;
    size_t query_count = 0u, count = 0u, capacity = 0u, i;
    memoria_structural_trail_recurrence *groups = NULL;
    if (!runtime || !query || !*query || !out_groups || !out_count) return 0;
    *out_groups = NULL;
    *out_count = 0u;
    if (!tokenize_alloc(query, &query_symbols, &query_count)) return 0;
    for (i = 0u; i < runtime->observation_count; ++i) {
        const runtime_observation *item = &runtime->observations[i];
        uint64_t *symbols = NULL;
        size_t symbol_count = 0u, overlap = 0u, q, s, j;
        memoria_structural_trail_recurrence *group;
        if (strncmp(item->hierarchy_id, "conversation:", 13) != 0 ||
            (strcmp(item->source_kind, "user_turn") != 0 &&
             strcmp(item->source_kind, "user_assertion") != 0)) continue;
        if (!tokenize_alloc(item->text, &symbols, &symbol_count)) goto fail;
        for (q = 0u; q < query_count; ++q) {
            for (s = 0u; s < symbol_count; ++s)
                if (query_symbols[q] == symbols[s]) break;
            if (s < symbol_count) ++overlap;
        }
        if (!overlap) { free(symbols); continue; }
        for (j = 0u; j < count; ++j)
            if (groups[j].symbol_count == symbol_count &&
                memcmp(groups[j].symbols, symbols,
                       symbol_count * sizeof(*symbols)) == 0) break;
        if (j == count) {
            memoria_structural_trail_recurrence *grown;
            if (count == capacity) {
                size_t next = capacity ? capacity * 2u : 8u;
                if (next < capacity || next > ((size_t)-1) / sizeof(*groups)) {
                    free(symbols); goto fail;
                }
                grown = realloc(groups, next * sizeof(*groups));
                if (!grown) { free(symbols); goto fail; }
                groups = grown;
                memset(groups + capacity, 0,
                       (next - capacity) * sizeof(*groups));
                capacity = next;
            }
            group = &groups[count];
            group->source_id = dup_text(item->source_id);
            group->hierarchy_id = dup_text(item->hierarchy_id);
            if (!group->source_id || !group->hierarchy_id) {
                free(symbols);
                memoria_structural_text_trail_recurrences_free(groups, count + 1u);
                free(query_symbols);
                return 0;
            }
            group->symbols = symbols;
            group->symbol_count = symbol_count;
            group->exact_overlap = overlap;
            group->query_echo = symbol_count == query_count &&
                memcmp(symbols, query_symbols,
                       query_count * sizeof(*symbols)) == 0;
            if (symbol_count > query_count) {
                group->embedded_positions = count_symbol_spans(
                    symbols, symbol_count, query_symbols, query_count,
                    &group->embedded_start);
                group->contains_query_trail = group->embedded_positions > 0u;
                if (group->contains_query_trail)
                    group->embedded_length = query_count;
            }
            recurrence_fingerprint(symbols, symbol_count, group->fingerprint);
            ++count;
        } else {
            group = &groups[j];
            free(symbols);
        }
        if (!recurrence_add_source(group, item)) goto fail;
        ++group->occurrences;
        for (j = 0u; j < group->region_count; ++j)
            if (strcmp(group->region_ids[j], item->hierarchy_id) == 0) break;
        if (j == group->region_count) {
            const char **grown;
            if (group->region_count == group->region_capacity) {
                size_t next = group->region_capacity ?
                    group->region_capacity * 2u : 2u;
                if (next < group->region_capacity ||
                    next > ((size_t)-1) / sizeof(*grown)) goto fail;
                grown = realloc(group->region_ids, next * sizeof(*grown));
                if (!grown) goto fail;
                group->region_ids = grown;
                group->region_capacity = next;
            }
            group->region_ids[group->region_count++] = item->hierarchy_id;
        }
    }
    {
        const char *observed_base = NULL;
        for (i = 0u; i < count; ++i)
            if (groups[i].query_echo) {
                observed_base = groups[i].fingerprint;
                break;
            }
        if (observed_base)
            for (i = 0u; i < count; ++i)
                if (groups[i].contains_query_trail)
                    memcpy(groups[i].composed_base_address,
                           observed_base, sizeof(groups[i].composed_base_address));
    }
    for (i = 0u; i < count; ++i) {
        size_t j;
        for (j = i + 1u; j < count; ++j) {
            size_t prefix = 0u;
            memoria_structural_trail_recurrence *left = &groups[i];
            memoria_structural_trail_recurrence *right = &groups[j];
            size_t shorter = left->symbol_count < right->symbol_count ?
                left->symbol_count : right->symbol_count;
            while (prefix < shorter &&
                   left->symbols[prefix] == right->symbols[prefix]) ++prefix;
            /* A prefix extension is not a fork: both trails need a next symbol. */
            if (!prefix || prefix == shorter) continue;
            if (prefix > left->branch_depth) {
                left->branch_depth = prefix;
                left->divergent_trail_count = 1u;
                recurrence_fingerprint(left->symbols, prefix,
                                       left->branch_address);
            } else if (prefix == left->branch_depth) {
                ++left->divergent_trail_count;
            }
            if (prefix > right->branch_depth) {
                right->branch_depth = prefix;
                right->divergent_trail_count = 1u;
                recurrence_fingerprint(right->symbols, prefix,
                                       right->branch_address);
            } else if (prefix == right->branch_depth) {
                ++right->divergent_trail_count;
            }
        }
    }
    free(query_symbols);
    *out_groups = groups;
    *out_count = count;
    return 1;
fail:
    free(query_symbols);
    memoria_structural_text_trail_recurrences_free(groups, count);
    return 0;
}

static int resolve_text_impl(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id,
    const char *query,
    size_t top_k,
    memoria_structural_text_context **out_contexts,
    size_t *out_count,
    int window_group,
    int personal_evidence
) {
    const runtime_hierarchy *hierarchy;
    uint64_t *query_symbols = NULL;
    size_t *query_frequency = NULL;
    double query_weight_total = 0.0;
    size_t query_count = 0u;
    memoria_structural_text_context *contexts = NULL;
    size_t context_count = 0u;
    size_t context_capacity = 0u;
    size_t i;
    if (!runtime || !hierarchy_id || !*hierarchy_id ||
        !query || !*query || top_k < 1u ||
        !out_contexts || !out_count)
        return 0;
    *out_contexts = NULL;
    *out_count = 0u;
    hierarchy = find_hierarchy_const(runtime, hierarchy_id);
    if (!hierarchy && !personal_evidence) return 1;
    if (!tokenize_alloc(query, &query_symbols, &query_count)) return 0;
    if (personal_evidence) {
        query_frequency = (size_t *)calloc(query_count, sizeof(*query_frequency));
        if (!query_frequency) { free(query_symbols); return 0; }
        for (i = 0; i < runtime->observation_count; ++i) {
            const runtime_observation *item = &runtime->observations[i];
            uint64_t *symbols = NULL;
            size_t count = 0u, q, s;
            if (strncmp(item->hierarchy_id, "conversation:", 13) != 0 ||
                (strcmp(item->source_kind, "user_turn") != 0 &&
                 strcmp(item->source_kind, "user_assertion") != 0)) continue;
            if (!tokenize_alloc(item->text, &symbols, &count)) {
                free(query_frequency); free(query_symbols); return 0;
            }
            for (q = 0; q < query_count; ++q)
                for (s = 0; s < count; ++s)
                    if (query_symbols[q] == symbols[s]) {
                        ++query_frequency[q]; break;
                    }
            free(symbols);
        }
        for (i = 0; i < query_count; ++i)
            query_weight_total += 1.0 / (1.0 + (double)query_frequency[i]);
    }

    for (i = 0; i < runtime->observation_count; ++i) {
        const runtime_observation *observation = &runtime->observations[i];
        uint64_t *candidate_symbols = NULL;
        size_t candidate_count = 0u;
        memoria_structural_text_score score;
        size_t j;
        memoria_structural_text_context *context = NULL;
        if (!personal_evidence &&
            strcmp(observation->hierarchy_id, hierarchy_id) != 0)
            continue;
        if (personal_evidence &&
            (strncmp(observation->hierarchy_id, "conversation:", 13) != 0 ||
             (strcmp(observation->source_kind, "user_turn") != 0 &&
              strcmp(observation->source_kind, "user_assertion") != 0)))
            continue;
        if (!tokenize_alloc(
            observation->text, &candidate_symbols, &candidate_count
        )) {
            memoria_structural_text_contexts_free(contexts, context_count);
            free(query_frequency); free(query_symbols);
            return 0;
        }
        if (!memoria_structural_text_score_candidate(
            personal_evidence ?
                find_hierarchy_const(runtime, observation->hierarchy_id)->field :
                hierarchy->field,
            query_symbols,
            query_count,
            candidate_symbols,
            candidate_count,
            &score
        )) {
            free(candidate_symbols);
            memoria_structural_text_contexts_free(contexts, context_count);
            free(query_frequency); free(query_symbols);
            return 0;
        }
        if (!memoria_structural_text_surface_overlap(
            query, observation->text, &score.surface_overlap
        )) {
            free(candidate_symbols);
            memoria_structural_text_contexts_free(contexts, context_count);
            free(query_frequency); free(query_symbols);
            return 0;
        }
        score.score += 0.4 * (double)score.surface_overlap / (double)query_count;
        if (personal_evidence) {
            size_t k, novel = 0u;
            double shared_weight = 0.0;
            for (k = 0; k < candidate_count; ++k) {
                size_t q;
                for (q = 0; q < query_count; ++q)
                    if (candidate_symbols[k] == query_symbols[q]) break;
                if (q == query_count) ++novel;
            }
            /* A repeated question supplies no new evidence. For old records
             * tagged user_assertion, the tag alone cannot establish truth. */
            if (!novel || (score.exact_overlap < 2u &&
                           score.surface_overlap < 2u)) {
                free(candidate_symbols);
                continue;
            }
            for (k = 0; k < query_count; ++k) {
                size_t c;
                for (c = 0; c < candidate_count; ++c)
                    if (query_symbols[k] == candidate_symbols[c]) {
                        shared_weight += 1.0 / (1.0 + (double)query_frequency[k]);
                        break;
                    }
            }
            /* Rare shared symbols carry more regional evidence than common
             * query scaffolding. Associations only break close ties. */
            score.score = shared_weight / query_weight_total +
                0.05 * score.association_mass;
        }
        if (score.score <= 0.0) {
            free(candidate_symbols);
            continue;
        }

        for (j = 0; j < context_count; ++j) {
            int same = strcmp(contexts[j].source_text, observation->text) == 0;
            if (personal_evidence && strcmp(
                contexts[j].source_hierarchy_id,
                observation->hierarchy_id
            ) != 0) same = 0;
            if (window_group &&
                strcmp(contexts[j].source_kind, observation->source_kind) != 0)
                same = 0;
            if (!same && window_group &&
                strcmp(contexts[j].source_kind, observation->source_kind) == 0)
                same = same_symbol_trail(
                    contexts[j].source_text, candidate_symbols, candidate_count
                );
            if (same < 0) {
                free(candidate_symbols);
                memoria_structural_text_contexts_free(contexts, context_count);
                free(query_frequency); free(query_symbols);
                return 0;
            }
            if (same) {
                context = &contexts[j];
                break;
            }
        }
        free(candidate_symbols);
        if (!context) {
            if (context_count == context_capacity) {
                size_t capacity = context_capacity ? context_capacity * 2u : 8u;
                memoria_structural_text_context *grown =
                    (memoria_structural_text_context *)realloc(
                        contexts, capacity * sizeof(*grown)
                    );
                if (!grown) {
                    memoria_structural_text_contexts_free(
                        contexts, context_count
                    );
                    free(query_frequency); free(query_symbols);
                    return 0;
                }
                contexts = grown;
                memset(
                    contexts + context_capacity,
                    0,
                    (capacity - context_capacity) * sizeof(*contexts)
                );
                context_capacity = capacity;
            }
            context = &contexts[context_count++];
            if (!context_set_source(context, observation) ||
                !context_add_source_id(context, observation, window_group)) {
                memoria_structural_text_contexts_free(contexts, context_count);
                free(query_frequency); free(query_symbols);
                return 0;
            }
            context->score = score.score;
            context->exact_overlap = score.exact_overlap;
            context->surface_overlap = score.surface_overlap;
            context->association_mass = score.association_mass;
            context->repetitions = 1u;
        } else {
            if (!context_add_source_id(context, observation, window_group)) {
                memoria_structural_text_contexts_free(contexts, context_count);
                free(query_frequency); free(query_symbols);
                return 0;
            }
            ++context->repetitions;
            if (score.score > context->score ||
                (score.score == context->score &&
                 score.exact_overlap > context->exact_overlap) ||
                (score.score == context->score &&
                 score.exact_overlap == context->exact_overlap &&
                 score.association_mass > context->association_mass)) {
                if (!context_set_source(context, observation)) {
                    memoria_structural_text_contexts_free(
                        contexts, context_count
                    );
                    free(query_frequency); free(query_symbols);
                    return 0;
                }
                context->score = score.score;
                context->exact_overlap = score.exact_overlap;
                context->surface_overlap = score.surface_overlap;
                context->association_mass = score.association_mass;
            }
        }
    }
    free(query_frequency); free(query_symbols);

    qsort(
        contexts,
        context_count,
        sizeof(*contexts),
        context_compare
    );
    /*
     * When a query has a candidate with two distinct directly shared
     * symbols, other candidates supported by only one shared symbol (or
     * indirect temporal association alone) are weak distractors. Keep the
     * association-only path when no candidate has that direct support.
     * This is an evidence threshold, independent of particular words.
     */
    {
        size_t strongest_exact = 0u;
        size_t kept = 0u;
        size_t strongest_surface = 0u;
        for (i = 0; i < context_count; ++i) {
            if (contexts[i].exact_overlap > strongest_exact)
                strongest_exact = contexts[i].exact_overlap;
            if (contexts[i].surface_overlap > strongest_surface)
                strongest_surface = contexts[i].surface_overlap;
        }
        if (strongest_exact >= 2u ||
            (strongest_exact == 0u && strongest_surface > 0u)) {
            for (i = 0; i < context_count; ++i) {
                if ((strongest_exact >= 2u && contexts[i].exact_overlap < 2u) ||
                    (strongest_exact == 0u && strongest_surface > 0u &&
                     contexts[i].surface_overlap == 0u)) {
                    free_context(&contexts[i]);
                    memset(&contexts[i], 0, sizeof(contexts[i]));
                    continue;
                }
                if (kept != i) {
                    contexts[kept] = contexts[i];
                    memset(&contexts[i], 0, sizeof(contexts[i]));
                }
                ++kept;
            }
            context_count = kept;
        }
    }
    if (context_count > top_k) {
        for (i = top_k; i < context_count; ++i)
            free_context(&contexts[i]);
        context_count = top_k;
    }
    *out_contexts = contexts;
    *out_count = context_count;
    return 1;
}

int memoria_structural_text_runtime_resolve(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id,
    const char *query,
    size_t top_k,
    memoria_structural_text_context **out_contexts,
    size_t *out_count
) {
    return resolve_text_impl(
        runtime, hierarchy_id, query, top_k, out_contexts, out_count, 0, 0
    );
}

int memoria_structural_text_runtime_resolve_window_group(
    memoria_structural_text_runtime *runtime,
    const char *hierarchy_id,
    const char *query,
    size_t top_k,
    memoria_structural_text_context **out_contexts,
    size_t *out_count
) {
    return resolve_text_impl(
        runtime, hierarchy_id, query, top_k, out_contexts, out_count, 1, 0
    );
}

int memoria_structural_text_runtime_resolve_personal_evidence(
    memoria_structural_text_runtime *runtime,
    const char *current_hierarchy_id,
    const char *query,
    size_t top_k,
    memoria_structural_text_context **out_contexts,
    size_t *out_count
) {
    return resolve_text_impl(runtime, current_hierarchy_id, query, top_k,
                             out_contexts, out_count, 0, 1);
}

size_t memoria_structural_text_runtime_window_revision(
    const memoria_structural_text_runtime *runtime,
    const char *hierarchy_id
) {
    size_t i, count = 0u;
    if (!runtime || !hierarchy_id) return 0u;
    for (i = 0u; i < runtime->observation_count; ++i)
        if (strcmp(runtime->observations[i].hierarchy_id, hierarchy_id) == 0)
            ++count;
    return count;
}

size_t memoria_structural_text_runtime_observation_count(
    const memoria_structural_text_runtime *runtime
) {
    return runtime ? runtime->observation_count : 0u;
}

int memoria_structural_text_runtime_observation_at(
    const memoria_structural_text_runtime *runtime,
    size_t index,
    memoria_structural_text_observation_view *out
) {
    const runtime_observation *observation;
    if (!runtime || !out || index >= runtime->observation_count) return 0;
    observation = &runtime->observations[index];
    out->hierarchy_id = observation->hierarchy_id;
    out->source_id = observation->source_id;
    out->source_kind = observation->source_kind;
    out->text = observation->text;
    out->sequence = observation->sequence;
    return 1;
}

size_t memoria_structural_text_runtime_hierarchy_count(
    const memoria_structural_text_runtime *runtime
) {
    return runtime ? runtime->hierarchy_count : 0u;
}

size_t memoria_structural_text_runtime_edge_count(
    const memoria_structural_text_runtime *runtime,
    const char *hierarchy_id
) {
    const runtime_hierarchy *hierarchy =
        find_hierarchy_const(runtime, hierarchy_id);
    return hierarchy
        ? memoria_structural_text_field_edge_count(hierarchy->field)
        : 0u;
}

int memoria_structural_text_runtime_sync(
    memoria_structural_text_runtime *runtime
) {
    return runtime &&
        bdr_atomic_c_sync(runtime->db) == BDR_ATOMIC_C_OK;
}

void memoria_structural_text_runtime_close(
    memoria_structural_text_runtime *runtime
) {
    size_t i;
    if (!runtime) return;
    for (i = 0; i < runtime->observation_count; ++i)
        free_observation(&runtime->observations[i]);
    for (i = 0; i < runtime->hierarchy_count; ++i) {
        free(runtime->hierarchies[i].hierarchy_id);
        memoria_structural_text_field_destroy(
            runtime->hierarchies[i].field
        );
    }
    free(runtime->observations);
    free(runtime->hierarchies);
    free(runtime->org);
    free(runtime);
}
