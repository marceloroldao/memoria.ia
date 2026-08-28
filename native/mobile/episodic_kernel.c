#include "episodic_kernel.h"

#include <ctype.h>
#include <math.h>
#include <string.h>

static int eqi(const char *a, const char *b) {
    if (!a || !b) return a == b;
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0;
        ++a; ++b;
    }
    return *a == 0 && *b == 0;
}

static int is_stopword(const char *w) {
    static const char *stop[] = {"a","ao","aos","as","da","das","de","do","dos","e","em","eu","foi","me","meu","meus","minha","minhas","o","os","para","por","que","qual","quais","um","uma","uns","umas","voce","ultimo","ultima","mais","recente","the","what","which","last","latest"};
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

static size_t csv_item_count(const char *value) {
    size_t count = 0;
    int in_item = 0;
    if (!value) return 0;
    while (*value) {
        if (*value == ',') {
            if (in_item) ++count;
            in_item = 0;
        } else if (!isspace((unsigned char)*value)) {
            in_item = 1;
        }
        ++value;
    }
    if (in_item) ++count;
    return count;
}

static int csv_contains_all(const char *requested, const char *available, const char *text) {
    char req[32][64]; size_t nr, i;
    if (!requested || !*requested) return 1;
    nr = tokens(requested, req, 32);
    for (i = 0; i < nr; ++i) {
        char av[64][64], tx[128][64]; size_t na = tokens(available, av, 64), nt = tokens(text, tx, 128), j; int found = 0;
        for (j = 0; j < na; ++j) if (strcmp(req[i], av[j]) == 0) { found = 1; break; }
        if (!found) for (j = 0; j < nt; ++j) if (strcmp(req[i], tx[j]) == 0) { found = 1; break; }
        if (!found) return 0;
    }
    return 1;
}

static double overlap_score(const char *query, const memoria_episode_source *episode) {
    char q[64][64], t[160][64]; size_t nq = tokens(query, q, 64), nt = 0, i, j, hits = 0;
    nt += tokens(episode->text, t + nt, 128 - nt);
    nt += tokens(episode->topics_csv, t + nt, 128 - nt);
    nt += tokens(episode->event_type, t + nt, 128 - nt);
    if (!nq) return 0.0;
    for (i = 0; i < nq; ++i) for (j = 0; j < nt; ++j) if (strcmp(q[i], t[j]) == 0) { ++hits; break; }
    return (double)hits / (double)nq;
}

memoria_episode_result memoria_episode_recall_latest(const char *query, const char *role, const char *event_type, const char *topics_csv, const memoria_episode_source *episodes, size_t episode_count) {
    memoria_episode_result unresolved = {0,0,0,0,0,0,0,0,0.0,0,0.0};
    size_t i, best = 0; double best_score = -1.0; long latest_order = -1; int found = 0, ambiguous = 0;
    if (!query || !*query || !episodes || episode_count == 0) return unresolved;
    for (i = 0; i < episode_count; ++i) {
        const memoria_episode_source *e = &episodes[i]; double overlap, explicit_score, score;
        if (e->superseded) continue;
        if (role && *role && !eqi(role, e->role)) continue;
        if (event_type && *event_type && !eqi(event_type, e->event_type)) continue;
        if (!csv_contains_all(topics_csv, e->topics_csv, e->text)) continue;
        overlap = overlap_score(query, e);
        explicit_score = (event_type && *event_type ? 2.0 : 0.0) + (double)csv_item_count(topics_csv);
        if (overlap <= 0.0 && explicit_score <= 0.0) continue;
        score = explicit_score + overlap;
        if (!found || score > best_score + 1e-12) {
            best = i; best_score = score; latest_order = e->order; found = 1; ambiguous = 0;
        } else if (fabs(score - best_score) < 1e-12) {
            if (e->order > latest_order) {
                best = i; latest_order = e->order; ambiguous = 0;
            } else if (e->order == latest_order && strcmp(e->episode_id, episodes[best].episode_id) != 0) {
                ambiguous = 1;
            }
        }
    }
    if (!found || ambiguous) return unresolved;
    {
        const memoria_episode_source *e = &episodes[best];
        memoria_episode_result r = {1,e->episode_id,e->text,e->order,e->timestamp,e->event_type,e->topics_csv,e->source_type,e->source_authority,e->ultimate_source_memory_id,0.55 + 0.1 * (best_score > 4.0 ? 4.0 : best_score)};
        if (r.confidence > 1.0) r.confidence = 1.0;
        return r;
    }
}
