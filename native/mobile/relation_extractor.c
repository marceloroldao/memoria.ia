#include "relation_extractor.h"

#include <ctype.h>
#include <string.h>

static int is_word_byte(unsigned char c) {
    return isalnum(c) || c == '_' || c == '.' || c == '-' || c >= 0x80;
}

static int ascii_equal_ci(char a, char b) {
    return tolower((unsigned char)a) == tolower((unsigned char)b);
}

static int keyword_at(const char *p, const char *keyword, const char **end_out) {
    const char *q = p;
    const char *k = keyword;
    while (*k) {
        if (!*q || !ascii_equal_ci(*q, *k)) return 0;
        ++q;
        ++k;
    }
    if (*q && is_word_byte((unsigned char)*q)) return 0;
    if (end_out) *end_out = q;
    return 1;
}

static const char *skip_spaces(const char *p) {
    while (*p && isspace((unsigned char)*p)) ++p;
    return p;
}

static int is_token_start(const char *text, const char *p) {
    if (p == text) return 1;
    return !is_word_byte((unsigned char)p[-1]);
}

static int edge_punctuation(unsigned char c) {
    return c == '.' || c == ',' || c == ';' || c == ':' || c == '!' || c == '?' || c == '"';
}

static int copy_word(const char *p, char *out, size_t cap, const char **end_out) {
    const char *start = p;
    size_t n;
    if (!p || !*p || !is_word_byte((unsigned char)*p)) return 0;
    while (*p && is_word_byte((unsigned char)*p)) ++p;
    while (start < p && edge_punctuation((unsigned char)*start)) ++start;
    while (p > start && edge_punctuation((unsigned char)p[-1])) --p;
    if (p <= start) return 0;
    n = (size_t)(p - start);
    if (n >= cap) n = cap - 1;
    memcpy(out, start, n);
    out[n] = 0;
    if (end_out) {
        const char *raw_end = p;
        while (*raw_end && is_word_byte((unsigned char)*raw_end)) ++raw_end;
        *end_out = raw_end;
    }
    return 1;
}

static int string_equal_ci_ascii(const char *a, const char *b) {
    while (*a && *b) {
        unsigned char ca = (unsigned char)*a;
        unsigned char cb = (unsigned char)*b;
        if (ca < 0x80 && cb < 0x80) {
            if (tolower(ca) != tolower(cb)) return 0;
        } else if (ca != cb) {
            return 0;
        }
        ++a;
        ++b;
    }
    return *a == 0 && *b == 0;
}

static int is_noise_term(const char *value) {
    static const char *noise[] = {
        "a", "ao", "aos", "as", "da", "das", "de", "do", "dos", "e", "eh",
        "em", "eu", "foi", "me", "meu", "meus", "minha", "minhas", "o", "os",
        "para", "por", "que", "qual", "quais", "um", "uma", "uns", "umas", "voce",
        "você", "outro", "outra", "é"
    };
    size_t i;
    for (i = 0; i < sizeof(noise) / sizeof(noise[0]); ++i) {
        if (string_equal_ci_ascii(value, noise[i])) return 1;
    }
    return 0;
}

static int match_copula(const char *p, const char **end_out) {
    const char *end;
    if (*p == '=') {
        if (end_out) *end_out = p + 1;
        return 1;
    }
    if ((unsigned char)p[0] == 0xC3 &&
        ((unsigned char)p[1] == 0xA9 || (unsigned char)p[1] == 0x89)) {
        if (end_out) *end_out = p + 2;
        return 1;
    }
    if (keyword_at(p, "eh", &end) || keyword_at(p, "is", &end) || keyword_at(p, "e", &end)) {
        if (end_out) *end_out = end;
        return 1;
    }
    return 0;
}

static const char *skip_object_article(const char *p) {
    const char *end;
    if (keyword_at(p, "um", &end) || keyword_at(p, "uma", &end) ||
        keyword_at(p, "a", &end) || keyword_at(p, "an", &end)) {
        if (*end && isspace((unsigned char)*end)) return skip_spaces(end);
    }
    return p;
}

static int parse_copular_at(
    const char *text,
    const char *start,
    memoria_relation *row,
    const char **end_out
) {
    char left[96], right[96];
    const char *p, *after_left, *after_copula, *after_right;
    if (!is_token_start(text, start)) return 0;
    if (!copy_word(start, left, sizeof(left), &after_left)) return 0;
    if (is_noise_term(left)) return 0;
    p = skip_spaces(after_left);
    if (!match_copula(p, &after_copula)) return 0;
    p = skip_spaces(after_copula);
    p = skip_object_article(p);
    if (!copy_word(p, right, sizeof(right), &after_right)) return 0;
    if (is_noise_term(right)) return 0;

    strncpy(row->subject, left, sizeof(row->subject) - 1);
    row->subject[sizeof(row->subject) - 1] = 0;
    strcpy(row->predicate, "is");
    strncpy(row->object, right, sizeof(row->object) - 1);
    row->object[sizeof(row->object) - 1] = 0;
    row->confidence = 0.95;
    if (end_out) *end_out = after_right;
    return 1;
}

static int parse_elliptic_at(
    const char *text,
    const char *start,
    memoria_relation *row,
    const char **end_out
) {
    char left[96], right[96];
    const char *p = start;
    const char *end, *after_left, *after_right;
    int boundary_ok = 0;

    if (p == text) {
        boundary_ok = 1;
    } else if (*p == ',' || *p == ';' || *p == '.') {
        boundary_ok = 1;
        ++p;
    } else if (is_token_start(text, p) && keyword_at(p, "e", &end)) {
        boundary_ok = 1;
        p = end;
    }
    if (!boundary_ok) return 0;
    p = skip_spaces(p);

    if (!(keyword_at(p, "o", &end) || keyword_at(p, "a", &end))) return 0;
    if (!*end || !isspace((unsigned char)*end)) return 0;
    p = skip_spaces(end);
    if (!copy_word(p, left, sizeof(left), &after_left)) return 0;
    if (is_noise_term(left)) return 0;
    p = skip_spaces(after_left);
    if (!(keyword_at(p, "um", &end) || keyword_at(p, "uma", &end))) return 0;
    if (!*end || !isspace((unsigned char)*end)) return 0;
    p = skip_spaces(end);
    if (!copy_word(p, right, sizeof(right), &after_right)) return 0;
    if (is_noise_term(right)) return 0;

    strncpy(row->subject, left, sizeof(row->subject) - 1);
    row->subject[sizeof(row->subject) - 1] = 0;
    strcpy(row->predicate, "is");
    strncpy(row->object, right, sizeof(row->object) - 1);
    row->object[sizeof(row->object) - 1] = 0;
    row->confidence = 0.85;
    if (end_out) *end_out = after_right;
    return 1;
}

static int same_relation(const memoria_relation *a, const memoria_relation *b) {
    return string_equal_ci_ascii(a->subject, b->subject) &&
           strcmp(a->predicate, b->predicate) == 0 &&
           string_equal_ci_ascii(a->object, b->object);
}

static void add_unique(memoria_relation *out, size_t *count, size_t capacity, const memoria_relation *candidate) {
    size_t i;
    for (i = 0; i < *count; ++i) {
        if (same_relation(&out[i], candidate)) return;
    }
    if (*count < capacity) {
        out[*count] = *candidate;
        ++(*count);
    }
}

size_t memoria_extract_relations(const char *text, memoria_relation *out, size_t capacity) {
    const char *p;
    size_t count = 0;
    memoria_relation candidate;
    const char *match_end;

    if (!text || !out || capacity == 0) return 0;

    /* Product contract: collect all explicit copular relations first. */
    for (p = text; *p && count < capacity; ++p) {
        if (parse_copular_at(text, p, &candidate, &match_end)) {
            add_unique(out, &count, capacity, &candidate);
        }
    }

    /* Then collect lower-confidence Portuguese elliptic relations. */
    for (p = text; *p && count < capacity; ++p) {
        if (parse_elliptic_at(text, p, &candidate, &match_end)) {
            add_unique(out, &count, capacity, &candidate);
        }
    }

    return count;
}
