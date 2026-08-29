from pathlib import Path

path = Path("native/mobile/memoria_mobile.c")
text = path.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match, got {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    "#include <stdlib.h>\n#include <string.h>\n",
    "#include <stdlib.h>\n#include <stdint.h>\n#include <string.h>\n",
)
replace_once(
    "#define INITIAL_TURN_CAPACITY 256u\n#define MAX_EPISODES 256",
    "#define INITIAL_TURN_CAPACITY 256u\n#define INITIAL_MEMORY_INDEX_CAPACITY 1024u\n#define MAX_EPISODES 256",
)
replace_once(
    "typedef memoria_persist_turn turn_row;\ntypedef memoria_persist_episode episode_row;\n\nstruct memoria_mobile_handle {",
    "typedef memoria_persist_turn turn_row;\ntypedef memoria_persist_episode episode_row;\n\ntypedef struct memory_index_slot {\n    uint64_t hash;\n    size_t turn_index;\n    int relation_index;\n    unsigned char occupied;\n} memory_index_slot;\n\nstruct memoria_mobile_handle {",
)
replace_once(
    "    memoria_semantic_source *semantic_sources;\n    size_t semantic_capacity;\n    episode_row episodes[MAX_EPISODES];",
    "    memoria_semantic_source *semantic_sources;\n    size_t semantic_capacity;\n    memory_index_slot *memory_index;\n    size_t memory_index_capacity;\n    size_t memory_index_count;\n    episode_row episodes[MAX_EPISODES];",
)

old_lookup = """static int find_memory_ref(memoria_mobile_handle *h, const char *memory_id, const char *namespace_id, memory_ref *out) {
    size_t i, j;
    if (!h || !memory_id || !out) return 0;
    for (i = 0; i < h->turn_count; ++i) {
        turn_row *turn = &h->turns[i];
        if (!turn_namespace_matches(turn, namespace_id)) continue;
        if (turn->memory_id && strcmp(turn->memory_id, memory_id) == 0) {
            out->turn = turn; out->relation_index = -1; return 1;
        }
        for (j = 0; j < turn->relation_count; ++j) if (turn->relation_memory_ids[j][0] && strcmp(turn->relation_memory_ids[j], memory_id) == 0) {
            out->turn = turn; out->relation_index = (int)j; return 1;
        }
    }
    return 0;
}
"""

new_lookup = r'''static uint64_t memory_key_hash(const char *namespace_id, const char *memory_id) {
    const unsigned char *p;
    uint64_t hash = UINT64_C(14695981039346656037);
    const char *ns = namespace_id ? namespace_id : "";
    if (!memory_id) return 0;
    for (p = (const unsigned char *)ns; *p; ++p) { hash ^= (uint64_t)*p; hash *= UINT64_C(1099511628211); }
    hash ^= UINT64_C(255); hash *= UINT64_C(1099511628211);
    for (p = (const unsigned char *)memory_id; *p; ++p) { hash ^= (uint64_t)*p; hash *= UINT64_C(1099511628211); }
    return hash ? hash : UINT64_C(1);
}

static const char *memory_index_slot_id(memoria_mobile_handle *h, const memory_index_slot *slot) {
    turn_row *turn;
    if (!h || !slot || !slot->occupied || slot->turn_index >= h->turn_count) return NULL;
    turn = &h->turns[slot->turn_index];
    if (slot->relation_index < 0) return turn->memory_id;
    if ((size_t)slot->relation_index >= turn->relation_count) return NULL;
    return turn->relation_memory_ids[slot->relation_index];
}

static int memory_index_slot_matches(
    memoria_mobile_handle *h,
    const memory_index_slot *slot,
    uint64_t hash,
    const char *memory_id,
    const char *namespace_id
) {
    const char *stored_id;
    turn_row *turn;
    if (!h || !slot || !slot->occupied || slot->hash != hash || slot->turn_index >= h->turn_count) return 0;
    turn = &h->turns[slot->turn_index];
    if (!turn_namespace_matches(turn, namespace_id)) return 0;
    stored_id = memory_index_slot_id(h, slot);
    return stored_id && strcmp(stored_id, memory_id) == 0;
}

static int memory_index_rehash(memoria_mobile_handle *h, size_t new_capacity) {
    memory_index_slot *slots;
    size_t i;
    if (!h || new_capacity < INITIAL_MEMORY_INDEX_CAPACITY || (new_capacity & (new_capacity - 1u)) != 0) return 0;
    if (new_capacity > ((size_t)-1) / sizeof(*slots)) return 0;
    slots = (memory_index_slot *)calloc(new_capacity, sizeof(*slots));
    if (!slots) return 0;
    for (i = 0; i < h->memory_index_capacity; ++i) {
        memory_index_slot current = h->memory_index[i];
        size_t pos;
        if (!current.occupied) continue;
        pos = (size_t)(current.hash & (uint64_t)(new_capacity - 1u));
        while (slots[pos].occupied) pos = (pos + 1u) & (new_capacity - 1u);
        slots[pos] = current;
    }
    free(h->memory_index);
    h->memory_index = slots;
    h->memory_index_capacity = new_capacity;
    return 1;
}

static int memory_index_reserve(memoria_mobile_handle *h, size_t desired_count) {
    size_t capacity;
    if (!h) return 0;
    capacity = h->memory_index_capacity ? h->memory_index_capacity : INITIAL_MEMORY_INDEX_CAPACITY;
    while (desired_count > (capacity * 7u) / 10u) {
        if (capacity > ((size_t)-1) / 2u) return 0;
        capacity *= 2u;
    }
    if (capacity == h->memory_index_capacity) return 1;
    return memory_index_rehash(h, capacity);
}

static int memory_index_insert_prepared(
    memoria_mobile_handle *h,
    size_t turn_index,
    int relation_index,
    const char *memory_id,
    const char *namespace_id
) {
    uint64_t hash;
    size_t pos, probes = 0;
    if (!h || !memory_id || !*memory_id || !h->memory_index_capacity || turn_index >= h->turn_count) return 0;
    hash = memory_key_hash(namespace_id, memory_id);
    pos = (size_t)(hash & (uint64_t)(h->memory_index_capacity - 1u));
    while (probes++ < h->memory_index_capacity) {
        memory_index_slot *slot = &h->memory_index[pos];
        if (!slot->occupied) {
            slot->hash = hash;
            slot->turn_index = turn_index;
            slot->relation_index = relation_index;
            slot->occupied = 1;
            ++h->memory_index_count;
            return 1;
        }
        if (memory_index_slot_matches(h, slot, hash, memory_id, namespace_id)) return 1;
        pos = (pos + 1u) & (h->memory_index_capacity - 1u);
    }
    return 0;
}

static int memory_index_rebuild(memoria_mobile_handle *h) {
    size_t i, j, desired = 0;
    if (!h) return 0;
    free(h->memory_index);
    h->memory_index = NULL;
    h->memory_index_capacity = 0;
    h->memory_index_count = 0;
    for (i = 0; i < h->turn_count; ++i) desired += 1u + h->turns[i].relation_count;
    if (!memory_index_reserve(h, desired)) return 0;
    for (i = 0; i < h->turn_count; ++i) {
        turn_row *turn = &h->turns[i];
        if (!memory_index_insert_prepared(h, i, -1, turn->memory_id, turn->namespace_id)) return 0;
        for (j = 0; j < turn->relation_count; ++j)
            if (turn->relation_memory_ids[j][0] &&
                !memory_index_insert_prepared(h, i, (int)j, turn->relation_memory_ids[j], turn->namespace_id)) return 0;
    }
    return 1;
}

static int find_memory_ref_linear(memoria_mobile_handle *h, const char *memory_id, const char *namespace_id, memory_ref *out) {
    size_t i, j;
    if (!h || !memory_id || !out) return 0;
    for (i = 0; i < h->turn_count; ++i) {
        turn_row *turn = &h->turns[i];
        if (!turn_namespace_matches(turn, namespace_id)) continue;
        if (turn->memory_id && strcmp(turn->memory_id, memory_id) == 0) {
            out->turn = turn; out->relation_index = -1; return 1;
        }
        for (j = 0; j < turn->relation_count; ++j) if (turn->relation_memory_ids[j][0] && strcmp(turn->relation_memory_ids[j], memory_id) == 0) {
            out->turn = turn; out->relation_index = (int)j; return 1;
        }
    }
    return 0;
}

static int find_memory_ref(memoria_mobile_handle *h, const char *memory_id, const char *namespace_id, memory_ref *out) {
    uint64_t hash;
    size_t pos, probes = 0;
    if (!h || !memory_id || !out) return 0;
    if (!h->memory_index_capacity) return find_memory_ref_linear(h, memory_id, namespace_id, out);
    hash = memory_key_hash(namespace_id, memory_id);
    pos = (size_t)(hash & (uint64_t)(h->memory_index_capacity - 1u));
    while (probes++ < h->memory_index_capacity) {
        memory_index_slot *slot = &h->memory_index[pos];
        if (!slot->occupied) return 0;
        if (memory_index_slot_matches(h, slot, hash, memory_id, namespace_id)) {
            out->turn = &h->turns[slot->turn_index];
            out->relation_index = slot->relation_index;
            return 1;
        }
        pos = (pos + 1u) & (h->memory_index_capacity - 1u);
    }
    return 0;
}
'''
replace_once(old_lookup, new_lookup)

replace_once(
    "    h->turn_count = turns;\n    for (i = 0; i < episodes; ++i) {",
    "    h->turn_count = turns;\n    if (!memory_index_rebuild(h)) {\n        memoria_mobile_close(h);\n        return MEMORIA_MOBILE_INTERNAL_ERROR;\n    }\n    for (i = 0; i < episodes; ++i) {",
)

replace_once(
    "    if (!memoria_relations_to_json_with_ids(candidate.relations, relation_id_ptrs, candidate.relation_count, id, relations_json, sizeof(relations_json))) {",
    "    if (!memory_index_reserve(h, h->memory_index_count + 1u + candidate.relation_count)) {\n        free_string_array(relation_ids, relation_id_count); free_string_array(parents,parent_count);\n        free_string_array(corrections, correction_count); free(created_time);\n        free(json); free_turn(&candidate); return MEMORIA_MOBILE_INTERNAL_ERROR;\n    }\n    if (!memoria_relations_to_json_with_ids(candidate.relations, relation_id_ptrs, candidate.relation_count, id, relations_json, sizeof(relations_json))) {",
)

replace_once(
    "    h->turns[h->turn_count++] = candidate;\n    h->sequence = next_sequence;",
    """    {
        size_t inserted_turn = h->turn_count;
        int index_ok = 1;
        h->turns[h->turn_count++] = candidate;
        index_ok = memory_index_insert_prepared(h, inserted_turn, -1, candidate.memory_id, candidate.namespace_id);
        for (i = 0; index_ok && i < candidate.relation_count; ++i)
            if (candidate.relation_memory_ids[i][0])
                index_ok = memory_index_insert_prepared(h, inserted_turn, (int)i, candidate.relation_memory_ids[i], candidate.namespace_id);
        if (!index_ok) {
            free(h->memory_index);
            h->memory_index = NULL;
            h->memory_index_capacity = 0;
            h->memory_index_count = 0;
        }
    }
    h->sequence = next_sequence;""",
)

replace_once(
    "    free(h->turns);\n    free(h->semantic_sources);\n    free(h->data_dir);",
    "    free(h->turns);\n    free(h->semantic_sources);\n    free(h->memory_index);\n    free(h->data_dir);",
)

path.write_text(text)
