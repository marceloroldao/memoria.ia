#ifndef MEMORIA_MOBILE_H
#define MEMORIA_MOBILE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MEMORIA_MOBILE_ABI_VERSION 1

typedef struct memoria_mobile_handle memoria_mobile_handle;

typedef enum memoria_mobile_status {
    MEMORIA_MOBILE_OK = 0,
    MEMORIA_MOBILE_INVALID_ARGUMENT = 1,
    MEMORIA_MOBILE_UNRESOLVED = 2,
    MEMORIA_MOBILE_NOT_FOUND = 3,
    MEMORIA_MOBILE_PERSISTENCE_ERROR = 4,
    MEMORIA_MOBILE_INTERNAL_ERROR = 5
} memoria_mobile_status;

typedef struct memoria_mobile_buffer {
    const uint8_t *data;
    size_t size;
} memoria_mobile_buffer;

/*
 * All request/response payloads are UTF-8 JSON documents whose semantic
 * contracts mirror the validated Product API. The ABI owns no domain ontology.
 */

uint32_t memoria_mobile_abi_version(void);

memoria_mobile_status memoria_mobile_open(
    const char *data_dir,
    const char *organization_id,
    memoria_mobile_handle **out_handle
);

memoria_mobile_status memoria_mobile_learn_turn_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_resolve_context_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_store_episode_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_recall_episode_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

/*
 * Read-only, versioned diagnostic export. request_json accepts optional
 * turn_offset/turn_limit and episode_offset/episode_limit pagination fields.
 * The returned buffer is released with memoria_mobile_free_buffer().
 * This additive ABI-v1 symbol does not expose BDR implementation details.
 */
memoria_mobile_status memoria_mobile_export_snapshot_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_apply_concept_catalog_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *handle);
void memoria_mobile_free_buffer(memoria_mobile_buffer buffer);
void memoria_mobile_close(memoria_mobile_handle *handle);

#ifdef __cplusplus
}
#endif

#endif
