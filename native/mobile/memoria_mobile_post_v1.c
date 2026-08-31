/*
 * Post-v1 mobile extension layer.
 *
 * The validated v1 mobile implementation remains unchanged in memoria_mobile.c
 * and mobile_persistence_bdr.c.  This translation unit composes that frozen
 * implementation with the additive external/public-knowledge contract from
 * issue #114.  Keeping the extension here avoids rewriting the accepted v1
 * runtime while the post-v1 contract is still experimental.
 */

#include "mobile_persistence_bdr.c"

/* Wrap the validated resolver so post-v1 can add public-source conflict and
 * provenance semantics without changing the frozen implementation. */
#define memoria_mobile_resolve_context_json memoria_mobile_resolve_context_json_v1_core
#define memoria_mobile_close memoria_mobile_close_v1_core
#include "memoria_mobile.c"
#undef memoria_mobile_close
#undef memoria_mobile_resolve_context_json
#include "subconscious_mobile.h"

#define EXTERNAL_KNOWLEDGE_CLASS "external_public"
#define EXTERNAL_SOURCE_TYPE "external_import"
#define EXTERNAL_DERIVED_TYPE "derived_relation"
#define EXTERNAL_DEFAULT_AUTHORITY 0.85
#define EXTERNAL_DERIVED_AUTHORITY 0.75
#define EXTERNAL_MAX_SOURCE_FIELDS 16u

typedef struct external_request {
    char *content;
    char *namespace_id;
    char *source_url;
    char *source_domain;
    char *source_title;
    char *acquired_time;
    char *source_excerpt;
    char *provider_id;
    char *import_kind;
    char *request_id;
    char *session_id;
    char *parents[MAX_PARENTS];
    size_t parent_count;
    double validation_confidence;
} external_request;

typedef struct external_builder {
    char *data;
    size_t size;
    size_t capacity;
} external_builder;

static int external_builder_reserve(external_builder *b, size_t extra) {
    size_t needed, capacity;
    char *next;
    if (!b) return 0;
    if (extra > (size_t)-1 - b->size - 1u) return 0;
    needed = b->size + extra + 1u;
    if (needed <= b->capacity) return 1;
    capacity = b->capacity ? b->capacity : 512u;
    while (capacity < needed) {
        if (capacity > ((size_t)-1) / 2u) { capacity = needed; break; }
        capacity *= 2u;
    }
    next = (char *)realloc(b->data, capacity);
    if (!next) return 0;
    b->data = next;
    b->capacity = capacity;
    return 1;
}

static int external_builder_append(external_builder *b, const char *text) {
    size_t n;
    if (!b || !text) return 0;
    n = strlen(text);
    if (!external_builder_reserve(b, n)) return 0;
    memcpy(b->data + b->size, text, n);
    b->size += n;
    b->data[b->size] = 0;
    return 1;
}

static int external_builder_appendf(external_builder *b, const char *fmt, ...) {
    va_list args, measure;
    int needed, written;
    if (!b || !fmt) return 0;
    va_start(args, fmt);
    va_copy(measure, args);
    needed = vsnprintf(NULL, 0, fmt, measure);
    va_end(measure);
    if (needed < 0 || !external_builder_reserve(b, (size_t)needed)) {
        va_end(args);
        return 0;
    }
    written = vsnprintf(b->data + b->size, b->capacity - b->size, fmt, args);
    va_end(args);
    if (written != needed) return 0;
    b->size += (size_t)written;
    return 1;
}

static int external_nonblank(const char *s) {
    if (!s) return 0;
    while (*s) {
        if (!isspace((unsigned char)*s)) return 1;
        ++s;
    }
    return 0;
}

static int external_ci_equal(const char *a, const char *b) {
    unsigned char ca, cb;
    if (!a || !b) return a == b;
    while (*a && *b) {
        ca = (unsigned char)*a++;
        cb = (unsigned char)*b++;
        if (ca < 128u) ca = (unsigned char)tolower(ca);
        if (cb < 128u) cb = (unsigned char)tolower(cb);
        if (ca != cb) return 0;
    }
    return *a == 0 && *b == 0;
}

static int external_valid_domain(const char *domain) {
    const unsigned char *p = (const unsigned char *)domain;
    if (!external_nonblank(domain)) return 0;
    for (; *p; ++p)
        if (isspace(*p) || *p == '/' || *p == '\\') return 0;
    return 1;
}

static int external_valid_url(const char *url) {
    return url && (strncmp(url, "https://", 8) == 0 || strncmp(url, "http://", 7) == 0);
}

static char *external_normalize_text(const char *text) {
    size_t n, i, w = 0;
    int pending_space = 0;
    char *out;
    if (!text) return NULL;
    n = strlen(text);
    out = (char *)malloc(n + 1u);
    if (!out) return NULL;
    for (i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)text[i];
        if (isspace(c)) {
            if (w) pending_space = 1;
            continue;
        }
        if (pending_space) { out[w++] = ' '; pending_space = 0; }
        out[w++] = c < 128u ? (char)tolower(c) : (char)c;
    }
    out[w] = 0;
    return out;
}

static int external_relations_equal(
    const memoria_relation *a, size_t a_count,
    const memoria_relation *b, size_t b_count
) {
    size_t i;
    if (!a_count || !b_count || a_count != b_count) return 0;
    for (i = 0; i < a_count; ++i) {
        if (!external_ci_equal(a[i].subject, b[i].subject) ||
            !external_ci_equal(a[i].predicate, b[i].predicate) ||
            !external_ci_equal(a[i].object, b[i].object)) return 0;
    }
    return 1;
}

static char *external_fact_signature(const char *content, const memoria_relation *relations, size_t relation_count) {
    external_builder b = {0};
    char *normalized;
    size_t i;
    if (relation_count) {
        if (!external_builder_append(&b, "rel:")) goto fail;
        for (i = 0; i < relation_count; ++i) {
            char *s = external_normalize_text(relations[i].subject);
            char *p = external_normalize_text(relations[i].predicate);
            char *o = external_normalize_text(relations[i].object);
            if (!s || !p || !o || !external_builder_appendf(&b, "%s|%s|%s;", s, p, o)) {
                free(s); free(p); free(o); goto fail;
            }
            free(s); free(p); free(o);
        }
        return b.data;
    }
    normalized = external_normalize_text(content);
    if (!normalized) goto fail;
    if (!external_builder_appendf(&b, "txt:%s", normalized)) { free(normalized); goto fail; }
    free(normalized);
    return b.data;
fail:
    free(b.data);
    return NULL;
}

static void external_request_free(external_request *r) {
    if (!r) return;
    free(r->content); free(r->namespace_id); free(r->source_url); free(r->source_domain);
    free(r->source_title); free(r->acquired_time); free(r->source_excerpt); free(r->provider_id);
    free(r->import_kind); free(r->request_id); free(r->session_id);
    free_string_array(r->parents, r->parent_count);
    memset(r, 0, sizeof(*r));
}

/* The frozen v1 helper extracts JSON string bytes but deliberately does not
 * unescape them. External/public knowledge is fed by Android JSONObject, so
 * provenance values such as URLs may legally arrive with JSON escapes (for
 * example https:\/\/example.org). Decode the common JSON escapes before
 * validating or persisting the post-v1 external contract. */
static char *external_json_string(const char *json, const char *key) {
    char *value = json_string(json, key);
    char *read, *write;
    if (!value) return NULL;
    read = value;
    write = value;
    while (*read) {
        if (*read == '\\' && read[1]) {
            ++read;
            switch (*read) {
                case '"': *write++ = '"'; ++read; break;
                case '\\': *write++ = '\\'; ++read; break;
                case '/': *write++ = '/'; ++read; break;
                case 'n': *write++ = '\n'; ++read; break;
                case 'r': *write++ = '\r'; ++read; break;
                case 't': *write++ = '\t'; ++read; break;
                case 'b': *write++ = '\b'; ++read; break;
                case 'f': *write++ = '\f'; ++read; break;
                default:
                    /* Preserve unsupported escapes (notably \uXXXX) bytewise
                     * rather than silently corrupting public evidence. */
                    *write++ = '\\';
                    *write++ = *read++;
                    break;
            }
        } else {
            *write++ = *read++;
        }
    }
    *write = 0;
    return value;
}

static int external_parse_request(memoria_mobile_buffer req, external_request *r) {
    char *json = NULL, *source_class = NULL;
    if (!r || !req.data || !req.size) return 0;
    memset(r, 0, sizeof(*r));
    json = buffer_to_string(req);
    if (!json) return 0;
    r->content = external_json_string(json, "content");
    r->namespace_id = external_json_string(json, "namespace");
    r->source_url = external_json_string(json, "source_url");
    r->source_domain = external_json_string(json, "source_domain");
    r->source_title = external_json_string(json, "source_title");
    r->acquired_time = external_json_string(json, "acquired_time");
    r->source_excerpt = external_json_string(json, "source_excerpt");
    r->provider_id = external_json_string(json, "provider_id");
    r->import_kind = external_json_string(json, "import_kind");
    r->request_id = external_json_string(json, "request_id");
    r->session_id = external_json_string(json, "session_id");
    source_class = external_json_string(json, "source_class");
    r->parent_count = json_string_array(json, "parent_memory_ids", r->parents, MAX_PARENTS);
    r->validation_confidence = json_double(json, "validation_confidence", 0.85);
    free(json);

    if (!r->namespace_id) r->namespace_id = dup_string("");
    if (!r->source_excerpt) r->source_excerpt = dup_string("");
    if (!r->provider_id) r->provider_id = dup_string("");
    if (!r->import_kind) r->import_kind = dup_string("synthesized");
    if (!r->request_id) r->request_id = dup_string("");
    if (!r->session_id) r->session_id = dup_string("");

    if ((source_class && strcmp(source_class, EXTERNAL_KNOWLEDGE_CLASS) != 0) ||
        !external_nonblank(r->content) || !external_valid_url(r->source_url) ||
        !external_valid_domain(r->source_domain) || !external_nonblank(r->source_title) ||
        !external_nonblank(r->acquired_time) || !r->namespace_id || !r->source_excerpt ||
        !r->provider_id || !r->import_kind || !r->request_id || !r->session_id ||
        r->validation_confidence < 0.0 || r->validation_confidence > 1.0 ||
        (strcmp(r->import_kind, "imported") != 0 && strcmp(r->import_kind, "synthesized") != 0 &&
         strcmp(r->import_kind, "derived") != 0) ||
        (strcmp(r->import_kind, "derived") == 0 && r->parent_count == 0) ||
        (strcmp(r->import_kind, "derived") != 0 && r->parent_count != 0)) {
        free(source_class);
        external_request_free(r);
        return 0;
    }
    free(source_class);
    return 1;
}

static int external_fetch_field(memoria_persistence *p, size_t slot, const char *field, char **out) {
    return fetch(p, "external", slot, field, out);
}

static int external_slot_is_public(memoria_mobile_handle *h, size_t slot) {
    char *value = NULL;
    int result = 0;
    if (!h || !slot || !external_fetch_field(h->persistence, slot, "knowledge_class", &value)) return 0;
    result = value && strcmp(value, EXTERNAL_KNOWLEDGE_CLASS) == 0;
    free(value);
    return result;
}

static int external_source_count(memoria_mobile_handle *h, size_t slot, unsigned long *out) {
    char *value = NULL;
    unsigned long count = 0;
    if (!out || !external_fetch_field(h->persistence, slot, "source_count", &value)) return 0;
    if (!value || !parse_ul(value, &count)) { free(value); return 0; }
    free(value);
    *out = count;
    return 1;
}

static int external_source_url_at(memoria_mobile_handle *h, size_t slot, unsigned long index, char **out) {
    char field[80];
    snprintf(field, sizeof(field), "source/%lu/url", index);
    return external_fetch_field(h->persistence, slot, field, out);
}

static int external_source_exists(memoria_mobile_handle *h, size_t slot, const char *url, unsigned long *count_out) {
    unsigned long count = 0, i;
    if (!external_source_count(h, slot, &count)) return 0;
    if (count_out) *count_out = count;
    for (i = 0; i < count; ++i) {
        char *stored = NULL;
        if (!external_source_url_at(h, slot, i, &stored)) return 0;
        if (stored && strcmp(stored, url) == 0) { free(stored); return 1; }
        free(stored);
    }
    return 0;
}

static int external_add_source_fields(
    memoria_persistence *p,
    bdr_atomic_c_operation *ops,
    char keys[][KEY_CAP], size_t *n,
    size_t slot, unsigned long source_index,
    const external_request *r,
    char *confidence, size_t confidence_cap
) {
    char field[96];
    int confidence_len;
#define EXT_PUT(name, value) do { \
    snprintf(field, sizeof(field), "source/%lu/%s", source_index, name); \
    if (!add_put(p, ops, keys, n, "external", slot, field, value)) return 0; \
} while (0)
    if (!confidence || confidence_cap == 0) return 0;
    confidence_len = snprintf(confidence, confidence_cap, "%.17g", r->validation_confidence);
    if (confidence_len < 0 || (size_t)confidence_len >= confidence_cap) return 0;
    EXT_PUT("url", r->source_url);
    EXT_PUT("domain", r->source_domain);
    EXT_PUT("title", r->source_title);
    EXT_PUT("acquired_time", r->acquired_time);
    EXT_PUT("excerpt", r->source_excerpt);
    EXT_PUT("provider_id", r->provider_id);
    EXT_PUT("import_kind", r->import_kind);
    EXT_PUT("request_id", r->request_id);
    EXT_PUT("session_id", r->session_id);
    EXT_PUT("validation_confidence", confidence);
#undef EXT_PUT
    return 1;
}

static int external_append_source(memoria_mobile_handle *h, size_t slot, const external_request *r, unsigned long *new_count) {
    bdr_atomic_c_operation ops[EXTERNAL_MAX_SOURCE_FIELDS];
    char keys[EXTERNAL_MAX_SOURCE_FIELDS][KEY_CAP];
    bdr_atomic_c_batch_result result = {0};
    char countbuf[VAL_CAP], confidence[VAL_CAP];
    unsigned long count = 0;
    size_t n = 0;
    if (!external_source_count(h, slot, &count)) return 0;
    if (count >= 1000000ul) return 0;
    snprintf(countbuf, sizeof(countbuf), "%lu", count + 1ul);
    if (!add_put(h->persistence, ops, keys, &n, "external", slot, "source_count", countbuf) ||
        !external_add_source_fields(h->persistence, ops, keys, &n, slot, count, r, confidence, sizeof(confidence))) return 0;
    if (bdr_atomic_c_write_batch(h->persistence->db, ops, n, &result) != BDR_ATOMIC_C_OK ||
        result.durable != 1 || result.operations != n) return 0;
    if (new_count) *new_count = count + 1ul;
    return 1;
}

static int external_persist_new_turn(
    memoria_mobile_handle *h, size_t slot, unsigned long sequence,
    const turn_row *t, const external_request *r, const char *signature
) {
    bdr_atomic_c_operation ops[MAX_OPS];
    char keys[MAX_OPS][KEY_CAP];
    char vals[24][VAL_CAP];
    char external_confidence[VAL_CAP];
    char relation_ids[MEMORIA_PERSIST_MAX_RELATIONS][MEMORIA_PERSIST_MEMORY_ID_CAP];
    bdr_atomic_c_batch_result result = {0};
    size_t n = 0, i;
    if (!h || !slot || !t || !r || !signature || !t->memory_id || !t->namespace_id ||
        !t->text || !t->role || !t->source_type || !t->ultimate_source_memory_id ||
        t->relation_count > MEMORIA_PERSIST_MAX_RELATIONS || t->parent_count > MEMORIA_PERSIST_MAX_PARENTS)
        return 0;
    snprintf(vals[0], VAL_CAP, "%u", MEMORIA_MOBILE_STATE_SCHEMA);
    snprintf(vals[1], VAL_CAP, "%zu", slot);
    snprintf(vals[2], VAL_CAP, "%lu", sequence);
    snprintf(vals[3], VAL_CAP, "%.17g", t->authority);
    snprintf(vals[4], VAL_CAP, "%ld", t->order);
    snprintf(vals[5], VAL_CAP, "%zu", t->relation_count);
    snprintf(vals[6], VAL_CAP, "%d", t->superseded ? 1 : 0);
    snprintf(vals[7], VAL_CAP, "%zu", t->parent_count);
    if (!add_meta(h->persistence,ops,keys,&n,"schema",vals[0]) ||
        !add_meta(h->persistence,ops,keys,&n,"turn_count",vals[1]) ||
        !add_meta(h->persistence,ops,keys,&n,"sequence",vals[2]) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"memory_id",t->memory_id) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"namespace",t->namespace_id) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"text",t->text) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"role",t->role) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"source_type",t->source_type) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"ultimate_source_memory_id",t->ultimate_source_memory_id) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"authority",vals[3]) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"order",vals[4]) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"relation_count",vals[5]) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"superseded",vals[6]) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"created_time",t->created_time) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"superseded_by",t->superseded_by) ||
        !add_put(h->persistence,ops,keys,&n,"turn",slot,"parent_count",vals[7])) return 0;
    for (i = 0; i < t->parent_count; ++i) {
        char field[64];
        if (!t->parent_memory_ids[i][0]) return 0;
        snprintf(field,sizeof(field),"parent/%zu",i);
        if (!add_put(h->persistence,ops,keys,&n,"turn",slot,field,t->parent_memory_ids[i])) return 0;
    }
    for (i = 0; i < t->relation_count; ++i) {
        char field[64];
        const char *relation_id = t->relation_memory_ids[i];
        snprintf(field,sizeof(field),"relation/%zu/subject",i);
        if (!add_put(h->persistence,ops,keys,&n,"turn",slot,field,t->relations[i].subject)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/predicate",i);
        if (!add_put(h->persistence,ops,keys,&n,"turn",slot,field,t->relations[i].predicate)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/object",i);
        if (!add_put(h->persistence,ops,keys,&n,"turn",slot,field,t->relations[i].object)) return 0;
        if (!relation_id[0]) {
            int written = snprintf(relation_ids[i], sizeof(relation_ids[i]), "%s#relation:%zu", t->memory_id, i);
            if (written < 0 || (size_t)written >= sizeof(relation_ids[i])) return 0;
            relation_id = relation_ids[i];
        }
        snprintf(field,sizeof(field),"relation/%zu/memory_id",i);
        if (!add_put(h->persistence,ops,keys,&n,"turn",slot,field,relation_id)) return 0;
        snprintf(vals[8+i],VAL_CAP,"%.17g",t->relations[i].confidence);
        snprintf(field,sizeof(field),"relation/%zu/confidence",i);
        if (!add_put(h->persistence,ops,keys,&n,"turn",slot,field,vals[8+i])) return 0;
    }
    if (!add_put(h->persistence,ops,keys,&n,"external",slot,"knowledge_class",EXTERNAL_KNOWLEDGE_CLASS) ||
        !add_put(h->persistence,ops,keys,&n,"external",slot,"federation_eligible","0") ||
        !add_put(h->persistence,ops,keys,&n,"external",slot,"fact_signature",signature) ||
        !add_put(h->persistence,ops,keys,&n,"external",slot,"source_count","1") ||
        !external_add_source_fields(h->persistence,ops,keys,&n,slot,0,r,external_confidence,sizeof(external_confidence))) return 0;
    return bdr_atomic_c_write_batch(h->persistence->db,ops,n,&result) == BDR_ATOMIC_C_OK &&
           result.durable == 1 && result.operations == n;
}

static int external_same_fact(const turn_row *existing, const char *content,
                              const memoria_relation *relations, size_t relation_count) {
    char *a = NULL, *b = NULL;
    int same;
    if (!existing || !existing->text || existing->superseded) return 0;
    if (external_relations_equal(existing->relations, existing->relation_count, relations, relation_count)) return 1;
    a = external_normalize_text(existing->text);
    b = external_normalize_text(content);
    same = a && b && strcmp(a, b) == 0;
    free(a); free(b);
    return same;
}

static int external_parent_is_public(memoria_mobile_handle *h, const char *memory_id, const char *namespace_id) {
    memory_ref ref = {0};
    size_t slot;
    if (!find_memory_ref(h, memory_id, namespace_id, &ref) || !ref.turn) return 0;
    slot = (size_t)(ref.turn - h->turns) + 1u;
    return external_slot_is_public(h, slot);
}

static int external_build_provenance_json(memoria_mobile_handle *h, size_t slot, char **out_json) {
    external_builder b = {0};
    turn_row *turn;
    char *klass = NULL, *signature = NULL;
    unsigned long count = 0, i;
    if (!h || !out_json || slot == 0 || slot > h->turn_count || !external_slot_is_public(h, slot) ||
        !external_source_count(h, slot, &count)) return 0;
    turn = &h->turns[slot - 1u];
    if (!external_fetch_field(h->persistence, slot, "knowledge_class", &klass) || !klass ||
        !external_fetch_field(h->persistence, slot, "fact_signature", &signature) || !signature) {
        free(klass); free(signature); return 0;
    }
    {
        char *mid = json_escape(turn->memory_id);
        char *st = json_escape(turn->source_type ? turn->source_type : "");
        char *root = json_escape(turn->ultimate_source_memory_id ? turn->ultimate_source_memory_id : "");
        char *sig = json_escape(signature);
        if (!mid || !st || !root || !sig ||
            !external_builder_appendf(&b,
                "{\"knowledge_class\":\"external_public\",\"memory_id\":\"%s\","
                "\"source_type\":\"%s\",\"source_authority\":%.6f,"
                "\"ultimate_source_memory_id\":\"%s\",\"fact_signature\":\"%s\","
                "\"source_count\":%lu,\"federation_eligible\":false,\"sources\":[",
                mid ? mid : "", st ? st : "", turn->authority, root ? root : "", sig ? sig : "", count)) {
            free(mid); free(st); free(root); free(sig); free(klass); free(signature); free(b.data); return 0;
        }
        free(mid); free(st); free(root); free(sig);
    }
    for (i = 0; i < count; ++i) {
        static const char *names[] = {"url","domain","title","acquired_time","excerpt","provider_id","import_kind","request_id","session_id","validation_confidence"};
        char *values[10] = {0};
        char field[96];
        char *esc[9] = {0};
        size_t j;
        int ok = 1;
        for (j = 0; j < 10; ++j) {
            snprintf(field, sizeof(field), "source/%lu/%s", i, names[j]);
            if (!external_fetch_field(h->persistence, slot, field, &values[j]) || !values[j]) { ok = 0; break; }
        }
        if (ok) for (j = 0; j < 9; ++j) { esc[j] = json_escape(values[j]); if (!esc[j]) { ok = 0; break; } }
        if (ok) ok = external_builder_appendf(&b,
            "%s{\"source_url\":\"%s\",\"source_domain\":\"%s\",\"source_title\":\"%s\","
            "\"acquired_time\":\"%s\",\"source_excerpt\":\"%s\",\"provider_id\":\"%s\","
            "\"import_kind\":\"%s\",\"request_id\":\"%s\",\"session_id\":\"%s\","
            "\"validation_confidence\":%s}",
            i ? "," : "", esc[0],esc[1],esc[2],esc[3],esc[4],esc[5],esc[6],esc[7],esc[8],values[9]);
        for (j = 0; j < 9; ++j) free(esc[j]);
        for (j = 0; j < 10; ++j) free(values[j]);
        if (!ok) { free(klass); free(signature); free(b.data); return 0; }
    }
    if (!external_builder_append(&b, "]}")) { free(klass); free(signature); free(b.data); return 0; }
    free(klass); free(signature);
    *out_json = b.data;
    return 1;
}

static memoria_mobile_status external_provenance_response(memoria_mobile_handle *h, size_t slot, memoria_mobile_buffer *out) {
    char *json = NULL;
    memoria_mobile_status status;
    if (!external_build_provenance_json(h, slot, &json))
        return set_response(out, "{\"status\":\"NOT_FOUND\",\"reason\":\"external provenance not found\"}", MEMORIA_MOBILE_NOT_FOUND);
    status = set_responsef(out, MEMORIA_MOBILE_OK, "{\"status\":\"OK\",\"provenance\":%s}", json);
    free(json);
    return status;
}

static int external_conflict_for_turn(memoria_mobile_handle *h, const turn_row *selected, const char *namespace_id,
                                      const char **conflict_memory_id) {
    size_t i, j, k, selected_slot;
    if (!h || !selected || selected->relation_count == 0 || selected->superseded) return 0;
    selected_slot = (size_t)(selected - h->turns) + 1u;
    if (!external_slot_is_public(h, selected_slot) || strcmp(selected->source_type, EXTERNAL_SOURCE_TYPE) != 0) return 0;
    for (i = 0; i < selected->relation_count; ++i) {
        for (j = 0; j < h->turn_count; ++j) {
            turn_row *other = &h->turns[j];
            if (other == selected || other->superseded || !turn_namespace_matches(other, namespace_id) ||
                strcmp(other->source_type ? other->source_type : "", EXTERNAL_SOURCE_TYPE) != 0 ||
                !external_slot_is_public(h, j + 1u)) continue;
            for (k = 0; k < other->relation_count; ++k) {
                if (external_ci_equal(selected->relations[i].subject, other->relations[k].subject) &&
                    external_ci_equal(selected->relations[i].predicate, other->relations[k].predicate) &&
                    !external_ci_equal(selected->relations[i].object, other->relations[k].object)) {
                    if (conflict_memory_id) *conflict_memory_id = other->memory_id;
                    return 1;
                }
            }
        }
    }
    return 0;
}

static memoria_mobile_status external_enrich_resolve(memoria_mobile_handle *h, memoria_mobile_buffer req,
                                                       memoria_mobile_buffer core, memoria_mobile_buffer *out) {
    char *response = NULL, *request = NULL, *namespace_id = NULL;
    char *ids[2] = {0};
    size_t id_count;
    memory_ref ref = {0};
    size_t slot;
    const char *conflict_id = NULL;
    char *provenance = NULL;
    const char *end;
    external_builder b = {0};
    memoria_mobile_status status;
    response = buffer_to_string(core);
    request = buffer_to_string(req);
    if (!response || !request) { free(response); free(request); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    namespace_id = json_string(request, "namespace");
    if (!namespace_id) namespace_id = dup_string("");
    id_count = json_string_array(response, "memory_ids", ids, 2);
    if (!namespace_id || id_count == 0 || !find_memory_ref(h, ids[0], namespace_id, &ref) || !ref.turn) {
        free_string_array(ids,id_count); free(namespace_id); free(response); free(request);
        return set_response(out, (const char *)core.data, MEMORIA_MOBILE_OK);
    }
    slot = (size_t)(ref.turn - h->turns) + 1u;
    if (external_conflict_for_turn(h, ref.turn, namespace_id, &conflict_id)) {
        char *a = json_escape(ref.turn->memory_id);
        char *b_id = json_escape(conflict_id ? conflict_id : "");
        status = (a && b_id) ? set_responsef(out, MEMORIA_MOBILE_UNRESOLVED,
            "{\"status\":\"UNRESOLVED\",\"reason\":\"conflicting external public sources\","
            "\"knowledge_class\":\"external_public\",\"conflict_memory_ids\":[\"%s\",\"%s\"]}", a,b_id)
            : MEMORIA_MOBILE_INTERNAL_ERROR;
        free(a); free(b_id); free_string_array(ids,id_count); free(namespace_id); free(response); free(request);
        return status;
    }
    if (!external_slot_is_public(h, slot) || !external_build_provenance_json(h, slot, &provenance)) {
        free_string_array(ids,id_count); free(namespace_id); free(response); free(request);
        return set_response(out, (const char *)core.data, MEMORIA_MOBILE_OK);
    }
    end = strrchr(response, '}');
    if (!end || end[1] != 0) {
        free(provenance); free_string_array(ids,id_count); free(namespace_id); free(response); free(request);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    if (!external_builder_reserve(&b, strlen(response) + strlen(provenance) + 80u)) goto enrich_fail;
    if ((size_t)(end - response) && !external_builder_appendf(&b, "%.*s", (int)(end-response), response)) goto enrich_fail;
    if (!external_builder_appendf(&b, ",\"knowledge_class\":\"external_public\",\"external_public_provenance\":%s}", provenance)) goto enrich_fail;
    status = set_response(out, b.data, MEMORIA_MOBILE_OK);
    free(b.data); free(provenance); free_string_array(ids,id_count); free(namespace_id); free(response); free(request);
    return status;
enrich_fail:
    free(b.data); free(provenance); free_string_array(ids,id_count); free(namespace_id); free(response); free(request);
    return MEMORIA_MOBILE_INTERNAL_ERROR;
}

memoria_mobile_status memoria_mobile_learn_external_knowledge_json(
    memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out
) {
    external_request r;
    turn_row candidate;
    memoria_relation relations[MAX_RELATIONS_PER_TURN];
    size_t relation_count, i, duplicate_slot = 0;
    char *signature = NULL;
    unsigned long next_sequence, source_count = 0;
    char idbuf[96], relations_json[4096];
    const char *relation_id_ptrs[MAX_RELATIONS_PER_TURN] = {0};
    memoria_mobile_status response_status;
    if (!h || !out || !req.data || !req.size) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (!external_parse_request(req, &r))
        return set_response(out, "{\"status\":\"INVALID_ARGUMENT\",\"reason\":\"external knowledge requires content, http(s) source_url, source_domain, source_title, acquired_time and valid import_kind/provenance\"}", MEMORIA_MOBILE_INVALID_ARGUMENT);

    memset(relations, 0, sizeof(relations));
    relation_count = memoria_extract_relations(r.content, relations, MAX_RELATIONS_PER_TURN);
    signature = external_fact_signature(r.content, relations, relation_count);
    if (!signature) { external_request_free(&r); return MEMORIA_MOBILE_INTERNAL_ERROR; }

    if (strcmp(r.import_kind, "derived") == 0) {
        for (i = 0; i < r.parent_count; ++i) {
            if (!r.parents[i] || !*r.parents[i] || strlen(r.parents[i]) >= MEMORIA_PERSIST_MEMORY_ID_CAP ||
                !external_parent_is_public(h, r.parents[i], r.namespace_id)) {
                free(signature); external_request_free(&r);
                return set_response(out,
                    "{\"status\":\"INVALID_ARGUMENT\",\"reason\":\"derived external knowledge may only reference external/public parents in the same namespace\"}",
                    MEMORIA_MOBILE_INVALID_ARGUMENT);
            }
        }
    } else {
        for (i = 0; i < h->turn_count; ++i) {
            turn_row *existing = &h->turns[i];
            if (!turn_namespace_matches(existing, r.namespace_id) || !external_slot_is_public(h, i + 1u) ||
                strcmp(existing->source_type ? existing->source_type : "", EXTERNAL_SOURCE_TYPE) != 0) continue;
            if (external_same_fact(existing, r.content, relations, relation_count)) { duplicate_slot = i + 1u; break; }
        }
    }

    if (duplicate_slot) {
        int same_source = external_source_exists(h, duplicate_slot, r.source_url, &source_count);
        char *prov = NULL;
        if (!same_source) {
            if (!external_append_source(h, duplicate_slot, &r, &source_count)) {
                free(signature); external_request_free(&r); return MEMORIA_MOBILE_PERSISTENCE_ERROR;
            }
        }
        if (!external_build_provenance_json(h, duplicate_slot, &prov)) {
            free(signature); external_request_free(&r); return MEMORIA_MOBILE_INTERNAL_ERROR;
        }
        response_status = set_responsef(out, MEMORIA_MOBILE_OK,
            "{\"status\":\"OK\",\"stored_memory_ids\":[\"%s\"],\"knowledge_class\":\"external_public\","
            "\"deduplicated\":true,\"source_attached\":%s,\"source_count\":%lu,\"federation_eligible\":false,"
            "\"provenance\":%s}",
            h->turns[duplicate_slot-1u].memory_id, same_source ? "false" : "true", source_count, prov);
        free(prov); free(signature); external_request_free(&r);
        return response_status;
    }

    if (!ensure_turn_capacity(h, h->turn_count + 1u)) { free(signature); external_request_free(&r); return MEMORIA_MOBILE_INTERNAL_ERROR; }
    memset(&candidate, 0, sizeof(candidate));
    next_sequence = h->sequence + 1ul;
    snprintf(idbuf, sizeof(idbuf), "external:%lu", next_sequence);
    candidate.memory_id = dup_string(idbuf);
    candidate.namespace_id = r.namespace_id; r.namespace_id = NULL;
    candidate.text = r.content; r.content = NULL;
    candidate.role = dup_string("external");
    candidate.source_type = dup_string(strcmp(r.import_kind, "derived") == 0 ? EXTERNAL_DERIVED_TYPE : EXTERNAL_SOURCE_TYPE);
    candidate.authority = strcmp(r.import_kind, "derived") == 0 ? EXTERNAL_DERIVED_AUTHORITY : EXTERNAL_DEFAULT_AUTHORITY;
    candidate.order = (long)h->turn_count + 1;
    candidate.superseded = 0;
    if (strlen(r.acquired_time) >= sizeof(candidate.created_time)) {
        free(signature); external_request_free(&r); free_turn(&candidate); return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    snprintf(candidate.created_time, sizeof(candidate.created_time), "%s", r.acquired_time);
    candidate.relation_count = relation_count;
    for (i = 0; i < relation_count; ++i) candidate.relations[i] = relations[i];

    if (strcmp(r.import_kind, "derived") == 0) {
        lineage_root best = {0}, root = {0};
        int found = 0;
        for (i = 0; i < r.parent_count; ++i) {
            snprintf(candidate.parent_memory_ids[candidate.parent_count++], MEMORIA_PERSIST_MEMORY_ID_CAP, "%s", r.parents[i]);
            if (active_lineage_root(h, r.parents[i], candidate.namespace_id, &root) && better_root(&root, &best, found)) {
                best = root; found = 1;
            }
        }
        candidate.ultimate_source_memory_id = dup_string(found ? best.memory_id : r.parents[0]);
    } else {
        candidate.ultimate_source_memory_id = dup_string(candidate.memory_id);
    }
    if (!candidate.memory_id || !candidate.namespace_id || !candidate.text || !candidate.role ||
        !candidate.source_type || !candidate.ultimate_source_memory_id) {
        free(signature); external_request_free(&r); free_turn(&candidate); return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    for (i = 0; i < candidate.relation_count; ++i) {
        int written = snprintf(candidate.relation_memory_ids[i], sizeof(candidate.relation_memory_ids[i]), "%s#relation:%zu", candidate.memory_id, i);
        if (written < 0 || (size_t)written >= sizeof(candidate.relation_memory_ids[i])) {
            free(signature); external_request_free(&r); free_turn(&candidate); return MEMORIA_MOBILE_INVALID_ARGUMENT;
        }
        relation_id_ptrs[i] = candidate.relation_memory_ids[i];
    }
    if (!memory_index_reserve(h, h->memory_index_count + 1u + candidate.relation_count) ||
        !memoria_relations_to_json_with_ids(candidate.relations, relation_id_ptrs, candidate.relation_count,
                                            candidate.memory_id, relations_json, sizeof(relations_json))) {
        free(signature); external_request_free(&r); free_turn(&candidate); return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    if (!external_persist_new_turn(h, h->turn_count + 1u, next_sequence, &candidate, &r, signature)) {
        free(signature); external_request_free(&r); free_turn(&candidate); return MEMORIA_MOBILE_PERSISTENCE_ERROR;
    }
    {
        size_t inserted = h->turn_count;
        int index_ok = 1;
        h->turns[h->turn_count++] = candidate;
        index_ok = memory_index_insert_prepared(h, inserted, -1, candidate.memory_id, candidate.namespace_id);
        for (i = 0; index_ok && i < candidate.relation_count; ++i)
            index_ok = memory_index_insert_prepared(h, inserted, (int)i, candidate.relation_memory_ids[i], candidate.namespace_id);
        if (!index_ok) {
            free(h->memory_index); h->memory_index = NULL; h->memory_index_capacity = 0; h->memory_index_count = 0;
        }
    }
    h->sequence = next_sequence;
    {
        char *prov = NULL;
        if (!external_build_provenance_json(h, h->turn_count, &prov)) {
            free(signature); external_request_free(&r); return MEMORIA_MOBILE_INTERNAL_ERROR;
        }
        response_status = set_responsef(out, MEMORIA_MOBILE_OK,
            "{\"status\":\"OK\",\"stored_memory_ids\":[\"%s\"],\"relations\":%s,"
            "\"knowledge_class\":\"external_public\",\"source_type\":\"%s\",\"source_count\":1,"
            "\"deduplicated\":false,\"source_attached\":true,\"durable\":true,\"federation_eligible\":false,"
            "\"provenance\":%s}", candidate.memory_id, relations_json, candidate.source_type, prov);
        free(prov);
    }
    free(signature); external_request_free(&r);
    return response_status;
}

memoria_mobile_status memoria_mobile_inspect_external_knowledge_json(
    memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out
) {
    char *json = NULL, *memory_id = NULL, *namespace_id = NULL;
    memory_ref ref = {0};
    size_t slot;
    memoria_mobile_status status;
    if (!h || !out || !req.data || !req.size) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = buffer_to_string(req);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    memory_id = json_string(json, "memory_id");
    namespace_id = json_string(json, "namespace");
    if (!namespace_id) namespace_id = dup_string("");
    free(json);
    if (!memory_id || !namespace_id || !find_memory_ref(h, memory_id, namespace_id, &ref) || !ref.turn) {
        free(memory_id); free(namespace_id);
        return set_response(out, "{\"status\":\"NOT_FOUND\"}", MEMORIA_MOBILE_NOT_FOUND);
    }
    slot = (size_t)(ref.turn - h->turns) + 1u;
    status = external_provenance_response(h, slot, out);
    free(memory_id); free(namespace_id);
    return status;
}

memoria_mobile_status memoria_mobile_resolve_context_json(
    memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out
) {
    memoria_mobile_buffer core = {0};
    memoria_mobile_status status;
    if (!h || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    status = memoria_mobile_resolve_context_json_v1_core(h, req, &core);
    if (status != MEMORIA_MOBILE_OK || !core.data) {
        memoria_subconscious_mobile_observe_resolution(h, req, status, core);
        if (core.data) {
            memoria_mobile_status copied = set_response(out, (const char *)core.data, status);
            memoria_mobile_free_buffer(core);
            return copied;
        }
        return status;
    }
    status = external_enrich_resolve(h, req, core, out);
    memoria_subconscious_mobile_observe_resolution(h, req, status, *out);
    memoria_mobile_free_buffer(core);
    return status;
}

void memoria_mobile_close(memoria_mobile_handle *h) {
    if (!h) return;
    memoria_subconscious_mobile_forget_handle(h);
    memoria_mobile_close_v1_core(h);
}
