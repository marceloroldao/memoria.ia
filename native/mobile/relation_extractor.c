#include "relation_extractor.h"

#include <ctype.h>
#include <string.h>

static int is_sep(char c) {
    return c == 0 || c == ',' || c == ';' || c == '.' || c == '!' || c == '?';
}

static void trim_copy(const char *start, const char *end, char *out, size_t cap) {
    size_t n;
    while (start < end && isspace((unsigned char)*start)) ++start;
    while (end > start && isspace((unsigned char)end[-1])) --end;
    n = (size_t)(end - start);
    if (n >= cap) n = cap - 1;
    memcpy(out, start, n);
    out[n] = 0;
}

static const char *find_copula(const char *s) {
    const char *p;
    for (p = s; *p; ++p) {
        if ((p == s || isspace((unsigned char)p[-1])) &&
            (strncmp(p, "is ", 3) == 0 || strncmp(p, "eh ", 3) == 0 || strncmp(p, "e ", 2) == 0)) return p;
        if ((unsigned char)p[0] == 0xC3 && (unsigned char)p[1] == 0xA9 && isspace((unsigned char)p[2])) return p;
        if (*p == '=') return p;
    }
    return NULL;
}

static size_t copula_len(const char *p) {
    if (*p == '=') return 1;
    if ((unsigned char)p[0] == 0xC3 && (unsigned char)p[1] == 0xA9) return 2;
    if (strncmp(p, "is ", 3) == 0) return 2;
    if (strncmp(p, "eh ", 3) == 0) return 2;
    return 1;
}

size_t memoria_extract_relations(const char *text, memoria_relation *out, size_t capacity) {
    const char *segment, *p;
    size_t count = 0;
    if (!text || !out || capacity == 0) return 0;
    segment = text;
    for (p = text;; ++p) {
        if (is_sep(*p)) {
            char clause[256], left[96], right[96];
            const char *c;
            trim_copy(segment, p, clause, sizeof(clause));
            c = find_copula(clause);
            if (c && count < capacity) {
                const char *r = c + copula_len(c);
                while (*r && isspace((unsigned char)*r)) ++r;
                if (strncmp(r, "a ", 2) == 0) r += 2;
                else if (strncmp(r, "an ", 3) == 0) r += 3;
                else if (strncmp(r, "um ", 3) == 0) r += 3;
                else if (strncmp(r, "uma ", 4) == 0) r += 4;
                trim_copy(clause, c, left, sizeof(left));
                trim_copy(r, clause + strlen(clause), right, sizeof(right));
                if (left[0] && right[0]) {
                    strncpy(out[count].subject, left, sizeof(out[count].subject)-1);
                    out[count].subject[sizeof(out[count].subject)-1] = 0;
                    strcpy(out[count].predicate, "is");
                    strncpy(out[count].object, right, sizeof(out[count].object)-1);
                    out[count].object[sizeof(out[count].object)-1] = 0;
                    out[count].confidence = 0.95;
                    ++count;
                }
            }
            if (*p == 0) break;
            segment = p + 1;
        }
    }
    return count;
}
