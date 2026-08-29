#include "trajectory_kernel.h"

#include <ctype.h>
#include <math.h>
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

static double trajectory_weight(size_t index, size_t count, int direction) {
    double position;
    if (!count) return 0.0;
    position=(double)(index+1)/(double)count;
    if (direction < 0) return 1.0 - 0.45*position; /* favor earlier antecedents */
    return 0.55 + 0.45*position;                    /* normal/latest favors recent */
}

memoria_trajectory_result memoria_trajectory_resolve(
    const char *query,
    const char *session_id,
    const memoria_trajectory_turn *window,
    size_t window_count,
    const memoria_semantic_source *sources,
    size_t source_count
) {
    memoria_trajectory_result none={0,0,0.0,0};
    size_t i,j,best=0; double best_score=0.0,second=0.0; int found=0,used_window=0;
    size_t qtokens;
    int ordinal;
    if (!query || !sources || !source_count) return none;
    qtokens=content_tokens(query);
    ordinal=ordinal_direction(query);
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
        memoria_trajectory_result r={1,sources[best].memory_id,0.45+0.45*best_score,used_window};
        if (r.confidence>0.9) r.confidence=0.9;
        return r;
    }
}
