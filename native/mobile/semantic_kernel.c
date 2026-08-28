#include "semantic_kernel.h"

#include <ctype.h>
#include <math.h>
#include <string.h>

static int is_stopword(const char *w) {
    static const char *stop[] = {"a","an","and","as","at","da","das","de","do","dos","e","em","for","me","my","o","of","os","para","por","que","the","to","um","uma","what","which"};
    size_t i;
    for (i = 0; i < sizeof(stop)/sizeof(stop[0]); ++i) if (strcmp(w, stop[i]) == 0) return 1;
    return 0;
}

static size_t tokens(const char *s, char out[][64], size_t cap) {
    size_t n = 0, i = 0;
    while (s && s[i] && n < cap) {
        char w[64]; size_t k = 0;
        while (s[i] && !isalnum((unsigned char)s[i])) ++i;
        while (s[i] && isalnum((unsigned char)s[i]) && k + 1 < sizeof(w)) w[k++] = (char)tolower((unsigned char)s[i++]);
        w[k] = 0;
        if (k && !is_stopword(w)) { strcpy(out[n], w); ++n; }
        while (s[i] && isalnum((unsigned char)s[i])) ++i;
    }
    return n;
}

static double overlap_score(const char *query, const char *text) {
    char q[64][64], t[128][64];
    size_t nq = tokens(query, q, 64), nt = tokens(text, t, 128), i, j, hits = 0;
    if (!nq) return 0.0;
    for (i = 0; i < nq; ++i) for (j = 0; j < nt; ++j) if (strcmp(q[i], t[j]) == 0) { ++hits; break; }
    return (double)hits / (double)nq;
}

static int starts_word(const char *s, const char *word) {
    size_t i = 0, j = 0;
    if (!s || !word) return 0;
    while (s[i] && isspace((unsigned char)s[i])) ++i;
    while (word[j]) {
        if (!s[i + j]) return 0;
        if (tolower((unsigned char)s[i + j]) != tolower((unsigned char)word[j])) return 0;
        ++j;
    }
    return s[i + j] == 0 || !isalnum((unsigned char)s[i + j]);
}

static int looks_like_question(const char *text) {
    static const char *question_starts[] = {
        "qual", "quais", "quem", "onde", "quando", "como", "quanto", "quantos", "quantas",
        "por que", "porque", "what", "which", "who", "where", "when", "how", "why",
        "can", "could", "would", "should", "do", "does", "did"
    };
    size_t i;
    if (!text) return 0;
    if (strchr(text, '?')) return 1;
    for (i = 0; i < sizeof(question_starts)/sizeof(question_starts[0]); ++i)
        if (starts_word(text, question_starts[i])) return 1;
    return 0;
}

static int source_is_retrievable(const memoria_semantic_source *source) {
    if (!source || !source->text) return 0;
    if (source->source_type && strcmp(source->source_type, "user_query") == 0) return 0;
    /* Backward compatibility: older mobile stores classified every user turn as
       user_assertion. Detect question-shaped text at retrieval time so existing
       databases do not need an eager migration. */
    if (source->source_type && strcmp(source->source_type, "user_assertion") == 0 && looks_like_question(source->text)) return 0;
    return 1;
}

static const char *root_id(const memoria_semantic_source *source) {
    if (source->ultimate_source_memory_id && source->ultimate_source_memory_id[0]) return source->ultimate_source_memory_id;
    return source->memory_id;
}

static int same_root(const memoria_semantic_source *a, const memoria_semantic_source *b) {
    const char *ra = root_id(a), *rb = root_id(b);
    return ra && rb && strcmp(ra, rb) == 0;
}

static size_t canonical_source_for_root(const memoria_semantic_source *sources, size_t source_count, size_t selected) {
    const char *root = root_id(&sources[selected]);
    size_t i, best = selected;
    if (!root) return selected;
    for (i = 0; i < source_count; ++i) {
        if (!same_root(&sources[i], &sources[selected]) || !source_is_retrievable(&sources[i])) continue;
        if (sources[i].memory_id && strcmp(sources[i].memory_id, root) == 0) return i;
        if (sources[i].authority > sources[best].authority + 1e-12) best = i;
        else if (fabs(sources[i].authority - sources[best].authority) < 1e-12 && sources[i].order < sources[best].order) best = i;
    }
    return best;
}

memoria_semantic_result memoria_semantic_resolve_sources(const char *query, const memoria_semantic_source *sources, size_t source_count) {
    memoria_semantic_result unresolved = {0, 0, 0.0, 0, 0.0, 0};
    size_t i, best = 0;
    double best_rank = 0.0, best_overlap = 0.0, best_authority = -1.0;
    long best_order = -1;
    int found = 0, ambiguous = 0;
    if (!query || !sources || !source_count) return unresolved;

    for (i = 0; i < source_count; ++i) {
        double overlap, authority, rank;
        if (!source_is_retrievable(&sources[i])) continue;
        overlap = overlap_score(query, sources[i].text);
        if (overlap <= 0.0) continue;
        authority = sources[i].authority;
        if (authority < 0.0) authority = 0.0;
        if (authority > 1.0) authority = 1.0;

        /* Authority is intentionally slightly stronger than lexical overlap.
           This prevents a verbose generated echo/hallucination from outranking
           a shorter direct factual source merely because it repeats more query words. */
        rank = 0.45 * overlap + 0.55 * authority;

        if (!found || rank > best_rank + 1e-12 ||
            (fabs(rank-best_rank) < 1e-12 && authority > best_authority + 1e-12)) {
            best = i; best_rank = rank; best_overlap = overlap; best_authority = authority;
            best_order = sources[i].order; found = 1; ambiguous = 0;
        } else if (fabs(rank-best_rank) < 1e-12 && fabs(authority-best_authority) < 1e-12) {
            if (!same_root(&sources[i], &sources[best]) && strcmp(sources[i].text, sources[best].text) != 0) ambiguous = 1;
            if (!ambiguous && sources[i].order > best_order) {
                best = i; best_order = sources[i].order; best_overlap = overlap;
            }
        }
    }
    if (!found || ambiguous) return unresolved;
    best = canonical_source_for_root(sources, source_count, best);
    {
        double authority = sources[best].authority;
        memoria_semantic_result result;
        if (authority < 0.0) authority = 0.0;
        if (authority > 1.0) authority = 1.0;
        result.hit = 1;
        result.memory_id = sources[best].memory_id;
        result.confidence = 0.30 + 0.25 * best_overlap + 0.25 * authority;
        if (result.confidence > 0.8) result.confidence = 0.8;
        result.source_type = sources[best].source_type;
        result.source_authority = sources[best].authority;
        result.ultimate_source_memory_id = root_id(&sources[best]);
        return result;
    }
}
