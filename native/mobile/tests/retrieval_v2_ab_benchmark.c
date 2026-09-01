#include "retrieval_v2_normalization.h"

#include <stdio.h>
#include <string.h>

#define TOKEN_CAP 64u

typedef struct pair_case {
    const char *query;
    const char *memory;
    int should_match;
} pair_case;

static int exact_equal(const char *a, const char *b) {
    return a && b && strcmp(a, b) == 0;
}

static int normalized_equal(const char *a, const char *b) {
    char na[TOKEN_CAP], nb[TOKEN_CAP];
    if (!memoria_retrieval_v2_normalize_token(a, na, sizeof(na))) return 0;
    if (!memoria_retrieval_v2_normalize_token(b, nb, sizeof(nb))) return 0;
    return strcmp(na, nb) == 0;
}

int main(void) {
    static const pair_case cases[] = {
        {"tensoes", "tensão", 1},
        {"voltagem", "tensão", 1},
        {"voltagens", "tensao", 1},
        {"servidores", "servidor", 1},
        {"baterias", "bateria", 1},
        {"modulos", "módulo", 1},
        {"portas", "porta", 1},
        {"frequencias", "frequência", 1},
        {"cidades", "cidade", 1},
        {"paises", "pais", 1},
        {"idiomas", "lingua", 1},
        {"linguas", "idioma", 1},

        /* Negative controls: normalization must not collapse unrelated concepts. */
        {"pais", "mais", 0},
        {"ingles", "ingresso", 0},
        {"porta", "porto", 0},
        {"bateria", "batida", 0},
        {"servidor", "servico", 0},
        {"tensao", "temperatura", 0}
    };
    size_t i;
    unsigned baseline_tp = 0, baseline_fp = 0;
    unsigned normalized_tp = 0, normalized_fp = 0;
    unsigned positives = 0, negatives = 0;

    for (i = 0; i < sizeof(cases)/sizeof(cases[0]); ++i) {
        int baseline = exact_equal(cases[i].query, cases[i].memory);
        int normalized = normalized_equal(cases[i].query, cases[i].memory);
        if (cases[i].should_match) {
            ++positives;
            if (baseline) ++baseline_tp;
            if (normalized) ++normalized_tp;
        } else {
            ++negatives;
            if (baseline) ++baseline_fp;
            if (normalized) ++normalized_fp;
        }
    }

    printf("retrieval_v2_ab positives=%u negatives=%u baseline_tp=%u baseline_fp=%u normalized_tp=%u normalized_fp=%u\n",
           positives, negatives, baseline_tp, baseline_fp, normalized_tp, normalized_fp);

    /* This slice is useful only if recall improves materially without introducing
     * any false-positive collapse on the conservative negative controls. */
    if (normalized_tp <= baseline_tp) return 1;
    if (normalized_tp < positives - 1u) return 2;
    if (normalized_fp != 0u) return 3;
    return 0;
}
