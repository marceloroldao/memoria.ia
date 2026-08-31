#ifndef MEMORIA_SUBCONSCIOUS_KERNEL_H
#define MEMORIA_SUBCONSCIOUS_KERNEL_H

#include <stddef.h>
#include <stdlib.h>

#define MEMORIA_SUBCONSCIOUS_MAX_CANDIDATES 64u
#define MEMORIA_SUBCONSCIOUS_TOPIC_CAP 192u

typedef struct memoria_subconscious_candidate {
    char topic[MEMORIA_SUBCONSCIOUS_TOPIC_CAP];
    unsigned observations;
    unsigned unresolved_count;
    unsigned low_confidence_count;
    double confidence_deficit;
    long last_order;
    double priority;
} memoria_subconscious_candidate;

typedef struct memoria_subconscious_state {
    memoria_subconscious_candidate candidates[MEMORIA_SUBCONSCIOUS_MAX_CANDIDATES];
    size_t count;
} memoria_subconscious_state;

void memoria_subconscious_init(memoria_subconscious_state *state);

/* Observe a conversational knowledge demand. This function is local-only:
 * it never performs I/O or network access. `resolved` is non-zero for HIT and
 * zero for UNRESOLVED. `confidence` is clamped to [0,1]. */
void memoria_subconscious_observe(
    memoria_subconscious_state *state,
    const char *query,
    int resolved,
    double confidence,
    long order
);

/* Return the highest-priority knowledge gap without removing it. */
const memoria_subconscious_candidate *memoria_subconscious_peek(
    const memoria_subconscious_state *state
);

/* Mark a topic as externally satisfied. This removes its pending gap so the
 * consumer does not keep researching the same concept after evidence arrives. */
int memoria_subconscious_satisfy(memoria_subconscious_state *state, const char *topic);

#endif
