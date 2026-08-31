#include "subconscious_kernel.h"

#include <ctype.h>
#include <math.h>
#include <string.h>

#define TOKEN_CAP 32u
#define TOKEN_SIZE 48u

static int stopword(const char *w) {
    static const char *words[] = {
        "a","ao","aos","as","da","das","de","do","dos","e","em","me","o","os","para","por","que","um","uma",
        "fale","falar","diga","dizer","conte","sobre","mais","procure","pesquise","pesquisar","favor",
        "the","a","an","of","to","and","about","tell","please","find","search","more","what","which"
    };
    size_t i;
    for (i = 0; i < sizeof(words)/sizeof(words[0]); ++i) if (strcmp(w, words[i]) == 0) return 1;
    return 0;
}

static char fold_utf8(unsigned char a, unsigned char b) {
    if (a != 0xC3) return 0;
    switch (b) {
        case 0x80: case 0x81: case 0x82: case 0x83: case 0x84:
        case 0xA0: case 0xA1: case 0xA2: case 0xA3: case 0xA4: return 'a';
        case 0x87: case 0xA7: return 'c';
        case 0x88: case 0x89: case 0x8A: case 0x8B:
        case 0xA8: case 0xA9: case 0xAA: case 0xAB: return 'e';
        case 0x8C: case 0x8D: case 0x8E: case 0x8F:
        case 0xAC: case 0xAD: case 0xAE: case 0xAF: return 'i';
        case 0x91: case 0xB1: return 'n';
        case 0x92: case 0x93: case 0x94: case 0x95: case 0x96:
        case 0xB2: case 0xB3: case 0xB4: case 0xB5: case 0xB6: return 'o';
        case 0x99: case 0x9A: case 0x9B: case 0x9C:
        case 0xB9: case 0xBA: case 0xBB: case 0xBC: return 'u';
        default: return 0;
    }
}

static void alias(char *w) {
    struct pair { const char *from; const char *to; };
    static const struct pair aliases[] = {
        {"paises","pais"},{"nacao","pais"},{"nacoes","pais"},
        {"oceanos","oceano"},{"capitais","capital"},
        {"idioma","lingua"},{"idiomas","lingua"},{"linguas","lingua"},
        {"cidades","cidade"},{"countries","country"},{"oceans","ocean"}
    };
    size_t i;
    for (i = 0; i < sizeof(aliases)/sizeof(aliases[0]); ++i) {
        if (strcmp(w, aliases[i].from) == 0) { strcpy(w, aliases[i].to); return; }
    }
}

static int cmp_token(const void *a, const void *b) {
    return strcmp((const char *)a, (const char *)b);
}

static int topic_key(const char *query, char out[MEMORIA_SUBCONSCIOUS_TOPIC_CAP]) {
    char tokens[TOKEN_CAP][TOKEN_SIZE];
    size_t count = 0, i = 0, k = 0, j, written = 0;
    char word[TOKEN_SIZE];
    if (!query || !out) return 0;
    while (query[i] && count < TOKEN_CAP) {
        unsigned char ch = (unsigned char)query[i];
        char folded = 0;
        if (ch < 0x80) {
            ++i;
            if (isalnum(ch)) folded = (char)tolower(ch);
        } else if (query[i+1]) {
            folded = fold_utf8(ch, (unsigned char)query[i+1]);
            i += 2;
        } else ++i;
        if (folded) {
            if (k + 1 < TOKEN_SIZE) word[k++] = folded;
        } else if (k) {
            word[k] = 0; alias(word);
            if (!stopword(word)) { strcpy(tokens[count++], word); }
            k = 0;
        }
    }
    if (k && count < TOKEN_CAP) {
        word[k] = 0; alias(word);
        if (!stopword(word)) strcpy(tokens[count++], word);
    }
    if (!count) return 0;
    qsort(tokens, count, sizeof(tokens[0]), cmp_token);
    out[0] = 0;
    for (i = 0; i < count; ++i) {
        if (i && strcmp(tokens[i], tokens[i-1]) == 0) continue;
        if (written && written + 1 < MEMORIA_SUBCONSCIOUS_TOPIC_CAP) out[written++] = ' ';
        for (j = 0; tokens[i][j] && written + 1 < MEMORIA_SUBCONSCIOUS_TOPIC_CAP; ++j)
            out[written++] = tokens[i][j];
        out[written] = 0;
    }
    return written != 0;
}

static double clamp01(double v) {
    if (v < 0.0) return 0.0;
    if (v > 1.0) return 1.0;
    return v;
}

static void recompute(memoria_subconscious_candidate *c) {
    double recurrence, unresolved, low_conf, deficit, recency;
    if (!c) return;
    recurrence = c->observations > 5u ? 1.0 : (double)c->observations / 5.0;
    unresolved = c->unresolved_count > 3u ? 1.0 : (double)c->unresolved_count / 3.0;
    low_conf = c->low_confidence_count > 3u ? 1.0 : (double)c->low_confidence_count / 3.0;
    deficit = clamp01(c->confidence_deficit / (double)(c->observations ? c->observations : 1u));
    recency = c->last_order > 0 ? 1.0 : 0.0;
    c->priority = 0.30 * unresolved + 0.24 * recurrence + 0.20 * deficit + 0.16 * low_conf + 0.10 * recency;
}

void memoria_subconscious_init(memoria_subconscious_state *state) {
    if (state) memset(state, 0, sizeof(*state));
}

void memoria_subconscious_observe(memoria_subconscious_state *state, const char *query, int resolved, double confidence, long order) {
    char topic[MEMORIA_SUBCONSCIOUS_TOPIC_CAP];
    size_t i, slot;
    memoria_subconscious_candidate *c;
    confidence = clamp01(confidence);
    if (!state || !topic_key(query, topic)) return;
    for (i = 0; i < state->count; ++i) if (strcmp(state->candidates[i].topic, topic) == 0) break;
    if (i < state->count) slot = i;
    else if (state->count < MEMORIA_SUBCONSCIOUS_MAX_CANDIDATES) slot = state->count++;
    else {
        slot = 0;
        for (i = 1; i < state->count; ++i)
            if (state->candidates[i].priority < state->candidates[slot].priority) slot = i;
        memset(&state->candidates[slot], 0, sizeof(state->candidates[slot]));
    }
    c = &state->candidates[slot];
    if (!c->topic[0]) strncpy(c->topic, topic, sizeof(c->topic)-1u);
    ++c->observations;
    if (!resolved) ++c->unresolved_count;
    if (!resolved || confidence < 0.65) ++c->low_confidence_count;
    c->confidence_deficit += 1.0 - confidence;
    if (order > c->last_order) c->last_order = order;
    recompute(c);
}

const memoria_subconscious_candidate *memoria_subconscious_peek(const memoria_subconscious_state *state) {
    size_t i, best = 0;
    if (!state || !state->count) return NULL;
    for (i = 1; i < state->count; ++i) {
        if (state->candidates[i].priority > state->candidates[best].priority + 1e-12 ||
            (fabs(state->candidates[i].priority - state->candidates[best].priority) < 1e-12 &&
             state->candidates[i].last_order > state->candidates[best].last_order)) best = i;
    }
    return &state->candidates[best];
}

int memoria_subconscious_satisfy(memoria_subconscious_state *state, const char *topic) {
    char key[MEMORIA_SUBCONSCIOUS_TOPIC_CAP];
    size_t i;
    if (!state || !topic || !topic_key(topic, key)) return 0;
    for (i = 0; i < state->count; ++i) {
        if (strcmp(state->candidates[i].topic, key) == 0) {
            if (i + 1u < state->count)
                memmove(&state->candidates[i], &state->candidates[i+1u], (state->count-i-1u)*sizeof(state->candidates[0]));
            --state->count;
            memset(&state->candidates[state->count], 0, sizeof(state->candidates[0]));
            return 1;
        }
    }
    return 0;
}
