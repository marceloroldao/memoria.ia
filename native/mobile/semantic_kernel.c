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
        if (!same_root(&sources[i], &sources[selected])) continue;
        if (sources[i].memory_id && strcmp(sources[i].memory_id, root) == 0) return i;
        if (sources[i].authority > sources[best].authority + 1e-12) best = i;
        else if (fabs(sources[i].authority - sources[best].authority) < 1e-12 && sources[i].order < sources[best].order) best = i;
    }
    return best;
}

memoria_semantic_result memoria_semantic_resolve_sources(const char *query, const memoria_semantic_source *sources, size_t source_count) {
    memoria_semantic_result unresolved = {0, 0, 0.0, 0, 0.0, 0};
    size_t i, best = 0; double best_score = 0.0, best_authority = -1.0; long best_order = -1; int found = 0, ambiguous = 0;
    if (!query || !sources || !source_count) return unresolved;
    for (i = 0; i < source_count; ++i) {
        double score = overlap_score(query, sources[i].text);
        if (score <= 0.0) continue;
        if (!found || score > best_score + 1e-12 || (fabs(score-best_score) < 1e-12 && sources[i].authority > best_authority + 1e-12)) {
            best = i; best_score = score; best_authority = sources[i].authority; best_order = sources[i].order; found = 1; ambiguous = 0;
        } else if (fabs(score-best_score) < 1e-12 && fabs(sources[i].authority-best_authority) < 1e-12) {
            if (!same_root(&sources[i], &sources[best]) && strcmp(sources[i].text, sources[best].text) != 0) ambiguous = 1;
            if (!ambiguous && sources[i].order > best_order) { best = i; best_order = sources[i].order; }
        }
    }
    if (!found || ambiguous) return unresolved;
    best = canonical_source_for_root(sources, source_count, best);
    {
        memoria_semantic_result result = {
            1,
            sources[best].memory_id,
            0.45 + 0.35 * best_score,
            sources[best].source_type,
            sources[best].authority,
            root_id(&sources[best])
        };
        if (result.confidence > 0.8) result.confidence = 0.8;
        return result;
    }
}
