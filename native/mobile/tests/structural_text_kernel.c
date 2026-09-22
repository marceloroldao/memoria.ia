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
        CHECK(memoria_structural_text_symbol(
            (const unsigned char *)vectors[i].token,
            strlen(vectors[i].token),
            &got
        ));
        CHECK(got == vectors[i].expected);
    }

    {
        const uint64_t query[] = {
            UINT64_C(13761269655978280478),
            UINT64_C(13407524865874431819),
            UINT64_C(13761269655978280478)
        };
        const uint64_t candidate[] = {
            UINT64_C(7126544648815283343),
            UINT64_C(13761269655978280478),
            UINT64_C(2079710249054350336),
            UINT64_C(15732214716224006551),
            UINT64_C(4806113438364846566),
            UINT64_C(13761269655978280478)
        };
        const memoria_structural_edge edges[] = {
            {UINT64_C(13761269655978280478), UINT64_C(15732214716224006551), 2.0},
            {UINT64_C(15732214716224006551), UINT64_C(13761269655978280478), 0.5},
            {UINT64_C(13407524865874431819), UINT64_C(4806113438364846566), 0.8},
            {UINT64_C(4806113438364846566), UINT64_C(13407524865874431819), 0.2},
            {UINT64_C(13761269655978280478), UINT64_C(4806113438364846566), 0.6},
            {UINT64_C(13407524865874431819), UINT64_C(15732214716224006551), 0.4}
        };
        memoria_structural_text_score out;
        CHECK(memoria_structural_text_score_candidate(
            query, sizeof(query) / sizeof(query[0]),
            candidate, sizeof(candidate) / sizeof(candidate[0]),
            edges, sizeof(edges) / sizeof(edges[0]),
            &out
        ));
        CHECK(out.exact_overlap == 1u);
        CHECK(close_enough(out.association_mass, 0.38));
        CHECK(close_enough(out.score, 0.88));
    }

    return 0;
}
