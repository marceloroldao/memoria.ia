#include "resolutive_inference_kernel.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_inference_result_t r;
    memoria_inference_edge_t geo[] = {
        {"porto alegre", "esta_em", "rio grande do sul", "m1", 0.95, 0.96, 1},
        {"rio grande do sul", "esta_em", "brasil", "m2", 0.94, 0.93, 1}
    };
    assert(memoria_infer_two_hop_same_predicate(geo, 2, "porto alegre", "esta_em", &r) == 0);
    assert(r.status == MEMORIA_INFERENCE_RESOLVED);
    assert(strcmp(r.answer, "brasil") == 0);
    assert(strcmp(r.via, "rio grande do sul") == 0);
    assert(strcmp(r.evidence_memory_id_1, "m1") == 0);
    assert(strcmp(r.evidence_memory_id_2, "m2") == 0);
    assert(r.path_confidence > 0.92 && r.path_confidence < 0.94);

    /* Different predicates are not silently composed. */
    memoria_inference_edge_t mixed[] = {
        {"alt", "irmao_de", "alt2", "m3", 0.9, 0.9, 1},
        {"alt2", "cor", "preto", "m4", 0.9, 0.9, 1}
    };
    assert(memoria_infer_two_hop_same_predicate(mixed, 2, "alt", "irmao_de", &r) == 0);
    assert(r.status == MEMORIA_INFERENCE_UNRESOLVED);

    /* Equal-strength contradictory paths fail closed. */
    memoria_inference_edge_t conflict[] = {
        {"cidade x", "esta_em", "estado a", "m5", 0.9, 0.9, 1},
        {"estado a", "esta_em", "pais a", "m6", 0.9, 0.9, 1},
        {"cidade x", "esta_em", "estado b", "m7", 0.9, 0.9, 1},
        {"estado b", "esta_em", "pais b", "m8", 0.9, 0.9, 1}
    };
    assert(memoria_infer_two_hop_same_predicate(conflict, 4, "cidade x", "esta_em", &r) == 0);
    assert(r.status == MEMORIA_INFERENCE_CONFLICT);

    /* Inactive/superseded edges do not participate. */
    geo[1].active = 0;
    assert(memoria_infer_two_hop_same_predicate(geo, 2, "porto alegre", "esta_em", &r) == 0);
    assert(r.status == MEMORIA_INFERENCE_UNRESOLVED);
    return 0;
}
