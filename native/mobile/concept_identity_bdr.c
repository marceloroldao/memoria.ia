#include "concept_identity_bdr.h"
#include "bdr/atomic_c_api.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CONCEPT_STATE_SCHEMA 1u
#define KEY_CAP 384u
#define ROW_CAP 4096u

struct memoria_concept_bdr {
    bdr_atomic_c_handle *db;
    char *org;
};

static char *dup_text(const char *s) {
    size_t n;
    char *out;
    if (!s) s = "";
    n = strlen(s) + 1u;
    out = (char *)malloc(n);
    if (out) memcpy(out, s, n);
    return out;
}

static int make_key(memoria_concept_bdr *store, char *dst, size_t cap, const char *suffix) {
    int n;
    if (!store || !dst || !suffix) return 0;
    n = snprintf(dst, cap, "memoria-mobile/v1/%s/concept-state/%s", store->org, suffix);
    return n > 0 && (size_t)n < cap;
}

static int append_bytes(char *dst, size_t cap, size_t *used, const char *src, size_t n) {
    if (!dst || !used || !src || *used + n >= cap) return 0;
    memcpy(dst + *used, src, n);
    *used += n;
    dst[*used] = 0;
    return 1;
}

static int append_field(char *dst, size_t cap, size_t *used, const char *value) {
    char lenbuf[32];
    size_t n = strlen(value ? value : "");
    int written = snprintf(lenbuf, sizeof(lenbuf), "%zu:", n);
    if (written <= 0 || (size_t)written >= sizeof(lenbuf)) return 0;
    return append_bytes(dst, cap, used, lenbuf, (size_t)written) &&
           append_bytes(dst, cap, used, value ? value : "", n);
}

static int serialize_row(const memoria_concept_state_row *row, char *dst, size_t cap) {
    char countbuf[32];
    size_t used = 0, i;
    int written;
    if (!row || !dst || !cap ||
        row->alias_count > MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT ||
        row->context_cue_count > MEMORIA_CONCEPT_MAX_CUES) return 0;
    dst[0] = 0;
    if (!append_field(dst, cap, &used, row->concept_id) ||
        !append_field(dst, cap, &used, row->namespace_name) ||
        !append_field(dst, cap, &used, row->canonical) ||
        !append_field(dst, cap, &used, row->sense_key)) return 0;
    written = snprintf(countbuf, sizeof(countbuf), "%zu:", row->alias_count);
    if (written <= 0 || (size_t)written >= sizeof(countbuf) ||
        !append_bytes(dst, cap, &used, countbuf, (size_t)written)) return 0;
    for (i = 0; i < row->alias_count; ++i)
        if (!append_field(dst, cap, &used, row->aliases[i])) return 0;
    written = snprintf(countbuf, sizeof(countbuf), "%zu:", row->context_cue_count);
    if (written <= 0 || (size_t)written >= sizeof(countbuf) ||
        !append_bytes(dst, cap, &used, countbuf, (size_t)written)) return 0;
    for (i = 0; i < row->context_cue_count; ++i)
        if (!append_field(dst, cap, &used, row->context_cues[i])) return 0;
    return 1;
}

static int parse_number(const char **cursor, size_t *remaining, size_t *value) {
    size_t v = 0, digits = 0;
    const char *p;
    if (!cursor || !*cursor || !remaining || !value) return 0;
    p = *cursor;
    while (*remaining && *p >= '0' && *p <= '9') {
        if (v > ((size_t)-1 - (size_t)(*p - '0')) / 10u) return 0;
        v = v * 10u + (size_t)(*p - '0');
        ++p; --(*remaining); ++digits;
    }
    if (!digits || !*remaining || *p != ':') return 0;
    ++p; --(*remaining);
    *cursor = p;
    *value = v;
    return 1;
}

static int parse_field(const char **cursor, size_t *remaining, char *dst, size_t cap) {
    size_t n;
    if (!parse_number(cursor, remaining, &n) || n >= cap || n > *remaining) return 0;
    memcpy(dst, *cursor, n);
    dst[n] = 0;
    *cursor += n;
    *remaining -= n;
    return 1;
}

static int deserialize_row(const char *src, size_t len, memoria_concept_state_row *row) {
    const char *cursor = src;
    size_t remaining = len, i, count;
    if (!src || !row) return 0;
    memset(row, 0, sizeof(*row));
    if (!parse_field(&cursor, &remaining, row->concept_id, sizeof(row->concept_id)) ||
        !parse_field(&cursor, &remaining, row->namespace_name, sizeof(row->namespace_name)) ||
        !parse_field(&cursor, &remaining, row->canonical, sizeof(row->canonical)) ||
        !parse_field(&cursor, &remaining, row->sense_key, sizeof(row->sense_key)) ||
        !parse_number(&cursor, &remaining, &count) || count > MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT) return 0;
    row->alias_count = count;
    for (i = 0; i < count; ++i)
        if (!parse_field(&cursor, &remaining, row->aliases[i], sizeof(row->aliases[i]))) return 0;
    if (!parse_number(&cursor, &remaining, &count) || count > MEMORIA_CONCEPT_MAX_CUES) return 0;
    row->context_cue_count = count;
    for (i = 0; i < count; ++i)
        if (!parse_field(&cursor, &remaining, row->context_cues[i], sizeof(row->context_cues[i]))) return 0;
    return remaining == 0;
}

static int fetch_text(memoria_concept_bdr *store, const char *suffix, char **out, size_t *out_size) {
    char key[KEY_CAP];
    bdr_atomic_c_buffer buffer = {0};
    bdr_atomic_c_status status;
    char *copy;
    if (!out || !make_key(store, key, sizeof(key), suffix)) return 0;
    *out = NULL;
    if (out_size) *out_size = 0;
    status = bdr_atomic_c_get(store->db, key, strlen(key), &buffer);
    if (status == BDR_ATOMIC_C_NOT_FOUND) return 1;
    if (status != BDR_ATOMIC_C_OK) return 0;
    copy = (char *)malloc(buffer.size + 1u);
    if (!copy) { bdr_atomic_c_free_buffer(buffer); return 0; }
    if (buffer.size) memcpy(copy, buffer.data, buffer.size);
    copy[buffer.size] = 0;
    if (out_size) *out_size = buffer.size;
    bdr_atomic_c_free_buffer(buffer);
    *out = copy;
    return 1;
}

int memoria_concept_bdr_open(const char *data_dir, const char *organization_id, memoria_concept_bdr **out) {
    memoria_concept_bdr *store;
    if (!data_dir || !*data_dir || !organization_id || !*organization_id || !out) return 0;
    *out = NULL;
    store = (memoria_concept_bdr *)calloc(1, sizeof(*store));
    if (!store) return 0;
    store->org = dup_text(organization_id);
    if (!store->org || bdr_atomic_c_open(data_dir, &store->db) != BDR_ATOMIC_C_OK ||
        bdr_atomic_c_abi_version() != BDR_ATOMIC_C_ABI_VERSION ||
        bdr_atomic_c_integrity_check(store->db) != BDR_ATOMIC_C_OK) {
        memoria_concept_bdr_close(store);
        return 0;
    }
    *out = store;
    return 1;
}

int memoria_concept_bdr_save(memoria_concept_bdr *store, const memoria_concept_state_row *rows, size_t row_count) {
    size_t op_count = row_count + 2u, i;
    bdr_atomic_c_operation *ops;
    char (*keys)[KEY_CAP];
    char (*values)[ROW_CAP];
    char schema[32], count[32], suffix[64];
    bdr_atomic_c_batch_result result = {0};
    int ok = 0;
    if (!store || (row_count && !rows) || row_count > MEMORIA_CONCEPT_MAX_CONCEPTS) return 0;
    ops = (bdr_atomic_c_operation *)calloc(op_count, sizeof(*ops));
    keys = (char (*)[KEY_CAP])calloc(op_count, sizeof(*keys));
    values = (char (*)[ROW_CAP])calloc(op_count, sizeof(*values));
    if (!ops || !keys || !values) goto done;
    snprintf(schema, sizeof(schema), "%u", CONCEPT_STATE_SCHEMA);
    snprintf(count, sizeof(count), "%zu", row_count);
    if (!make_key(store, keys[0], KEY_CAP, "meta/schema") || !make_key(store, keys[1], KEY_CAP, "meta/count")) goto done;
    snprintf(values[0], ROW_CAP, "%s", schema);
    snprintf(values[1], ROW_CAP, "%s", count);
    for (i = 0; i < 2u; ++i) {
        ops[i].type = BDR_ATOMIC_C_PUT;
        ops[i].key = keys[i]; ops[i].key_size = strlen(keys[i]);
        ops[i].value = values[i]; ops[i].value_size = strlen(values[i]);
    }
    for (i = 0; i < row_count; ++i) {
        snprintf(suffix, sizeof(suffix), "row/%06zu", i + 1u);
        if (!make_key(store, keys[i + 2u], KEY_CAP, suffix) || !serialize_row(&rows[i], values[i + 2u], ROW_CAP)) goto done;
        ops[i + 2u].type = BDR_ATOMIC_C_PUT;
        ops[i + 2u].key = keys[i + 2u]; ops[i + 2u].key_size = strlen(keys[i + 2u]);
        ops[i + 2u].value = values[i + 2u]; ops[i + 2u].value_size = strlen(values[i + 2u]);
    }
    ok = bdr_atomic_c_write_batch(store->db, ops, op_count, &result) == BDR_ATOMIC_C_OK &&
         result.durable == 1 && result.operations == op_count;
done:
    free(ops); free(keys); free(values);
    return ok;
}

int memoria_concept_bdr_load(memoria_concept_bdr *store, memoria_concept_state_row *rows, size_t row_capacity, size_t *row_count) {
    char *schema = NULL, *count_text = NULL, *row_text = NULL, suffix[64];
    size_t count = 0, i, row_size = 0;
    char *end = NULL;
    unsigned long schema_value;
    unsigned long count_value;
    if (!store || !rows || !row_count) return 0;
    *row_count = 0;
    if (!fetch_text(store, "meta/schema", &schema, NULL) || !fetch_text(store, "meta/count", &count_text, NULL)) goto fail;
    if (!schema && !count_text) return 1;
    if (!schema || !count_text) goto fail;
    schema_value = strtoul(schema, &end, 10);
    if (end == schema || *end || schema_value != CONCEPT_STATE_SCHEMA) goto fail;
    end = NULL;
    count_value = strtoul(count_text, &end, 10);
    if (end == count_text || *end || count_value > MEMORIA_CONCEPT_MAX_CONCEPTS || count_value > row_capacity) goto fail;
    count = (size_t)count_value;
    for (i = 0; i < count; ++i) {
        snprintf(suffix, sizeof(suffix), "row/%06zu", i + 1u);
        if (!fetch_text(store, suffix, &row_text, &row_size) || !row_text || !deserialize_row(row_text, row_size, &rows[i])) goto fail;
        free(row_text); row_text = NULL;
    }
    *row_count = count;
    free(schema); free(count_text);
    return 1;
fail:
    free(schema); free(count_text); free(row_text);
    return 0;
}

int memoria_concept_bdr_sync(memoria_concept_bdr *store) {
    return store && bdr_atomic_c_sync(store->db) == BDR_ATOMIC_C_OK;
}

void memoria_concept_bdr_close(memoria_concept_bdr *store) {
    if (!store) return;
    if (store->db) bdr_atomic_c_close(store->db);
    free(store->org);
    free(store);
}
