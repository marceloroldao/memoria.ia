#include "subconscious_kernel.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_subconscious_state state;
    const memoria_subconscious_candidate *top;

    memoria_subconscious_init(&state);
    assert(state.count == 0);
    assert(memoria_subconscious_peek(&state) == 0);

    /* Paraphrased Portuguese queries converge to the same deterministic topic. */
    memoria_subconscious_observe(&state, "me fale sobre a China", 0, 0.0, 1);
    memoria_subconscious_observe(&state, "fale mais sobre China", 0, 0.0, 2);
    assert(state.count == 1);
    assert(strcmp(state.candidates[0].topic, "china") == 0);
    assert(state.candidates[0].observations == 2);
    assert(state.candidates[0].unresolved_count == 2);

    /* A repeated unresolved topic must outrank a one-off low-confidence topic. */
    memoria_subconscious_observe(&state, "capital da China", 1, 0.55, 3);
    memoria_subconscious_observe(&state, "oceanos do planeta", 1, 0.50, 4);
    top = memoria_subconscious_peek(&state);
    assert(top != 0);
    assert(strcmp(top->topic, "china") == 0);

    /* Word order and accents do not create duplicate gap keys. */
    memoria_subconscious_observe(&state, "população do país", 0, 0.0, 5);
    memoria_subconscious_observe(&state, "pais populacao", 0, 0.0, 6);
    assert(state.count == 4);
    {
        size_t i, seen = 0;
        for (i = 0; i < state.count; ++i)
            if (strcmp(state.candidates[i].topic, "pais populacao") == 0) ++seen;
        assert(seen == 1);
    }

    /* Once public evidence satisfies a gap, it leaves the pending queue. */
    assert(memoria_subconscious_satisfy(&state, "China") == 1);
    {
        size_t i;
        for (i = 0; i < state.count; ++i) assert(strcmp(state.candidates[i].topic, "china") != 0);
    }
    assert(memoria_subconscious_satisfy(&state, "China") == 0);

    /* Empty/conversational-only text must not create research tasks. */
    {
        size_t before = state.count;
        memoria_subconscious_observe(&state, "fale mais por favor", 0, 0.0, 7);
        assert(state.count == before);
    }

    return 0;
}
