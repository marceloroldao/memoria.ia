from pathlib import Path


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + replacement + text[b:]


# 1) Persistent turn contract: add a backward-compatible superseded bit and
# an atomic save primitive that can mark corrected slots in the same BDR batch.
p = Path("native/mobile/mobile_persistence.h")
text = p.read_text(encoding="utf-8")
text = text.replace(
    "    double authority;\n    long order;\n    memoria_relation relations[MEMORIA_PERSIST_MAX_RELATIONS];",
    "    double authority;\n    long order;\n    int superseded;\n    memoria_relation relations[MEMORIA_PERSIST_MAX_RELATIONS];",
)
text = text.replace(
    "int memoria_persistence_save_turn(memoria_persistence *p, size_t slot, unsigned long sequence, const memoria_persist_turn *turn);",
    "int memoria_persistence_save_turn(memoria_persistence *p, size_t slot, unsigned long sequence, const memoria_persist_turn *turn);\n"
    "int memoria_persistence_save_turn_with_supersessions(\n"
    "    memoria_persistence *p, size_t slot, unsigned long sequence,\n"
    "    const memoria_persist_turn *turn, const size_t *superseded_slots, size_t superseded_count\n"
    ");",
)
p.write_text(text, encoding="utf-8")


# 2) BDR persistence: write the new turn and all supersession markers atomically.
p = Path("native/mobile/mobile_persistence_bdr.c")
text = p.read_text(encoding="utf-8")
text = text.replace("#define MAX_OPS 32", "#define MAX_OPS 64")
start = "int memoria_persistence_save_turn(memoria_persistence *p, size_t slot,\n"
end = "int memoria_persistence_load_turn(memoria_persistence *p, size_t slot, memoria_persist_turn *t) {"
replacement = r'''static int save_turn_impl(memoria_persistence *p, size_t slot,
                          unsigned long sequence, const memoria_persist_turn *t,
                          const size_t *superseded_slots, size_t superseded_count) {
    bdr_atomic_c_operation ops[MAX_OPS];
    char keys[MAX_OPS][KEY_CAP];
    char vals[16][VAL_CAP];
    bdr_atomic_c_batch_result result = {0};
    size_t n = 0, i;
    if (!p || !slot || !t || !t->memory_id || !t->text || !t->role ||
        !t->source_type || !t->ultimate_source_memory_id ||
        t->relation_count > MEMORIA_PERSIST_MAX_RELATIONS ||
        (superseded_count && !superseded_slots)) return 0;
    snprintf(vals[0], VAL_CAP, "%u", MEMORIA_MOBILE_STATE_SCHEMA);
    snprintf(vals[1], VAL_CAP, "%zu", slot);
    snprintf(vals[2], VAL_CAP, "%lu", sequence);
    snprintf(vals[3], VAL_CAP, "%.17g", t->authority);
    snprintf(vals[4], VAL_CAP, "%ld", t->order);
    snprintf(vals[5], VAL_CAP, "%zu", t->relation_count);
    snprintf(vals[6], VAL_CAP, "%d", t->superseded ? 1 : 0);
    if (!add_meta(p,ops,keys,&n,"schema",vals[0]) ||
        !add_meta(p,ops,keys,&n,"turn_count",vals[1]) ||
        !add_meta(p,ops,keys,&n,"sequence",vals[2]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"memory_id",t->memory_id) ||
        !add_put(p,ops,keys,&n,"turn",slot,"text",t->text) ||
        !add_put(p,ops,keys,&n,"turn",slot,"role",t->role) ||
        !add_put(p,ops,keys,&n,"turn",slot,"source_type",t->source_type) ||
        !add_put(p,ops,keys,&n,"turn",slot,"ultimate_source_memory_id",t->ultimate_source_memory_id) ||
        !add_put(p,ops,keys,&n,"turn",slot,"authority",vals[3]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"order",vals[4]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"relation_count",vals[5]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"superseded",vals[6])) return 0;
    for (i = 0; i < t->relation_count; ++i) {
        char field[64];
        snprintf(field,sizeof(field),"relation/%zu/subject",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,t->relations[i].subject)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/predicate",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,t->relations[i].predicate)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/object",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,t->relations[i].object)) return 0;
        snprintf(vals[7+i],VAL_CAP,"%.17g",t->relations[i].confidence);
        snprintf(field,sizeof(field),"relation/%zu/confidence",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,vals[7+i])) return 0;
    }
    for (i = 0; i < superseded_count; ++i) {
        if (!superseded_slots[i] || superseded_slots[i] >= slot) return 0;
        if (!add_put(p,ops,keys,&n,"turn",superseded_slots[i],"superseded","1")) return 0;
    }
    return bdr_atomic_c_write_batch(p->db,ops,n,&result) == BDR_ATOMIC_C_OK &&
           result.durable == 1 && result.operations == n;
}

int memoria_persistence_save_turn(memoria_persistence *p, size_t slot,
                                  unsigned long sequence, const memoria_persist_turn *t) {
    return save_turn_impl(p, slot, sequence, t, NULL, 0);
}

int memoria_persistence_save_turn_with_supersessions(
    memoria_persistence *p, size_t slot, unsigned long sequence,
    const memoria_persist_turn *t, const size_t *superseded_slots, size_t superseded_count
) {
    return save_turn_impl(p, slot, sequence, t, superseded_slots, superseded_count);
}

'''
text = replace_between(text, start, end, replacement)
needle = "    free(v); v=NULL;\n    if (!fetch(p,\"turn\",slot,\"relation_count\",&v) || !v || !parse_ul(v,&rc) || rc > MEMORIA_PERSIST_MAX_RELATIONS) goto fail;"
insert = "    free(v); v=NULL;\n    if (!fetch(p,\"turn\",slot,\"superseded\",&v)) goto fail;\n    if (v) {\n        long sup = 0;\n        if (!parse_l(v,&sup)) goto fail;\n        t->superseded = sup != 0;\n        free(v); v=NULL;\n    } else {\n        t->superseded = 0;\n    }\n    if (!fetch(p,\"turn\",slot,\"relation_count\",&v) || !v || !parse_ul(v,&rc) || rc > MEMORIA_PERSIST_MAX_RELATIONS) goto fail;"
if needle not in text:
    raise SystemExit("turn load insertion point not found")
text = text.replace(needle, insert, 1)
p.write_text(text, encoding="utf-8")


# 3) Mobile runtime: parse correction IDs, persist atomically, and exclude
# superseded turns from ordinary semantic/trajectory recall. Temporal history
# intentionally keeps them because it resolves previous/current transitions.
p = Path("native/mobile/memoria_mobile.c")
text = p.read_text(encoding="utf-8")
json_helper_anchor = "static long json_long(const char *json, const char *key, long fallback) {"
json_helper = r'''#define MAX_CORRECTIONS 16u

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

'''
if json_helper_anchor not in text:
    raise SystemExit("json helper anchor not found")
text = text.replace(json_helper_anchor, json_helper + json_helper_anchor, 1)
start = "memoria_mobile_status memoria_mobile_learn_turn_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {"
end = "memoria_mobile_status memoria_mobile_resolve_context_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {"
replacement = r'''memoria_mobile_status memoria_mobile_learn_turn_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {
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

'''
text = replace_between(text, start, end, replacement)
old_sources = '''    for (i = 0; i < h->turn_count; ++i) {
        sources[i].memory_id = h->turns[i].memory_id;
        sources[i].text = h->turns[i].text;
        sources[i].authority = h->turns[i].authority;
        sources[i].order = h->turns[i].order;
        sources[i].source_type = h->turns[i].source_type;
        sources[i].ultimate_source_memory_id = h->turns[i].ultimate_source_memory_id;
    }'''
new_sources = '''    size_t source_count = 0;
    for (i = 0; i < h->turn_count; ++i) {
        if (h->turns[i].superseded) continue;
        sources[source_count].memory_id = h->turns[i].memory_id;
        sources[source_count].text = h->turns[i].text;
        sources[source_count].authority = h->turns[i].authority;
        sources[source_count].order = h->turns[i].order;
        sources[source_count].source_type = h->turns[i].source_type;
        sources[source_count].ultimate_source_memory_id = h->turns[i].ultimate_source_memory_id;
        ++source_count;
    }'''
if old_sources not in text:
    raise SystemExit("semantic source build block not found")
text = text.replace(old_sources, new_sources, 1)
text = text.replace(
    "trajectory_mode = memoria_trajectory_resolve_json(json, query, sources, h->turn_count, &tr, &window_count);",
    "trajectory_mode = memoria_trajectory_resolve_json(json, query, sources, source_count, &tr, &window_count);",
    1,
)
text = text.replace(
    "r = memoria_semantic_resolve_sources(query, sources, h->turn_count);",
    "r = memoria_semantic_resolve_sources(query, sources, source_count);",
    1,
)
p.write_text(text, encoding="utf-8")


# 4) Diagnostic snapshots expose the new current-state bit without changing the
# format version; it is additive and older persisted turns default to false.
p = Path("native/mobile/diagnostic_export.c")
text = p.read_text(encoding="utf-8")
old = '    if (!appendf(b, ",\\\"source_authority\\\":%.6f,\\\"order\\\":%ld,\\\"relations\\\":[", t->authority, t->order)) return 0;'
new = '    if (!appendf(b, ",\\\"source_authority\\\":%.6f,\\\"order\\\":%ld,\\\"superseded\\\":%s,\\\"relations\\\":[", t->authority, t->order, t->superseded ? "true" : "false")) return 0;'
if old not in text:
    raise SystemExit("diagnostic turn field insertion point not found")
text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
