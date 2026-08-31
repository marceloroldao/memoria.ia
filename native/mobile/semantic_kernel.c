#include "semantic_kernel.h"

#include <ctype.h>
#include <math.h>
#include <string.h>

#define MAX_QUERY_TOKENS 64u
#define MAX_TEXT_TOKENS 512u
#define TOKEN_SIZE 64u

static int is_stopword(const char *w) {
    static const char *stop[] = {
        "a","an","and","as","at","da","das","de","do","dos","e","em","for","me","my","o","of","os","para","por","que","the","to","um","uma","what","which",
        "fale","falar","diga","dizer","conte","procure","pesquise","pesquisar","sobre","mais","favor","outro","outra","outros","outras","escolha","escolhe","aleatoriamente",
        "please","tell","about","find","search","more"
    };
    size_t i;
    for (i = 0; i < sizeof(stop)/sizeof(stop[0]); ++i) if (strcmp(w, stop[i]) == 0) return 1;
    return 0;
}

static char fold_latin1(unsigned char lead, unsigned char tail) {
    if (lead != 0xC3) return 0;
    switch (tail) {
        case 0x80: case 0x81: case 0x82: case 0x83: case 0x84:
        case 0xA0: case 0xA1: case 0xA2: case 0xA3: case 0xA4: return 'a';
        case 0x88: case 0x89: case 0x8A: case 0x8B:
        case 0xA8: case 0xA9: case 0xAA: case 0xAB: return 'e';
        case 0x8C: case 0x8D: case 0x8E: case 0x8F:
        case 0xAC: case 0xAD: case 0xAE: case 0xAF: return 'i';
        case 0x92: case 0x93: case 0x94: case 0x95: case 0x96:
        case 0xB2: case 0xB3: case 0xB4: case 0xB5: case 0xB6: return 'o';
        case 0x99: case 0x9A: case 0x9B: case 0x9C:
        case 0xB9: case 0xBA: case 0xBB: case 0xBC: return 'u';
        case 0x87: case 0xA7: return 'c';
        case 0x91: case 0xB1: return 'n';
        default: return 0;
    }
}

static int next_folded(const char *s, size_t *index, char *out) {
    unsigned char ch;
    if (!s || !index || !out || !s[*index]) return 0;
    ch = (unsigned char)s[*index];
    if (ch < 0x80) {
        ++(*index);
        if (isalnum(ch)) {
            *out = (char)tolower(ch);
            return 1;
        }
        *out = 0;
        return 1;
    }
    if (s[*index + 1]) {
        char folded = fold_latin1(ch, (unsigned char)s[*index + 1]);
        *index += 2;
        *out = folded;
        return 1;
    }
    ++(*index);
    *out = 0;
    return 1;
}

static void canonicalize(char *w) {
    struct alias { const char *from; const char *to; };
    static const struct alias aliases[] = {
        {"paises", "pais"}, {"nacao", "pais"}, {"nacoes", "pais"},
        {"oceanos", "oceano"}, {"idioma", "lingua"}, {"idiomas", "lingua"}, {"linguas", "lingua"},
        {"capitais", "capital"}, {"cidades", "cidade"},
        {"countries", "country"}, {"oceans", "ocean"}, {"languages", "language"}, {"cities", "city"}
    };
    size_t i;
    for (i = 0; i < sizeof(aliases)/sizeof(aliases[0]); ++i) {
        if (strcmp(w, aliases[i].from) == 0) {
            strcpy(w, aliases[i].to);
            return;
        }
    }
}

static size_t tokens(const char *s, char out[][TOKEN_SIZE], size_t cap, int keep_stopwords) {
    size_t n = 0, i = 0;
    char w[TOKEN_SIZE];
    size_t k = 0;
    if (!s) return 0;
    while (s[i] && n < cap) {
        char folded = 0;
        if (!next_folded(s, &i, &folded)) break;
        if (folded) {
            if (k + 1 < sizeof(w)) w[k++] = folded;
        } else if (k) {
            w[k] = 0;
            canonicalize(w);
            if (keep_stopwords || !is_stopword(w)) {
                strcpy(out[n], w);
                ++n;
            }
            k = 0;
        }
    }
    if (k && n < cap) {
        w[k] = 0;
        canonicalize(w);
        if (keep_stopwords || !is_stopword(w)) {
            strcpy(out[n], w);
            ++n;
        }
    }
    return n;
}

static int token_equal(const char *a, const char *b) {
    return a && b && strcmp(a, b) == 0;
}

static double coverage_score(char q[][TOKEN_SIZE], size_t nq, char t[][TOKEN_SIZE], size_t nt) {
    size_t i, j, hits = 0;
    if (!nq) return 0.0;
    for (i = 0; i < nq; ++i) {
        for (j = 0; j < nt; ++j) {
            if (token_equal(q[i], t[j])) { ++hits; break; }
        }
    }
    return (double)hits / (double)nq;
}

static double centrality_score(char q[][TOKEN_SIZE], size_t nq, char t[][TOKEN_SIZE], size_t nt) {
    size_t i, j;
    double total = 0.0;
    if (!nq) return 0.0;
    for (i = 0; i < nq; ++i) {
        double one = 0.0;
        for (j = 0; j < nt; ++j) {
            if (token_equal(q[i], t[j])) {
                one = 1.0 / (1.0 + ((double)j / 12.0));
                break;
            }
        }
        total += one;
    }
    return total / (double)nq;
}

static double frequency_score(char q[][TOKEN_SIZE], size_t nq, char t[][TOKEN_SIZE], size_t nt) {
    size_t i, j;
    double total = 0.0;
    if (!nq) return 0.0;
    for (i = 0; i < nq; ++i) {
        size_t count = 0;
        for (j = 0; j < nt; ++j) if (token_equal(q[i], t[j])) ++count;
        if (count > 8u) count = 8u;
        total += (double)count / 8.0;
    }
    return total / (double)nq;
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

static int looks_like_overview_query(const char *query, size_t meaningful_tokens) {
    if (!query) return 0;
    if (meaningful_tokens == 1u) return 1;
    return starts_word(query, "fale") || starts_word(query, "conte") || starts_word(query, "tell") ||
           starts_word(query, "o que") || starts_word(query, "what is");
}

static int contains_token(char tokens_in[][TOKEN_SIZE], size_t count, const char *value, size_t limit) {
    size_t i, n = count < limit ? count : limit;
    for (i = 0; i < n; ++i) if (strcmp(tokens_in[i], value) == 0) return 1;
    return 0;
}

static double overview_profile_adjustment(const char *query, size_t meaningful_tokens, const char *text) {
    char head[32][TOKEN_SIZE];
    size_t n;
    int subtype = 0, broad = 0;
    static const char *subtype_cues[] = {"empresa","companhia","lista","serie","episodio","filme","album","partido","fases","fase","airline","company"};
    static const char *broad_cues[] = {"pais","republica","estado","continente","cidade","satelite","oceano","country","republic","state","continent","city","satellite","ocean"};
    size_t i;
    if (!looks_like_overview_query(query, meaningful_tokens)) return 0.0;
    n = tokens(text, head, 32, 0);
    for (i = 0; i < sizeof(subtype_cues)/sizeof(subtype_cues[0]); ++i)
        if (contains_token(head, n, subtype_cues[i], 8u)) { subtype = 1; break; }
    for (i = 0; i < sizeof(broad_cues)/sizeof(broad_cues[0]); ++i)
        if (contains_token(head, n, broad_cues[i], 12u)) { broad = 1; break; }
    if (subtype) return -0.22;
    if (broad) return 0.08;
    return 0.0;
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
    char q[MAX_QUERY_TOKENS][TOKEN_SIZE];
    size_t nq;
    size_t i, best = 0;
    double best_rank = 0.0, best_coverage = 0.0, best_authority = -1.0;
    long best_order = -1;
    int found = 0, ambiguous = 0;
    if (!query || !sources || !source_count) return unresolved;
    nq = tokens(query, q, MAX_QUERY_TOKENS, 0);
    if (!nq) return unresolved;

    for (i = 0; i < source_count; ++i) {
        char t[MAX_TEXT_TOKENS][TOKEN_SIZE];
        size_t nt;
        double coverage, authority, centrality, frequency, profile, rank;
        if (!source_is_retrievable(&sources[i])) continue;
        nt = tokens(sources[i].text, t, MAX_TEXT_TOKENS, 0);
        coverage = coverage_score(q, nq, t, nt);
        if (coverage <= 0.0) continue;
        centrality = centrality_score(q, nq, t, nt);
        frequency = frequency_score(q, nq, t, nt);
        profile = overview_profile_adjustment(query, nq, sources[i].text);
        authority = sources[i].authority;
        if (authority < 0.0) authority = 0.0;
        if (authority > 1.0) authority = 1.0;

        /* Retrieval v2: coverage still gates candidates, but ranking also asks
           whether the concept is central to the document. Authority remains
           strong enough that generated echoes cannot outrank direct evidence. */
        rank = 0.34 * coverage + 0.18 * centrality + 0.08 * frequency + 0.32 * authority + profile;

        if (!found || rank > best_rank + 1e-12 ||
            (fabs(rank-best_rank) < 1e-12 && authority > best_authority + 1e-12)) {
            best = i; best_rank = rank; best_coverage = coverage; best_authority = authority;
            best_order = sources[i].order; found = 1; ambiguous = 0;
        } else if (fabs(rank-best_rank) < 0.025 && fabs(authority-best_authority) < 0.05) {
            if (!same_root(&sources[i], &sources[best]) && strcmp(sources[i].text, sources[best].text) != 0) ambiguous = 1;
            if (!ambiguous && sources[i].order > best_order) {
                best = i; best_order = sources[i].order; best_coverage = coverage;
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
        result.confidence = 0.28 + 0.26 * best_coverage + 0.24 * authority + 0.12 * (best_rank > 1.0 ? 1.0 : best_rank);
        if (result.confidence > 0.9) result.confidence = 0.9;
        result.source_type = sources[best].source_type;
        result.source_authority = sources[best].authority;
        result.ultimate_source_memory_id = root_id(&sources[best]);
        return result;
    }
}
