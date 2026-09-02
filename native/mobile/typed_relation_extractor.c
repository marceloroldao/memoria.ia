#include "typed_relation_extractor.h"

#include <ctype.h>
#include <string.h>

static int typed_edge_punct(unsigned char c) {
    return c == '.' || c == ',' || c == ';' || c == ':' || c == '!' || c == '?' || c == '"';
}

static void typed_trim_copy(const char *start, const char *end, char *out, size_t cap) {
    size_t n;
    while (start < end && isspace((unsigned char)*start)) ++start;
    while (end > start && (isspace((unsigned char)end[-1]) || typed_edge_punct((unsigned char)end[-1]))) --end;
    while (start < end && typed_edge_punct((unsigned char)*start)) ++start;
    n = (size_t)(end - start);
    if (n >= cap) n = cap - 1;
    memcpy(out, start, n);
    out[n] = 0;
}

static const char *typed_find_phrase(const char *text, const char *phrase) {
    return strstr(text, phrase);
}

static int typed_extract_one(
    const char *text,
    const char *phrase,
    const char *predicate,
    memoria_relation *row,
    double confidence
) {
    const char *p = typed_find_phrase(text, phrase);
    const char *right;
    const char *end;
    if (!p) return 0;
    right = p + strlen(phrase);
    end = right + strlen(right);
    typed_trim_copy(text, p, row->subject, sizeof(row->subject));
    typed_trim_copy(right, end, row->object, sizeof(row->object));
    if (!row->subject[0] || !row->object[0]) return 0;
    strncpy(row->predicate, predicate, sizeof(row->predicate) - 1);
    row->predicate[sizeof(row->predicate) - 1] = 0;
    row->confidence = confidence;
    return 1;
}

static int typed_same_relation(const memoria_relation *a, const memoria_relation *b) {
    return strcmp(a->subject, b->subject) == 0 &&
           strcmp(a->predicate, b->predicate) == 0 &&
           strcmp(a->object, b->object) == 0;
}

static void typed_add_unique(memoria_relation *out, size_t *count, size_t capacity, const memoria_relation *r) {
    size_t i;
    for (i = 0; i < *count; ++i) if (typed_same_relation(&out[i], r)) return;
    if (*count < capacity) out[(*count)++] = *r;
}

size_t memoria_extract_typed_relations(const char *text, memoria_relation *out, size_t capacity) {
    memoria_relation r;
    size_t count = 0;
    if (!text || !out || capacity == 0) return 0;

    memset(&r, 0, sizeof(r));
    if (typed_extract_one(text, " está em ", "esta_em", &r, 0.98) ||
        typed_extract_one(text, " esta em ", "esta_em", &r, 0.96) ||
        typed_extract_one(text, " is in ", "esta_em", &r, 0.96))
        typed_add_unique(out, &count, capacity, &r);

    memset(&r, 0, sizeof(r));
    if (typed_extract_one(text, " faz parte de ", "parte_de", &r, 0.98) ||
        typed_extract_one(text, " is part of ", "parte_de", &r, 0.96))
        typed_add_unique(out, &count, capacity, &r);

    memset(&r, 0, sizeof(r));
    if (typed_extract_one(text, " é subclasse de ", "subclasse_de", &r, 0.98) ||
        typed_extract_one(text, " eh subclasse de ", "subclasse_de", &r, 0.96) ||
        typed_extract_one(text, " is subclass of ", "subclasse_de", &r, 0.96))
        typed_add_unique(out, &count, capacity, &r);

    return count;
}
