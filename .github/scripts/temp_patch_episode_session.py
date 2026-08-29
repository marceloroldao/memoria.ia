from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"start not found: {label}")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"end not found: {label}")
    return text[:a] + replacement + text[b:]


# Persist session id with each native episode. This is additive to schema v1:
# old rows that do not contain the field load into the empty session.
p = Path("native/mobile/mobile_persistence.h")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    "typedef struct memoria_persist_episode {\n    char *episode_id;\n    char *role;",
    "typedef struct memoria_persist_episode {\n    char *episode_id;\n    char *session_id;\n    char *role;",
    "episode struct session_id",
)
p.write_text(text, encoding="utf-8")


p = Path("native/mobile/mobile_persistence_bdr.c")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    "if (!p || !slot || !e || !e->episode_id || !e->role || !e->text || !e->timestamp ||\n        !e->event_type || !e->topics_csv || !e->source_type || !e->ultimate_source_memory_id) return 0;",
    "if (!p || !slot || !e || !e->episode_id || !e->session_id || !e->role || !e->text || !e->timestamp ||\n        !e->event_type || !e->topics_csv || !e->source_type || !e->ultimate_source_memory_id) return 0;",
    "episode save validation",
)
text = replace_once(
    text,
    '!add_put(p,ops,keys,&n,"episode",slot,"episode_id",e->episode_id) ||\n        !add_put(p,ops,keys,&n,"episode",slot,"role",e->role) ||',
    '!add_put(p,ops,keys,&n,"episode",slot,"episode_id",e->episode_id) ||\n        !add_put(p,ops,keys,&n,"episode",slot,"session_id",e->session_id) ||\n        !add_put(p,ops,keys,&n,"episode",slot,"role",e->role) ||',
    "episode save session field",
)
text = replace_once(
    text,
    '!fetch(p,"episode",slot,"episode_id",&e->episode_id) || !e->episode_id ||\n        !fetch(p,"episode",slot,"role",&e->role) || !e->role ||',
    '!fetch(p,"episode",slot,"episode_id",&e->episode_id) || !e->episode_id ||\n        !fetch(p,"episode",slot,"session_id",&e->session_id) ||\n        !fetch(p,"episode",slot,"role",&e->role) || !e->role ||',
    "episode load optional session field",
)
text = replace_once(
    text,
    '!fetch(p,"episode",slot,"authority",&v) || !v || !parse_d(v,&e->authority)) goto fail;\n    free(v); v=NULL;',
    '!fetch(p,"episode",slot,"authority",&v) || !v || !parse_d(v,&e->authority)) goto fail;\n    if (!e->session_id) {\n        e->session_id = sdup("");\n        if (!e->session_id) goto fail;\n    }\n    free(v); v=NULL;',
    "episode load session fallback",
)
text = replace_once(
    text,
    'free(e->episode_id); free(e->role); free(e->text); free(e->timestamp); free(e->event_type); free(e->topics_csv);',
    'free(e->episode_id); free(e->session_id); free(e->role); free(e->text); free(e->timestamp); free(e->event_type); free(e->topics_csv);',
    "episode free session",
)
p.write_text(text, encoding="utf-8")


# Boundary semantics: explicit session_id filters exactly; absent session_id
# preserves the existing organization-wide recall behavior, matching Python
# namespace=None semantics.
p = Path("native/mobile/memoria_mobile.c")
text = p.read_text(encoding="utf-8")
start = "memoria_mobile_status memoria_mobile_store_episode_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {"
end = "memoria_mobile_status memoria_mobile_recall_episode_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {"
store = r'''memoria_mobile_status memoria_mobile_store_episode_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {
    char *json, *id, *session_id, *role, *text, *timestamp, *event_type, *topics, *source_type, *root;
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
    session_id = json_string(json, "session_id");
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
        free(json); free(id); free(session_id); free(role); free(text); free(timestamp); free(event_type); free(topics); free(source_type); free(root);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    next_sequence = h->sequence;
    if (!id) {
        ++next_sequence;
        snprintf(idbuf, sizeof(idbuf), "episode:%lu", next_sequence);
        id = dup_string(idbuf);
    }
    if (!session_id) session_id = dup_string("");
    if (!source_type) source_type = dup_string(strcmp(role, "user") == 0 ? "user_assertion" : "assistant_generated");
    if (authority < 0.0) authority = strcmp(source_type, "user_assertion") == 0 ? 1.0 : 0.35;
    if (!root) root = dup_string(id);
    if (!timestamp) timestamp = dup_string("");
    if (!event_type) event_type = dup_string("");
    if (!topics) topics = dup_string("");
    if (!id || !session_id || !source_type || !root || !timestamp || !event_type || !topics) {
        free(json); free(id); free(session_id); free(role); free(text); free(timestamp); free(event_type); free(topics); free(source_type); free(root);
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
    candidate.episode_id = id;
    candidate.session_id = session_id;
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

'''
text = replace_between(text, start, end, store, "store episode function")

start = end
end = "memoria_mobile_status memoria_mobile_export_snapshot_json("
recall = r'''memoria_mobile_status memoria_mobile_recall_episode_json(memoria_mobile_handle *h, memoria_mobile_buffer req, memoria_mobile_buffer *out) {
    char *json, *query, *session_id, *role, *event_type, *topics, *ctx, *st, *root;
    memoria_episode_source eps[MAX_EPISODES];
    memoria_episode_result r;
    size_t i, episode_count = 0;
    memoria_mobile_status response_status;
    if (!h || !req.data || !req.size || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    json = buffer_to_string(req);
    if (!json) return MEMORIA_MOBILE_INTERNAL_ERROR;
    query = json_string(json, "query");
    session_id = json_string(json, "session_id");
    role = json_string(json, "role");
    event_type = json_string(json, "event_type");
    topics = json_string(json, "topics_csv");
    if (!query) { free(json); free(session_id); free(role); free(event_type); free(topics); return MEMORIA_MOBILE_INVALID_ARGUMENT; }
    for (i = 0; i < h->episode_count; ++i) {
        episode_row *e = &h->episodes[i];
        if (session_id && strcmp(session_id, e->session_id ? e->session_id : "") != 0) continue;
        eps[episode_count].episode_id = e->episode_id;
        eps[episode_count].role = e->role;
        eps[episode_count].text = e->text;
        eps[episode_count].order = e->order;
        eps[episode_count].timestamp = e->timestamp;
        eps[episode_count].event_type = e->event_type;
        eps[episode_count].topics_csv = e->topics_csv;
        eps[episode_count].source_type = e->source_type;
        eps[episode_count].source_authority = e->authority;
        eps[episode_count].ultimate_source_memory_id = e->ultimate_source_memory_id;
        eps[episode_count].superseded = e->superseded;
        ++episode_count;
    }
    r = memoria_episode_recall_latest(query, role, event_type, topics, eps, episode_count);
    free(query); free(session_id); free(role); free(event_type); free(topics); free(json);
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

'''
text = replace_between(text, start, end, recall, "recall episode function")
p.write_text(text, encoding="utf-8")


# Diagnostic snapshot must make session boundaries visible without exposing BDR.
p = Path("native/mobile/diagnostic_export.c")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    'if (!append_json_string(b, e->episode_id)) return 0;\n    if (!append(b, ",\\\"role\\\":")) return 0;',
    'if (!append_json_string(b, e->episode_id)) return 0;\n    if (!append(b, ",\\\"session_id\\\":")) return 0;\n    if (!append_json_string(b, e->session_id)) return 0;\n    if (!append(b, ",\\\"role\\\":")) return 0;',
    "diagnostic episode session",
)
p.write_text(text, encoding="utf-8")
