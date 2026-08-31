#ifndef MEMORIA_SUBCONSCIOUS_MOBILE_H
#define MEMORIA_SUBCONSCIOUS_MOBILE_H

#include "memoria_mobile.h"

void memoria_subconscious_mobile_observe_resolution(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_status status,
    memoria_mobile_buffer response_json
);

void memoria_subconscious_mobile_forget_handle(memoria_mobile_handle *handle);

/* Internal post-v1 bridge. The implementation is emitted only by the composed
 * post-v1 runtime translation unit, after the validated v1 persistence/runtime
 * implementation is visible. subconscious_mobile.c only consumes the symbols.
 * This keeps the queue in the same BDR instance and organization scope as the
 * rest of Memoria.ia instead of opening a second database connection. */
int memoria_subconscious_mobile_persistence_load(
    memoria_mobile_handle *handle,
    char **state_blob
);
int memoria_subconscious_mobile_persistence_save(
    memoria_mobile_handle *handle,
    const char *state_blob
);

#if defined(MEMORIA_MOBILE_PERSISTENCE_H) && defined(INITIAL_TURN_CAPACITY)
int memoria_subconscious_mobile_persistence_load(
    memoria_mobile_handle *handle,
    char **state_blob
) {
    if (!handle || !state_blob || !handle->persistence) return 0;
    return fetch(handle->persistence, "subconscious", 0, "state", state_blob);
}

int memoria_subconscious_mobile_persistence_save(
    memoria_mobile_handle *handle,
    const char *state_blob
) {
    bdr_atomic_c_operation op = {0};
    bdr_atomic_c_batch_result result = {0};
    char key[KEY_CAP];
    if (!handle || !handle->persistence || !state_blob ||
        !key_of(handle->persistence, key, sizeof(key), "subconscious", 0, "state")) return 0;
    op.type = BDR_ATOMIC_C_PUT;
    op.key = key;
    op.key_size = strlen(key);
    op.value = state_blob;
    op.value_size = strlen(state_blob);
    return bdr_atomic_c_write_batch(handle->persistence->db, &op, 1u, &result) == BDR_ATOMIC_C_OK &&
           result.durable == 1 && result.operations == 1u;
}
#endif

#endif
