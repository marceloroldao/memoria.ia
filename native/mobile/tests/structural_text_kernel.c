#include "structural_text_kernel.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); return 1; } } while (0)

static int close_enough(double a, double b) {
    return fabs(a - b) < 1e-12;
}

int main(void) {
    struct {
        const char *token;
        uint64_t expected;
    } vectors[] = {
        {"meu", UINT64_C(7126544648815283343)},
        {"gato", UINT64_C(13761269655978280478)},
        {"se", UINT64_C(2079710249054350336)},
        {"chama", UINT64_C(15732214716224006551)},
        {"alt", UINT64_C(4806113438364846566)},
        {"qual", UINT64_C(17186453383476100204)},
        {"é", UINT64_C(16350125043179424846)},
        {"o", UINT64_C(4204513158411050577)},
        {"nome", UINT64_C(13407524865874431819)},
        {"do", UINT64_C(7919684844612316212)}
    };
    size_t i;

    for (i = 0; i < sizeof(vectors) / sizeof(vectors[0]); ++i) {
        uint64_t got = 0;
        CHECK(memoria_structural_text_symbol(vectors[i].token, strlen(vectors[i].token), &got));
        CHECK(got == vectors[i].expected);
    }

    {
        const uint64_t gato = UINT64_C(13761269655978280478);
        const uint64_t se = UINT64_C(2079710249054350336);
        const uint64_t chama = UINT64_C(15732214716224006551);
        const uint64_t alt = UINT64_C(4806113438364846566);
        const uint64_t meu = UINT64_C(7126544648815283343);
        const uint64_t trail[] = {meu, gato, se, chama, alt};
        const uint64_t query[] = {gato, chama, gato};
        memoria_structural_text_score score;
        memoria_structural_text_field *field = memoria_structural_text_field_create(8u, 4u, 0.0);

        CHECK(field != NULL);
        CHECK(memoria_structural_text_field_observe(field, trail, 5u));
        CHECK(memoria_structural_text_field_observe(field, trail, 5u));
        CHECK(memoria_structural_text_field_tick(field) == 2u);
        CHECK(memoria_structural_text_field_edge_count(field) > 0u);

        CHECK(close_enough(
            memoria_structural_text_field_association(
                field, gato, se, MEMORIA_STRUCTURAL_CHANNEL_WITHIN
            ),
            2.0
        ));
        CHECK(close_enough(
            memoria_structural_text_field_association(
                field, gato, chama, MEMORIA_STRUCTURAL_CHANNEL_WITHIN
            ),
            1.0
        ));
        CHECK(close_enough(
            memoria_structural_text_field_association(
                field, gato, gato, MEMORIA_STRUCTURAL_CHANNEL_TEMPORAL
            ),
            1.0 / 25.0
        ));

        CHECK(memoria_structural_text_score_candidate(
            field,
            query, 3u,
            trail, 5u,
            &score
        ));
        CHECK(score.exact_overlap == 2u);
        CHECK(score.score > 1.0);
        CHECK(score.association_mass > 0.0);

        memoria_structural_text_field_destroy(field);
    }

    return 0;
}
