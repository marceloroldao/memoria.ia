#include "structural_text_kernel.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static int symbol(const char *token, uint64_t *out) {
    return memoria_structural_text_symbol(token, strlen(token), out);
}

int main(void) {
    const char *names[] = {
        "meu", "gato", "se", "chama", "alt", "dorme",
        "no", "sofa", "qual", "nome", "do", "ação"
    };
    uint64_t ids[12];
    uint64_t recurrent[5];
    uint64_t single[5];
    uint64_t query[5];
    memoria_structural_text_score recurrent_score;
    memoria_structural_text_score single_score;
    memoria_structural_text_field *field;
    size_t i;

    for (i = 0; i < 12u; ++i) {
        if (!symbol(names[i], &ids[i])) return 2;
    }

    recurrent[0] = ids[0];
    recurrent[1] = ids[1];
    recurrent[2] = ids[2];
    recurrent[3] = ids[3];
    recurrent[4] = ids[4];

    single[0] = ids[0];
    single[1] = ids[1];
    single[2] = ids[5];
    single[3] = ids[6];
    single[4] = ids[7];

    query[0] = ids[8];
    query[1] = ids[9];
    query[2] = ids[10];
    query[3] = ids[0];
    query[4] = ids[1];

    field = memoria_structural_text_field_create(8u, 4u, 0.0);
    if (!field) return 3;
    if (!memoria_structural_text_field_observe(field, recurrent, 5u)) return 4;
    if (!memoria_structural_text_field_observe(field, recurrent, 5u)) return 5;
    if (!memoria_structural_text_field_observe(field, single, 5u)) return 6;
    if (!memoria_structural_text_score_candidate(field, query, 5u, recurrent, 5u, &recurrent_score)) return 7;
    if (!memoria_structural_text_score_candidate(field, query, 5u, single, 5u, &single_score)) return 8;

    printf("{");
    printf("\"symbols\":{");
    for (i = 0; i < 12u; ++i) {
        if (i) printf(",");
        printf("\"%s\":%" PRIu64, names[i], ids[i]);
    }
    printf("},");
    printf("\"tick\":%" PRIu64 ",", memoria_structural_text_field_tick(field));
    printf("\"edge_count\":%zu,", memoria_structural_text_field_edge_count(field));
    printf("\"gato_se_within\":%.17g,",
        memoria_structural_text_field_association(
            field, ids[1], ids[2], MEMORIA_STRUCTURAL_CHANNEL_WITHIN
        )
    );
    printf("\"gato_dorme_within\":%.17g,",
        memoria_structural_text_field_association(
            field, ids[1], ids[5], MEMORIA_STRUCTURAL_CHANNEL_WITHIN
        )
    );
    printf("\"recurrent\":{");
    printf("\"score\":%.17g,", recurrent_score.score);
    printf("\"exact_overlap\":%zu,", recurrent_score.exact_overlap);
    printf("\"association_mass\":%.17g", recurrent_score.association_mass);
    printf("},");
    printf("\"single\":{");
    printf("\"score\":%.17g,", single_score.score);
    printf("\"exact_overlap\":%zu,", single_score.exact_overlap);
    printf("\"association_mass\":%.17g", single_score.association_mass);
    printf("}");
    printf("}\n");

    memoria_structural_text_field_destroy(field);
    return 0;
}
