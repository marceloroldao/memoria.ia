#include "concept_identity_state.h"

#include <string.h>

static int copy_text(char *dst, size_t cap, const char *src) {
    size_t n;
    if (!dst || !cap) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    if (!src) src = "";
    n = strlen(src);
    if (n >= cap) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    memcpy(dst, src, n + 1);
    return MEMORIA_CONCEPT_OK;
}

int memoria_concept_state_export(
    const memoria_concept_index *index,
    memoria_concept_state_row *rows,
    size_t row_capacity,
    size_t *row_count
) {
    size_t i, j;
    if (!index || !rows || !row_count || row_capacity < index->concept_count) {
        return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    }
    memset(rows, 0, row_capacity * sizeof(*rows));
    for (i = 0; i < index->concept_count; ++i) {
        const memoria_concept_record *concept = &index->concepts[i];
        memoria_concept_state_row *row = &rows[i];
        if (copy_text(row->concept_id, sizeof(row->concept_id), concept->concept_id) != MEMORIA_CONCEPT_OK ||
            copy_text(row->namespace_name, sizeof(row->namespace_name), concept->namespace_name) != MEMORIA_CONCEPT_OK ||
            copy_text(row->canonical, sizeof(row->canonical), concept->canonical) != MEMORIA_CONCEPT_OK ||
            copy_text(row->sense_key, sizeof(row->sense_key), concept->sense_key) != MEMORIA_CONCEPT_OK) {
            return MEMORIA_CONCEPT_INVALID_ARGUMENT;
        }
        row->context_cue_count = concept->context_cue_count;
        for (j = 0; j < concept->context_cue_count; ++j) {
            if (copy_text(row->context_cues[j], sizeof(row->context_cues[j]), concept->context_cues[j]) != MEMORIA_CONCEPT_OK) {
                return MEMORIA_CONCEPT_INVALID_ARGUMENT;
            }
        }
        for (j = 0; j < index->alias_count; ++j) {
            const memoria_concept_alias_record *alias = &index->aliases[j];
            if (strcmp(alias->namespace_name, concept->namespace_name) != 0 ||
                strcmp(alias->concept_id, concept->concept_id) != 0) {
                continue;
            }
            if (row->alias_count >= MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT) {
                return MEMORIA_CONCEPT_CAPACITY;
            }
            if (copy_text(row->aliases[row->alias_count], sizeof(row->aliases[row->alias_count]), alias->surface) != MEMORIA_CONCEPT_OK) {
                return MEMORIA_CONCEPT_INVALID_ARGUMENT;
            }
            row->alias_count++;
        }
    }
    *row_count = index->concept_count;
    return MEMORIA_CONCEPT_OK;
}

int memoria_concept_state_import(
    memoria_concept_index *index,
    const memoria_concept_state_row *rows,
    size_t row_count
) {
    size_t i, j;
    if (!index || (!rows && row_count)) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    memoria_concept_index_init(index);
    for (i = 0; i < row_count; ++i) {
        const memoria_concept_state_row *row = &rows[i];
        const char *aliases[MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT];
        const char *cues[MEMORIA_CONCEPT_MAX_CUES];
        memoria_concept_definition definition;
        if (!row->concept_id[0] || !row->canonical[0] ||
            row->alias_count > MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT ||
            row->context_cue_count > MEMORIA_CONCEPT_MAX_CUES) {
            return MEMORIA_CONCEPT_INVALID_ARGUMENT;
        }
        for (j = 0; j < row->alias_count; ++j) aliases[j] = row->aliases[j];
        for (j = 0; j < row->context_cue_count; ++j) cues[j] = row->context_cues[j];
        definition.concept_id = row->concept_id;
        definition.namespace_name = row->namespace_name;
        definition.canonical_name = row->canonical;
        definition.sense_key = row->sense_key;
        definition.aliases = aliases;
        definition.alias_count = row->alias_count;
        definition.context_cues = cues;
        definition.context_cue_count = row->context_cue_count;
        if (memoria_concept_register(index, &definition) != MEMORIA_CONCEPT_OK) {
            return MEMORIA_CONCEPT_INVALID_ARGUMENT;
        }
    }
    return MEMORIA_CONCEPT_OK;
}
