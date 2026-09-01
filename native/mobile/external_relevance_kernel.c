#include "external_relevance_kernel.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#define TOKEN_CAP 96u
#define TOKEN_LEN 64u

static int stopword(const char *s) {
    static const char *words[] = {
        "a","o","as","os","um","uma","uns","umas","de","do","da","dos","das","e","em","no","na","nos","nas",
        "para","por","com","sem","que","qual","quais","quanto","quantos","quanta","quantas","sobre","me","diga","fale",
        "existe","existem","ha","ser","sao","the","a","an","of","to","in","on","for","about","what","which","how","many","tell","me"
    };
    size_t i;
    for (i = 0; i < sizeof(words)/sizeof(words[0]); ++i) if (strcmp(s, words[i]) == 0) return 1;
    return 0;
}

static int fold_utf8(const unsigned char **p, char *out) {
    unsigned char a = (*p)[0], b = (*p)[1];
    if (a != 0xC3 || !b) return 0;
    switch (b) {
        case 0x80: case 0x81: case 0x82: case 0x83: case 0x84:
        case 0xA0: case 0xA1: case 0xA2: case 0xA3: case 0xA4: *out='a'; break;
        case 0x87: case 0xA7: *out='c'; break;
        case 0x88: case 0x89: case 0x8A: case 0x8B:
        case 0xA8: case 0xA9: case 0xAA: case 0xAB: *out='e'; break;
        case 0x8C: case 0x8D: case 0x8E: case 0x8F:
        case 0xAC: case 0xAD: case 0xAE: case 0xAF: *out='i'; break;
        case 0x92: case 0x93: case 0x94: case 0x95: case 0x96:
        case 0xB2: case 0xB3: case 0xB4: case 0xB5: case 0xB6: *out='o'; break;
        case 0x99: case 0x9A: case 0x9B: case 0x9C:
        case 0xB9: case 0xBA: case 0xBB: case 0xBC: *out='u'; break;
        default: return 0;
    }
    *p += 2;
    return 1;
}

static size_t tokenize(const char *text, char out[][TOKEN_LEN], size_t cap, int remove_stopwords) {
    const unsigned char *p = (const unsigned char *)text;
    size_t count = 0u;
    char token[TOKEN_LEN];
    size_t n = 0u;
    if (!text) return 0u;
    while (1) {
        unsigned char c = *p;
        int word = c && (isalnum(c) || c >= 0x80u);
        if (word) {
            char folded = 0;
            if (c >= 0x80u && fold_utf8(&p, &folded)) {
                if (n + 1u < TOKEN_LEN) token[n++] = folded;
                continue;
            }
            if (n + 1u < TOKEN_LEN) token[n++] = (char)(c < 0x80u ? tolower(c) : c);
            if (c) ++p;
            continue;
        }
        if (n) {
            token[n] = 0;
            if ((!remove_stopwords || !stopword(token)) && count < cap) {
                size_t i, duplicate = 0u;
                if (remove_stopwords) {
                    for (i = 0; i < count; ++i) if (strcmp(out[i], token) == 0) { duplicate = 1u; break; }
                }
                if (!duplicate) { memcpy(out[count], token, n + 1u); ++count; }
            }
            n = 0u;
        }
        if (!c) break;
        ++p;
    }
    return count;
}

static int token_present(char tokens[][TOKEN_LEN], size_t count, const char *needle, size_t *first_index) {
    size_t i;
    for (i = 0; i < count; ++i) {
        if (strcmp(tokens[i], needle) == 0) {
            if (first_index) *first_index = i;
            return 1;
        }
    }
    return 0;
}

int memoria_external_relevance_evaluate(
    const char *query,
    const char *content,
    const memoria_external_relevance_policy *policy,
    memoria_external_relevance_result *out
) {
    char q[TOKEN_CAP][TOKEN_LEN], c[TOKEN_CAP][TOKEN_LEN];
    size_t qn, cn, i, matched = 0u, early = 0u;
    double coverage, early_ratio, score;
    if (!query || !content || !policy || !out ||
        policy->min_query_coverage < 0.0 || policy->min_query_coverage > 1.0 ||
        policy->min_anchor_matches == 0u || policy->early_window_tokens == 0u) return 0;
    memset(out, 0, sizeof(*out));
    qn = tokenize(query, q, TOKEN_CAP, 1);
    cn = tokenize(content, c, TOKEN_CAP, 0);
    if (qn == 0u || cn == 0u) return 0;
    for (i = 0; i < qn; ++i) {
        size_t idx = 0u;
        if (token_present(c, cn, q[i], &idx)) {
            ++matched;
            if (idx < policy->early_window_tokens) ++early;
        }
    }
    coverage = (double)matched / (double)qn;
    early_ratio = matched ? (double)early / (double)matched : 0.0;
    score = 0.80 * coverage + 0.20 * early_ratio;
    out->query_content_tokens = qn;
    out->matched_query_tokens = matched;
    out->content_tokens = cn;
    out->early_matched_query_tokens = early;
    out->query_coverage = coverage;
    out->early_match_ratio = early_ratio;
    out->relevance_score = score;
    out->accepted = matched >= policy->min_anchor_matches && coverage >= policy->min_query_coverage;
    return 1;
}
