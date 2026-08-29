#include "trajectory_kernel.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static int stopword(const char *w) {
    static const char *s[] = {"a","an","and","as","at","da","das","de","do","dos","e","em","for","me","my","o","of","os","para","por","que","the","to","um","uma","what","which"};
    size_t i;
    for (i = 0; i < sizeof(s)/sizeof(s[0]); ++i) if (strcmp(w,s[i]) == 0) return 1;
    return 0;
}

static size_t tok(const char *s, char out[][64], size_t cap) {
    size_t n=0,i=0;
    while (s && s[i] && n<cap) {
        char w[64]; size_t k=0;
        while (s[i] && !isalnum((unsigned char)s[i])) ++i;
        while (s[i] && isalnum((unsigned char)s[i]) && k+1<sizeof(w)) w[k++]=(char)tolower((unsigned char)s[i++]);
        w[k]=0;
        if (k && !stopword(w)) { strcpy(out[n],w); ++n; }
        while (s[i] && isalnum((unsigned char)s[i])) ++i;
    }
    return n;
}

static double overlap(const char *a, const char *b) {
    char x[64][64], y[128][64]; size_t nx=tok(a,x,64), ny=tok(b,y,128), i,j,h=0;
    if (!nx) return 0.0;
    for (i=0;i<nx;++i) for (j=0;j<ny;++j) if (strcmp(x[i],y[j])==0) { ++h; break; }
    return (double)h/(double)nx;
}

static size_t content_tokens(const char *s) { char t[32][64]; return tok(s,t,32); }

static int same_session(const char *wanted, const char *actual) {
    if (!wanted || !*wanted || !actual || !*actual) return 0;
    return strcmp(wanted,actual)==0;
}

static int starts_word(const char *s, const char *word) {
    size_t i=0,j=0;
    if (!s || !word) return 0;
    while (s[i] && isspace((unsigned char)s[i])) ++i;
    while (word[j]) {
        if (!s[i+j]) return 0;
        if (tolower((unsigned char)s[i+j]) != tolower((unsigned char)word[j])) return 0;
        ++j;
    }
    return s[i+j] == 0 || !isalnum((unsigned char)s[i+j]);
}

static int looks_like_question(const char *text) {
    static const char *q[] = {
        "qual","quais","quem","onde","quando","como","quanto","quantos","quantas",
        "por que","porque","what","which","who","where","when","how","why",
        "can","could","would","should","do","does","did"
    };
    size_t i;
    if (!text) return 0;
    if (strchr(text,'?')) return 1;
    for (i=0;i<sizeof(q)/sizeof(q[0]);++i) if (starts_word(text,q[i])) return 1;
    return 0;
}

static int retrievable(const memoria_semantic_source *s) {
    if (!s || !s->text || !s->memory_id) return 0;
    if (s->source_type && strcmp(s->source_type,"user_query")==0) return 0;
    if (s->source_type && strcmp(s->source_type,"user_assertion")==0 && looks_like_question(s->text)) return 0;
    return 1;
}

static const char *root_id(const memoria_semantic_source *s) {
    if (!s) return NULL;
    if (s->ultimate_source_memory_id && s->ultimate_source_memory_id[0]) return s->ultimate_source_memory_id;
    return s->memory_id;
}

static int same_root(const memoria_semantic_source *a, const memoria_semantic_source *b) {
    const char *ra=root_id(a), *rb=root_id(b);
    return ra && rb && strcmp(ra,rb)==0;
}

/* -1 = earliest/first, +1 = latest/last, 0 = normal recency. */
static int ordinal_direction(const char *query) {
    char words[48][64];
    size_t n=tok(query,words,48), i;
    static const char *early[] = {"first","earliest","primeiro","primeira","inicial"};
    static const char *late[] = {"last","latest","ultimo","ultima","final"};
    size_t j;
    for (i=0;i<n;++i) {
        for (j=0;j<sizeof(early)/sizeof(early[0]);++j) if (strcmp(words[i],early[j])==0) return -1;
        for (j=0;j<sizeof(late)/sizeof(late[0]);++j) if (strcmp(words[i],late[j])==0) return 1;
    }
    /* UTF-8 accented Portuguese forms are checked literally because tok() is ASCII-oriented. */
    if (query && (strstr(query,"último") || strstr(query,"Último") || strstr(query,"última") || strstr(query,"Última"))) return 1;
    return 0;
}

static int pair_reference_intent(const char *query) {
    char words[48][64];
    size_t n=tok(query,words,48), i, j;
    static const char *pair_words[] = {"both","two","pair","ambos","ambas","dois","duas"};
    for (i=0;i<n;++i)
        for (j=0;j<sizeof(pair_words)/sizeof(pair_words[0]);++j)
            if (strcmp(words[i],pair_words[j])==0) return 1;
    return 0;
}

static double trajectory_weight(size_t index, size_t count, int direction) {
    double position;
    if (!count) return 0.0;
    position=(double)(index+1)/(double)count;
    if (direction < 0) return 1.0 - 0.45*position; /* favor earlier antecedents */
    return 0.55 + 0.45*position;                    /* normal/latest favors recent */
}

typedef struct trajectory_candidate {
    size_t source_index;
    double score;
} trajectory_candidate;

static int candidate_cmp_desc(const void *a, const void *b) {
    const trajectory_candidate *ca=(const trajectory_candidate *)a;
    const trajectory_candidate *cb=(const trajectory_candidate *)b;
    if (ca->score < cb->score) return 1;
    if (ca->score > cb->score) return -1;
    return 0;
}

static memoria_trajectory_result resolve_pair_reference(
    const char *query,
    const char *session_id,
    const memoria_trajectory_turn *window,
    size_t window_count,
    const memoria_semantic_source *sources,
    size_t source_count,
    int ordinal
) {
    memoria_trajectory_result none={0};
    trajectory_candidate *candidates;
    size_t candidate_count=0,i,j;

    if (!query || !session_id || !*session_id || !window || !window_count || !sources || !source_count) return none;
    candidates=(trajectory_candidate *)calloc(source_count,sizeof(*candidates));
    if (!candidates) return none;

    for (i=0;i<source_count;++i) {
        double qs,ws=0.0,score;
        size_t existing=source_count;
        if (!retrievable(&sources[i])) continue;
        qs=overlap(query,sources[i].text);
        for (j=0;j<window_count;++j) {
            double weight,os;
            if (!same_session(session_id,window[j].session_id) || !window[j].text) continue;
            os=overlap(window[j].text,sources[i].text);
            weight=trajectory_weight(j,window_count,ordinal);
            if (os*weight > ws) ws=os*weight;
        }
        if (ws<=0.0) continue;
        score=0.58*qs + 0.27*ws + 0.15*sources[i].authority;
        if (score<0.20) continue;

        for (j=0;j<candidate_count;++j) {
            if (same_root(&sources[candidates[j].source_index],&sources[i])) { existing=j; break; }
        }
        if (existing<source_count) {
            const memoria_semantic_source *old=&sources[candidates[existing].source_index];
            if (score>candidates[existing].score+1e-12 ||
                (fabs(score-candidates[existing].score)<1e-12 && sources[i].authority>old->authority+1e-12)) {
                candidates[existing].source_index=i;
                candidates[existing].score=score;
            }
        } else {
            candidates[candidate_count].source_index=i;
            candidates[candidate_count].score=score;
            ++candidate_count;
        }
    }

    if (candidate_count<2) { free(candidates); return none; }
    qsort(candidates,candidate_count,sizeof(*candidates),candidate_cmp_desc);

    /* If a third independent root is effectively tied with the requested pair,
       the antecedent set is not uniquely justified and must remain unresolved. */
    if (candidate_count>2 && fabs(candidates[1].score-candidates[2].score)<0.035) {
        free(candidates);
        return none;
    }

    {
        size_t a=candidates[0].source_index,b=candidates[1].source_index;
        double weakest=candidates[0].score<candidates[1].score?candidates[0].score:candidates[1].score;
        memoria_trajectory_result r={0};
        if (sources[a].order>sources[b].order) { size_t t=a; a=b; b=t; }
        r.hit=1;
        r.memory_id=sources[a].memory_id;
        r.confidence=0.45+0.45*weakest;
        if (r.confidence>0.9) r.confidence=0.9;
        r.used_window=1;
        r.memory_count=2;
        r.memory_ids[0]=sources[a].memory_id;
        r.memory_ids[1]=sources[b].memory_id;
        free(candidates);
        return r;
    }
}

memoria_trajectory_result memoria_trajectory_resolve(
    const char *query,
    const char *session_id,
    const memoria_trajectory_turn *window,
    size_t window_count,
    const memoria_semantic_source *sources,
    size_t source_count
) {
    memoria_trajectory_result none={0};
    size_t i,j,best=0; double best_score=0.0,second=0.0; int found=0,used_window=0;
    size_t qtokens;
    int ordinal;
    if (!query || !sources || !source_count) return none;
    qtokens=content_tokens(query);
    ordinal=ordinal_direction(query);

    if (pair_reference_intent(query))
        return resolve_pair_reference(query,session_id,window,window_count,sources,source_count,ordinal);

    for (i=0;i<source_count;++i) {
        double qs, ws=0.0, score;
        if (!retrievable(&sources[i])) continue;
        qs=overlap(query,sources[i].text);
        if (window && window_count && session_id && *session_id) {
            for (j=0;j<window_count;++j) {
                double weight, os;
                if (!same_session(session_id,window[j].session_id) || !window[j].text) continue;
                os=overlap(window[j].text,sources[i].text);
                weight=trajectory_weight(j,window_count,ordinal);
                if (os*weight > ws) ws=os*weight;
            }
        }
        if (qtokens<=4 && qs<=0.34 && ws<=0.0) continue;
        score=0.58*qs + 0.27*ws + 0.15*sources[i].authority;
        if (score>best_score+1e-9) { second=best_score; best_score=score; best=i; found=1; used_window=(ws>0.0); }
        else if (score>second) second=score;
    }
    if (!found || best_score<0.20) return none;
    if (second>0.0 && fabs(best_score-second)<0.035) return none;
    {
        memoria_trajectory_result r={0};
        r.hit=1;
        r.memory_id=sources[best].memory_id;
        r.confidence=0.45+0.45*best_score;
        if (r.confidence>0.9) r.confidence=0.9;
        r.used_window=used_window;
        r.memory_count=1;
        r.memory_ids[0]=sources[best].memory_id;
        return r;
    }
}
