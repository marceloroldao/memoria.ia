#include "concept_identity_kernel.h"

#include <ctype.h>
#include <stdint.h>
#include <string.h>

static const char *nz(const char *s) { return s ? s : ""; }

static int copy_text(char *dst, size_t cap, const char *src) {
    size_t n;
    if (!dst || cap == 0) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    src = nz(src);
    n = strlen(src);
    if (n >= cap) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    memcpy(dst, src, n + 1);
    return MEMORIA_CONCEPT_OK;
}

static uint32_t utf8_next(const unsigned char **p) {
    const unsigned char *s = *p;
    uint32_t cp;
    if (*s < 0x80) {
        cp = *s++;
    } else if ((*s & 0xE0) == 0xC0 && s[1]) {
        cp = ((uint32_t)(s[0] & 0x1F) << 6) | (uint32_t)(s[1] & 0x3F);
        s += 2;
    } else if ((*s & 0xF0) == 0xE0 && s[1] && s[2]) {
        cp = ((uint32_t)(s[0] & 0x0F) << 12) | ((uint32_t)(s[1] & 0x3F) << 6) | (uint32_t)(s[2] & 0x3F);
        s += 3;
    } else {
        cp = *s++;
    }
    *p = s;
    return cp;
}

static char fold_latin(uint32_t cp) {
    switch (cp) {
        case 0x00C0: case 0x00C1: case 0x00C2: case 0x00C3: case 0x00C4: case 0x00C5:
        case 0x00E0: case 0x00E1: case 0x00E2: case 0x00E3: case 0x00E4: case 0x00E5: return 'a';
        case 0x00C7: case 0x00E7: return 'c';
        case 0x00C8: case 0x00C9: case 0x00CA: case 0x00CB:
        case 0x00E8: case 0x00E9: case 0x00EA: case 0x00EB: return 'e';
        case 0x00CC: case 0x00CD: case 0x00CE: case 0x00CF:
        case 0x00EC: case 0x00ED: case 0x00EE: case 0x00EF: return 'i';
        case 0x00D1: case 0x00F1: return 'n';
        case 0x00D2: case 0x00D3: case 0x00D4: case 0x00D5: case 0x00D6:
        case 0x00F2: case 0x00F3: case 0x00F4: case 0x00F5: case 0x00F6: return 'o';
        case 0x00D9: case 0x00DA: case 0x00DB: case 0x00DC:
        case 0x00F9: case 0x00FA: case 0x00FB: case 0x00FC: return 'u';
        case 0x00DD: case 0x00FD: case 0x00FF: return 'y';
        default: return 0;
    }
}

int memoria_concept_normalize(const char *input, char *output, size_t output_cap) {
    const unsigned char *p = (const unsigned char *)nz(input);
    size_t out = 0;
    int pending_space = 0;
    if (!output || output_cap == 0) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    while (*p) {
        uint32_t cp = utf8_next(&p);
        char folded = fold_latin(cp);
        char ch = 0;
        if (folded) {
            ch = folded;
        } else if (cp < 128 && (isalnum((unsigned char)cp) || cp == '_')) {
            ch = (char)tolower((unsigned char)cp);
        } else if (cp >= 0x0300 && cp <= 0x036F) {
            continue;
        } else {
            pending_space = out > 0;
            continue;
        }
        if (pending_space) {
            if (out + 1 >= output_cap) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
            output[out++] = ' ';
            pending_space = 0;
        }
        if (out + 1 >= output_cap) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
        output[out++] = ch;
    }
    output[out] = '\0';
    return MEMORIA_CONCEPT_OK;
}

void memoria_concept_index_init(memoria_concept_index *index) {
    if (index) memset(index, 0, sizeof(*index));
}

static memoria_concept_record *find_concept(memoria_concept_index *index, const char *ns, const char *id) {
    size_t i;
    for (i = 0; i < index->concept_count; ++i) {
        memoria_concept_record *row = &index->concepts[i];
        if (strcmp(row->namespace_name, nz(ns)) == 0 && strcmp(row->concept_id, id) == 0) return row;
    }
    return NULL;
}

static const memoria_concept_record *find_concept_const(const memoria_concept_index *index, const char *ns, const char *id) {
    size_t i;
    for (i = 0; i < index->concept_count; ++i) {
        const memoria_concept_record *row = &index->concepts[i];
        if (strcmp(row->namespace_name, nz(ns)) == 0 && strcmp(row->concept_id, id) == 0) return row;
    }
    return NULL;
}

static int alias_exists(const memoria_concept_index *index, const char *ns, const char *surface, const char *id) {
    size_t i;
    for (i = 0; i < index->alias_count; ++i) {
        const memoria_concept_alias_record *row = &index->aliases[i];
        if (strcmp(row->namespace_name, nz(ns)) == 0 && strcmp(row->surface, surface) == 0 && strcmp(row->concept_id, id) == 0) return 1;
    }
    return 0;
}

static int add_alias(memoria_concept_index *index, const char *ns, const char *surface, const char *id) {
    memoria_concept_alias_record *row;
    if (!surface[0] || alias_exists(index, ns, surface, id)) return MEMORIA_CONCEPT_OK;
    if (index->alias_count >= MEMORIA_CONCEPT_MAX_ALIASES) return MEMORIA_CONCEPT_CAPACITY;
    row = &index->aliases[index->alias_count++];
    if (copy_text(row->namespace_name, sizeof(row->namespace_name), nz(ns)) != MEMORIA_CONCEPT_OK ||
        copy_text(row->surface, sizeof(row->surface), surface) != MEMORIA_CONCEPT_OK ||
        copy_text(row->concept_id, sizeof(row->concept_id), id) != MEMORIA_CONCEPT_OK) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    return MEMORIA_CONCEPT_OK;
}

int memoria_concept_register(memoria_concept_index *index, const memoria_concept_definition *definition) {
    memoria_concept_record *record;
    char canonical[MEMORIA_CONCEPT_SURFACE_CAP];
    char sense[MEMORIA_CONCEPT_SURFACE_CAP];
    size_t i;
    int rc;
    if (!index || !definition || !definition->concept_id || !definition->concept_id[0]) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    if (memoria_concept_normalize(definition->canonical_name, canonical, sizeof(canonical)) != MEMORIA_CONCEPT_OK || !canonical[0]) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    if (memoria_concept_normalize(definition->sense_key, sense, sizeof(sense)) != MEMORIA_CONCEPT_OK) return MEMORIA_CONCEPT_INVALID_ARGUMENT;

    record = find_concept(index, definition->namespace_name, definition->concept_id);
    if (record) {
        if (strcmp(record->canonical, canonical) != 0 || strcmp(record->sense_key, sense) != 0) return MEMORIA_CONCEPT_IDENTITY_CONFLICT;
    } else {
        if (index->concept_count >= MEMORIA_CONCEPT_MAX_CONCEPTS) return MEMORIA_CONCEPT_CAPACITY;
        record = &index->concepts[index->concept_count++];
        memset(record, 0, sizeof(*record));
        if (copy_text(record->concept_id, sizeof(record->concept_id), definition->concept_id) != MEMORIA_CONCEPT_OK ||
            copy_text(record->namespace_name, sizeof(record->namespace_name), nz(definition->namespace_name)) != MEMORIA_CONCEPT_OK ||
            copy_text(record->canonical, sizeof(record->canonical), canonical) != MEMORIA_CONCEPT_OK ||
            copy_text(record->sense_key, sizeof(record->sense_key), sense) != MEMORIA_CONCEPT_OK) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    }

    rc = add_alias(index, definition->namespace_name, canonical, definition->concept_id);
    if (rc != MEMORIA_CONCEPT_OK) return rc;
    for (i = 0; i < definition->alias_count; ++i) {
        char alias[MEMORIA_CONCEPT_SURFACE_CAP];
        if (memoria_concept_normalize(definition->aliases[i], alias, sizeof(alias)) != MEMORIA_CONCEPT_OK) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
        rc = add_alias(index, definition->namespace_name, alias, definition->concept_id);
        if (rc != MEMORIA_CONCEPT_OK) return rc;
    }
    for (i = 0; i < definition->context_cue_count; ++i) {
        char cue[MEMORIA_CONCEPT_SURFACE_CAP];
        size_t j;
        int exists = 0;
        if (memoria_concept_normalize(definition->context_cues[i], cue, sizeof(cue)) != MEMORIA_CONCEPT_OK) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
        if (!cue[0]) continue;
        for (j = 0; j < record->context_cue_count; ++j) if (strcmp(record->context_cues[j], cue) == 0) exists = 1;
        if (exists) continue;
        if (record->context_cue_count >= MEMORIA_CONCEPT_MAX_CUES) return MEMORIA_CONCEPT_CAPACITY;
        if (copy_text(record->context_cues[record->context_cue_count++], MEMORIA_CONCEPT_SURFACE_CAP, cue) != MEMORIA_CONCEPT_OK) return MEMORIA_CONCEPT_INVALID_ARGUMENT;
    }
    return MEMORIA_CONCEPT_OK;
}

static memoria_concept_resolution empty_resolution(void) {
    memoria_concept_resolution out;
    memset(&out, 0, sizeof(out));
    out.status = MEMORIA_CONCEPT_UNRESOLVED;
    out.reason = MEMORIA_CONCEPT_REASON_UNKNOWN;
    return out;
}

memoria_concept_resolution memoria_concept_resolve(const memoria_concept_index *index, const char *namespace_name, const char *surface) {
    memoria_concept_resolution out = empty_resolution();
    size_t i;
    char first_id[MEMORIA_CONCEPT_ID_CAP] = {0};
    if (!index || memoria_concept_normalize(surface, out.normalized_query, sizeof(out.normalized_query)) != MEMORIA_CONCEPT_OK || !out.normalized_query[0]) {
        out.reason = MEMORIA_CONCEPT_REASON_EMPTY;
        return out;
    }
    for (i = 0; i < index->alias_count; ++i) {
        const memoria_concept_alias_record *row = &index->aliases[i];
        if (strcmp(row->namespace_name, nz(namespace_name)) != 0 || strcmp(row->surface, out.normalized_query) != 0) continue;
        if (!first_id[0]) {
            copy_text(first_id, sizeof(first_id), row->concept_id);
            out.candidate_count = 1;
        } else if (strcmp(first_id, row->concept_id) != 0) {
            out.candidate_count++;
        }
    }
    if (out.candidate_count == 0) {
        out.reason = MEMORIA_CONCEPT_REASON_UNKNOWN;
        return out;
    }
    if (out.candidate_count > 1) {
        out.reason = MEMORIA_CONCEPT_REASON_AMBIGUOUS;
        return out;
    }
    out.status = MEMORIA_CONCEPT_HIT;
    out.reason = MEMORIA_CONCEPT_REASON_NONE;
    copy_text(out.concept_id, sizeof(out.concept_id), first_id);
    return out;
}

static int contains_phrase(const char *normalized_context, const char *cue) {
    size_t context_len = strlen(normalized_context), cue_len = strlen(cue), i;
    if (!cue_len || cue_len > context_len) return 0;
    for (i = 0; i + cue_len <= context_len; ++i) {
        if (i > 0 && normalized_context[i - 1] != ' ') continue;
        if (strncmp(normalized_context + i, cue, cue_len) != 0) continue;
        if (i + cue_len < context_len && normalized_context[i + cue_len] != ' ') continue;
        return 1;
    }
    return 0;
}

memoria_concept_resolution memoria_concept_resolve_with_context(const memoria_concept_index *index, const char *namespace_name, const char *surface, const char *context) {
    memoria_concept_resolution base = memoria_concept_resolve(index, namespace_name, surface);
    char normalized_context[MEMORIA_CONCEPT_SURFACE_CAP];
    char selected[MEMORIA_CONCEPT_ID_CAP] = {0};
    size_t supported = 0, i;
    if (base.status == MEMORIA_CONCEPT_HIT || base.reason != MEMORIA_CONCEPT_REASON_AMBIGUOUS) return base;
    if (memoria_concept_normalize(context, normalized_context, sizeof(normalized_context)) != MEMORIA_CONCEPT_OK || !normalized_context[0]) return base;
    for (i = 0; i < index->alias_count; ++i) {
        const memoria_concept_alias_record *alias = &index->aliases[i];
        const memoria_concept_record *concept;
        size_t j;
        int cue_hit = 0;
        if (strcmp(alias->namespace_name, nz(namespace_name)) != 0 || strcmp(alias->surface, base.normalized_query) != 0) continue;
        concept = find_concept_const(index, namespace_name, alias->concept_id);
        if (!concept) continue;
        for (j = 0; j < concept->context_cue_count; ++j) if (contains_phrase(normalized_context, concept->context_cues[j])) cue_hit = 1;
        if (!cue_hit) continue;
        if (!selected[0]) {
            copy_text(selected, sizeof(selected), concept->concept_id);
            supported = 1;
        } else if (strcmp(selected, concept->concept_id) != 0) {
            supported++;
        }
    }
    if (supported == 1) {
        base.status = MEMORIA_CONCEPT_HIT;
        base.reason = MEMORIA_CONCEPT_REASON_CONTEXT_CUE;
        copy_text(base.concept_id, sizeof(base.concept_id), selected);
    } else if (supported > 1) {
        base.status = MEMORIA_CONCEPT_UNRESOLVED;
        base.reason = MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT;
        base.concept_id[0] = '\0';
    }
    return base;
}
