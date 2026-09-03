#include "semantic_consolidation_kernel.h"

#include <assert.h>
#include <string.h>

static memoria_semantic_support support(
    const char *ns, const char *subject, const char *predicate, const char *object,
    const char *memory_id, const char *root_id, double confidence, int active
) {
    memoria_semantic_support s;
    s.namespace_id = ns;
    s.subject = subject;
    s.predicate = predicate;
    s.object = object;
    s.support_memory_id = memory_id;
    s.factual_root_id = root_id;
    s.confidence = confidence;
    s.factual_active = active;
    return s;
}

int main(void) {
    memoria_semantic_candidate out[4];
    size_t n;

    {
        memoria_semantic_support rows[] = {
            support("s1", "Bateria", "is", "carregada", "r1", "u1", 0.95, 1),
            support("s1", "bateria", "IS", "carregada", "r2", "u2", 0.85, 1),
        };
        memset(out, 0, sizeof(out));
        n = memoria_semantic_consolidation_candidates(rows, 2, 2, out, 4);
        assert(n == 1);
        assert(out[0].support_count == 2);
        assert(strcmp(out[0].factual_root_ids[0], "u1") == 0);
        assert(strcmp(out[0].factual_root_ids[1], "u2") == 0);
        assert(out[0].confidence > 0.849 && out[0].confidence < 0.851);
    }

    {
        memoria_semantic_support rows[] = {
            support("s1", "bateria", "is", "carregada", "r1", "u1", 0.95, 1),
            support("s1", "bateria", "is", "carregada", "r2", "u1", 0.95, 1),
        };
        memset(out, 0, sizeof(out));
        assert(memoria_semantic_consolidation_candidates(rows, 2, 2, out, 4) == 0);
    }

    {
        memoria_semantic_support rows[] = {
            support("s1", "bateria", "is", "carregada", "r1", "u1", 0.95, 1),
            support("s2", "bateria", "is", "carregada", "r2", "u2", 0.95, 1),
        };
        memset(out, 0, sizeof(out));
        assert(memoria_semantic_consolidation_candidates(rows, 2, 2, out, 4) == 0);
    }

    {
        memoria_semantic_support rows[] = {
            support("s1", "bateria", "is", "carregada", "r1", "u1", 0.95, 1),
            support("s1", "bateria", "is", "carregada", "r2", "u2", 0.95, 0),
            support("s1", "bateria", "is", "carregada", "r3", "u3", 0.95, 1),
        };
        memset(out, 0, sizeof(out));
        n = memoria_semantic_consolidation_candidates(rows, 3, 2, out, 4);
        assert(n == 1);
        assert(out[0].support_count == 2);
        assert(strcmp(out[0].factual_root_ids[0], "u1") == 0);
        assert(strcmp(out[0].factual_root_ids[1], "u3") == 0);
    }

    return 0;
}
